"""
Supply-Demand Intelligence Engine (R7 — "Holy Grail" upgrade)
=============================================================
Composes the existing supply and demand engines into one integrated
balance and adds an empirically calibrated 2-20 week price path.

Pipeline
--------
Supply side:
  - Norway: smolt pipeline projected harvest (existing 6-month balance)
  - Norway: biomass outlook (Monte Carlo, deterministic seed 42)
  - Global: Chile / Scotland / Faroe balance from `global_supply`
  - Lice-driven harvest-delay adjustment (heuristic, bounded, labelled)
Demand side:
  - Baseline demand: smolt pipeline demand model (existing)
  - China demand momentum (`china_demand` engine)
  - SSB export volume trend (13w vs prior 13w, real data)

Price path (2-20 weeks ahead):
  core(h)   = seasonal_median(week_t + h) * (1 + gap_rel * 0.5**(h/HALF_LIFE))
              where gap_rel = spot_t / seasonal_median(week_t) - 1
  bands(h)  = core(h) * (1 + q_h)   with q_h = WALK-FORWARD residual quantiles
              (prior-only seasonal per origin; ~80% out-of-sample coverage;
              in-sample quantiles only when history < 2 years)
  tilt(h)   = clamp(global_deficit_tilt + lice_tilt, +/-5%) * min(1, h/4)
              heuristic overlays, explicitly NOT backtested

Honesty contract
----------------
- `backtest` is only ever populated from the real walk-forward artifact
  written by `scripts/backtest_supply_demand.py` (validated on load, same
  contract as price_ml's `_load_backtest_artifact`). Missing artifact ->
  null, never invented numbers.
- Every composed source is recorded in `integration.sources`; any source
  that raised is recorded in `integration.fallbacks` and the response
  provenance is downgraded to `degraded` with a reason.
"""
from __future__ import annotations

import datetime as dt
import inspect
import json
from pathlib import Path

import numpy as np
import structlog

from core.market.data_provenance import DataProvenance
from core.market.global_supply import global_supply_engine
from core.market.ssb_price_client import SSBPriceClient, ssb_price_client

log = structlog.get_logger(__name__)

# ── Forecast method constants (documented, bounded) ───────────────────
FORECAST_MIN_WEEKS = 2
FORECAST_MAX_WEEKS = 20
FORECAST_HORIZONS: tuple[int, ...] = tuple(range(FORECAST_MIN_WEEKS, FORECAST_MAX_WEEKS + 1))

REVERSION_HALF_LIFE_WEEKS = 4.0   # current deviation decays to 50% in 4 weeks
GLOBAL_DEFICIT_TILT_PER_PCT = 0.5  # 1pt global supply deficit -> +0.5% price tilt
TILT_CAP_PCT = 5.0                # hard cap on the combined heuristic tilt
TILT_RAMP_WEEKS = 4.0             # tilt fades in over 4 weeks

LICE_THRESHOLD = 0.5              # adult female lice/avg regulatory action level
LICE_PRESSURE_FULL_SCALE = 1.0    # avg lice at which pressure saturates
LICE_MAX_DELAY_PCT = 2.0          # max % of projected harvest pushed out of window

MIN_HISTORY_WEEKS = 104           # 2 years minimum before a price path is emitted
ARTIFACT_HORIZONS: tuple[int, ...] = (2, 4, 8, 12, 16, 20)

BACKTEST_ARTIFACT = (
    Path(__file__).resolve().parent.parent.parent / "data" / "models" / "supply_demand_backtest.json"
)

METHOD_NOTE = (
    "Core: SSB weekly seasonal median + mean-reversion of the current "
    f"deviation (half-life {REVERSION_HALF_LIFE_WEEKS:g}w), measured from the "
    "latest published SSB week. Bands: walk-forward residual quantiles "
    "p10-p90 (measured out-of-sample coverage ~80%); in-sample quantiles only "
    "when history is too short for a walk-forward fit (needs 104w train + 20w "
    "horizon). Heuristic overlays (not backtested): global supply-deficit tilt "
    f"{GLOBAL_DEFICIT_TILT_PER_PCT:g}%/deficit-point (cap {TILT_CAP_PCT:g}%) and "
    f"lice-driven harvest-delay tilt (cap {LICE_MAX_DELAY_PCT:g}%), ramped in "
    f"over {TILT_RAMP_WEEKS:g} weeks. The legacy smolt price_pressure signal "
    "is deliberately not used as a tilt (its balance is pipeline coverage, "
    "structurally ~-80%)."
)

