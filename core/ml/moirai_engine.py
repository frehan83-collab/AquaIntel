"""
MOIRAI-2 Foundation Model Forecasting Engine
==============================================
Salesforce's MOIRAI-2 (30M params) for ultra-fast zero-shot time series
forecasting. Designed for low-latency inference — 2x faster than MOIRAI 1.0,
ranks #1 by MASE among non-data-leaking models on GIFT-Eval.

Model: salesforce/moirai-2-small (~30M params, HuggingFace)
Context window: 512 time steps
Max horizon: 128 steps
Speed: ~2x faster than MOIRAI 1.0, ideal for real-time WebSocket endpoints

References:
    Liu et al. (2025). "MOIRAI-2: Mastering Non-Stationary Time Series
    Forecasting with Capacity-Boosted Mixture of Experts."
    Salesforce AI Research. https://arxiv.org/abs/2502.20000
    MOIRAI-2 release (2025): MoE architecture, non-stationary adaptation,
    30M/300M/1B param variants, uni2ts package.

Comparison framework: benchmarks MOIRAI-2 vs Chronos-2 vs TimesFM 2.5 vs
TFT vs naive on holdout windows.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# MOIRAI-2 model constants
MOIRAI_CONTEXT_LENGTH = 512
MOIRAI_MAX_HORIZON = 128
MOIRAI_MODEL_NAME = "salesforce/moirai-2-small"
MOIRAI_PARAMS = "30M"

# Default quantile levels for probabilistic forecasting
DEFAULT_QUANTILES = [0.1, 0.25, 0.5, 0.75, 0.9]


class MoiraiEngine:
    """Singleton for Salesforce MOIRAI-2 zero-shot forecasting.

    Uses lazy model loading: the 30M-parameter model is downloaded from
    HuggingFace on first use. Falls back to seasonal-naive when the
    ``uni2ts`` package is not installed.

    Key differentiator: MOIRAI-2 is optimized for low-latency inference,
    making it ideal for real-time WebSocket endpoints and interactive
    dashboards. At 30M params, it is 4-7x smaller than Chronos (120M)
    and TimesFM (200M), trading minimal accuracy for significant speed.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._model_name = MOIRAI_MODEL_NAME
        self._available: Optional[bool] = None

    # ── Model Loading ────────────────────────────────────────────────────

    def _get_model(self) -> Any:
        """Lazy-load MOIRAI-2 model (downloads on first use).

        Uses ``uni2ts`` (Salesforce's unified time series package) to
        load the pretrained model. The model runs on CPU by default.
        """
        if self._model is not None:
            return self._model

        try:
            from uni2ts.model.moirai import MoiraiForecast, MoiraiModule

            # Load pretrained MOIRAI-2 small model
            module = MoiraiModule.from_pretrained(self._model_name)
            self._model = MoiraiForecast(
                module=module,
                prediction_length=MOIRAI_MAX_HORIZON,
                context_length=MOIRAI_CONTEXT_LENGTH,
                patch_size="auto",
                num_samples=20,
            )
            self._available = True
            log.info(
                "moirai_model_loaded",
                model=self._model_name,
                params=MOIRAI_PARAMS,
                context_length=MOIRAI_CONTEXT_LENGTH,
                max_horizon=MOIRAI_MAX_HORIZON,
            )
        except ImportError:
            self._available = False
            log.warning(
                "moirai_not_installed",
                hint="pip install uni2ts>=1.0",
            )
            return None
        except Exception as e:
            self._available = False
            log.error("moirai_load_error", error=str(e))
            return None

        return self._model

    def is_available(self) -> bool:
        """Check if MOIRAI-2 is installed and model can be loaded."""
        if self._available is None:
            self._get_model()
        return bool(self._available)

    # ── Core Forecast ────────────────────────────────────────────────────

    async def forecast_series(
        self,
        values: list[float],
        horizon: int = 8,
        num_samples: int = 20,
        quantiles: Optional[list[float]] = None,
    ) -> dict:
        """Zero-shot forecast for any float array using MOIRAI-2.

        Args:
            values: Historical time series values.
            horizon: Number of future steps to forecast (max 128).
            num_samples: Number of probabilistic samples for uncertainty
                         quantification.
            quantiles: Quantile levels to output. Defaults to
                       [0.1, 0.25, 0.5, 0.75, 0.9].

        Returns:
            Dict with model name, horizon, quantile forecasts, and metadata.
        """
        horizon = min(horizon, MOIRAI_MAX_HORIZON)
        q_levels = quantiles or DEFAULT_QUANTILES

        model = self._get_model()
        if model is None:
            return self._fallback_forecast(values, horizon)

        try:
            import torch

            # Truncate context to model's window
            context = values[-MOIRAI_CONTEXT_LENGTH:]
            context_tensor = torch.tensor(context, dtype=torch.float32).unsqueeze(0)

            # MOIRAI-2 forecast call via uni2ts
            # The model generates samples for probabilistic forecasting
            forecast = model.predict(
                context_tensor,
                prediction_length=horizon,
                num_samples=num_samples,
            )

            # forecast shape: (1, num_samples, horizon)
            samples = forecast.numpy()[0]  # (num_samples, horizon)

            median = np.median(samples, axis=0).tolist()

            # Extract quantiles from samples
            q_dict: dict[str, list[float]] = {}
            for q in q_levels:
                q_dict[f"q{int(q * 100):02d}"] = np.percentile(
                    samples, q * 100, axis=0
                ).tolist()

            # Map to standard interval format (compatible with Chronos/TimesFM output)
            lo80 = q_dict.get("q10", [m - abs(m) * 0.1 for m in median])
            hi80 = q_dict.get("q90", [m + abs(m) * 0.1 for m in median])
            lo95 = np.percentile(samples, 2.5, axis=0).tolist()
            hi95 = np.percentile(samples, 97.5, axis=0).tolist()

            return {
                "model": "moirai-2-small",
                "model_params": MOIRAI_PARAMS,
                "horizon": horizon,
                "median": median,
                "lo80": lo80,
                "hi80": hi80,
                "lo95": lo95,
                "hi95": hi95,
                "quantiles": q_dict,
                "context_length": len(context),
                "is_live": True,
                "confidence": 0.72,
                "data_quality": "live",
                "latency_class": "low",
            }
        except Exception as e:
            log.error("moirai_forecast_error", error=str(e))
            return self._fallback_forecast(values, horizon)

    # ── Seasonal-Naive Fallback ──────────────────────────────────────────

    def _fallback_forecast(self, values: list[float], horizon: int) -> dict:
        """Seasonal-naive fallback when MOIRAI-2 is unavailable.

        Uses the last available yearly cycle (up to 52 weeks) as a naive
        forecast, with standard deviation-based prediction intervals.
        Identical logic to ChronosBaselineEngine._fallback_forecast for
        consistent comparison.
        """
        arr = np.array(values[-52:]) if len(values) >= 52 else np.array(values)
        if len(arr) < 2:
            flat = [float(arr[-1])] * horizon if len(arr) > 0 else [0.0] * horizon
            return {
                "model": "naive-fallback",
                "model_params": "0",
                "horizon": horizon,
                "median": flat,
                "lo80": flat,
                "hi80": flat,
                "lo95": flat,
                "hi95": flat,
                "quantiles": {},
                "context_length": len(values),
                "is_live": False,
                "confidence": 0.1,
                "data_quality": "degraded",
                "latency_class": "low",
            }

        # Seasonal naive: repeat last year's pattern
        period = min(len(arr), 52)
        median: list[float] = []
        for h in range(horizon):
            idx = -(period - (h % period))
            median.append(float(arr[idx]))

        std = float(np.std(arr))
        lo80 = [m - 1.28 * std for m in median]
        hi80 = [m + 1.28 * std for m in median]
        lo95 = [m - 1.96 * std for m in median]
        hi95 = [m + 1.96 * std for m in median]

        return {
            "model": "seasonal-naive-fallback",
            "model_params": "0",
            "horizon": horizon,
            "median": median,
            "lo80": lo80,
            "hi80": hi80,
            "lo95": lo95,
            "hi95": hi95,
            "quantiles": {},
            "context_length": len(values),
            "is_live": False,
            "confidence": 0.3,
            "data_quality": "degraded",
            "latency_class": "low",
        }

    # ── DB Data Retrieval (mirrors ChronosBaselineEngine / TimesFMEngine) ──

    async def _get_price_series(self) -> list[float]:
        """Pull SSB weekly salmon prices from DB."""
        from core.models import SSBWeeklyPrice
        from core.async_db import get_async_session
        from sqlalchemy import select

        async with get_async_session() as s:
            result = await s.execute(
                select(SSBWeeklyPrice.price_nok_kg)
                .where(SSBWeeklyPrice.price_nok_kg.isnot(None))
                .order_by(SSBWeeklyPrice.year, SSBWeeklyPrice.week)
            )
            rows = result.scalars().all()
        return [float(r) for r in rows]

    async def _get_lice_series(self, locality_no: int) -> list[float]:
        """Pull lice counts from DB for a specific farm."""
        from core.models import LiceRecord
        from core.async_db import get_async_session
        from sqlalchemy import select

        async with get_async_session() as s:
            result = await s.execute(
                select(LiceRecord.avg_adult_female_lice)
                .where(LiceRecord.locality_no == locality_no)
                .where(LiceRecord.avg_adult_female_lice.isnot(None))
                .order_by(LiceRecord.year, LiceRecord.week)
            )
            rows = result.scalars().all()
        return [float(r) for r in rows]

    async def _get_temperature_series(self, locality_no: int) -> list[float]:
        """Pull sea temperature from DB for a specific farm."""
        from core.models import LiceRecord
        from core.async_db import get_async_session
        from sqlalchemy import select

        async with get_async_session() as s:
            result = await s.execute(
                select(LiceRecord.sea_temp_c)
                .where(LiceRecord.locality_no == locality_no)
                .where(LiceRecord.sea_temp_c.isnot(None))
                .order_by(LiceRecord.year, LiceRecord.week)
            )
            rows = result.scalars().all()
        return [float(r) for r in rows]

    async def _get_export_series(self) -> list[float]:
        """Pull monthly export volumes from DB."""
        from core.models import ExportVolume
        from core.async_db import get_async_session
        from sqlalchemy import select

        async with get_async_session() as s:
            result = await s.execute(
                select(ExportVolume.volume_tonnes)
                .where(ExportVolume.volume_tonnes.isnot(None))
                .order_by(ExportVolume.year, ExportVolume.month)
            )
            rows = result.scalars().all()
        return [float(r) for r in rows]

    # ── Domain-Specific Forecasts ────────────────────────────────────────

    async def forecast_salmon_prices(self, horizon: int = 4) -> dict:
        """Zero-shot salmon price forecast using MOIRAI-2.

        Optimized for low-latency: 30M params delivers fast inference
        suitable for real-time WebSocket streaming.

        Args:
            horizon: Weeks ahead to forecast (default 4).
        """
        values = await self._get_price_series()
        if not values:
            return {"error": "No SSB price data available"}
        result = await self.forecast_series(values, horizon=horizon)
        result["series"] = "salmon_price_nok"
        result["unit"] = "NOK/kg"
        result["last_value"] = values[-1]
        return result

    async def forecast_lice_counts(
        self, locality_no: int, horizon: int = 8
    ) -> dict:
        """Zero-shot lice count forecast for a farm using MOIRAI-2.

        Args:
            locality_no: BarentsWatch locality number.
            horizon: Weeks ahead to forecast (default 8).
        """
        values = await self._get_lice_series(locality_no)
        if not values:
            return {"error": f"No lice data for locality {locality_no}"}
        result = await self.forecast_series(values, horizon=horizon)
        result["series"] = "adult_female_lice"
        result["locality_no"] = locality_no
        result["unit"] = "lice/fish"
        result["last_value"] = values[-1]
        return result

    async def forecast_temperatures(
        self, locality_no: int, horizon: int = 8
    ) -> dict:
        """Zero-shot sea temperature forecast using MOIRAI-2."""
        values = await self._get_temperature_series(locality_no)
        if not values:
            return {"error": f"No temperature data for locality {locality_no}"}
        result = await self.forecast_series(values, horizon=horizon)
        result["series"] = "sea_temperature"
        result["locality_no"] = locality_no
        result["unit"] = "celsius"
        result["last_value"] = values[-1]
        return result

    async def forecast_supply_volumes(self, horizon: int = 6) -> dict:
        """Zero-shot supply volume forecast (monthly) using MOIRAI-2."""
        values = await self._get_export_series()
        if not values:
            return {"error": "No export volume data available"}
        result = await self.forecast_series(values, horizon=horizon)
        result["series"] = "export_volume_tonnes"
        result["unit"] = "tonnes"
        result["last_value"] = values[-1]
        return result

    # ── Model Comparison ─────────────────────────────────────────────────

    async def compare_models(
        self, series: str = "price", horizon: int = 4
    ) -> dict:
        """Compare MOIRAI-2 vs Chronos-2 vs TimesFM 2.5 vs TFT vs naive.

        Uses the last ``horizon`` observations as the test set and trains
        on all preceding data. Reports MAPE, RMSE, and 80% coverage for
        each model. Highlights MOIRAI-2 latency advantage.
        """
        # Get full series
        if series == "price":
            values = await self._get_price_series()
            unit = "NOK/kg"
        elif series == "supply":
            values = await self._get_export_series()
            unit = "tonnes"
        else:
            return {"error": f"Unknown series: {series}"}

        if len(values) < horizon + 20:
            return {
                "error": (
                    f"Not enough data for comparison "
                    f"(need {horizon + 20}, have {len(values)})"
                )
            }

        # Split: train on all-but-last-horizon, test on last horizon
        train = values[:-horizon]
        actual = values[-horizon:]

        # MOIRAI-2 forecast
        moirai_fc = await self.forecast_series(train, horizon=horizon)
        fallback_members = ["moirai"] if "fallback" in str(moirai_fc.get("model", "")) else []

        # Chronos-2 forecast (if available)
        chronos_fc = None
        try:
            from core.ml.chronos_baseline import chronos_baseline
            chronos_fc = await chronos_baseline.forecast_series(
                train, horizon=horizon
            )
        except Exception:
            pass

        # TimesFM 2.5 forecast (if available)
        timesfm_fc = None
        try:
            from core.ml.timesfm_engine import timesfm_engine
            timesfm_fc = await timesfm_engine.forecast_series(
                train, horizon=horizon
            )
        except Exception:
            pass

        # Naive baseline (seasonal repeat)
        naive_fc = self._fallback_forecast(train, horizon)

        # Price-ensemble comparison (honest label: this is the
        # TFT/XGBoost/rule cascade in PriceEnsemble.predict, NOT a pure TFT)
        ensemble_fc = None
        if series == "price":
            try:
                from core.market.price_ml import price_ensemble
                preds: list[float] = []
                variant = None
                for h in range(1, horizon + 1):
                    fc_h = price_ensemble.predict(current_spot=values[-1], horizon_weeks=h)
                    if fc_h is None:
                        preds = []
                        break
                    preds.append(float(fc_h.predicted_nok))
                    variant = fc_h.model_version
                if len(preds) == horizon:
                    ensemble_fc = {"median": preds, "variant": variant}
            except Exception:
                ensemble_fc = None

        def _mape(actual_vals: list, pred_vals: list) -> float:
            pairs = [
                (a, p)
                for a, p in zip(actual_vals, pred_vals)
                if a != 0
            ]
            if not pairs:
                return 0.0
            return float(
                np.mean([abs(a - p) / abs(a) for a, p in pairs]) * 100
            )

        def _rmse(actual_vals: list, pred_vals: list) -> float:
            return float(
                np.sqrt(
                    np.mean(
                        [(a - p) ** 2 for a, p in zip(actual_vals, pred_vals)]
                    )
                )
            )

        def _coverage(
            actual_vals: list, lo: list, hi: list
        ) -> float:
            inside = sum(
                1
                for a, l, h in zip(actual_vals, lo, hi)
                if l <= a <= h
            )
            return (
                round(inside / len(actual_vals) * 100, 1)
                if actual_vals
                else 0
            )

        results: dict[str, Any] = {
            "series": series,
            "unit": unit,
            "horizon": horizon,
            "actual": actual,
            "models": {},
        }

        # MOIRAI-2 metrics
        results["models"]["moirai-2"] = {
            "median": moirai_fc["median"],
            "lo80": moirai_fc["lo80"],
            "hi80": moirai_fc["hi80"],
            "mape": round(_mape(actual, moirai_fc["median"]), 2),
            "rmse": round(_rmse(actual, moirai_fc["median"]), 2),
            "coverage_80": _coverage(
                actual, moirai_fc["lo80"], moirai_fc["hi80"]
            ),
            "quantiles": moirai_fc.get("quantiles", {}),
            "params": MOIRAI_PARAMS,
            "latency_class": "low",
        }

        # Chronos-2 metrics (if available)
        if chronos_fc and "median" in chronos_fc:
            results["models"]["chronos-2"] = {
                "median": chronos_fc["median"],
                "lo80": chronos_fc["lo80"],
                "hi80": chronos_fc["hi80"],
                "mape": round(_mape(actual, chronos_fc["median"]), 2),
                "rmse": round(_rmse(actual, chronos_fc["median"]), 2),
                "coverage_80": _coverage(
                    actual, chronos_fc["lo80"], chronos_fc["hi80"]
                ),
                "params": "120M",
            }

        # TimesFM 2.5 metrics (if available)
        if timesfm_fc and "median" in timesfm_fc:
            results["models"]["timesfm-2.5"] = {
                "median": timesfm_fc["median"],
                "lo80": timesfm_fc["lo80"],
                "hi80": timesfm_fc["hi80"],
                "mape": round(_mape(actual, timesfm_fc["median"]), 2),
                "rmse": round(_rmse(actual, timesfm_fc["median"]), 2),
                "coverage_80": _coverage(
                    actual, timesfm_fc["lo80"], timesfm_fc["hi80"]
                ),
                "params": "200M",
            }

        # Naive metrics
        results["models"]["seasonal-naive"] = {
            "median": naive_fc["median"],
            "mape": round(_mape(actual, naive_fc["median"]), 2),
            "rmse": round(_rmse(actual, naive_fc["median"]), 2),
        }

        # TFT metrics (if available)
        if ensemble_fc:
            results["models"]["price_ensemble"] = {
                "median": ensemble_fc["median"],
                "variant": ensemble_fc["variant"],
                "mape": round(_mape(actual, ensemble_fc["median"]), 2),
                "rmse": round(_rmse(actual, ensemble_fc["median"]), 2),
            }

        # Members computed from seasonal-naive fallbacks are tagged so the
        # honesty layer can degrade provenance (AGENTS.md rule 1).
        results["fallback_members"] = fallback_members

        results["generated_at"] = dt.datetime.now(dt.UTC).isoformat()
        return results


# Singleton
moirai_engine = MoiraiEngine()
