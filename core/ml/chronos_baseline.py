"""
Chronos Zero-Shot Forecasting Baseline
========================================
Uses Amazon's Chronos foundation model for zero-shot time series forecasting.
No training required — instant probabilistic baselines for any time series.

Model: configurable via FISHINTEL_CHRONOS_MODEL (default: amazon/chronos-2,
requires chronos-forecasting>=2.0; set to amazon/chronos-t5-small for the
v1 model on chronos-forecasting 1.x). Downloads on first use.
Capability: probabilistic forecasts with quantile intervals.
If torch/chronos is not installed, every forecast falls back to a
seasonal-naive method and the result is tagged model="...-fallback" —
callers must propagate that as degraded provenance, never as live.

Comparison framework: benchmarks the loaded Chronos model vs TFT vs XGBoost
on holdout windows.
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Any

import numpy as np
import structlog

log = structlog.get_logger(__name__)

DEFAULT_CHRONOS_MODEL = "amazon/chronos-2"


class ChronosBaselineEngine:
    """Singleton for Chronos zero-shot forecasting."""

    def __init__(self) -> None:
        self._pipeline: Any = None
        self._model_name = os.environ.get("FISHINTEL_CHRONOS_MODEL", DEFAULT_CHRONOS_MODEL).strip() or DEFAULT_CHRONOS_MODEL

    @property
    def is_loaded(self) -> bool:
        """True only when the real Chronos model is in memory."""
        return self._pipeline is not None

    def _get_pipeline(self) -> Any:
        """Lazy-load Chronos pipeline (downloads model on first use)."""
        if self._pipeline is None:
            try:
                import torch  # noqa: F401
                from chronos import ChronosPipeline
            except ImportError as e:
                log.warning("chronos_not_installed", hint="pip install chronos-forecasting", error=str(e))
                return None
            try:
                self._pipeline = ChronosPipeline.from_pretrained(
                    self._model_name,
                    device_map="cpu",
                    torch_dtype=__import__("torch").float32,
                )
                log.info("chronos_model_loaded", model=self._model_name)
            except Exception as e:
                log.error("chronos_load_error", model=self._model_name, error=str(e))
                self._pipeline = None
                return None
        return self._pipeline

    async def forecast_series(
        self,
        values: list[float],
        horizon: int = 8,
        num_samples: int = 20,
    ) -> dict:
        """Zero-shot forecast for any float array.

        Returns a dict whose "model" field names what ACTUALLY produced the
        forecast: the model id on success, "<name>-fallback" otherwise.
        Never requires torch — the fallback path is import-safe.
        """
        pipeline = self._get_pipeline()
        if pipeline is None:
            return self._fallback_forecast(values, horizon)

        import torch

        context = torch.tensor(values, dtype=torch.float32).unsqueeze(0)
        forecast = pipeline.predict(context, prediction_length=horizon, num_samples=num_samples)
        samples = forecast.numpy()[0]  # (num_samples, horizon)

        median = np.median(samples, axis=0).tolist()
        lo80 = np.percentile(samples, 10, axis=0).tolist()
        hi80 = np.percentile(samples, 90, axis=0).tolist()
        lo95 = np.percentile(samples, 2.5, axis=0).tolist()
        hi95 = np.percentile(samples, 97.5, axis=0).tolist()

        return {
            "model": self._model_name,
            "horizon": horizon,
            "median": median,
            "lo80": lo80,
            "hi80": hi80,
            "lo95": lo95,
            "hi95": hi95,
            "context_length": len(values),
        }

    def _fallback_forecast(self, values: list[float], horizon: int) -> dict:
        """Simple seasonal naive fallback when Chronos is unavailable."""
        arr = np.array(values[-52:]) if len(values) >= 52 else np.array(values)
        if len(arr) < 2:
            flat = [float(arr[-1])] * horizon if len(arr) > 0 else [0.0] * horizon
            return {
                "model": "naive-fallback",
                "horizon": horizon,
                "median": flat,
                "lo80": flat,
                "hi80": flat,
                "lo95": flat,
                "hi95": flat,
                "context_length": len(values),
                "is_live": False,
                "confidence": 0.1,
                "data_quality": "degraded",
            }

        # Seasonal naive: repeat last year's pattern
        period = min(len(arr), 52)
        median = []
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
            "horizon": horizon,
            "median": median,
            "lo80": lo80,
            "hi80": hi80,
            "lo95": lo95,
            "hi95": hi95,
            "context_length": len(values),
            "is_live": False,
            "confidence": 0.3,
            "data_quality": "degraded",
        }

    async def _get_price_series(self) -> list[float]:
        """Pull SSB weekly prices from DB."""
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

    async def forecast_salmon_prices(self, horizon: int = 4) -> dict:
        """Zero-shot salmon price forecast."""
        values = await self._get_price_series()
        if not values:
            return {"error": "No SSB price data available"}
        result = await self.forecast_series(values, horizon=horizon)
        result["series"] = "salmon_price_nok"
        result["unit"] = "NOK/kg"
        result["last_value"] = values[-1]
        return result

    async def forecast_lice_counts(self, locality_no: int, horizon: int = 8) -> dict:
        """Zero-shot lice count forecast for a farm."""
        values = await self._get_lice_series(locality_no)
        if not values:
            return {"error": f"No lice data for locality {locality_no}"}
        result = await self.forecast_series(values, horizon=horizon)
        result["series"] = "adult_female_lice"
        result["locality_no"] = locality_no
        result["unit"] = "lice/fish"
        result["last_value"] = values[-1]
        return result

    async def forecast_temperatures(self, locality_no: int, horizon: int = 8) -> dict:
        """Zero-shot sea temperature forecast."""
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
        """Zero-shot supply volume forecast (monthly)."""
        values = await self._get_export_series()
        if not values:
            return {"error": "No export volume data available"}
        result = await self.forecast_series(values, horizon=horizon)
        result["series"] = "export_volume_tonnes"
        result["unit"] = "tonnes"
        result["last_value"] = values[-1]
        return result

    async def compare_models(self, series: str = "price", horizon: int = 4) -> dict:
        """Compare Chronos-2 vs TFT vs naive on holdout window."""
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
            return {"error": f"Not enough data for comparison (need {horizon + 20}, have {len(values)})"}

        # Split: train on all-but-last-horizon, test on last horizon
        train = values[:-horizon]
        actual = values[-horizon:]

        # Chronos-2 forecast
        chronos_fc = await self.forecast_series(train, horizon=horizon)
        fallback_members = ["chronos"] if "fallback" in str(chronos_fc.get("model", "")) else []

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
            pairs = [(a, p) for a, p in zip(actual_vals, pred_vals) if a != 0]
            if not pairs:
                return 0.0
            return float(np.mean([abs(a - p) / abs(a) for a, p in pairs]) * 100)

        def _rmse(actual_vals: list, pred_vals: list) -> float:
            return float(np.sqrt(np.mean([(a - p) ** 2 for a, p in zip(actual_vals, pred_vals)])))

        def _coverage(actual_vals: list, lo: list, hi: list) -> float:
            inside = sum(1 for a, l, h in zip(actual_vals, lo, hi) if l <= a <= h)
            return round(inside / len(actual_vals) * 100, 1) if actual_vals else 0

        results: dict[str, Any] = {
            "series": series,
            "unit": unit,
            "horizon": horizon,
            "actual": actual,
            "models": {},
        }

        # Chronos-2 metrics
        results["models"]["chronos-2"] = {
            "median": chronos_fc["median"],
            "lo80": chronos_fc["lo80"],
            "hi80": chronos_fc["hi80"],
            "mape": round(_mape(actual, chronos_fc["median"]), 2),
            "rmse": round(_rmse(actual, chronos_fc["median"]), 2),
            "coverage_80": _coverage(actual, chronos_fc["lo80"], chronos_fc["hi80"]),
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
chronos_baseline = ChronosBaselineEngine()
