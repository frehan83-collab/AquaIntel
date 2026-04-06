"""
Supply Forecast Module (Buyers & Processors)
==============================================
Generates regional and company-level supply volume forecasts:
  1. Projected weekly harvest volumes by production area (PA 1-13)
  2. Quality impact scores (lice damage → downgrade risk)
  3. Contract risk alerts (supply shortfall warnings)
  4. Price pressure indicators

Uses lice predictions + treatment forecasts to estimate how much
biomass will be harvested vs. delayed/lost.

Key assumptions:
  - Norwegian production: ~1.7M tonnes HOG/year, ~33,000 tonnes/week avg
  - Production areas 3-6 account for ~55% of total volume
  - High lice → forced early harvest or delayed harvest (after treatment)
  - Treatment mortality reduces available biomass by 1-3%
  - Quality downgrading: lice-damaged fish fetch 5-15% lower price
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# ── Production area baselines (approximate weekly tonnes HOG) ────────
PA_WEEKLY_BASELINE = {
    1: 800,   2: 1200,  3: 3500,  4: 4000,
    5: 3800,  6: 3200,  7: 2800,  8: 2400,
    9: 2200,  10: 1800, 11: 2500, 12: 2800, 13: 1500,
}

# Seasonal harvest multipliers (index by month, 1-12)
SEASONAL_MULTIPLIER = {
    1: 0.75, 2: 0.70, 3: 0.80, 4: 0.90, 5: 1.00, 6: 1.10,
    7: 1.05, 8: 1.15, 9: 1.25, 10: 1.20, 11: 1.05, 12: 0.85,
}

QUALITY_GRADES = {
    "Superior": {"lice_max": 0.1, "price_premium_pct": 5},
    "Ordinary": {"lice_max": 0.5, "price_premium_pct": 0},
    "Production": {"lice_max": 2.0, "price_premium_pct": -12},
}


@dataclass
class RegionalSupplyForecast:
    """Supply forecast for a production area or company."""
    region: str  # "PA-3" or "MOWI" etc
    forecast_week: int
    forecast_year: int
    horizon_weeks: int = 4

    # Volume
    baseline_tonnes: float = 0.0
    predicted_tonnes: float = 0.0
    tonnes_lo80: float = 0.0
    tonnes_hi80: float = 0.0

    # Adjustments
    lice_treatment_delay_tonnes: float = 0.0
    treatment_mortality_tonnes: float = 0.0
    early_harvest_tonnes: float = 0.0  # positive = extra supply
    net_adjustment_pct: float = 0.0

    # Quality
    pct_superior: float = 0.0
    pct_ordinary: float = 0.0
    pct_production: float = 0.0
    avg_quality_score: float = 0.0  # 0-100

    # Risk
    supply_risk: str = "low"
    contract_risk: bool = False
    price_pressure: str = "neutral"  # bullish/neutral/bearish

    rationale: str = ""


@dataclass
class BuyerIntelligence:
    """Complete buyer/processor intelligence package."""
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    regional_forecasts: list[RegionalSupplyForecast] = field(default_factory=list)
    total_predicted_tonnes: float = 0.0
    total_baseline_tonnes: float = 0.0
    net_supply_change_pct: float = 0.0
    overall_quality_score: float = 0.0
    price_outlook: str = "neutral"
    key_risks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def forecast_regional_supply(
    production_area: int,
    avg_lice_in_pa: float,
    pct_above_threshold: float,
    expected_treatments: int,
    sea_temp: float,
    forecast_weeks: int = 4,
) -> RegionalSupplyForecast:
    """Generate supply forecast for a production area."""
    now = dt.datetime.now(dt.UTC)
    year, week, _ = now.isocalendar()
    month = now.month

    baseline = PA_WEEKLY_BASELINE.get(production_area, 2000)
    seasonal = SEASONAL_MULTIPLIER.get(month, 1.0)
    weekly_baseline = baseline * seasonal * forecast_weeks

    # ── Adjustments from lice impact ─────────────────────────────────

    # Treatment delays: each treatment delays ~1 week of harvest for affected sites
    # Assume 30% of sites in PA affected per treatment
    delay_fraction = min(0.15, expected_treatments * 0.03)
    delay_tonnes = weekly_baseline * delay_fraction

    # Mortality from treatments
    mortality_fraction = expected_treatments * 0.015 * pct_above_threshold
    mortality_tonnes = weekly_baseline * min(mortality_fraction, 0.05)

    # Forced early harvest (sites hitting crisis levels harvest early)
    early_fraction = 0.0
    if avg_lice_in_pa >= 0.8:
        early_fraction = 0.05  # 5% extra early harvest
    early_tonnes = weekly_baseline * early_fraction

    # Net adjustment
    net_change = early_tonnes - delay_tonnes - mortality_tonnes
    net_pct = (net_change / weekly_baseline * 100) if weekly_baseline > 0 else 0

    predicted = max(0, weekly_baseline + net_change)

    # Uncertainty
    std_pct = 8 + 2 * pct_above_threshold * 10  # higher uncertainty with more lice
    lo80 = predicted * (1 - std_pct / 100 * 1.28)
    hi80 = predicted * (1 + std_pct / 100 * 1.28)

    # ── Quality distribution ─────────────────────────────────────────
    if avg_lice_in_pa < 0.1:
        pct_sup, pct_ord, pct_prod = 60, 35, 5
    elif avg_lice_in_pa < 0.3:
        pct_sup, pct_ord, pct_prod = 35, 55, 10
    elif avg_lice_in_pa < 0.5:
        pct_sup, pct_ord, pct_prod = 15, 60, 25
    else:
        pct_sup, pct_ord, pct_prod = 5, 45, 50

    quality_score = pct_sup * 1.0 + pct_ord * 0.6 + pct_prod * 0.2

    # ── Risk assessment ──────────────────────────────────────────────
    if net_pct < -10:
        supply_risk = "high"
    elif net_pct < -5:
        supply_risk = "medium"
    else:
        supply_risk = "low"

    contract_risk = net_pct < -8 or pct_prod > 30

    if net_pct < -5:
        price_pressure = "bullish"  # less supply → higher prices
    elif net_pct > 5:
        price_pressure = "bearish"
    else:
        price_pressure = "neutral"

    fw = week + forecast_weeks
    fy = year
    if fw > 52:
        fw -= 52
        fy += 1

    rationale_parts = []
    if delay_tonnes > 0:
        rationale_parts.append(f"Treatment delays reduce supply by {delay_tonnes:.0f}t")
    if mortality_tonnes > 0:
        rationale_parts.append(f"Treatment mortality: -{mortality_tonnes:.0f}t")
    if early_tonnes > 0:
        rationale_parts.append(f"Crisis-driven early harvest: +{early_tonnes:.0f}t")

    return RegionalSupplyForecast(
        region=f"PA-{production_area}",
        forecast_week=fw,
        forecast_year=fy,
        horizon_weeks=forecast_weeks,
        baseline_tonnes=round(weekly_baseline, 0),
        predicted_tonnes=round(predicted, 0),
        tonnes_lo80=round(lo80, 0),
        tonnes_hi80=round(hi80, 0),
        lice_treatment_delay_tonnes=round(delay_tonnes, 0),
        treatment_mortality_tonnes=round(mortality_tonnes, 0),
        early_harvest_tonnes=round(early_tonnes, 0),
        net_adjustment_pct=round(net_pct, 1),
        pct_superior=pct_sup,
        pct_ordinary=pct_ord,
        pct_production=pct_prod,
        avg_quality_score=round(quality_score, 1),
        supply_risk=supply_risk,
        contract_risk=contract_risk,
        price_pressure=price_pressure,
        rationale="; ".join(rationale_parts) if rationale_parts else "Normal supply conditions",
    )


def generate_buyer_intelligence(
    pa_lice_data: dict[int, dict],
) -> BuyerIntelligence:
    """
    Generate complete buyer intelligence from per-PA lice summaries.

    pa_lice_data: {pa_number: {avg_lice, pct_above, treatments, temp}}
    """
    forecasts = []
    total_predicted = 0
    total_baseline = 0

    for pa in range(1, 14):
        data = pa_lice_data.get(pa, {})
        f = forecast_regional_supply(
            production_area=pa,
            avg_lice_in_pa=data.get("avg_lice", 0.1),
            pct_above_threshold=data.get("pct_above", 0.0),
            expected_treatments=data.get("treatments", 0),
            sea_temp=data.get("temp", 8.0),
        )
        forecasts.append(f)
        total_predicted += f.predicted_tonnes
        total_baseline += f.baseline_tonnes

    net_change = ((total_predicted - total_baseline) / total_baseline * 100
                  if total_baseline > 0 else 0)

    # Overall quality
    quality_scores = [f.avg_quality_score for f in forecasts]
    avg_quality = np.mean(quality_scores) if quality_scores else 50

    # Price outlook
    if net_change < -3:
        price_outlook = "bullish"
    elif net_change > 3:
        price_outlook = "bearish"
    else:
        price_outlook = "neutral"

    # Key risks
    risks = []
    high_risk_pas = [f.region for f in forecasts if f.supply_risk == "high"]
    if high_risk_pas:
        risks.append(f"High supply risk in: {', '.join(high_risk_pas)}")
    contract_risks = [f.region for f in forecasts if f.contract_risk]
    if contract_risks:
        risks.append(f"Contract risk flags: {', '.join(contract_risks)}")

    # Recommendations
    recs = []
    if price_outlook == "bullish":
        recs.append("Secure forward contracts — supply likely tightening.")
    if avg_quality < 40:
        recs.append("Expect higher proportion of production-grade fish. Adjust processing plans.")
    if any(f.early_harvest_tonnes > 0 for f in forecasts):
        recs.append("Some regions seeing early harvest — spot buying opportunity.")

    return BuyerIntelligence(
        regional_forecasts=forecasts,
        total_predicted_tonnes=round(total_predicted, 0),
        total_baseline_tonnes=round(total_baseline, 0),
        net_supply_change_pct=round(net_change, 1),
        overall_quality_score=round(avg_quality, 1),
        price_outlook=price_outlook,
        key_risks=risks,
        recommendations=recs,
    )
