"""
TFT Inference Wrapper
======================
Loads trained TFT checkpoint and provides prediction + interpretability.
Drop-in replacement for XGBoost path in price_ml.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import structlog

log = structlog.get_logger(__name__)

MODEL_DIR = Path("data/models")
CHECKPOINT_PATH = MODEL_DIR / "tft_best.ckpt"
PARAMS_PATH = MODEL_DIR / "tft_dataset_params.json"

# Quantile index mapping for the 7 quantiles [0.025, 0.1, 0.25, 0.5, 0.75, 0.9, 0.975]
Q_LO95, Q_LO80, Q_LO50, Q_MEDIAN, Q_HI50, Q_HI80, Q_HI95 = range(7)


class TFTPredictor:
    """
    Wraps a trained TFT model for inference.
    Returns predictions in the same format as the XGBoost path.
    """

    def __init__(self) -> None:
        self._model = None
        self._params = None
        self._loaded = False
        self._last_attention = None  # cached for explain endpoint

    def load(self) -> bool:
        """Load TFT checkpoint + dataset params. Returns True if successful."""
        if self._loaded:
            return True

        if not CHECKPOINT_PATH.exists() or not PARAMS_PATH.exists():
            log.debug("tft_predictor.no_checkpoint")
            return False

        try:
            from pytorch_forecasting import TemporalFusionTransformer
            self._model = TemporalFusionTransformer.load_from_checkpoint(str(CHECKPOINT_PATH))
            self._model.eval()

            with open(PARAMS_PATH, "r") as f:
                self._params = json.load(f)

            self._loaded = True
            n_params = sum(p.numel() for p in self._model.parameters())
            log.info("tft_predictor.loaded", parameters=n_params)
            return True

        except Exception as exc:
            log.warning("tft_predictor.load_failed", error=str(exc)[:120])
            return False

    async def predict(self, horizon_weeks: int = 4) -> dict | None:
        """
        Generate TFT prediction for a specific horizon.

        Returns dict with:
          - predicted_nok: median point estimate
          - bands: {lo95, lo80, lo50, hi50, hi80, hi95}
          - scenarios: {p10, p25, p50, p75, p90}
          - attention: feature importance + temporal attention
        Or None if TFT is not available.
        """
        if not self.load():
            return None

        try:
            import torch
            import pandas as pd
            from pytorch_forecasting import TimeSeriesDataSet
            from core.market.tft_data import build_weekly_dataframe, get_dataset_config

            # Build the latest data
            df = await build_weekly_dataframe(start_year=2012)
            if len(df) < 60:
                return None

            # Create dataset for prediction
            from pytorch_forecasting.data import GroupNormalizer
            cfg = get_dataset_config()
            encoder_len = cfg["max_encoder_length"]
            pred_len = cfg["max_prediction_length"]

            # We need the last encoder_length + prediction_length rows as context
            df_recent = df.tail(encoder_len + pred_len).copy()
            df_recent["time_idx"] = range(len(df_recent))

            # Build a fresh dataset (avoids serialization issues with GroupNormalizer)
            pred_ds = TimeSeriesDataSet(
                df_recent,
                **cfg,
                target_normalizer=GroupNormalizer(groups=["group_id"], transformation="softplus"),
                predict_mode=True,
            )
            pred_dl = pred_ds.to_dataloader(train=False, batch_size=1, num_workers=0)

            # Run inference — get quantile predictions
            with torch.no_grad():
                raw_output = self._model.predict(pred_dl, mode="quantiles", return_x=False)

            # raw_output shape: (n_samples, prediction_length, n_quantiles)
            # or could be (prediction_length, n_quantiles) for single sample
            output = raw_output
            if isinstance(output, torch.Tensor):
                output = output.numpy()
            elif hasattr(output, 'output'):
                output = output.output.numpy() if hasattr(output.output, 'numpy') else np.array(output.output)
            else:
                output = np.array(output)

            # Ensure 3D: (batch, pred_len, quantiles)
            if output.ndim == 2:
                output = output[np.newaxis, ...]

            quantiles = output[0]  # first (only) sample
            h_idx = min(horizon_weeks - 1, quantiles.shape[0] - 1)
            h_idx = max(0, h_idx)

            q = quantiles[h_idx]  # 7 quantile values
            if hasattr(q, 'numpy'):
                q = q.numpy()
            q = np.array(q).flatten()

            # Extract attention weights for interpretability
            try:
                interpretation = self._model.interpret_output(
                    raw_output.output, reduction="sum"
                )
                self._last_attention = {
                    "encoder_variables": {
                        k: round(float(v), 4)
                        for k, v in zip(
                            self._model.encoder_variables,
                            interpretation.get("encoder_variables", []),
                        )
                    } if "encoder_variables" in interpretation else {},
                    "decoder_variables": {
                        k: round(float(v), 4)
                        for k, v in zip(
                            self._model.decoder_variables,
                            interpretation.get("decoder_variables", []),
                        )
                    } if "decoder_variables" in interpretation else {},
                }
            except Exception:
                self._last_attention = None

            return {
                "predicted_nok": round(float(q[Q_MEDIAN]), 2),
                "bands": {
                    "lo95": round(float(q[Q_LO95]), 2),
                    "lo80": round(float(q[Q_LO80]), 2),
                    "lo50": round(float(q[Q_LO50]), 2),
                    "hi50": round(float(q[Q_HI50]), 2),
                    "hi80": round(float(q[Q_HI80]), 2),
                    "hi95": round(float(q[Q_HI95]), 2),
                },
                "scenarios": {
                    "p10": round(float(q[Q_LO80]), 2),
                    "p25": round(float(q[Q_LO50]), 2),
                    "p50": round(float(q[Q_MEDIAN]), 2),
                    "p75": round(float(q[Q_HI50]), 2),
                    "p90": round(float(q[Q_HI80]), 2),
                },
                "horizon_weeks": horizon_weeks,
                "model": "tft",
                "attention": self._last_attention,
            }

        except Exception as exc:
            log.warning("tft_predictor.predict_failed", error=str(exc)[:200])
            return None

    def get_attention(self) -> dict | None:
        """Return cached attention weights from last prediction."""
        return self._last_attention

    @property
    def is_available(self) -> bool:
        """True only when the TFT can actually produce predictions.

        A checkpoint on disk is not enough — pytorch_forecasting + torch must
        be importable, otherwise predict() always returns None and callers
        that trust this flag would silently take the rule fallback while
        reporting "TFT active".
        """
        if self._loaded:
            return True
        if not (CHECKPOINT_PATH.exists() and PARAMS_PATH.exists()):
            return False
        import importlib.util

        return (
            importlib.util.find_spec("pytorch_forecasting") is not None
            and importlib.util.find_spec("torch") is not None
        )


# Singleton
tft_predictor = TFTPredictor()
