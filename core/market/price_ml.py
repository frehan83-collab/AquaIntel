"""
ML Price Prediction Ensemble
==============================
Hybrid ensemble combining:
  1. Seasonal decomposition (baseline)
  2. XGBoost gradient-boosted regression (primary ML layer)
  3. Conformal prediction for calibrated uncertainty bands

Features consumed:
  - Lice stage-specific forecasts (from Stige model)
  - Cleaner fish deployment signals
  - Supply volume projections (biomass tracker)
  - Seasonal position (week-of-year harmonics)
  - Historical price momentum (lagged returns)
  - Export volume trends

Designed for nightly incremental retraining via Self-Improvement Agent.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PriceScenario:
    """Single Monte Carlo scenario output."""
    horizon_week: int
    price_nok: float
    lice_driver_pct: float
    supply_driver_pct: float
    seasonal_driver_pct: float


@dataclass
class EnsemblePriceForecast:
    """Full ML ensemble price forecast with calibrated uncertainty."""
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    horizon_weeks: int = 4
    current_spot_nok: float = 0.0

    # Point estimates
    predicted_nok: float = 0.0
    direction: str = "neutral"
    confidence: float = 0.0

    # Conformal prediction bands (calibrated coverage)
    price_lo95: float = 0.0
    price_hi95: float = 0.0
    price_lo80: float = 0.0
    price_hi80: float = 0.0
    price_lo50: float = 0.0
    price_hi50: float = 0.0

    # Component signals
    lice_signal: str = "neutral"
    supply_signal: str = "neutral"
    seasonal_signal: str = "neutral"
    export_signal: str = "neutral"
    futures_signal: str = "neutral"
    combined_signal: str = "NEUTRAL"

    # Model metadata
    model_version: str = "ensemble_v1"
    n_scenarios: int = 0
    # Measured MAPE ONLY when a validated backtest artifact matched this
    # model_version; None means "no validated backtest on record".
    mape_backtest: Optional[float] = None
    # Empirical band calibration from the validated backtest — the "trust"
    # field (QUANT #2): per-horizon measured coverage_80 + sample size.
    band_trust: Optional[dict] = None
    rationale: str = ""

    # Scenario distribution
    scenarios_p10: float = 0.0
    scenarios_p25: float = 0.0
    scenarios_p50: float = 0.0
    scenarios_p75: float = 0.0
    scenarios_p90: float = 0.0

    # Accuracy transparency
    accuracy_statement: str = ""
    model_quality: str = "ml_model"  # "ml_model" | "rule_based_fallback"
    disclaimer: str = (
        "Price forecasts are probabilistic and not financial advice. "
        "Historical patterns do not guarantee future results."
    )


# ── Fallback seasonal pattern (used only when SSB data unavailable) ──
_FALLBACK_SEASONAL = {
    1: 72, 2: 73, 3: 74, 4: 75, 5: 77, 6: 79, 7: 80, 8: 82,
    9: 84, 10: 86, 11: 88, 12: 90, 13: 91, 14: 92, 15: 93, 16: 93,
    17: 92, 18: 90, 19: 88, 20: 85, 21: 82, 22: 80, 23: 78, 24: 76,
    25: 74, 26: 72, 27: 71, 28: 70, 29: 69, 30: 68, 31: 67, 32: 66,
    33: 65, 34: 64, 35: 63, 36: 62, 37: 62, 38: 63, 39: 64, 40: 66,
    41: 68, 42: 70, 43: 72, 44: 74, 45: 76, 46: 78, 47: 79, 48: 80,
    49: 79, 50: 78, 51: 76, 52: 74,
}

# Dynamic seasonal pattern — set from real SSB data at startup
SEASONAL_PATTERN = dict(_FALLBACK_SEASONAL)  # mutable copy, updated at runtime

# ── Lice-to-price elasticity (empirical, horizon-dependent) ──
LICE_PRICE_ELASTICITY = {
    2: -1.5, 4: -0.5, 6: 2.0, 8: 3.5, 10: 2.5, 12: 1.0,
    14: 0.5, 16: 0.3, 18: 0.2, 20: 0.1,
}

# ── Backtest artifact (optional) ──────────────────────────────────────────────
# HORIZON_MAPE below is a REFERENCE table from an offline rule-tier analysis —
# it is NOT a validated backtest of the model that runs in production, so it
# must never be surfaced to users as "Backtested MAPE". Accuracy claims are
# only allowed when a real artifact written by scripts/backtest_price_ml.py
# exists (data/models/price_backtest.json) and matches the running
# model_version.
REFERENCE_HORIZON_MAPE = {
    2: 3.8, 4: 5.2, 6: 7.1, 8: 9.4, 10: 11.6,
    12: 13.5, 14: 15.2, 16: 16.8, 18: 18.1, 20: 19.3,
}
# Backwards-compatible alias (internal tuning only — never shown to users)
HORIZON_MAPE = REFERENCE_HORIZON_MAPE

BACKTEST_ARTIFACT = MODEL_DIR / "price_backtest.json"


class PriceEnsemble:
    """
    ML ensemble for salmon spot-price prediction.

    Architecture:
      Layer 1: Seasonal decomposition + momentum
      Layer 2: XGBoost regression on biological + market features
      Layer 3: Conformal prediction for calibrated uncertainty

    When XGBoost is not available (no trained model), falls back to
    the rule-based engine with enhanced uncertainty quantification.
    """

    def __init__(self) -> None:
        self._xgb_model = None
        self._conformal_residuals: list[float] = []          # legacy flat list
        self._conformal_residuals_by_h: dict[int, list[float]] = {}  # horizon-keyed
        self._model_version = "ensemble_v1_rule"
        self._last_retrain: Optional[dt.datetime] = None
        self._backtest_mape: dict[int, float] = dict(HORIZON_MAPE)
        self._ssb_seasonal_loaded = False
        self._load_model()

    def set_seasonal_pattern(self, pattern: dict[int, float]) -> None:
        """
        Update the seasonal pattern with real SSB data.
        Called at startup after fetching bulk SSB price history.
        """
        global SEASONAL_PATTERN
        if pattern and len(pattern) >= 40:
            SEASONAL_PATTERN.update(pattern)
            self._ssb_seasonal_loaded = True
            log.info(
                "price_ml.seasonal_updated",
                source="ssb",
                n_weeks=len(pattern),
                sample_w1=pattern.get(1),
                sample_w26=pattern.get(26),
            )

    def _load_model(self) -> None:
        """Attempt to load pre-trained XGBoost model."""
        model_path = MODEL_DIR / "price_xgb.json"
        residuals_path = MODEL_DIR / "conformal_residuals.json"

        try:
            import xgboost as xgb
            if model_path.exists():
                self._xgb_model = xgb.XGBRegressor()
                self._xgb_model.load_model(str(model_path))
                self._model_version = "ensemble_v1_xgb"
                log.info("price_ml.xgb_loaded", path=str(model_path))
        except ImportError:
            log.info("price_ml.xgb_not_available", fallback="rule_based")
        except Exception as e:
            log.warning("price_ml.xgb_load_error", error=str(e)[:100])

        try:
            if residuals_path.exists():
                data = json.loads(residuals_path.read_text())
                if isinstance(data, dict) and "horizon_residuals" in data:
                    # Structured calibration (scripts/backtest_price_ml.py):
                    # per-horizon residuals, horizon-specific quantiles (MSCP).
                    if data.get("model_version") == self._model_version:
                        self._conformal_residuals_by_h = {
                            int(h): [float(v) for v in vals]
                            for h, vals in data["horizon_residuals"].items()
                            if vals
                        }
                        log.info(
                            "price_ml.conformal_loaded",
                            model_version=data.get("model_version"),
                            horizons=sorted(self._conformal_residuals_by_h),
                        )
                    else:
                        log.warning(
                            "price_ml.conformal_version_mismatch",
                            artifact=data.get("model_version"),
                            current=self._model_version,
                        )
                elif isinstance(data, dict) and "residuals_flat" in data:
                    # Version-gated flat calibration (PriceEnsemble.retrain)
                    if data.get("model_version") == self._model_version:
                        self._conformal_residuals = [float(v) for v in data["residuals_flat"]]
                        log.info(
                            "price_ml.conformal_loaded",
                            n_residuals=len(self._conformal_residuals),
                            format="flat_versioned",
                        )
                    else:
                        log.warning(
                            "price_ml.conformal_version_mismatch",
                            artifact=data.get("model_version"),
                            current=self._model_version,
                        )
                else:
                    # Legacy bare-list artifacts have an unknown sign
                    # convention and no version — refuse to load rather than
                    # risk sign-inverted bands.
                    log.warning("price_ml.conformal_legacy_format_refused")
        except Exception:
            pass

    def _load_backtest(self) -> dict | None:
        """Load the validated backtest artifact, if present and well-formed.

        The artifact must be produced by scripts/backtest_price_ml.py for the
        exact model_version being served. Absence (or malformed structure)
        means: no accuracy claim may be made (see honesty contract in
        forecast()). A malformed artifact must never fabricate "0.0% MAPE"
        or crash the forecast path.
        """
        try:
            if not BACKTEST_ARTIFACT.exists():
                return None
            data = json.loads(BACKTEST_ARTIFACT.read_text())
        except Exception as e:
            log.warning("price_ml.backtest_artifact_unreadable", error=str(e)[:100])
            return None

        # Structural validation: non-empty mape map, int-coercible horizon
        # keys, numeric values. Anything else = no artifact.
        if not isinstance(data, dict):
            return None
        mape_map = data.get("mape")
        if not isinstance(mape_map, dict) or not mape_map:
            log.warning("price_ml.backtest_artifact_invalid", reason="mape missing or empty")
            return None
        try:
            validated = {int(k): float(v) for k, v in mape_map.items()}
        except (TypeError, ValueError):
            log.warning("price_ml.backtest_artifact_invalid", reason="non-numeric mape entries")
            return None
        data["mape"] = {str(k): v for k, v in validated.items()}
        return data

    def _build_features(
        self,
        current_spot: float,
        horizon_weeks: int,
        national_avg_lice: float,
        lice_trend: str,
        pct_above_threshold: float,
        biomass_vs_normal: float,
        avg_mobile_lice: float = 0.0,
        avg_sessile_lice: float = 0.0,
        cleaner_fish_pct: float = 0.0,
        export_volume_trend: float = 0.0,
        futures_premium_pct: float = 0.0,
        as_of: dt.datetime | None = None,
    ) -> np.ndarray:
        """Build feature vector for the XGBoost model.

        as_of: evaluation timestamp (UTC) for seasonal features — used by the
        walk-forward backtest so features reflect the historical week, not
        today's. Defaults to now.
        """
        now = as_of or dt.datetime.now(dt.UTC)
        _, week, _ = now.isocalendar()

        # Seasonal harmonics (sin/cos encoding for circularity)
        week_sin = np.sin(2 * np.pi * week / 52)
        week_cos = np.cos(2 * np.pi * week / 52)

        # Future week harmonics
        fw = (week + horizon_weeks) % 52 or 52
        fw_sin = np.sin(2 * np.pi * fw / 52)
        fw_cos = np.cos(2 * np.pi * fw / 52)

        # Lice trend encoding
        trend_enc = {"increasing": 1.0, "stable": 0.0, "decreasing": -1.0}
        trend_val = trend_enc.get(lice_trend, 0.0)

        # Price momentum (deviation from seasonal expectation)
        seasonal_now = SEASONAL_PATTERN.get(week, 75)
        price_deviation = (current_spot - seasonal_now) / seasonal_now

        features = np.array([
            current_spot,
            horizon_weeks,
            national_avg_lice,
            avg_mobile_lice,
            avg_sessile_lice,
            trend_val,
            pct_above_threshold,
            biomass_vs_normal,
            cleaner_fish_pct,
            export_volume_trend,
            futures_premium_pct,
            week_sin,
            week_cos,
            fw_sin,
            fw_cos,
            price_deviation,
            national_avg_lice * biomass_vs_normal,  # interaction: lice × supply
            pct_above_threshold * horizon_weeks,     # interaction: crisis × time
        ]).reshape(1, -1)

        return features

    def predict(
        self,
        current_spot: float,
        horizon_weeks: int = 4,
        national_avg_lice: float = 0.15,
        lice_trend: str = "stable",
        pct_above_threshold: float = 0.0,
        biomass_vs_normal: float = 1.0,
        avg_mobile_lice: float = 0.0,
        avg_sessile_lice: float = 0.0,
        cleaner_fish_pct: float = 0.0,
        export_volume_trend: float = 0.0,
        futures_premium_pct: float = 0.0,
        n_scenarios: int = 1000,
        as_of: dt.datetime | None = None,
    ) -> EnsemblePriceForecast:
        """
        Generate probabilistic price forecast.

        Uses XGBoost if available, otherwise falls back to rule-based
        with enhanced conformal prediction bands.

        as_of: evaluation timestamp for seasonal features — used by the
        walk-forward backtest (scripts/backtest_price_ml.py) so forecasts
        issued for historical weeks use that week's seasonal phase.
        """
        if current_spot <= 0:
            now = as_of or dt.datetime.now(dt.UTC)
            _, week, _ = now.isocalendar()
            current_spot = SEASONAL_PATTERN.get(week, 75)

        # ── Layer 1: Seasonal + Momentum baseline ──────────────
        seasonal_pred = self._seasonal_forecast(current_spot, horizon_weeks, as_of=as_of)

        # ── Layer 2: TFT → XGBoost → Rule-based (3-tier cascade) ──
        model_tag = ""
        tft_bands = None

        # Tier 1: Temporal Fusion Transformer (best accuracy)
        if not model_tag:
            try:
                from core.market.tft_predictor import tft_predictor
                if tft_predictor.is_available:
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Already in async context — create task
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as pool:
                                tft_result = pool.submit(
                                    asyncio.run, tft_predictor.predict(horizon_weeks)
                                ).result(timeout=30)
                        else:
                            tft_result = asyncio.run(tft_predictor.predict(horizon_weeks))
                    except RuntimeError:
                        tft_result = None

                    if tft_result and "predicted_nok" in tft_result:
                        predicted = tft_result["predicted_nok"]
                        tft_bands = tft_result["bands"]
                        model_tag = "tft"
                        log.debug("price_ml.tft_used", predicted=predicted, horizon=horizon_weeks)
            except Exception as exc:
                log.debug("price_ml.tft_fallback", error=str(exc)[:80])

        # Tier 2: XGBoost (good accuracy, always available if trained)
        if not model_tag and self._xgb_model is not None:
            features = self._build_features(
                current_spot, horizon_weeks, national_avg_lice,
                lice_trend, pct_above_threshold, biomass_vs_normal,
                avg_mobile_lice, avg_sessile_lice, cleaner_fish_pct,
                export_volume_trend, futures_premium_pct, as_of=as_of,
            )
            try:
                ml_pred = float(self._xgb_model.predict(features)[0])
                predicted = 0.4 * seasonal_pred + 0.6 * ml_pred
                model_tag = "xgb"
            except Exception as e:
                log.warning("price_ml.xgb_error", error=str(e)[:80])

        # Tier 3: Rule-based (always works, lowest accuracy)
        if not model_tag:
            predicted = self._rule_based_forecast(
                current_spot, horizon_weeks, national_avg_lice,
                lice_trend, pct_above_threshold, biomass_vs_normal,
                export_volume_trend, futures_premium_pct, as_of=as_of,
            )
            model_tag = "rule"
            log.info("price_ml.using_rule_based_fallback", reason="TFT and XGBoost unavailable")

        # ── Layer 3: Prediction bands ─────────────────────────
        if tft_bands:
            # TFT provides native quantile bands — no conformal needed
            bands = tft_bands
        else:
            bands = self._conformal_bands(
                predicted, current_spot, horizon_weeks, n_scenarios,
            )

        # ── Signal classification ──────────────────────────────
        change_pct = (predicted - current_spot) / current_spot * 100
        signals = self._classify_signals(
            change_pct, national_avg_lice, lice_trend,
            pct_above_threshold, biomass_vs_normal,
            export_volume_trend, futures_premium_pct, horizon_weeks,
        )

        # ── Accuracy statement (honesty contract) ────────────────
        # Only claim measured accuracy when a real backtest artifact exists
        # AND it was produced for this exact model version. Otherwise state
        # plainly that no validated backtest is on record — never fabricate
        # MAPE or coverage numbers.
        expected_version = (
            f"ensemble_v2_{model_tag}" if model_tag == "tft"
            else f"ensemble_v1_{model_tag}"
        )
        backtest = self._load_backtest()
        mape_value: float | None = None
        band_trust: Optional[dict] = None

        if backtest and backtest.get("model_version") == expected_version:
            mape_map = backtest.get("mape", {})
            nearest = min(mape_map.keys(), key=lambda k: abs(int(k) - horizon_weeks))
            mape_value = float(mape_map[nearest])
            coverage = backtest.get("coverage_80")
            # Trust: empirical calibration of the uncertainty bands, per horizon
            per_h = backtest.get("per_horizon", {})
            if nearest in per_h:
                band_trust = {
                    "horizon_weeks": int(nearest),
                    "measured_coverage_80": per_h[nearest].get("coverage_80"),
                    "n_eval_points": per_h[nearest].get("n"),
                    "backtest_run": backtest.get("generated_at"),
                }
            accuracy_stmt = (
                f"Backtested {horizon_weeks}-week MAPE: {mape_value:.1f}% "
                f"on {backtest.get('window', 'held-out data')} "
                f"(run {backtest.get('generated_at', 'unknown date')}, {model_tag} model)."
            )
            if coverage is not None:
                accuracy_stmt += f" {float(coverage):.0f}% of actual prices fell within the indicated band."
        elif model_tag == "rule":
            accuracy_stmt = (
                "Rule-based forecast (TFT and XGBoost models unavailable in this "
                "deployment) — no validated backtest on record for this tier; "
                "uncertainty bands are heuristically widened, not calibrated."
            )
        else:
            accuracy_stmt = (
                f"{model_tag} model active, but no validated backtest artifact is "
                "on record for this model version — treat accuracy as unverified."
            )

        model_quality = "rule_based_fallback" if model_tag == "rule" else "ml_model"

        return EnsemblePriceForecast(
            horizon_weeks=horizon_weeks,
            current_spot_nok=round(current_spot, 1),
            predicted_nok=round(predicted, 1),
            direction=signals["direction"],
            confidence=round(signals["confidence"], 2),
            price_lo95=round(bands["lo95"], 1),
            price_hi95=round(bands["hi95"], 1),
            price_lo80=round(bands["lo80"], 1),
            price_hi80=round(bands["hi80"], 1),
            price_lo50=round(bands["lo50"], 1),
            price_hi50=round(bands["hi50"], 1),
            lice_signal=signals["lice"],
            supply_signal=signals["supply"],
            seasonal_signal=signals["seasonal"],
            export_signal=signals["export"],
            futures_signal=signals["futures"],
            combined_signal=signals["combined"],
            model_version=f"ensemble_v2_{model_tag}" if model_tag == "tft" else f"ensemble_v1_{model_tag}",
            n_scenarios=n_scenarios,
            mape_backtest=mape_value,
            band_trust=band_trust,
            rationale=signals["rationale"],
            scenarios_p10=round(bands["p10"], 1),
            scenarios_p25=round(bands["p25"], 1),
            scenarios_p50=round(bands["p50"], 1),
            scenarios_p75=round(bands["p75"], 1),
            scenarios_p90=round(bands["p90"], 1),
            accuracy_statement=accuracy_stmt,
            model_quality=model_quality,
        )

    def _seasonal_forecast(
        self, current_spot: float, horizon_weeks: int,
        as_of: dt.datetime | None = None,
    ) -> float:
        """Pure seasonal baseline prediction (as_of = evaluation timestamp)."""
        now = as_of or dt.datetime.now(dt.UTC)
        _, week, _ = now.isocalendar()

        future_week = (week + horizon_weeks - 1) % 52 + 1
        seasonal_now = SEASONAL_PATTERN.get(week, 75)
        seasonal_future = SEASONAL_PATTERN.get(future_week, 75)

        seasonal_ratio = seasonal_future / seasonal_now if seasonal_now > 0 else 1.0
        return current_spot * seasonal_ratio

    def _rule_based_forecast(
        self,
        current_spot: float,
        horizon_weeks: int,
        national_avg_lice: float,
        lice_trend: str,
        pct_above_threshold: float,
        biomass_vs_normal: float,
        export_volume_trend: float,
        futures_premium_pct: float,
        as_of: dt.datetime | None = None,
    ) -> float:
        """Enhanced rule-based forecast with biological + market features."""
        now = as_of or dt.datetime.now(dt.UTC)
        _, week, _ = now.isocalendar()

        # Seasonal
        future_week = (week + horizon_weeks - 1) % 52 + 1
        seasonal_now = SEASONAL_PATTERN.get(week, 75)
        seasonal_future = SEASONAL_PATTERN.get(future_week, 75)
        seasonal_change = (seasonal_future - seasonal_now) / seasonal_now * 100

        # Lice impact
        nearest_h = min(LICE_PRICE_ELASTICITY.keys(),
                        key=lambda k: abs(k - horizon_weeks))
        lice_response = LICE_PRICE_ELASTICITY[nearest_h]
        lice_severity = national_avg_lice / 0.5
        lice_impact = lice_response * lice_severity

        trend_mult = {"increasing": 1.5, "stable": 1.0, "decreasing": 0.5}
        lice_impact *= trend_mult.get(lice_trend, 1.0)

        # Supply
        supply_impact = (1 - biomass_vs_normal) * 15
        supply_impact += pct_above_threshold * 10

        # Export demand
        export_impact = export_volume_trend * 3  # +1% export growth → +3% price

        # Futures signal
        futures_impact = futures_premium_pct * 0.5  # futures premium → mean reversion

        # Weighted blend
        total_pct = (
            0.30 * seasonal_change +
            0.25 * lice_impact +
            0.20 * supply_impact +
            0.15 * export_impact +
            0.10 * futures_impact
        )

        return current_spot * (1 + total_pct / 100)

    def _conformal_bands(
        self,
        predicted: float,
        current_spot: float,
        horizon_weeks: int,
        n_scenarios: int,
    ) -> dict:
        """
        Conformal prediction uncertainty bands.

        Uses stored calibration residuals if available, otherwise
        parametric estimation based on historical volatility.
        """
        # Base weekly volatility ~4% for salmon spot prices
        weekly_vol = current_spot * 0.04
        horizon_vol = weekly_vol * np.sqrt(horizon_weeks)

        if self._conformal_residuals_by_h:
            # Horizon-specific split-conformal residuals from the walk-forward
            # backtest (MSCP-style): quantiles come from the residual
            # distribution of THIS horizon — no sqrt-scaling heuristic.
            nearest_h = min(
                self._conformal_residuals_by_h,
                key=lambda k: abs(k - horizon_weeks),
            )
            residuals = np.array(self._conformal_residuals_by_h[nearest_h])
            lo95 = predicted + np.percentile(residuals, 2.5)
            hi95 = predicted + np.percentile(residuals, 97.5)
            lo80 = predicted + np.percentile(residuals, 10)
            hi80 = predicted + np.percentile(residuals, 90)
            lo50 = predicted + np.percentile(residuals, 25)
            hi50 = predicted + np.percentile(residuals, 75)
        elif self._conformal_residuals and len(self._conformal_residuals) > 30:
            # Non-parametric: scale stored residuals to horizon
            residuals = np.array(self._conformal_residuals)
            scale = np.sqrt(horizon_weeks)
            scaled = residuals * scale

            lo95 = predicted + np.percentile(scaled, 2.5)
            hi95 = predicted + np.percentile(scaled, 97.5)
            lo80 = predicted + np.percentile(scaled, 10)
            hi80 = predicted + np.percentile(scaled, 90)
            lo50 = predicted + np.percentile(scaled, 25)
            hi50 = predicted + np.percentile(scaled, 75)
        else:
            # Parametric Gaussian with slight fat tails (t-distribution effect)
            tail_factor = 1.15  # slightly wider than Gaussian
            lo95 = predicted - 1.96 * horizon_vol * tail_factor
            hi95 = predicted + 1.96 * horizon_vol * tail_factor
            lo80 = predicted - 1.28 * horizon_vol * tail_factor
            hi80 = predicted + 1.28 * horizon_vol * tail_factor
            lo50 = predicted - 0.67 * horizon_vol
            hi50 = predicted + 0.67 * horizon_vol

        # Monte Carlo scenarios for distribution
        rng = np.random.default_rng(42)
        # Mix of Gaussian + occasional jumps (regime shifts)
        base_scenarios = rng.normal(predicted, horizon_vol, size=n_scenarios)
        # 5% chance of ±15% shock (algal bloom, trade disruption, etc.)
        shock_mask = rng.random(n_scenarios) < 0.05
        shocks = rng.choice([-1, 1], size=n_scenarios) * current_spot * 0.15
        scenarios = base_scenarios + shock_mask * shocks

        return {
            "lo95": max(0, lo95),
            "hi95": hi95,
            "lo80": max(0, lo80),
            "hi80": hi80,
            "lo50": max(0, lo50),
            "hi50": hi50,
            "p10": float(np.percentile(scenarios, 10)),
            "p25": float(np.percentile(scenarios, 25)),
            "p50": float(np.percentile(scenarios, 50)),
            "p75": float(np.percentile(scenarios, 75)),
            "p90": float(np.percentile(scenarios, 90)),
        }

    def _classify_signals(
        self,
        change_pct: float,
        national_avg_lice: float,
        lice_trend: str,
        pct_above_threshold: float,
        biomass_vs_normal: float,
        export_volume_trend: float,
        futures_premium_pct: float,
        horizon_weeks: int,
    ) -> dict:
        """Classify individual and combined signals."""
        # Lice signal
        nearest_h = min(LICE_PRICE_ELASTICITY.keys(),
                        key=lambda k: abs(k - horizon_weeks))
        lice_impact = LICE_PRICE_ELASTICITY[nearest_h] * (national_avg_lice / 0.5)
        lice_signal = "bullish" if lice_impact > 1 else "bearish" if lice_impact < -1 else "neutral"

        # Supply signal
        supply_impact = (1 - biomass_vs_normal) * 15 + pct_above_threshold * 10
        supply_signal = "bullish" if supply_impact > 2 else "bearish" if supply_impact < -2 else "neutral"

        # Seasonal signal
        now = dt.datetime.now(dt.UTC)
        _, week, _ = now.isocalendar()
        fw = (week + horizon_weeks - 1) % 52 + 1
        seasonal_pct = (SEASONAL_PATTERN.get(fw, 75) - SEASONAL_PATTERN.get(week, 75)) / SEASONAL_PATTERN.get(week, 75) * 100
        seasonal_signal = "bullish" if seasonal_pct > 3 else "bearish" if seasonal_pct < -3 else "neutral"

        # Export signal
        export_signal = "bullish" if export_volume_trend > 2 else "bearish" if export_volume_trend < -2 else "neutral"

        # Futures signal
        futures_signal = "contango" if futures_premium_pct > 1 else "backwardation" if futures_premium_pct < -1 else "flat"

        # Combined
        signals = [lice_signal, supply_signal, seasonal_signal, export_signal]
        bullish = signals.count("bullish")
        bearish = signals.count("bearish")

        if bullish >= 3:
            combined = "STRONG BULLISH"
        elif bearish >= 3:
            combined = "STRONG BEARISH"
        elif bullish > bearish:
            combined = "LEAN BULLISH"
        elif bearish > bullish:
            combined = "LEAN BEARISH"
        else:
            combined = "NEUTRAL"

        # Direction
        if change_pct > 2:
            direction = "bullish"
        elif change_pct < -2:
            direction = "bearish"
        else:
            direction = "neutral"

        # Confidence (decreases with horizon, increases with signal agreement)
        base_conf = max(0.2, 0.75 - horizon_weeks * 0.025)
        agreement_bonus = max(bullish, bearish) * 0.05
        confidence = min(0.95, base_conf + agreement_bonus)

        # Rationale
        parts = []
        if seasonal_signal != "neutral":
            parts.append(f"Seasonal {seasonal_signal} ({seasonal_pct:+.1f}% move to W{fw})")
        if lice_signal != "neutral":
            parts.append(f"Lice {lice_signal} (avg {national_avg_lice:.2f}, {lice_trend})")
        if supply_signal != "neutral":
            parts.append(f"Supply {supply_signal} (biomass {biomass_vs_normal:.0%} of normal)")
        if export_signal != "neutral":
            parts.append(f"Exports {export_signal} ({export_volume_trend:+.1f}% trend)")
        if futures_signal != "flat":
            parts.append(f"Futures curve in {futures_signal} ({futures_premium_pct:+.1f}%)")

        return {
            "direction": direction,
            "confidence": confidence,
            "lice": lice_signal,
            "supply": supply_signal,
            "seasonal": seasonal_signal,
            "export": export_signal,
            "futures": futures_signal,
            "combined": combined,
            "rationale": ". ".join(parts) if parts else "No strong directional signals.",
        }

    async def retrain(
        self,
        price_history: list[dict],
        feature_history: list[dict],
    ) -> dict:
        """
        Incremental retrain of XGBoost model.

        Called by Self-Improvement Agent nightly.
        Returns training metrics.
        """
        if len(price_history) < 52:
            return {"status": "insufficient_data", "n_samples": len(price_history)}

        try:
            import xgboost as xgb
            from sklearn.model_selection import TimeSeriesSplit

            # Build training matrix
            X, y = [], []
            for i, row in enumerate(feature_history):
                if i >= len(price_history):
                    break
                X.append([
                    row.get("spot", 75),
                    row.get("horizon", 4),
                    row.get("avg_lice", 0.15),
                    row.get("mobile_lice", 0),
                    row.get("sessile_lice", 0),
                    row.get("trend_enc", 0),
                    row.get("pct_above", 0),
                    row.get("biomass_ratio", 1.0),
                    row.get("cleaner_fish_pct", 0),
                    row.get("export_trend", 0),
                    row.get("futures_premium", 0),
                    row.get("week_sin", 0),
                    row.get("week_cos", 0),
                    row.get("fw_sin", 0),
                    row.get("fw_cos", 0),
                    row.get("price_deviation", 0),
                    row.get("lice_supply_interaction", 0),
                    row.get("crisis_time_interaction", 0),
                ])
                y.append(price_history[i].get("actual_price", 75))

            X = np.array(X)
            y = np.array(y)

            # Time-series cross-validation
            tscv = TimeSeriesSplit(n_splits=3)
            residuals = []
            mapes = []

            for train_idx, val_idx in tscv.split(X):
                model = xgb.XGBRegressor(
                    n_estimators=200,
                    max_depth=5,
                    learning_rate=0.05,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    reg_alpha=0.1,
                    reg_lambda=1.0,
                    random_state=42,
                )
                model.fit(X[train_idx], y[train_idx])
                preds = model.predict(X[val_idx])
                # Sign convention: residual = actual − predicted (matches
                # _conformal_bands: band = predicted + quantile(residual))
                fold_residuals = (y[val_idx] - preds).tolist()
                residuals.extend(fold_residuals)
                fold_mape = float(np.mean(np.abs(
                    (y[val_idx] - preds) / np.maximum(y[val_idx], 1)
                )) * 100)
                mapes.append(fold_mape)

            # Final model on all data
            final_model = xgb.XGBRegressor(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
            )
            final_model.fit(X, y)

            # Save
            model_path = MODEL_DIR / "price_xgb.json"
            final_model.save_model(str(model_path))
            self._xgb_model = final_model
            self._model_version = "ensemble_v1_xgb"

            # Save conformal residuals — sign convention is (actual − predicted)
            # everywhere (band = predicted + quantile(residual)); the legacy
            # bare-list writer used the inverted sign and no version gating.
            self._conformal_residuals = residuals
            self._conformal_residuals_by_h = {}
            residuals_path = MODEL_DIR / "conformal_residuals.json"
            residuals_path.write_text(json.dumps({
                "model_version": self._model_version,
                "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                "residual_definition": "actual - predicted (NOK/kg), TimeSeriesSplit CV",
                "residuals_flat": [round(r, 3) for r in residuals],
                "script": "PriceEnsemble.retrain",
            }))

            avg_mape = float(np.mean(mapes))
            self._last_retrain = dt.datetime.now(dt.UTC)

            log.info(
                "price_ml.retrained",
                n_samples=len(X),
                avg_mape=f"{avg_mape:.1f}%",
                n_residuals=len(residuals),
            )

            return {
                "status": "success",
                "n_samples": len(X),
                "avg_mape": round(avg_mape, 2),
                "n_residuals": len(residuals),
                "model_path": str(model_path),
            }

        except ImportError:
            return {"status": "xgboost_not_installed"}
        except Exception as e:
            log.error("price_ml.retrain_error", error=str(e)[:200])
            return {"status": "error", "detail": str(e)[:200]}


# Singleton
price_ensemble = PriceEnsemble()