COMPONENTS_BACKTESTED = ["seasonal + reversion core (combined)"]
COMPONENTS_HEURISTIC = ["global supply-deficit tilt", "lice-delay tilt"]

# ── Pure helpers (shared by the engine, the backtest script and tests) ──

def _week_to_date(year: int, week: int) -> dt.date | None:
    """ISO (year, week) -> Monday date; None when the week doesn't exist."""
    try:
        return dt.date.fromisocalendar(year, week, 1)
    except ValueError:
        return None


def _decay(horizon_weeks: int) -> float:
    return float(0.5 ** (horizon_weeks / REVERSION_HALF_LIFE_WEEKS))


def _core_forecast(seasonal: dict[int, float], target_week: int, gap_rel: float, h: int) -> float:
    """Seasonal baseline + reversion of the origin's relative deviation."""
    return float(seasonal[target_week]) * (1.0 + gap_rel * _decay(h))


def _target_week(year: int, week: int, h: int) -> tuple[int, int] | None:
    d = _week_to_date(year, week)
    if d is None:
        return None
    iso = (d + dt.timedelta(weeks=h)).isocalendar()
    return iso[0], iso[1]


def residual_quantiles_by_horizon(
    prices: list, seasonal: dict[int, float], horizons: tuple[int, ...]
) -> dict[int, dict[str, float]]:
    """Empirical quantiles of `actual / core - 1` per horizon (real history).

    For every week in history that has a target week `h` ahead, computes the
    same core formula the live forecast uses and collects the relative error.
    Returns {h: {"p10", "p25", "p75", "p90", "n"}}.
    """
    by_week: dict[tuple[int, int], float] = {
        (p.year, p.week): p.price_nok_kg for p in prices if 1 <= p.week <= 52 and p.price_nok_kg > 0
    }
    out: dict[int, dict[str, float]] = {}
    for h in horizons:
        residuals: list[float] = []
        for p in prices:
            if p.week not in seasonal or seasonal[p.week] <= 0 or p.price_nok_kg <= 0:
                continue
            tw = _target_week(p.year, p.week, h)
            if tw is None or tw not in by_week:
                continue
            gap_rel = p.price_nok_kg / seasonal[p.week] - 1.0
            core = _core_forecast(seasonal, tw[1], gap_rel, h)
            if core > 0:
                residuals.append(by_week[tw] / core - 1.0)
        if len(residuals) >= 20:
            arr = np.array(residuals)
            out[h] = {
                "p10": round(float(np.quantile(arr, 0.10)), 4),
                "p25": round(float(np.quantile(arr, 0.25)), 4),
                "p75": round(float(np.quantile(arr, 0.75)), 4),
                "p90": round(float(np.quantile(arr, 0.90)), 4),
                "n": len(residuals),
            }
    return out


