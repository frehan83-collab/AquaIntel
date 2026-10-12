"""
Farmer Advisory Module
=======================
Generates per-farm actionable intelligence:
  1. Treatment recommendations (type, timing, expected efficacy)
  2. Harvest-timing optimization (lice vs growth vs price tradeoffs)
  3. Risk scores and early warnings
  4. Cleaner-fish deployment guidance

Uses stage-structured lice forecasts + infestation pressure to determine
optimal intervention strategies.

Treatment types and typical Norwegian parameters:
  - Mechanical (Hydrolicer, Optilicer): 80-95% efficacy, 0.5-2% mortality
  - Thermal (Thermolicer): 90-97% efficacy, 1-3% mortality
  - Medicinal bath (azamethiphos, deltamethrin): 70-90% efficacy, <0.5% mortality
  - Medicinal in-feed (emamectin): 80-95% efficacy, <0.1% mortality
  - Cleaner fish (wrasse/lumpfish): ongoing 10-30% reduction, low mortality
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import structlog

from core.predictors.short_term import StageForcast

log = structlog.get_logger(__name__)

REGULATORY_LIMIT = 0.5
WARNING_LEVEL = 0.2
TREATMENT_TRIGGER = 0.3  # recommend proactive treatment above this


@dataclass
class TreatmentOption:
    treatment_type: str
    efficacy_pct: float
    mortality_risk_pct: float
    cost_per_fish_nok: float
    recovery_weeks: int  # weeks for lice to rebound
    environmental_impact: str  # low/medium/high
    suitable_temp_range: tuple[float, float] = (4.0, 18.0)
    notes: str = ""


# ── Available treatment options ──────────────────────────────────────
TREATMENTS = {
    "mechanical": TreatmentOption(
        "Mechanical (Hydrolicer/Optilicer)", 87.5, 1.25, 3.0, 6,
        "low", (4, 18), "Best all-round option. Avoid during smolt windows."
    ),
    "thermal": TreatmentOption(
        "Thermal (Thermolicer)", 93.5, 2.0, 4.0, 8,
        "low", (6, 16), "High efficacy but higher mortality. Not for warm water."
    ),
    "medicinal_bath": TreatmentOption(
        "Medicinal bath (azamethiphos)", 80.0, 0.3, 1.5, 4,
        "medium", (4, 16), "Lower mortality but resistance emerging. Regulatory constraints."
    ),
    "medicinal_feed": TreatmentOption(
        "Medicinal in-feed (emamectin)", 87.5, 0.1, 2.0, 10,
        "medium", (4, 18), "Long-lasting but 6-week withdrawal before harvest."
    ),
    "cleaner_fish": TreatmentOption(
        "Cleaner fish deployment", 20.0, 0.0, 5.0, 0,
        "low", (4, 16), "Preventive. Deploy early in production cycle."
    ),
}


@dataclass
class FarmerAdvisory:
    """Complete advisory package for a single farm/locality."""
    locality_no: int
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))

    # Current status
    current_lice: float = 0.0
    risk_level: str = "low"  # low/moderate/high/critical
    risk_score: float = 0.0  # 0-100

    # Treatment recommendation
    treatment_needed: bool = False
    recommended_treatment: str = ""
    treatment_urgency: str = "none"  # none/low/medium/high/immediate
    optimal_treatment_week: int = 0
    estimated_treatment_cost_nok: float = 0.0
    expected_lice_reduction_pct: float = 0.0
    expected_mortality_pct: float = 0.0
    alternative_treatments: list[str] = field(default_factory=list)

    # Harvest timing
    harvest_advice: str = ""
    optimal_harvest_window: str = ""

    # Forecast summary
    forecast_1w: float = 0.0
    forecast_2w: float = 0.0
    prob_exceed_1w: float = 0.0
    trend: str = "stable"

    # Narrative
    summary: str = ""
    detailed_rationale: str = ""


def generate_farm_advisory(
    locality_no: int,
    current_lice: float,
    sea_temp: float,
    forecasts_1w: list[StageForcast],
    forecasts_2w: list[StageForcast],
    pressure_index: float = 0.0,
    has_cleaner_fish: bool = False,
    fish_weight_kg: float = 3.5,
    weeks_to_planned_harvest: int | None = None,
) -> FarmerAdvisory:
    """Generate comprehensive farm advisory from predictions."""

    # Find this locality's forecasts
    f1w = next((f for f in forecasts_1w if f.locality_no == locality_no), None)
    f2w = next((f for f in forecasts_2w if f.locality_no == locality_no), None)

    pred_1w = f1w.pred_adult_female if f1w else current_lice
    pred_2w = f2w.pred_adult_female if f2w else current_lice
    prob_exceed = f1w.prob_exceed_threshold if f1w else 0
    trend = f1w.trend if f1w else "stable"

    # ── Risk score (0-100) ───────────────────────────────────────────
    risk_score = _compute_risk_score(
        current_lice, pred_1w, pred_2w, pressure_index, sea_temp, trend
    )

    if risk_score >= 75:
        risk_level = "critical"
    elif risk_score >= 50:
        risk_level = "high"
    elif risk_score >= 25:
        risk_level = "moderate"
    else:
        risk_level = "low"

    # ── Treatment recommendation ─────────────────────────────────────
    treatment_needed = False
    recommended = ""
    urgency = "none"
    alternatives = []
    est_cost = 0.0
    est_reduction = 0.0
    est_mortality = 0.0
    optimal_week = 0

    now = dt.datetime.now(dt.UTC)
    _, current_week, _ = now.isocalendar()

    if current_lice >= REGULATORY_LIMIT or pred_1w >= REGULATORY_LIMIT:
        treatment_needed = True
        urgency = "immediate" if current_lice >= REGULATORY_LIMIT else "high"
    elif pred_2w >= TREATMENT_TRIGGER or risk_score >= 50:
        treatment_needed = True
        urgency = "medium"
    elif trend == "increasing" and current_lice >= WARNING_LEVEL:
        treatment_needed = True
        urgency = "low"

    if treatment_needed:
        best, alts = _select_treatment(sea_temp, current_lice, has_cleaner_fish,
                                        weeks_to_planned_harvest)
        recommended = best.treatment_type
        est_reduction = best.efficacy_pct
        est_mortality = best.mortality_risk_pct
        est_cost = best.cost_per_fish_nok * 200_000  # assume 200k fish
        alternatives = [a.treatment_type for a in alts[:2]]
        optimal_week = current_week if urgency == "immediate" else current_week + 1

    # ── Harvest timing ───────────────────────────────────────────────
    harvest_advice, harvest_window = _harvest_timing_advice(
        current_lice, pred_1w, pred_2w, fish_weight_kg,
        weeks_to_planned_harvest, trend
    )

    # ── Narrative ────────────────────────────────────────────────────
    summary = _build_summary(
        locality_no, current_lice, pred_1w, risk_level,
        treatment_needed, urgency, recommended, trend
    )

    return FarmerAdvisory(
        locality_no=locality_no,
        current_lice=round(current_lice, 3),
        risk_level=risk_level,
        risk_score=round(risk_score, 1),
        treatment_needed=treatment_needed,
        recommended_treatment=recommended,
        treatment_urgency=urgency,
        optimal_treatment_week=optimal_week,
        estimated_treatment_cost_nok=round(est_cost, 0),
        expected_lice_reduction_pct=round(est_reduction, 1),
        expected_mortality_pct=round(est_mortality, 2),
        alternative_treatments=alternatives,
        harvest_advice=harvest_advice,
        optimal_harvest_window=harvest_window,
        forecast_1w=round(pred_1w, 4),
        forecast_2w=round(pred_2w, 4),
        prob_exceed_1w=round(prob_exceed, 3),
        trend=trend,
        summary=summary,
    )


def _compute_risk_score(
    current: float, pred_1w: float, pred_2w: float,
    pressure: float, temp: float, trend: str,
) -> float:
    """Composite risk score 0-100."""
    # Current lice severity (0-40 points)
    severity = min(40, current / REGULATORY_LIMIT * 30)

    # Forecast trajectory (0-25 points)
    trajectory = min(25, pred_2w / REGULATORY_LIMIT * 20)
    if trend == "increasing":
        trajectory *= 1.3

    # External pressure (0-20 points)
    ext_pressure = min(20, pressure / 5 * 20)

    # Temperature risk (warm = faster development) (0-15 points)
    temp_risk = min(15, max(0, (temp - 8) / 10 * 15))

    return min(100, severity + trajectory + ext_pressure + temp_risk)


def _select_treatment(
    temp: float, lice_level: float, has_cleaner: bool,
    weeks_to_harvest: int | None,
) -> tuple[TreatmentOption, list[TreatmentOption]]:
    """Select best treatment option given constraints."""
    eligible = []

    for key, t in TREATMENTS.items():
        if key == "cleaner_fish" and has_cleaner:
            continue  # already deployed
        if not (t.suitable_temp_range[0] <= temp <= t.suitable_temp_range[1]):
            continue
        if key == "medicinal_feed" and weeks_to_harvest and weeks_to_harvest < 8:
            continue  # withdrawal period

        # Score: efficacy - mortality penalty - cost factor
        score = t.efficacy_pct - t.mortality_risk_pct * 10 - t.cost_per_fish_nok * 2
        if lice_level >= REGULATORY_LIMIT:
            score += t.efficacy_pct * 0.2  # favor high efficacy when critical
        eligible.append((score, t))

    eligible.sort(key=lambda x: x[0], reverse=True)

    if not eligible:
        return TREATMENTS["mechanical"], []

    best = eligible[0][1]
    alts = [e[1] for e in eligible[1:]]
    return best, alts


def _harvest_timing_advice(
    current: float, pred_1w: float, pred_2w: float,
    fish_weight: float, weeks_to_harvest: int | None, trend: str,
) -> tuple[str, str]:
    """Generate harvest timing recommendation."""
    now = dt.datetime.now(dt.UTC)
    _, week, _ = now.isocalendar()

    if current >= REGULATORY_LIMIT * 1.5:
        return (
            "Consider accelerating harvest to avoid further lice damage and mandatory treatment costs.",
            f"W{week}-W{week+2}"
        )

    if trend == "increasing" and pred_2w >= TREATMENT_TRIGGER:
        if fish_weight >= 4.0:
            return (
                "Fish weight is adequate. Harvesting within 2-3 weeks avoids upcoming treatment costs.",
                f"W{week+1}-W{week+3}"
            )
        return (
            "Lice rising but fish below optimal weight. Treat first, then harvest at target weight.",
            f"W{week+4}-W{week+8}"
        )

    if weeks_to_harvest and weeks_to_harvest <= 4 and current < WARNING_LEVEL:
        return (
            "Lice levels are low. Maintain current schedule for optimal harvest weight.",
            f"W{week + weeks_to_harvest}"
        )

    return ("No change to harvest schedule recommended.", "")


def _build_summary(
    loc: int, current: float, pred_1w: float,
    risk: str, treatment: bool, urgency: str,
    treatment_type: str, trend: str,
) -> str:
    parts = [f"Locality {loc}: {risk.upper()} risk."]
    parts.append(f"Current lice: {current:.2f}, 1-week forecast: {pred_1w:.2f} ({trend}).")

    if treatment:
        parts.append(f"Treatment recommended ({urgency}): {treatment_type}.")
    else:
        parts.append("No treatment needed at this time.")

    return " ".join(parts)
