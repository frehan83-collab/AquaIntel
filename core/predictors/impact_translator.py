"""
Impact Translation Layer
=========================
Converts lice predictions into company-specific financial impacts:

  Lice Forecast → Harvest Reduction % → Revenue Impact → Expected Stock Move

Key factors:
  1. Regulatory enforcement (mandatory treatments above 0.5 threshold)
  2. Treatment costs and fish mortality from treatments
  3. Growth reduction from lice parasitism
  4. Forced early harvest / biomass downgrade
  5. Traffic-light system production capacity cuts (PA colors)
  6. Historical price elasticity to lice shocks

Reference data:
  - Treatment cost: ~NOK 2-5 per fish (non-medicinal), NOK 0.5-2 (medicinal)
  - Treatment mortality: 0.5-3% per event (thermal/mechanical)
  - Growth reduction: ~10% per 0.1 lice above 0.2 threshold
  - Regulatory quota cut (red PA): up to 6% mandatory reduction
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)


# ── Company production estimates (approximate, from annual reports) ───
COMPANY_PRODUCTION = {
    "MOWI": {
        "annual_harvest_tonnes": 460_000,
        "avg_revenue_per_kg": 65.0,  # NOK
        "market_cap_bnok": 120.0,
        "shares_outstanding_m": 517,
        "avg_fish_per_site": 500_000,
    },
    "SALM": {
        "annual_harvest_tonnes": 185_000,
        "avg_revenue_per_kg": 62.0,
        "market_cap_bnok": 65.0,
        "shares_outstanding_m": 565,
        "avg_fish_per_site": 400_000,
    },
    "LSG": {
        "annual_harvest_tonnes": 210_000,
        "avg_revenue_per_kg": 60.0,
        "market_cap_bnok": 40.0,
        "shares_outstanding_m": 596,
        "avg_fish_per_site": 350_000,
    },
    "GSF": {
        "annual_harvest_tonnes": 85_000,
        "avg_revenue_per_kg": 58.0,
        "market_cap_bnok": 18.0,
        "shares_outstanding_m": 112,
        "avg_fish_per_site": 300_000,
    },
}

# ── Treatment impact parameters ──────────────────────────────────────
TREATMENT_MORTALITY_PCT = 0.015  # 1.5% average per treatment event
TREATMENT_COST_PER_FISH = 3.0   # NOK average
GROWTH_REDUCTION_PER_LICE = 0.08  # 8% per 0.1 lice above base
GROWTH_BASE_LICE = 0.1          # growth unaffected below this

# ── Traffic-light production cuts ────────────────────────────────────
PA_COLOR_CUTS = {
    "green": 0.0,
    "yellow": 0.0,
    "red": 0.06,  # 6% mandatory capacity reduction
}

# ── Historical price elasticity (estimated from 2018-2025 data) ──────
# % stock price change per 1% harvest reduction
PRICE_ELASTICITY = {
    "MOWI": -0.45,
    "SALM": -0.55,
    "LSG": -0.50,
    "GSF": -0.65,  # smaller company = higher sensitivity
}


@dataclass
class HarvestImpact:
    """Quantified impact of lice on a company's production."""
    ticker: str
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))

    # Lice-driven impacts
    growth_reduction_pct: float = 0.0       # % harvest weight lost
    treatment_mortality_pct: float = 0.0    # % fish lost to treatments
    treatment_cost_mnok: float = 0.0        # total treatment cost
    regulatory_cut_pct: float = 0.0         # traffic-light forced cut

    # Combined
    total_harvest_reduction_pct: float = 0.0
    harvest_reduction_tonnes: float = 0.0
    revenue_impact_mnok: float = 0.0

    # Market impact
    expected_eps_impact_pct: float = 0.0
    expected_stock_move_pct: float = 0.0
    expected_stock_move_nok: float = 0.0

    # Confidence
    confidence: float = 0.0
    drivers: list[str] = field(default_factory=list)


@dataclass
class ArbitrageSignal:
    """Final trading signal from the impact translator."""
    ticker: str
    direction: str  # SHORT or LONG
    strength: float  # 0-1
    expected_move_pct: float
    time_horizon_weeks: int
    harvest_impact: HarvestImpact | None = None
    lice_trend: str = "stable"
    prob_exceed_threshold: float = 0.0
    rationale: str = ""


