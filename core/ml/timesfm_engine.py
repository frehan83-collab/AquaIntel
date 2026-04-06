"""
TimesFM 2.5 Foundation Model Forecasting Engine
=================================================
Google's TimesFM 2.5 (Temporal Fusion via Foundation Model) for zero-shot
time series forecasting with native quantile output and exogenous regressors.

Model: google/timesfm-2.5-200m-pytorch (~200M params, HuggingFace)
Context window: 1024 time steps
Max horizon: 256 steps
Quantile head: continuous quantile output (10%, 25%, 50%, 75%, 90%) natively

References:
    Das et al. (2024). "TimesFM: Time Series Foundation Model for Forecasting."
    Google Research. https://arxiv.org/abs/2310.10688
    TimesFM 2.5 release (2025): adds covariate (XReg) support,
    continuous quantile head, and ForecastConfig compilation.

Comparison framework: benchmarks TimesFM vs Chronos-2 vs TFT on holdout windows.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# TimesFM 2.5 model constants
TIMESFM_CONTEXT_LENGTH = 1024
TIMESFM_MAX_HORIZON = 256
TIMESFM_MODEL_NAME = "google/timesfm-2.5-200m-pytorch"

# Default quantile levels for the continuous quantile head
DEFAULT_QUANTILES = [0.1, 0.25, 0.5, 0.75, 0.9]


class TimesFMEngine:
    """Singleton for Google TimesFM 2.5 zero-shot forecasting.

    Uses lazy model loading: the 200M-parameter model is downloaded from
    HuggingFace on first use. Falls back to seasonal-naive when the
    ``timesfm`` package is not installed.

    The quantile head outputs percentiles natively (no MC sampling needed),
    unlike Chronos which requires multiple forward passes.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._model_name = TIMESFM_MODEL_NAME
        self._available: Optional[bool] = None

    # ── Model Loading ────────────────────────────────────────────────────

    def _get_model(self) -> Any:
        """Lazy-load TimesFM 2.5 model (downloads ~800MB on first use).

        Uses ``timesfm.TimesFm.from_pretrained()`` with ForecastConfig
        for JIT compilation. The model runs on CPU by default.
        """
        if self._model is not None:
            return self._model

        try:
            import timesfm

            # TimesFM 2.5 uses ForecastConfig for compilation settings
            self._model = timesfm.TimesFm.from_pretrained(
                self._model_name,
            )
            self._available = True
            log.info(
                "timesfm_model_loaded",
                model=self._model_name,
                context_length=TIMESFM_CONTEXT_LENGTH,
                max_horizon=TIMESFM_MAX_HORIZON,
            )
        except ImportError:
            self._available = False
            log.warning(
                "timesfm_not_installed",
                hint="pip install timesfm>=2.0",
            )
            return None
        except Exception as e:
            self._available = False
            log.error("timesfm_load_error", error=str(e))
            return None

        return self._model

    def is_available(self) -> bool:
        """Check if TimesFM is installed and model can be loaded."""
        if self._available is None:
            self._get_model()
        return bool(self._available)

    # ── Core Forecast ────────────────────────────────────────────────────

    async def forecast_series(
        self,
        values: list[float],
        horizon: int = 8,
        freq: int = 0,
        xreg: Optional[list[list[float]]] = None,
        quantiles: Optional[list[float]] = None,
    ) -> dict:
        """Zero-shot forecast for any float array using TimesFM 2.5.

        Args:
            values: Historical time series values.
            horizon: Number of future steps to forecast (max 256).
            freq: Frequency indicator (0=auto, 1=minutely, ..., 5=yearly).
                  TimesFM 2.5 infers frequency if set to 0.
            xreg: Optional exogenous regressors. List of covariate arrays,
                  each of length ``len(values) + horizon``. TimesFM 2.5
                  supports dynamic covariates via its XReg interface.
            quantiles: Quantile levels to output. Defaults to
                       [0.1, 0.25, 0.5, 0.75, 0.9].

        Returns:
            Dict with model name, horizon, quantile forecasts, and metadata.
        """
        horizon = min(horizon, TIMESFM_MAX_HORIZON)
        q_levels = quantiles or DEFAULT_QUANTILES

        model = self._get_model()
        if model is None:
            return self._fallback_forecast(values, horizon)

        try:
            # Truncate context to model's window
            context = values[-TIMESFM_CONTEXT_LENGTH:]

            # TimesFM 2.5 predict call
            # The API accepts a list of time series and returns point + quantile
            forecast_input = [np.array(context, dtype=np.float32)]

            # Build kwargs for the predict call
            predict_kwargs: dict[str, Any] = {
                "horizon": horizon,
            }

            # XReg covariate support (TimesFM 2.5 feature)
            if xreg is not None:
                predict_kwargs["xreg"] = [
                    np.array(x, dtype=np.float32) for x in xreg
                ]

            # Frequency hint
            if freq > 0:
                predict_kwargs["freq"] = [freq]

            point_forecast, quantile_forecast = model.forecast(
                forecast_input,
                **predict_kwargs,
            )

            # point_forecast shape: (1, horizon)
            # quantile_forecast shape: (1, num_quantiles, horizon)
            median = point_forecast[0].tolist()

            # Extract quantiles from the continuous quantile head
            # TimesFM 2.5 outputs quantiles natively without MC sampling
            q_dict: dict[str, list[float]] = {}
            if quantile_forecast is not None and len(quantile_forecast) > 0:
                qf = quantile_forecast[0]  # (num_quantiles, horizon)
                for i, q in enumerate(q_levels):
                    if i < len(qf):
                        q_dict[f"q{int(q * 100):02d}"] = qf[i].tolist()

            # Map to standard interval format (compatible with Chronos output)
            lo80 = q_dict.get("q10", [m - abs(m) * 0.1 for m in median])
            hi80 = q_dict.get("q90", [m + abs(m) * 0.1 for m in median])
            lo95 = q_dict.get("q10", lo80)  # Use q10 as approximate lo95
            hi95 = q_dict.get("q90", hi80)  # Use q90 as approximate hi95

            return {
                "model": "timesfm-2.5-200m",
                "horizon": horizon,
                "median": median,
                "lo80": lo80,
                "hi80": hi80,
                "lo95": lo95,
                "hi95": hi95,
                "quantiles": q_dict,
                "context_length": len(context),
                "is_live": True,
                "confidence": 0.75,
                "data_quality": "live",
            }
        except Exception as e:
            log.error("timesfm_forecast_error", error=str(e))
            return self._fallback_forecast(values, horizon)

    # ── Seasonal-Naive Fallback ──────────────────────────────────────────

    def _fallback_forecast(self, values: list[float], horizon: int) -> dict:
        """Seasonal-naive fallback when TimesFM is unavailable.

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
        }

    # ── DB Data Retrieval (mirrors ChronosBaselineEngine) ────────────────

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

    async def _get_lice_with_temperature(
        self, locality_no: int
    ) -> tuple[list[float], list[float]]:
        """Pull lice counts AND sea temperature for XReg covariate support.

        Temperature is a known driver of salmon louse reproduction rates
        (Stige et al. 2006; Kristoffersen et al. 2014). TimesFM 2.5
        can incorporate this as a dynamic covariate.
        """
        from core.models import LiceRecord
        from core.async_db import get_async_session
        from sqlalchemy import select

        async with get_async_session() as s:
            result = await s.execute(
                select(
                    LiceRecord.avg_adult_female_lice,
                    LiceRecord.sea_temp_c,
                )
                .where(LiceRecord.locality_no == locality_no)
                .where(LiceRecord.avg_adult_female_lice.isnot(None))
                .where(LiceRecord.sea_temp_c.isnot(None))
                .order_by(LiceRecord.year, LiceRecord.week)
            )
            rows = result.all()

        lice = [float(r[0]) for r in rows]
        temps = [float(r[1]) for r in rows]
        return lice, temps

    async def _get_price_with_supply(self) -> tuple[list[float], list[float]]:
        """Pull salmon prices AND export volumes for XReg covariate support.

        Supply volume is a key price driver in the salmon spot market
        (Asche & Bjorndal 2011; Oglend 2013). TimesFM 2.5 can incorporate
        this as a dynamic covariate for improved price forecasting.

        Note: prices are weekly, supply is monthly. We repeat monthly
        values to align with the weekly cadence.
        """
        prices = await self._get_price_series()
        supply = await self._get_export_series()

        if not supply:
            return prices, []

        # Repeat monthly supply to weekly (~4.33 weeks per month)
        weekly_supply: list[float] = []
        for vol in supply:
            weekly_supply.extend([vol] * 4)
            if len(weekly_supply) >= len(prices):
                break

        # Align lengths
        min_len = min(len(prices), len(weekly_supply))
        return prices[-min_len:], weekly_supply[-min_len:]

    # ── Domain-Specific Forecasts ────────────────────────────────────────

    async def forecast_salmon_prices(
        self, horizon: int = 4, use_xreg: bool = True
    ) -> dict:
        """Zero-shot salmon price forecast with optional supply covariate.

        Args:
            horizon: Weeks ahead to forecast (default 4).
            use_xreg: If True, includes supply volume as exogenous regressor.
        """
        xreg = None
        if use_xreg:
            prices, supply = await self._get_price_with_supply()
            if supply and len(supply) >= 20:
                # Extend supply with naive repeat for the horizon
                supply_extended = supply + supply[-horizon:]
                xreg = [supply_extended]
                values = prices
            else:
                values = await self._get_price_series()
        else:
            values = await self._get_price_series()

        if not values:
            return {"error": "No SSB price data available"}

        result = await self.forecast_series(values, horizon=horizon, xreg=xreg)
        result["series"] = "salmon_price_nok"
        result["unit"] = "NOK/kg"
        result["last_value"] = values[-1]
        result["xreg_used"] = xreg is not None
        return result

    async def forecast_lice_counts(
        self, locality_no: int, horizon: int = 8, use_xreg: bool = True
    ) -> dict:
        """Zero-shot lice count forecast with optional temperature covariate.

        Temperature drives louse reproduction (Stige et al. 2006).
        TimesFM 2.5 can leverage this via its XReg interface.
        """
        xreg = None
        if use_xreg:
            lice, temps = await self._get_lice_with_temperature(locality_no)
            if temps and len(temps) >= 20:
                # Extend temperature with seasonal repeat for horizon
                period = min(len(temps), 52)
                temp_ext = temps + [
                    temps[-(period - (h % period))] for h in range(horizon)
                ]
                xreg = [temp_ext]
                values = lice
            else:
                values = await self._get_lice_series(locality_no)
        else:
            values = await self._get_lice_series(locality_no)

        if not values:
            return {"error": f"No lice data for locality {locality_no}"}

        result = await self.forecast_series(values, horizon=horizon, xreg=xreg)
        result["series"] = "adult_female_lice"
        result["locality_no"] = locality_no
        result["unit"] = "lice/fish"
        result["last_value"] = values[-1]
        result["xreg_used"] = xreg is not None
        return result

    async def forecast_temperatures(
        self, locality_no: int, horizon: int = 8
    ) -> dict:
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

    # ── Model Comparison ─────────────────────────────────────────────────

    async def compare_models(
        self, series: str = "price", horizon: int = 4
    ) -> dict:
        """Compare TimesFM 2.5 vs Chronos-2 vs TFT vs naive on holdout.

        Uses the last ``horizon`` observations as the test set and trains
        on all preceding data. Reports MAPE, RMSE, and 80% coverage for
        each model.
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

        # TimesFM 2.5 forecast
        timesfm_fc = await self.forecast_series(train, horizon=horizon)

        # Chronos-2 forecast (if available)
        chronos_fc = None
        try:
            from core.ml.chronos_baseline import chronos_baseline

            chronos_fc = await chronos_baseline.forecast_series(
                train, horizon=horizon
            )
        except Exception:
            pass

        # Naive baseline (seasonal repeat)
        naive_fc = self._fallback_forecast(train, horizon)

        # TFT comparison (if available)
        tft_fc = None
        try:
            from core.market.price_ml import price_engine

            if series == "price" and hasattr(price_engine, "forecast"):
                tft_result = await price_engine.forecast(
                    horizon_weeks=horizon
                )
                if tft_result and "predictions" in tft_result:
                    tft_fc = {
                        "median": [
                            p.get("predicted_nok", 0)
                            for p in tft_result["predictions"][:horizon]
                        ],
                    }
        except Exception:
            pass

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

        # TimesFM 2.5 metrics
        results["models"]["timesfm-2.5"] = {
            "median": timesfm_fc["median"],
            "lo80": timesfm_fc["lo80"],
            "hi80": timesfm_fc["hi80"],
            "mape": round(_mape(actual, timesfm_fc["median"]), 2),
            "rmse": round(_rmse(actual, timesfm_fc["median"]), 2),
            "coverage_80": _coverage(
                actual, timesfm_fc["lo80"], timesfm_fc["hi80"]
            ),
            "quantiles": timesfm_fc.get("quantiles", {}),
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
            }

        # Naive metrics
        results["models"]["seasonal-naive"] = {
            "median": naive_fc["median"],
            "mape": round(_mape(actual, naive_fc["median"]), 2),
            "rmse": round(_rmse(actual, naive_fc["median"]), 2),
        }

        # TFT metrics (if available)
        if tft_fc and len(tft_fc["median"]) == horizon:
            results["models"]["tft"] = {
                "median": tft_fc["median"],
                "mape": round(_mape(actual, tft_fc["median"]), 2),
                "rmse": round(_rmse(actual, tft_fc["median"]), 2),
            }

        results["generated_at"] = dt.datetime.now(dt.UTC).isoformat()
        return results


# Singleton
timesfm_engine = TimesFMEngine()
