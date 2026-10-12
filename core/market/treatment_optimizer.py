"""
Treatment Cost Optimizer
=========================
Finds optimal treatment timing, compares ROI across 5 methods, coordinates
PA-wide treatment schedules, and projects cost-benefit outcomes.

ALL lice counts, temperatures, and farm data come from LIVE sources:
  - LiceRecord table (BarentsWatch via DB)
  - MET.no via met_ocean (sea surface temperature forecasts)
  - farm_graph (neighbor topology, PA membership)

Only structural constants are static: treatment profiles (from farmer_advisory),
regulatory thresholds, and treatment efficacy parameters.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass

import numpy as np
import structlog

from sqlalchemy import select, desc

from core.models import LiceRecord, Locality
# Lazy-import farmer_advisory to avoid circular/broken import chains.
# We only need the static constants (TREATMENTS, thresholds).
def _get_advisory_constants():
    from core.valuechain.farmer_advisory import TREATMENTS, REGULATORY_LIMIT, TREATMENT_TRIGGER
    return TREATMENTS, REGULATORY_LIMIT, TREATMENT_TRIGGER


# ── Use shared treatment constants (single source of truth) ──────────
# BUG FIX (Session 22): Previously had LOCAL efficacy values that diverged
# from treatment_constants.py (e.g. mechanical 87.5% here vs 83% in constants).
# Now uses the shared TreatmentProfile dataclass to ensure consistency.
from core.market.treatment_constants import (
    TREATMENT_PROFILES as _SHARED_PROFILES,
    REGULATORY_LIMIT,
    TREATMENT_TRIGGER,
)
from dataclasses import dataclass as _dc  # already imported above, alias to avoid shadow

@_dc
class _TreatmentOption:
    treatment_type: str
    efficacy_pct: float
    mortality_risk_pct: float
    cost_per_fish_nok: float
    recovery_weeks: int
    environmental_impact: str
    suitable_temp_range: tuple
    notes: str = ""

# Build TREATMENTS from shared constants — no local overrides
TREATMENTS = {
    key: _TreatmentOption(
        treatment_type=p.label,
        efficacy_pct=p.efficacy_pct,
        mortality_risk_pct=p.mortality_risk_pct,
        cost_per_fish_nok=p.cost_per_fish_nok,
        recovery_weeks=p.recovery_weeks,
        environmental_impact=p.environmental_impact,
        suitable_temp_range=p.suitable_temp_range,
        notes=p.notes,
    )
    for key, p in _SHARED_PROFILES.items()
    if key in ("mechanical", "thermal", "medicinal_bath", "medicinal_feed", "biological")
}
# Map "biological" key to "cleaner_fish" for backward compatibility
if "biological" in TREATMENTS:
    TREATMENTS["cleaner_fish"] = TREATMENTS.pop("biological")

log = structlog.get_logger(__name__)

# ── Structural constants (not dynamic data) ──────────────────────────
FISH_PER_CAGE = 200_000  # standard Norwegian cage stocking
LICE_GROWTH_RATE_PER_DEGREE_WEEK = 0.03  # lice/degree-week empirical
WEEKS_LOOKAHEAD = 8  # optimization horizon


@dataclass
class TimingRecommendation:
    optimal_week: int
    optimal_year: int
    recommended_treatment: str
    reasoning: str
    projected_lice_at_treatment: float
    projected_cost_nok: float
    weeks_until_limit: int
    urgency: str  # immediate / high / medium / low


@dataclass
class TreatmentComparison:
    treatment_key: str
    treatment_name: str
    efficacy_pct: float
    mortality_pct: float
    cost_per_fish_nok: float
    recovery_weeks: int
    total_cost_nok: float
    post_treatment_lice: float
    roi_score: float  # benefit per NOK spent
    suitable: bool
    unsuitable_reason: str = ""


@dataclass
class NetworkScheduleEntry:
    locality_no: int
    farm_name: str
    current_lice: float
    recommended_week: int
    recommended_treatment: str
    priority: int  # 1=highest
    reason: str


class TreatmentOptimizer:
    """Optimizes treatment cost, timing, and coordination using LIVE data."""

    # ── Public API ───────────────────────────────────────────────────

    async def optimize_timing(
        self,
        locality_no: int,
        budget_nok: float | None = None,
    ) -> dict:
        """
        Find optimal treatment week based on LIVE lice trajectory from DB,
        LIVE SST from met_ocean, and treatment cost profiles.
        """
        # Fetch LIVE data from DB
        lice_history = await self._get_lice_history(locality_no, weeks=12)
        if not lice_history:
            return {"error": f"No lice data for locality {locality_no}"}

        current = lice_history[-1]
        current_lice = current["avg_adult_female_lice"] or 0.0
        current_temp = current["sea_temp_c"] or 8.0
        has_cleaner = current.get("has_cleaner_fish", False)
        current_week = current["week"]
        current_year = current["year"]

        # Project lice trajectory using recent trend + temperature
        trajectory = self._project_lice_trajectory(
            lice_history, current_temp, WEEKS_LOOKAHEAD
        )

        # Find week where lice would exceed regulatory limit
        weeks_until_limit = WEEKS_LOOKAHEAD
        for i, projected in enumerate(trajectory):
            if projected >= REGULATORY_LIMIT:
                weeks_until_limit = i
                break

        # Determine urgency
        if current_lice >= REGULATORY_LIMIT:
            urgency = "immediate"
            optimal_offset = 0
        elif weeks_until_limit <= 2:
            urgency = "high"
            optimal_offset = 0
        elif weeks_until_limit <= 4:
            urgency = "medium"
            optimal_offset = max(0, weeks_until_limit - 2)
        else:
            urgency = "low"
            optimal_offset = max(0, weeks_until_limit - 3)

        optimal_week = (current_week + optimal_offset - 1) % 52 + 1
        optimal_year = current_year if current_week + optimal_offset <= 52 else current_year + 1
        projected_lice_at_treatment = trajectory[min(optimal_offset, len(trajectory) - 1)]

        # Select best treatment considering temp and budget
        best_key, best_option = self._select_best_treatment(
            current_temp, current_lice, has_cleaner, budget_nok
        )

        total_cost = best_option.cost_per_fish_nok * FISH_PER_CAGE

        # Build reasoning
        trend_desc = self._describe_trend(lice_history)
        reasoning_parts = [
            f"Current lice level: {current_lice:.3f} adult female/fish.",
            f"Trend: {trend_desc}.",
            f"SST: {current_temp:.1f} C (from DB).",
            f"Projected to reach regulatory limit ({REGULATORY_LIMIT}) in ~{weeks_until_limit} weeks.",
            f"Recommended: {best_option.treatment_type} (efficacy {best_option.efficacy_pct}%, mortality {best_option.mortality_risk_pct}%).",
        ]
        if budget_nok and total_cost > budget_nok:
            reasoning_parts.append(
                f"Warning: estimated cost NOK {total_cost:,.0f} exceeds budget NOK {budget_nok:,.0f}."
            )

        rec = TimingRecommendation(
            optimal_week=optimal_week,
            optimal_year=optimal_year,
            recommended_treatment=best_option.treatment_type,
            reasoning=" ".join(reasoning_parts),
            projected_lice_at_treatment=round(projected_lice_at_treatment, 4),
            projected_cost_nok=round(total_cost, 0),
            weeks_until_limit=weeks_until_limit,
            urgency=urgency,
        )

        return {
            "locality_no": locality_no,
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "current_lice": round(current_lice, 4),
            "current_sst_c": round(current_temp, 1),
            "has_cleaner_fish": has_cleaner,
            "lice_trajectory": [round(v, 4) for v in trajectory],
            "recommendation": {
                "optimal_week": rec.optimal_week,
                "optimal_year": rec.optimal_year,
                "treatment": rec.recommended_treatment,
                "urgency": rec.urgency,
                "projected_lice_at_treatment": rec.projected_lice_at_treatment,
                "projected_cost_nok": rec.projected_cost_nok,
                "weeks_until_limit": rec.weeks_until_limit,
                "reasoning": rec.reasoning,
            },
            "budget_nok": budget_nok,
            "within_budget": budget_nok is None or total_cost <= budget_nok,
        }

    async def compare_treatments(self, locality_no: int) -> dict:
        """ROI comparison across 5 treatment methods using LIVE farm data."""
        lice_history = await self._get_lice_history(locality_no, weeks=8)
        if not lice_history:
            return {"error": f"No lice data for locality {locality_no}"}

        current = lice_history[-1]
        current_lice = current["avg_adult_female_lice"] or 0.0
        current_temp = current["sea_temp_c"] or 8.0
        has_cleaner = current.get("has_cleaner_fish", False)

        comparisons = []
        for key, t in TREATMENTS.items():
            suitable = True
            reason = ""

            # Temperature suitability
            if not (t.suitable_temp_range[0] <= current_temp <= t.suitable_temp_range[1]):
                suitable = False
                reason = f"SST {current_temp:.1f}C outside range {t.suitable_temp_range[0]}-{t.suitable_temp_range[1]}C"

            # Already has cleaner fish
            if key == "cleaner_fish" and has_cleaner:
                suitable = False
                reason = "Cleaner fish already deployed at this farm"

            total_cost = t.cost_per_fish_nok * FISH_PER_CAGE
            post_lice = current_lice * (1 - t.efficacy_pct / 100.0)

            # ROI: lice reduction per NOK 1000 spent
            lice_reduction = current_lice - post_lice
            roi = (lice_reduction / (total_cost / 1000.0)) if total_cost > 0 else 0.0

            comparisons.append(TreatmentComparison(
                treatment_key=key,
                treatment_name=t.treatment_type,
                efficacy_pct=t.efficacy_pct,
                mortality_pct=t.mortality_risk_pct,
                cost_per_fish_nok=t.cost_per_fish_nok,
                recovery_weeks=t.recovery_weeks,
                total_cost_nok=round(total_cost, 0),
                post_treatment_lice=round(post_lice, 4),
                roi_score=round(roi, 4),
                suitable=suitable,
                unsuitable_reason=reason,
            ))

        # Sort by ROI (suitable first)
        comparisons.sort(key=lambda c: (-int(c.suitable), -c.roi_score))

        return {
            "locality_no": locality_no,
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "current_lice": round(current_lice, 4),
            "current_sst_c": round(current_temp, 1),
            "has_cleaner_fish": has_cleaner,
            "treatments": [
                {
                    "key": c.treatment_key,
                    "name": c.treatment_name,
                    "efficacy_pct": c.efficacy_pct,
                    "mortality_pct": c.mortality_pct,
                    "cost_per_fish_nok": c.cost_per_fish_nok,
                    "recovery_weeks": c.recovery_weeks,
                    "total_cost_nok": c.total_cost_nok,
                    "post_treatment_lice": c.post_treatment_lice,
                    "roi_score": c.roi_score,
                    "suitable": c.suitable,
                    "unsuitable_reason": c.unsuitable_reason,
                }
                for c in comparisons
            ],
        }

    async def network_schedule(self, pa: int) -> dict:
        """Coordinate treatment across neighboring farms using LIVE farm_graph data."""
        from core.market.farm_graph import farm_graph

        # Get all farms in this PA from LIVE farm_graph
        await farm_graph.get_graph_summary()
        clusters = await farm_graph.get_clusters()

        # Get all farms for this PA from DB
        pa_farms = await self._get_pa_farms(pa)
        if not pa_farms:
            return {"error": f"No farms found in PA {pa}", "production_area": pa}

        # Batch-fetch lice history for ALL farms in this PA (fixes N+1 query)
        pa_lice_batch = await self._get_pa_lice_history_batch(pa, weeks=4)

        schedule_entries: list[dict] = []
        for farm in pa_farms:
            loc_no = farm["locality_no"]
            lice_history = pa_lice_batch.get(loc_no, [])
            if not lice_history:
                continue

            latest = lice_history[-1]
            current_lice = latest.get("avg_adult_female_lice") or 0.0
            current_temp = latest.get("sea_temp_c") or 8.0

            # Determine priority based on lice level
            if current_lice >= REGULATORY_LIMIT:
                priority = 1
                reason = f"Above regulatory limit ({current_lice:.3f} >= {REGULATORY_LIMIT})"
                rec_week = latest["week"]
            elif current_lice >= TREATMENT_TRIGGER:
                priority = 2
                reason = f"Above treatment trigger ({current_lice:.3f} >= {TREATMENT_TRIGGER})"
                rec_week = latest["week"] + 1
            elif current_lice >= 0.1:
                priority = 3
                reason = f"Elevated lice ({current_lice:.3f}), monitor closely"
                rec_week = latest["week"] + 3
            else:
                priority = 4
                reason = f"Low lice ({current_lice:.3f}), no treatment needed"
                rec_week = 0  # no treatment

            # Select treatment based on live conditions
            best_key, best_option = self._select_best_treatment(
                current_temp, current_lice, latest.get("has_cleaner_fish", False)
            )

            # Normalize week
            rec_week = ((rec_week - 1) % 52) + 1 if rec_week > 0 else 0

            schedule_entries.append({
                "locality_no": loc_no,
                "farm_name": farm.get("name", f"Farm {loc_no}"),
                "current_lice": round(current_lice, 4),
                "sst_c": round(current_temp, 1),
                "recommended_week": rec_week,
                "recommended_treatment": best_option.treatment_type if rec_week > 0 else "None needed",
                "priority": priority,
                "reason": reason,
                "estimated_cost_nok": round(best_option.cost_per_fish_nok * FISH_PER_CAGE, 0) if rec_week > 0 else 0,
            })

        # Sort by priority then lice level
        schedule_entries.sort(key=lambda e: (e["priority"], -e["current_lice"]))

        # Stagger treatments to avoid resource bottleneck
        # Farms with same priority in same week get staggered by 1 week
        seen_weeks: dict[int, int] = {}
        for entry in schedule_entries:
            if entry["recommended_week"] == 0:
                continue
            week = entry["recommended_week"]
            count = seen_weeks.get(week, 0)
            if count >= 3:  # max 3 farms per week
                entry["recommended_week"] = ((week) % 52) + 1
            seen_weeks[week] = seen_weeks.get(week, 0) + 1

        total_cost = sum(e["estimated_cost_nok"] for e in schedule_entries)
        farms_needing_treatment = sum(1 for e in schedule_entries if e["recommended_week"] > 0)

        # Get neighbor info from farm_graph for context
        pa_cluster = None
        for c in clusters:
            if c.get("production_area") == pa:
                pa_cluster = c
                break

        return {
            "production_area": pa,
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "total_farms": len(schedule_entries),
            "farms_needing_treatment": farms_needing_treatment,
            "total_estimated_cost_nok": round(total_cost, 0),
            "network_risk": pa_cluster.get("risk_level", "unknown") if pa_cluster else "unknown",
            "cascade_probability": pa_cluster.get("cascade_probability", 0) if pa_cluster else 0,
            "schedule": schedule_entries,
        }

    async def cost_benefit_analysis(
        self,
        locality_no: int,
        treatment_type: str,
    ) -> dict:
        """Project post-treatment lice trajectory vs cost using LIVE baseline."""
        lice_history = await self._get_lice_history(locality_no, weeks=12)
        if not lice_history:
            return {"error": f"No lice data for locality {locality_no}"}

        treatment = TREATMENTS.get(treatment_type)
        if not treatment:
            return {"error": f"Unknown treatment type: {treatment_type}", "valid_types": list(TREATMENTS.keys())}

        current = lice_history[-1]
        current_lice = current["avg_adult_female_lice"] or 0.0
        current_temp = current["sea_temp_c"] or 8.0
        current_week = current["week"]

        # Project baseline (no treatment)
        baseline = self._project_lice_trajectory(
            lice_history, current_temp, WEEKS_LOOKAHEAD + treatment.recovery_weeks
        )

        # Project with treatment applied at week 0
        post_treatment_lice = current_lice * (1 - treatment.efficacy_pct / 100.0)
        treated = self._project_treated_trajectory(
            post_treatment_lice, current_temp, treatment.recovery_weeks,
            WEEKS_LOOKAHEAD + treatment.recovery_weeks,
        )

        total_cost = treatment.cost_per_fish_nok * FISH_PER_CAGE
        mortality_fish = int(FISH_PER_CAGE * treatment.mortality_risk_pct / 100.0)

        # Cost of NOT treating: regulatory fine risk + mortality from high lice
        weeks_over_limit_baseline = sum(1 for v in baseline if v >= REGULATORY_LIMIT)
        regulatory_risk_cost = weeks_over_limit_baseline * 50_000  # estimated fine/forced treatment

        # Net benefit
        net_benefit = regulatory_risk_cost - total_cost

        return {
            "locality_no": locality_no,
            "treatment_type": treatment_type,
            "treatment_name": treatment.treatment_type,
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "current_lice": round(current_lice, 4),
            "current_sst_c": round(current_temp, 1),
            "treatment_cost_nok": round(total_cost, 0),
            "expected_mortality_fish": mortality_fish,
            "expected_mortality_pct": treatment.mortality_risk_pct,
            "post_treatment_lice": round(post_treatment_lice, 4),
            "recovery_weeks": treatment.recovery_weeks,
            "baseline_trajectory": [round(v, 4) for v in baseline],
            "treated_trajectory": [round(v, 4) for v in treated],
            "weeks_labels": [
                f"W{((current_week + i - 1) % 52) + 1}"
                for i in range(len(baseline))
            ],
            "weeks_over_limit_without_treatment": weeks_over_limit_baseline,
            "regulatory_risk_cost_nok": round(regulatory_risk_cost, 0),
            "net_benefit_nok": round(net_benefit, 0),
            "roi_ratio": round(net_benefit / total_cost, 2) if total_cost > 0 else 0,
        }

    # ── Private helpers ──────────────────────────────────────────────

    async def _get_lice_history(self, locality_no: int, weeks: int = 8) -> list[dict]:
        """Fetch recent lice records from DB (LIVE BarentsWatch data)."""
        try:
            from core.async_db import get_async_session
            async with get_async_session() as s:
                result = await s.execute(
                    select(LiceRecord)
                    .where(LiceRecord.locality_no == locality_no)
                    .order_by(desc(LiceRecord.year), desc(LiceRecord.week))
                    .limit(weeks)
                )
                rows = result.scalars().all()

                if not rows:
                    return []

                return [
                    {
                        "year": r.year,
                        "week": r.week,
                        "avg_adult_female_lice": r.avg_adult_female_lice,
                        "avg_mobile_lice": r.avg_mobile_lice,
                        "sea_temp_c": r.sea_temp_c,
                        "has_cleaner_fish": r.has_cleaner_fish,
                    }
                    for r in reversed(rows)  # oldest first
                ]
        except Exception as e:
            log.error("treatment_optimizer.db_error", error=str(e))
            return []

    async def _get_pa_lice_history_batch(self, pa: int, weeks: int = 4) -> dict[int, list[dict]]:
        """Fetch recent lice records for ALL farms in a PA in a single query.

        Returns a dict keyed by locality_no, each value a list of lice records
        (oldest first), matching the format of _get_lice_history().
        """
        try:
            from core.async_db import get_async_session

            # Step 1: get all locality_nos in this PA
            async with get_async_session() as s:
                loc_result = await s.execute(
                    select(Locality.locality_no)
                    .where(Locality.production_area == pa)
                    .where(Locality.latitude.isnot(None))
                )
                locality_nos = [row[0] for row in loc_result.all()]

            if not locality_nos:
                return {}

            # Step 2: fetch lice records for ALL farms in one query
            async with get_async_session() as s:
                # Use a window function to rank rows per locality and pick top N

                result = await s.execute(
                    select(LiceRecord)
                    .where(LiceRecord.locality_no.in_(locality_nos))
                    .order_by(
                        LiceRecord.locality_no,
                        desc(LiceRecord.year),
                        desc(LiceRecord.week),
                    )
                )
                all_rows = result.scalars().all()

            # Step 3: group by locality_no and limit to `weeks` per farm
            from collections import defaultdict
            grouped: dict[int, list] = defaultdict(list)
            for r in all_rows:
                if len(grouped[r.locality_no]) < weeks:
                    grouped[r.locality_no].append(r)

            # Step 4: convert to dict format (oldest first) matching _get_lice_history
            result_dict: dict[int, list[dict]] = {}
            for loc_no, rows in grouped.items():
                result_dict[loc_no] = [
                    {
                        "year": r.year,
                        "week": r.week,
                        "avg_adult_female_lice": r.avg_adult_female_lice,
                        "avg_mobile_lice": r.avg_mobile_lice,
                        "sea_temp_c": r.sea_temp_c,
                        "has_cleaner_fish": r.has_cleaner_fish,
                    }
                    for r in reversed(rows)  # oldest first
                ]

            return result_dict
        except Exception as e:
            log.error("treatment_optimizer.pa_lice_batch_error", error=str(e))
            return {}

    async def _get_pa_farms(self, pa: int) -> list[dict]:
        """Get all farms in a production area from DB."""
        try:
            from core.async_db import get_async_session
            async with get_async_session() as s:
                result = await s.execute(
                    select(Locality)
                    .where(Locality.production_area == pa)
                    .where(Locality.latitude.isnot(None))
                )
                rows = result.scalars().all()

                return [
                    {
                        "locality_no": r.locality_no,
                        "name": r.name,
                        "latitude": r.latitude,
                        "longitude": r.longitude,
                        "owner_company": r.owner_company,
                    }
                    for r in rows
                ]
        except Exception as e:
            log.error("treatment_optimizer.pa_farms_error", error=str(e))
            return []

    async def _project_lice_growth(self, current_lice: float, weeks_ahead: int, sea_temp: float) -> float:
        """Project lice growth using Stige model with linear fallback."""
        try:
            import pandas as pd
            from core.predictors.short_term import stige_predictor

            if stige_predictor.is_fitted:
                # Build a minimal DataFrame for the Stige model
                now = dt.datetime.now(dt.UTC)
                _, week, _ = now.isocalendar()
                row = {
                    "locality_no": 0,
                    "year": now.year,
                    "week": week,
                    "avg_adult_female_lice": current_lice,
                    "avg_mobile_lice": current_lice * 0.8,
                    "avg_stationary_lice": current_lice * 0.5,
                    "sea_temp_c": sea_temp,
                    "pressure_index": 0.0,
                    "has_cleaner_fish": False,
                }
                df = pd.DataFrame([row])
                forecasts = stige_predictor.predict(df, horizon_weeks=min(weeks_ahead, 2))
                if forecasts and forecasts[0].pred_adult_female > 0:
                    return forecasts[0].pred_adult_female
        except Exception:
            pass

        # Fallback to linear heuristic (Stige model unavailable or unfitted)
        # Literature note: this is a simplification; actual lice dynamics are non-linear
        degree_weeks = sea_temp * weeks_ahead
        return current_lice * (1 + LICE_GROWTH_RATE_PER_DEGREE_WEEK * degree_weeks)

    def _project_lice_trajectory(
        self,
        history: list[dict],
        current_temp: float,
        weeks_ahead: int,
    ) -> list[float]:
        """Project lice trajectory from historical trend + temperature."""
        values = [h["avg_adult_female_lice"] or 0.0 for h in history if h.get("avg_adult_female_lice") is not None]
        if not values:
            return [0.0] * weeks_ahead

        current = values[-1]

        # Try Stige model for the first projection point
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context already — can't await here in sync method
                # Use the Stige model via a direct synchronous call
                import pandas as pd
                from core.predictors.short_term import stige_predictor

                if stige_predictor.is_fitted:
                    now = dt.datetime.now(dt.UTC)
                    _, week, _ = now.isocalendar()
                    row = {
                        "locality_no": 0,
                        "year": now.year,
                        "week": week,
                        "avg_adult_female_lice": current,
                        "avg_mobile_lice": current * 0.8,
                        "avg_stationary_lice": current * 0.5,
                        "sea_temp_c": current_temp,
                        "pressure_index": 0.0,
                        "has_cleaner_fish": False,
                    }
                    df = pd.DataFrame([row])
                    for horizon in [1, 2]:
                        forecasts = stige_predictor.predict(df, horizon_weeks=horizon)
                        if forecasts and forecasts[0].pred_adult_female > 0:
                            # Use Stige prediction as anchor, extrapolate remaining weeks
                            stige_val = forecasts[0].pred_adult_female
                            weekly_growth = (stige_val - current) / horizon
                            trajectory = []
                            lice = current
                            for w in range(weeks_ahead):
                                lice = max(0.0, lice + weekly_growth)
                                trajectory.append(lice)
                            log.info("treatment_optimizer.stige_trajectory",
                                     horizon=horizon, stige_val=round(stige_val, 4))
                            return trajectory
        except Exception:
            pass

        # Fallback: linear heuristic with historical trend
        # Calculate weekly growth rate from recent data
        if len(values) >= 3:
            diffs = [values[i] - values[i - 1] for i in range(1, len(values))]
            avg_weekly_change = np.mean(diffs[-4:])  # last 4 weeks
        else:
            avg_weekly_change = 0.0

        # Temperature-adjusted growth: warmer = faster lice development
        temp_factor = max(0.5, min(2.0, current_temp / 10.0))

        trajectory = []
        lice = current
        for _ in range(weeks_ahead):
            growth = avg_weekly_change * temp_factor + LICE_GROWTH_RATE_PER_DEGREE_WEEK * (current_temp / 10.0)
            lice = max(0.0, lice + growth)
            trajectory.append(lice)

        return trajectory

    def _project_treated_trajectory(
        self,
        post_treatment_lice: float,
        temp: float,
        recovery_weeks: int,
        total_weeks: int,
    ) -> list[float]:
        """Project lice rebound after treatment, using Stige model with linear fallback."""
        # Try Stige model for post-treatment growth projection
        try:
            import pandas as pd
            from core.predictors.short_term import stige_predictor

            if stige_predictor.is_fitted:
                now = dt.datetime.now(dt.UTC)
                _, week, _ = now.isocalendar()
                row = {
                    "locality_no": 0,
                    "year": now.year,
                    "week": week,
                    "avg_adult_female_lice": post_treatment_lice,
                    "avg_mobile_lice": post_treatment_lice * 0.8,
                    "avg_stationary_lice": post_treatment_lice * 0.5,
                    "sea_temp_c": temp,
                    "pressure_index": 0.0,
                    "has_cleaner_fish": False,
                }
                df = pd.DataFrame([row])
                forecasts = stige_predictor.predict(df, horizon_weeks=2)
                if forecasts and forecasts[0].pred_adult_female > 0:
                    stige_val = forecasts[0].pred_adult_female
                    # Derive weekly growth rate from Stige, apply recovery dampening
                    stige_weekly_growth = (stige_val - post_treatment_lice) / 2
                    trajectory = []
                    lice = post_treatment_lice
                    for w in range(total_weeks):
                        if w < recovery_weeks:
                            growth = stige_weekly_growth * 0.3  # dampened during recovery
                        else:
                            growth = stige_weekly_growth
                        lice = max(0.0, lice + growth)
                        trajectory.append(lice)
                    log.info("treatment_optimizer.stige_treated_trajectory",
                             stige_val=round(stige_val, 4))
                    return trajectory
        except Exception:
            pass

        # Fallback: linear heuristic
        trajectory = []
        lice = post_treatment_lice
        temp_factor = max(0.5, min(2.0, temp / 10.0))

        for week in range(total_weeks):
            if week < recovery_weeks:
                # Slow rebound during recovery
                growth = LICE_GROWTH_RATE_PER_DEGREE_WEEK * temp_factor * 0.3
            else:
                # Normal growth post-recovery
                growth = LICE_GROWTH_RATE_PER_DEGREE_WEEK * temp_factor
            lice = max(0.0, lice + growth)
            trajectory.append(lice)

        return trajectory

    def _select_best_treatment(
        self,
        temp: float,
        lice_level: float,
        has_cleaner: bool,
        budget_nok: float | None = None,
    ) -> tuple[str, _TreatmentOption]:
        """Select best treatment from TREATMENTS based on live conditions."""
        eligible = []

        for key, t in TREATMENTS.items():
            if key == "cleaner_fish" and has_cleaner:
                continue
            if not (t.suitable_temp_range[0] <= temp <= t.suitable_temp_range[1]):
                continue

            total_cost = t.cost_per_fish_nok * FISH_PER_CAGE
            if budget_nok and total_cost > budget_nok:
                continue

            # Score: efficacy - mortality penalty - cost factor
            score = t.efficacy_pct - t.mortality_risk_pct * 10 - t.cost_per_fish_nok * 2
            if lice_level >= REGULATORY_LIMIT:
                score += t.efficacy_pct * 0.2  # favor high efficacy when critical
            eligible.append((score, key, t))

        eligible.sort(key=lambda x: x[0], reverse=True)

        if not eligible:
            return "mechanical", TREATMENTS["mechanical"]

        return eligible[0][1], eligible[0][2]

    def _describe_trend(self, history: list[dict]) -> str:
        """Describe lice trend from recent history."""
        values = [h["avg_adult_female_lice"] or 0.0 for h in history if h.get("avg_adult_female_lice") is not None]
        if len(values) < 3:
            return "insufficient data"

        recent = values[-3:]
        if recent[-1] > recent[0] * 1.1:
            return "increasing"
        elif recent[-1] < recent[0] * 0.9:
            return "decreasing"
        return "stable"


# ── Singleton ────────────────────────────────────────────────────────
treatment_optimizer = TreatmentOptimizer()