def compute_harvest_impact(
    ticker: str,
    avg_predicted_lice: float,
    pct_sites_above_threshold: float,
    predicted_treatments: int = 0,
    pa_color: str = "green",
    n_active_sites: int = 0,
) -> HarvestImpact:
    """
    Compute the full harvest-reduction impact chain.
    """
    prod = COMPANY_PRODUCTION.get(ticker)
    if not prod:
        return HarvestImpact(ticker=ticker, confidence=0)

    drivers = []

    # 1. Growth reduction from elevated lice
    excess_lice = max(0, avg_predicted_lice - GROWTH_BASE_LICE)
    growth_reduction = min(
        excess_lice / 0.1 * GROWTH_REDUCTION_PER_LICE,
        0.25  # cap at 25%
    ) * 100  # as percentage
    if growth_reduction > 1:
        drivers.append(f"Growth reduction {growth_reduction:.1f}% from avg lice {avg_predicted_lice:.2f}")

    # 2. Treatment mortality (expected treatments based on sites above threshold)
    expected_treatments = max(predicted_treatments, int(pct_sites_above_threshold * n_active_sites))
    treatment_mortality = expected_treatments * TREATMENT_MORTALITY_PCT * 100
    treatment_mortality = min(treatment_mortality, 10)  # cap
    if treatment_mortality > 0.5:
        drivers.append(f"Treatment mortality {treatment_mortality:.1f}% from {expected_treatments} expected treatments")

    # 3. Treatment costs
    fish_per_treatment = prod["avg_fish_per_site"]
    treatment_cost = expected_treatments * fish_per_treatment * TREATMENT_COST_PER_FISH / 1e6
    if treatment_cost > 1:
        drivers.append(f"Treatment cost NOK {treatment_cost:.0f}M")

    # 4. Traffic-light regulatory cut
    regulatory_cut = PA_COLOR_CUTS.get(pa_color, 0) * 100
    if regulatory_cut > 0:
        drivers.append(f"Red traffic-light: {regulatory_cut:.0f}% capacity cut")

    # 5. Total impact
    total_reduction = min(
        growth_reduction + treatment_mortality + regulatory_cut,
        40  # max 40% total reduction
    )
    harvest_tonnes = prod["annual_harvest_tonnes"] * total_reduction / 100
    revenue_mnok = harvest_tonnes * prod["avg_revenue_per_kg"] / 1000

    # 6. Market impact
    elasticity = PRICE_ELASTICITY.get(ticker, -0.5)
    stock_move_pct = total_reduction * elasticity
    share_price_est = prod["market_cap_bnok"] * 1e3 / prod["shares_outstanding_m"]
    stock_move_nok = share_price_est * stock_move_pct / 100

    eps_impact = revenue_mnok / prod["shares_outstanding_m"] * 1000  # øre per share

    # Confidence
    confidence = 0.4
    if n_active_sites > 20:
        confidence += 0.1
    if avg_predicted_lice > 0.3:
        confidence += 0.1
    if pct_sites_above_threshold > 0.1:
        confidence += 0.1
    confidence = min(0.85, confidence)

    return HarvestImpact(
        ticker=ticker,
        growth_reduction_pct=round(growth_reduction, 2),
        treatment_mortality_pct=round(treatment_mortality, 2),
        treatment_cost_mnok=round(treatment_cost, 1),
        regulatory_cut_pct=round(regulatory_cut, 1),
        total_harvest_reduction_pct=round(total_reduction, 2),
        harvest_reduction_tonnes=round(harvest_tonnes, 0),
        revenue_impact_mnok=round(revenue_mnok, 1),
        expected_eps_impact_pct=round(eps_impact, 2),
        expected_stock_move_pct=round(stock_move_pct, 2),
        expected_stock_move_nok=round(stock_move_nok, 1),
        confidence=round(confidence, 2),
        drivers=drivers,
    )


def generate_arbitrage_signal(
    ticker: str,
    impact: HarvestImpact,
    lice_trend: str = "stable",
    prob_exceed: float = 0.0,
    forecast_horizon_weeks: int = 4,
) -> ArbitrageSignal | None:
    """
    Generate a trading signal from the harvest impact analysis.

    Only generates signals when impact is material and confidence sufficient.
    """
    # Minimum thresholds for signal generation
    if impact.total_harvest_reduction_pct < 1.0:
        return None
    if impact.confidence < 0.3:
        return None

    # Direction
    direction = "SHORT"  # lice crisis → bearish
    if lice_trend == "decreasing" and impact.total_harvest_reduction_pct < 3:
        direction = "LONG"  # recovery

    # Strength (0-1)
    strength = min(1.0, (
        0.3 * min(impact.total_harvest_reduction_pct / 10, 1.0) +
        0.2 * min(abs(impact.expected_stock_move_pct) / 5, 1.0) +
        0.2 * prob_exceed +
        0.15 * impact.confidence +
        0.15 * (1.0 if lice_trend == "increasing" else 0.3)
    ))

    # Rationale
    rationale_parts = [
        f"Predicted {impact.total_harvest_reduction_pct:.1f}% harvest reduction for {ticker}.",
        f"Expected stock impact: {impact.expected_stock_move_pct:+.1f}% "
        f"(NOK {impact.expected_stock_move_nok:+.0f}/share).",
    ]
    if impact.drivers:
        rationale_parts.append("Key drivers: " + "; ".join(impact.drivers[:3]))
    rationale_parts.append(
        f"Lice trend: {lice_trend}. P(exceed threshold): {prob_exceed:.0%}. "
        f"Model confidence: {impact.confidence:.0%}."
    )

    return ArbitrageSignal(
        ticker=ticker,
        direction=direction,
        strength=round(strength, 3),
        expected_move_pct=impact.expected_stock_move_pct,
        time_horizon_weeks=forecast_horizon_weeks,
        harvest_impact=impact,
        lice_trend=lice_trend,
        prob_exceed_threshold=prob_exceed,
        rationale=" ".join(rationale_parts),
    )
