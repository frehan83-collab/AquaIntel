"""
TFT Training Pipeline
======================
Trains the Temporal Fusion Transformer on SSB price + lice data.
Saves checkpoint + dataset parameters for inference.

Usage:
  python -m core.market.tft_trainer
  python scripts/train_tft.py --epochs 100
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

MODEL_DIR = Path("data/models")
CHECKPOINT_PATH = MODEL_DIR / "tft_best.ckpt"
PARAMS_PATH = MODEL_DIR / "tft_dataset_params.json"


async def train_tft(
    epochs: int = 100,
    batch_size: int = 32,
    hidden_size: int = 32,
    attention_heads: int = 4,
    lstm_layers: int = 2,
    dropout: float = 0.3,
    learning_rate: float = 1e-3,
    start_year: int = 2012,
    val_weeks: int = 104,
) -> dict:
    """
    Train TFT model and save checkpoint.

    Returns dict with training results (val_loss, mape, etc.)
    """
    import torch
    import lightning.pytorch as pl
    from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint, LearningRateMonitor
    from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
    from pytorch_forecasting.metrics import QuantileLoss
    from pytorch_forecasting.data import GroupNormalizer

    from core.market.tft_data import build_weekly_dataframe, get_dataset_config

    # ── 1. Build data ─────────────────────────────────────────────────
    log.info("tft_train.building_data", start_year=start_year)
    df = await build_weekly_dataframe(start_year=start_year)
    if len(df) < 100:
        return {"error": f"Insufficient data: {len(df)} rows (need 100+)"}

    log.info("tft_train.data_ready", rows=len(df))

    # ── 2. Create TimeSeriesDataSet ───────────────────────────────────
    training_cutoff = df.time_idx.max() - val_weeks
    cfg = get_dataset_config()

    training_ds = TimeSeriesDataSet(
        df[df.time_idx <= training_cutoff],
        **cfg,
        target_normalizer=GroupNormalizer(groups=["group_id"], transformation="softplus"),
    )

    validation_ds = TimeSeriesDataSet.from_dataset(
        training_ds,
        df[df.time_idx > training_cutoff - cfg["max_encoder_length"]],
        predict=True,
        stop_randomization=True,
    )

    train_dl = training_ds.to_dataloader(train=True, batch_size=batch_size, num_workers=0)
    val_dl = validation_ds.to_dataloader(train=False, batch_size=batch_size * 2, num_workers=0)

    log.info("tft_train.datasets_created",
             train_samples=len(training_ds), val_samples=len(validation_ds))

    # ── 3. Create model ───────────────────────────────────────────────
    tft = TemporalFusionTransformer.from_dataset(
        training_ds,
        learning_rate=learning_rate,
        hidden_size=hidden_size,
        attention_head_size=attention_heads,
        dropout=dropout,
        hidden_continuous_size=hidden_size // 2,
        loss=QuantileLoss(quantiles=[0.025, 0.1, 0.25, 0.5, 0.75, 0.9, 0.975]),
        lstm_layers=lstm_layers,
        output_size=7,
        reduce_on_plateau_patience=5,
    )

    n_params = sum(p.numel() for p in tft.parameters())
    log.info("tft_train.model_created", parameters=n_params, hidden=hidden_size)

    # ── 4. Train ──────────────────────────────────────────────────────
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    callbacks = [
        EarlyStopping(monitor="val_loss", patience=10, mode="min", verbose=True),
        ModelCheckpoint(
            dirpath=str(MODEL_DIR),
            filename="tft_best",
            monitor="val_loss",
            save_top_k=1,
            mode="min",
        ),
        LearningRateMonitor(logging_interval="epoch"),
    ]

    trainer = pl.Trainer(
        max_epochs=epochs,
        accelerator="auto",
        gradient_clip_val=0.5,
        callbacks=callbacks,
        enable_progress_bar=True,
        log_every_n_steps=10,
    )

    log.info("tft_train.starting", epochs=epochs)
    trainer.fit(tft, train_dataloaders=train_dl, val_dataloaders=val_dl)

    # ── 5. Save dataset params for inference ──────────────────────────
    params = training_ds.get_parameters()
    with open(PARAMS_PATH, "w") as f:
        json.dump(params, f, default=str)

    log.info("tft_train.saved", checkpoint=str(CHECKPOINT_PATH), params=str(PARAMS_PATH))

    # ── 6. Validate ───────────────────────────────────────────────────
    best_model_path = trainer.checkpoint_callback.best_model_path
    mape = 0.0
    if best_model_path:
        try:
            best_tft = TemporalFusionTransformer.load_from_checkpoint(best_model_path)
            val_predictions = best_tft.predict(val_dl, mode="prediction", return_x=False)

            # val_predictions is a tensor of shape (n_samples, prediction_length)
            # Get actuals from validation dataloader
            import numpy as np
            actuals_list = []
            for batch in iter(val_dl):
                y = batch[1]  # target
                if isinstance(y, (tuple, list)):
                    actuals_list.append(y[0])
                else:
                    actuals_list.append(y)
            if actuals_list:
                actuals = torch.cat(actuals_list).numpy()
                preds = val_predictions.numpy() if hasattr(val_predictions, 'numpy') else np.array(val_predictions)

                # Flatten and compute MAPE
                a_flat = actuals.flatten()
                p_flat = preds.flatten()[:len(a_flat)]
                mask = a_flat > 0
                if mask.any():
                    mape = float(np.mean(np.abs(p_flat[mask] - a_flat[mask]) / a_flat[mask]) * 100)
        except Exception as exc:
            log.warning("tft_train.mape_calc_failed", error=str(exc)[:120])
            mape = 0.0

    result = {
        "status": "success",
        "val_loss": float(trainer.callback_metrics.get("val_loss", 0)),
        "val_mape": round(mape, 2),
        "n_parameters": n_params,
        "epochs_run": trainer.current_epoch,
        "best_checkpoint": best_model_path or str(CHECKPOINT_PATH),
        "data_rows": len(df),
        "train_samples": len(training_ds),
        "val_samples": len(validation_ds),
    }

    log.info("tft_train.complete", **result)
    return result


if __name__ == "__main__":
    asyncio.run(train_tft())