def walk_forward_residual_quantiles(
    prices: list,
    horizons: tuple[int, ...] = FORECAST_HORIZONS,
    min_train_weeks: int = MIN_HISTORY_WEEKS,
) -> dict[int, dict[str, float]]:
    """Walk-forward residual quantiles — the band calibration the engine uses.

    For every origin (>= min_train_weeks in), the seasonal pattern is computed
    strictly from PRIOR data, then residuals `actual / core - 1` are collected
    per horizon. Measured out-of-sample coverage of the p10-p90 band: ~80%
    (see the walk-forward backtest artifact). Returns {} when history is
    shorter than min_train_weeks + horizon.
    """
    ordered = sorted(
        (p for p in prices if p.price_nok_kg > 0 and 1 <= p.week <= 52),
        key=lambda p: (p.year, p.week),
    )
    if len(ordered) < min_train_weeks + max(horizons):
        return {}

    by_week = {(p.year, p.week): p.price_nok_kg for p in ordered}
    seasonal_cache: dict[int, dict[int, float]] = {}
    residuals: dict[int, list[float]] = {h: [] for h in horizons}

    for i in range(min_train_weeks, len(ordered)):
        origin = ordered[i]
        seasonal = seasonal_cache.get(i)
        if seasonal is None:
            seasonal = SSBPriceClient.compute_seasonal_pattern(ordered[:i])
            seasonal_cache[i] = seasonal
        if origin.week not in seasonal or seasonal[origin.week] <= 0:
            continue
        gap_rel = origin.price_nok_kg / seasonal[origin.week] - 1.0
        for h in horizons:
            tw = _target_week(origin.year, origin.week, h)
            if tw is None or tw not in by_week:
                continue
            wk_key = tw[1] if tw[1] in seasonal else min(tw[1], 52)
            core = _core_forecast(seasonal, wk_key, gap_rel, h)
            if core > 0:
                residuals[h].append(by_week[tw] / core - 1.0)

    out: dict[int, dict[str, float]] = {}
    for h, vals in residuals.items():
        if len(vals) < 20:
            continue
        arr = np.array(vals)
        out[h] = {
            "p10": round(float(np.quantile(arr, 0.10)), 4),
            "p25": round(float(np.quantile(arr, 0.25)), 4),
            "p75": round(float(np.quantile(arr, 0.75)), 4),
            "p90": round(float(np.quantile(arr, 0.90)), 4),
            "n": len(vals),
        }
    return out


def run_walk_forward(
    prices: list,
    min_train_weeks: int = MIN_HISTORY_WEEKS,
    report_horizons: tuple[int, ...] = ARTIFACT_HORIZONS,
) -> dict:
    """Walk-forward backtest of the core (seasonal + reversion) method.

    Strictly no lookahead: the seasonal pattern for every origin is computed
    from data strictly before that origin. Returns MAPE per reported horizon
    plus in-sample band coverage (labelled as such) and the residual
    quantiles a live forecast uses for its bands.
    """
    ordered = sorted(
        (p for p in prices if p.price_nok_kg > 0 and 1 <= p.week <= 52),
        key=lambda p: (p.year, p.week),
    )
    if len(ordered) < min_train_weeks + max(report_horizons):
        raise ValueError(
            f"insufficient history: {len(ordered)} weeks < "
            f"{min_train_weeks + max(report_horizons)} required"
        )

    pairs: dict[int, list[tuple[float, float]]] = {h: [] for h in report_horizons}
    seasonal_cache: dict[int, dict[int, float]] = {}
    by_week = {(p.year, p.week): p.price_nok_kg for p in ordered}

    for i in range(min_train_weeks, len(ordered)):
        origin = ordered[i]
        seasonal = seasonal_cache.get(i)
        if seasonal is None:
            seasonal = SSBPriceClient.compute_seasonal_pattern(ordered[:i])
            seasonal_cache[i] = seasonal
        if origin.week not in seasonal or seasonal[origin.week] <= 0:
            continue
        gap_rel = origin.price_nok_kg / seasonal[origin.week] - 1.0
        for h in report_horizons:
            tw = _target_week(origin.year, origin.week, h)
            if tw is None or tw not in by_week:
                continue
            wk_key = tw[1] if tw[1] in seasonal else min(tw[1], 52)
            core = _core_forecast(seasonal, wk_key, gap_rel, h)
            actual = by_week[tw]
            if core > 0 and actual > 0:
                pairs[h].append((core, actual))

    mape: dict[str, float] = {}
    n_by_h: dict[str, int] = {}
    for h in report_horizons:
        if pairs[h]:
            errs = [abs(core - actual) / actual * 100.0 for core, actual in pairs[h]]
            mape[str(h)] = round(float(np.mean(errs)), 2)
            n_by_h[str(h)] = len(pairs[h])

    # Full-history (in-sample) quantiles — kept for coverage comparison
    # against the walk-forward bands the live engine actually ships.
    full_seasonal = SSBPriceClient.compute_seasonal_pattern(ordered)
    quantiles = residual_quantiles_by_horizon(ordered, full_seasonal, report_horizons)

    # In-sample coverage of the 80% band on the walk-forward targets.
    coverage: dict[str, float] = {}
    for h in report_horizons:
        q = quantiles.get(h)
        if not q or not pairs[h]:
            continue
        inside = sum(
            1 for core, actual in pairs[h] if core * (1 + q["p10"]) <= actual <= core * (1 + q["p90"])
        )
        coverage[str(h)] = round(inside / len(pairs[h]) * 100.0, 1)

    # Walk-forward residuals -> out-of-sample band quantiles + their coverage
    # (this is the band calibration the live engine ships; the in-sample
    # variant above is only a comparison baseline).
    wf_q = walk_forward_residual_quantiles(ordered, report_horizons, min_train_weeks)
    wf_quantiles: dict[str, dict[str, float]] = {str(h): q for h, q in wf_q.items()}
    wf_coverage: dict[str, float] = {}
    for h in report_horizons:
        q = wf_q.get(h)
        if not q or not pairs[h]:
            continue
        inside = sum(
            1
            for core, actual in pairs[h]
            if core * (1 + q["p10"]) <= actual <= core * (1 + q["p90"])
        )
        wf_coverage[str(h)] = round(inside / len(pairs[h]) * 100.0, 1)

    return {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "method": "walk-forward (no-lookahead seasonal + reversion core)",
        "source": "SSB table 03024 weekly salmon export prices",
        "min_train_weeks": min_train_weeks,
        "n_origins": len(ordered) - min_train_weeks,
        "history_weeks": len(ordered),
        "horizon_weeks": max(report_horizons),
        "mape": mape,
        "mape_n_by_horizon": n_by_h,
        "coverage_80_band_in_sample": coverage,
        "wf_residual_quantiles": wf_quantiles,
        "coverage_80_band_walk_forward": wf_coverage,
        "residual_quantiles": {str(h): q for h, q in quantiles.items()},
        "components_backtested": COMPONENTS_BACKTESTED,
        "components_not_backtested": COMPONENTS_HEURISTIC,
        "method_note": METHOD_NOTE,
    }



# ── Backtest artifact loader (same contract as price_ml) ──────────────

def load_backtest_artifact() -> dict | None:
    """Read + validate the walk-forward artifact; None when absent/invalid."""
    try:
        if not BACKTEST_ARTIFACT.exists():
            return None
        data = json.loads(BACKTEST_ARTIFACT.read_text())
    except Exception as e:
        log.warning("supply_demand.backtest_artifact_unreadable", error=str(e)[:100])
        return None

    if not isinstance(data, dict):
        return None
    mape_map = data.get("mape")
    if not isinstance(mape_map, dict) or not mape_map:
        log.warning("supply_demand.backtest_artifact_invalid", reason="mape missing or empty")
        return None
    try:
        validated = {int(k): float(v) for k, v in mape_map.items()}
    except (TypeError, ValueError):
        log.warning("supply_demand.backtest_artifact_invalid", reason="non-numeric mape entries")
        return None
    data["mape"] = {str(k): v for k, v in validated.items()}
    return data


class SupplyDemandEngine:
    """Integrated supply-demand balance + 2-20 week price path.

    Composes existing singletons (smolt model, biomass predictor, global
    supply, China demand, SSB price client + lice DB). Every composed part
    is recorded; failures degrade the response instead of fabricating data.
    """

    def __init__(self) -> None:
        self._sources_all = [
            "smolt pipeline (Norway supply + baseline demand)",
            "biomass outlook (Monte Carlo)",
            "global supply (Chile/Scotland/Faroe)",
            "lice pressure (Fiskeridirektoratet weekly)",
            "china demand momentum (SSB exports)",
            "SSB 03024 price history",
        ]

    async def compute(self) -> dict:
        """Build the integrated balance + forecast payload (API-ready dict)."""
        fallbacks: list[str] = []
        sources_used: list[str] = []

        # 1. Norway pipeline balance (deterministic local model)
        legacy = await self._safe(self._norway_pipeline, "smolt pipeline", fallbacks)
        legacy = legacy or {}
        if legacy:
            sources_used.append(self._sources_all[0])

        # 2. Biomass context
        biomass = await self._safe(self._biomass_context, "biomass outlook", fallbacks)
        if biomass is not None:
            sources_used.append(self._sources_all[1])

        # 3. Global supply context
        global_ctx = await self._safe(self._global_context, "global supply", fallbacks)
        if global_ctx is not None:
            sources_used.append(self._sources_all[2])

        # 4. Lice pressure -> harvest-delay adjustment
        lice = await self._safe(self._lice_pressure, "lice pressure", fallbacks)
        if lice is not None:
            sources_used.append(self._sources_all[3])

        # 5. Price history (needed by both forecast and export trend)
        prices = await self._safe(self._price_history, "SSB 03024 history", fallbacks)
        if prices is not None:
            sources_used.append(self._sources_all[5])

        # 6. Demand context (China momentum + export volume trend)
        demand = await self._safe(
            lambda: self._demand_context(prices), "china demand", fallbacks
        )
        if demand is not None:
            sources_used.append(self._sources_all[4])
            if demand.get("china_live_data") is False:
                # The china engine's designed fallback is curated industry
                # estimates — disclosed, never presented as live exports.
                fallbacks.append("china demand: live SSB exports unavailable (estimates used)")

        supply = float(legacy.get("total_supply_tonnes") or 0.0)
        demand_tonnes = float(legacy.get("total_demand_tonnes") or 0.0)

        delay_pct = float((lice or {}).get("delay_adjustment_pct") or 0.0)
        deficit_pct = float((global_ctx or {}).get("supply_deficit_pct") or 0.0)
        # NOTE: the legacy smolt balance_pct is structurally ~-82% (pipeline
        # supply vs the demand model's aspiration) and is deliberately NOT
        # used as a price tilt — only real cross-country tightness is.
        deficit_tilt = max(-TILT_CAP_PCT, min(TILT_CAP_PCT, deficit_pct * GLOBAL_DEFICIT_TILT_PER_PCT))
        lice_tilt = max(-TILT_CAP_PCT, min(TILT_CAP_PCT, -delay_pct))
        tilt_pct = max(-TILT_CAP_PCT, min(TILT_CAP_PCT, deficit_tilt + lice_tilt))

        forecast = None
        if prices:
            forecast = self._price_forecast(
                prices,
                global_deficit_tilt_pct=deficit_tilt,
                lice_tilt_pct=lice_tilt,
                tilt_pct=tilt_pct,
            )
            if forecast is None:
                fallbacks.append("price path (insufficient SSB history)")


        payload = {
            "balance_label": self._balance_label(str(legacy.get("signal") or "")),
            "integration": {
                "engine": "supply_demand_engine",
                "contract": "additive-v1",
                "composed_at": dt.datetime.now(dt.UTC).isoformat(),
                "sources": sources_used,
                "fallbacks": fallbacks,
            },
            "supply_breakdown": {
                "norway_pipeline_tonnes": supply,
                "pipeline_adjusted_tonnes": round(supply * (1 + delay_pct / 100.0), 0),
                "lice_delay_adjustment_pct": delay_pct,
                "lice_pressure": (lice or {}).get("lice_pressure"),
                "lice_avg_adult_female": (lice or {}).get("avg_adult_female_lice"),
                "biomass_current_tonnes": (biomass or {}).get("current_biomass_tonnes"),
                "biomass_utilization_pct": (biomass or {}).get("utilization_pct"),
                "biomass_national_mab": (biomass or {}).get("national_mab"),
                "global_balance": (global_ctx or {}).get("balance"),
                "global_supply_deficit_pct": (global_ctx or {}).get("supply_deficit_pct"),
                "norway_premium_pct": (global_ctx or {}).get("norway_premium_pct"),
            },
            "demand_breakdown": {
                "pipeline_demand_tonnes": demand_tonnes,
                "china_signal_score": (demand or {}).get("china_signal_score"),
                "china_signal_label": (demand or {}).get("china_signal_label"),
                "china_yoy_growth_pct": (demand or {}).get("china_yoy_growth_pct"),
                "export_volume_trend_pct": (demand or {}).get("export_volume_trend_pct"),
            },
            "price_forecast": forecast,
            "data_provenance": self._provenance(fallbacks).to_dict(),
        }
        return payload

    # ── Composition helpers ───────────────────────────────────────────

    @staticmethod
    async def _safe(fn, name: str, fallbacks: list[str]):
        """Run a composition step (sync or async); record + absorb failures."""
        try:
            result = fn()
            if inspect.isawaitable(result):
                return await result
            return result
        except Exception as e:
            reason = str(e)[:80]
            log.warning("supply_demand.source_failed", source=name, error=reason)
            fallbacks.append(f"{name}: {reason}")
            return None

    @staticmethod
    def _balance_label(signal: str) -> str:
        return {
            "oversupply": "Oversupply",
            "undersupply": "Undersupply",
            "balanced": "Balanced",
        }.get(signal, signal.title() if signal else "Unknown")

    def _provenance(self, fallbacks: list[str]) -> DataProvenance:
        source = "SSB 03024 + smolt pipeline + global supply + lice DB + china demand"
        if not fallbacks:
            return DataProvenance.live(source, confidence=0.75)
        return DataProvenance.degraded(
            source,
            reason="fallbacks: " + "; ".join(fallbacks),
            confidence=max(0.35, 0.75 - 0.15 * len(fallbacks)),
        )

    @staticmethod
    def _norway_pipeline() -> dict:
        from core.valuechain.smolt_model import smolt_model

        return smolt_model.get_demand_balance()

    @staticmethod
    async def _biomass_context() -> dict:
        from core.market.biomass_predictor import biomass_predictor

        # Route-default params (20w / 1000 scenarios) keep the predictor's
        # single-slot cache consistent with /api/biomass/outlook.
        await biomass_predictor.compute_outlook(20, 1000, "current")
        d = biomass_predictor.get_outlook_dict()
        if not d:
            raise RuntimeError("biomass outlook empty")
        return {
            "current_biomass_tonnes": d.get("current_biomass_tonnes"),
            "utilization_pct": d.get("utilization_pct"),
            "national_mab": d.get("national_mab"),
        }

    @staticmethod
    async def _global_context() -> dict:
        balance = await global_supply_engine.compute()
        if not balance.global_salmon_usd_kg and not balance.norway_spot_nok_kg:
            # The engine's internal sub-fetches all failed (its defaults are
            # 0.0) — surface that instead of presenting defaults as live.
            raise RuntimeError("global supply has no live market anchors")
        return {
            "balance": balance.balance,
            "supply_deficit_pct": balance.supply_deficit_pct,
            "norway_premium_pct": balance.norway_premium_pct,
            "effective_production_tonnes": balance.effective_production_tonnes,
        }


    @staticmethod
    async def _lice_pressure() -> dict:
        from sqlalchemy import select

        from core.async_db import get_async_session
        from core.models import LiceRecord, Locality

        async with get_async_session() as s:
            latest = (await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )).first()
            if not latest:
                raise RuntimeError("no lice records")
            year, week = latest
            rows = (await s.execute(
                select(LiceRecord.avg_adult_female_lice)
                .join(Locality, LiceRecord.locality_no == Locality.locality_no)
                .where(LiceRecord.year == year, LiceRecord.week == week)
                .where(LiceRecord.avg_adult_female_lice.isnot(None))
            )).scalars().all()

        values = [float(v) for v in rows if v is not None]
        if not values:
            raise RuntimeError("no lice values in latest week")

        avg = sum(values) / len(values)
        pct_above = sum(1 for v in values if v > LICE_THRESHOLD) / len(values)
        pressure = min(1.0, avg / LICE_PRESSURE_FULL_SCALE)
        # Clearer pressure signal: saturation OR a high share of sites over
        # the regulatory threshold, whichever is stronger.
        pressure = max(pressure, min(1.0, pct_above * 2.0))
        return {
            "year": year,
            "week": week,
            "avg_adult_female_lice": round(avg, 3),
            "pct_sites_above_threshold": round(pct_above * 100, 1),
            "lice_pressure": round(pressure, 3),
            "delay_adjustment_pct": round(-pressure * LICE_MAX_DELAY_PCT, 3),
        }

    @staticmethod
    async def _price_history() -> list:
        bulk = await ssb_price_client.fetch_bulk_history(2020)
        if not bulk.prices:
            raise RuntimeError("empty SSB bulk history")
        return bulk.prices

    @staticmethod
    async def _demand_context(prices: list | None) -> dict:
        from core.market.china_demand import china_demand_engine

        out: dict = {}
        signals = await china_demand_engine.get_demand_signals()
        out["china_signal_score"] = signals.get("signal_score")
        out["china_signal_label"] = signals.get("signal_label")
        out["china_yoy_growth_pct"] = signals.get("yoy_growth_pct")
        snap = await china_demand_engine.get_snapshot()
        norway = (snap or {}).get("norway_exports_to_china") or {}
        out["china_live_data"] = bool(norway.get("tonnes_12m"))
        if prices:
            out["export_volume_trend_pct"] = SSBPriceClient.compute_export_volume_trend(prices)
        return out

    @staticmethod
    def _price_forecast(
        prices: list,
        *,
        global_deficit_tilt_pct: float,
        lice_tilt_pct: float,
        tilt_pct: float,
    ) -> dict | None:
        """Empirically calibrated 2-20 week price path with residual bands."""
        ordered = sorted(
            (p for p in prices if p.price_nok_kg > 0 and 1 <= p.week <= 52),
            key=lambda p: (p.year, p.week),
        )
        if len(ordered) < MIN_HISTORY_WEEKS:
            return None

        seasonal = SSBPriceClient.compute_seasonal_pattern(ordered)
        spot_week = ordered[-1]
        spot = float(spot_week.price_nok_kg)
        if seasonal.get(spot_week.week, 0) <= 0:
            return None
        gap_rel = spot / seasonal[spot_week.week] - 1.0

        # Horizons are measured from the latest PUBLISHED week — the same
        # reference the walk-forward calibration uses — so "MAPE 2w" and the
        # h-indexed bands describe exactly these horizons even though SSB
        # publishes with a 1-3 week lag (disclosed via spot_lag_weeks).
        today = dt.date.today()
        t_iso = today.isocalendar()
        spot_monday = _week_to_date(spot_week.year, spot_week.week)
        lag_weeks = max(0, (today - spot_monday).days // 7) if spot_monday else 0

        quantiles = walk_forward_residual_quantiles(ordered, FORECAST_HORIZONS)
        bands_source = "walk_forward_residuals"
        if not quantiles:
            quantiles = residual_quantiles_by_horizon(ordered, seasonal, FORECAST_HORIZONS)
            bands_source = "in_sample_history"
        if not quantiles:
            return None

        weekly: list[dict] = []
        for h in FORECAST_HORIZONS:
            tw = _target_week(spot_week.year, spot_week.week, h)
            if tw is None:
                continue
            target_year, target_week = tw
            # ISO years can have 53 weeks; the SSB seasonal pattern covers
            # weeks 1-52, so week 53 uses the week-52 value.
            wk_key = target_week if target_week in seasonal else min(target_week, 52)
            core = _core_forecast(seasonal, wk_key, gap_rel, h)
            ramp = min(1.0, h / TILT_RAMP_WEEKS)
            tilt_factor = 1.0 + (tilt_pct / 100.0) * ramp
            q = quantiles.get(h) or {}
            point = {
                "horizon_weeks": h,
                "year": target_year,
                "iso_week": target_week,
                "mid_nok_kg": round(core * tilt_factor, 1),
            }
            for band, qkey in (("p10", "p10"), ("p25", "p25"), ("p75", "p75"), ("p90", "p90")):
                if qkey in q:
                    point[band] = round(core * (1.0 + q[qkey]) * tilt_factor, 1)
            weekly.append(point)

        if not weekly:
            return None
        return {
            "horizon_weeks": max(FORECAST_HORIZONS),
            "generated_week": f"{t_iso[0]}W{t_iso[1]:02d}",
            "horizon_reference": "latest published SSB week (spot_week)",
            "spot_nok_kg": round(spot, 1),
            "spot_week": f"{spot_week.year}W{spot_week.week:02d}",
            "spot_lag_weeks": lag_weeks,
            "seasonal_median_nok_kg": round(float(seasonal[spot_week.week]), 1),
            "gap_vs_seasonal_pct": round(gap_rel * 100.0, 1),
            "global_deficit_tilt_pct": round(global_deficit_tilt_pct, 2),
            "lice_tilt_pct": round(lice_tilt_pct, 2),
            "combined_tilt_pct": round(tilt_pct, 2),
            "method": METHOD_NOTE,
            "bands_source": bands_source,
            "components_backtested": COMPONENTS_BACKTESTED,
            "components_heuristic": COMPONENTS_HEURISTIC,
            "history_weeks_used": len(ordered),
            "weekly": weekly,
            "backtest": load_backtest_artifact(),
        }


# Singleton
supply_demand_engine = SupplyDemandEngine()

