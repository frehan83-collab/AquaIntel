"""
Miscellaneous routes: tiers, climate, competitiveness, global-supply,
and regulatory traffic-light endpoints.
Extracted from the original monolithic misc_routes.py (Session 39 decomposition).
Feed-cost, ocean, satellite, causal, AIS, ESG, macro, contracts, regime,
pairs, and RAS routes moved to dedicated router modules.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["misc"])


# ══════════════════════════════════════════════════════════════════════
# TIERS & SUPPLY
# ══════════════════════════════════════════════════════════════════════
@router.get("/api/tiers")
async def list_tiers():
    """List subscription plans and pricing from the ONE entitlement source.

    Enforcement status (core/entitlements.py, docs/ENTITLEMENTS.md):
    - `daily_quota_enforced`: the per-day allowance IS enforced for
      authenticated usage (Bearer JWT / X-API-Key) by core/tier_quota.py.
    - `route_gating_enforced`: premium route gating IS enforced for authenticated
      accounts on the curated premium outputs (HTTP 402 + upgrade payload).
      Anonymous visitors keep browsing — they are not an account, so nothing is
      gated for them (that is the funnel).
    - `api_calls_limit` is the MONTHLY figure DERIVED from the enforced per-day
      quota. This endpoint previously served two contradictory tables (one from
      core/auth.py, one from core/valuechain/subscription.py).
    """
    from core.entitlements import PLANS
    from core.tier_quota import gating_enabled

    return {
        key: {
            "name": plan.name,
            "audience": plan.audience,
            "monthly_price_nok": plan.price_nok_month,
            "api_calls_limit": plan.api_calls_per_month,
            "api_calls_per_day": plan.api_calls_per_day,
            "enforced_api_calls_per_day": plan.api_calls_per_day,
            "features": list(plan.features),
            "seats": plan.seats,
            "sites": plan.sites,
            "daily_quota_enforced": plan.api_calls_per_day > 0,
            "route_gating_enforced": gating_enabled(),
            "premium_outputs_included": plan.premium,
            "upgrade_to": plan.upgrade_to,
        }
        for key, plan in PLANS.items()
    }


# ── Climate ──────────────────────────────────────────────────────────
@router.get("/api/climate/risk-scores")
async def climate_risk_scores():
    from core.market.climate_risk_engine import climate_risk_engine
    return await climate_risk_engine.get_dashboard()


@router.get("/api/climate/pa/{pa}")
async def climate_pa(pa: int):
    from core.market.climate_risk_engine import climate_risk_engine
    scores = await climate_risk_engine.compute_pa_scores()
    match = next((s for s in scores if s.get("pa") == pa), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Production area {pa} not found")
    return match


@router.get("/api/climate/projections")
async def climate_projections(pa: int = 3, years: int = 5):
    from core.market.climate_risk_engine import climate_risk_engine
    from core.market.data_provenance import DataProvenance
    result = await climate_risk_engine.get_projections(pa, years)
    if isinstance(result, dict):
        result.setdefault("data_provenance", DataProvenance.degraded(
            "Climate risk engine (CMIP-style projection over MET.no baseline)",
            reason=(
                "forward projection over a warming scenario — a modelled estimate, "
                "not an observed measurement"
            ),
            confidence=0.4,
        ).to_dict())
    return result


@router.get("/api/climate/heatwave-risk")
async def climate_heatwave_risk():
    """Marine heatwave early warning per production area.
    Compares live SST to seasonal baseline using Hobday et al. (2016) framework.
    Categories: NORMAL (<1°C), WATCH (1-2°C), WARNING (2-3°C), CRITICAL (>3°C)."""
    from core.market.climate_risk_engine import climate_risk_engine
    from core.market.data_provenance import DataProvenance
    result = await climate_risk_engine.marine_heatwave_risk()
    result["data_provenance"] = DataProvenance.live(
        "MET.no Frost + OceanForecast (Hobday et al. 2016)", confidence=0.85
    ).to_dict()
    return result


# ── Competitiveness ──────────────────────────────────────────────────
@router.get("/api/competitiveness/origin-index")
async def competitiveness_origin_index():
    from core.market.competitiveness_engine import competitiveness_engine
    return await competitiveness_engine.compute_index()


@router.post("/api/competitiveness/tariff-scenario")
async def competitiveness_tariff_scenario(request: Request):
    from core.market.competitiveness_engine import competitiveness_engine
    try:
        body = await request.json()
    except Exception:
        body = {}
    return competitiveness_engine.compute_tariff_scenarios(body)


# ── Global Supply ────────────────────────────────────────────────────
@router.get("/api/global-supply")
async def global_supply():
    from core.market.global_supply import global_supply_engine
    from core.market.data_provenance import DataProvenance
    gs = await global_supply_engine.compute()
    result = global_supply_engine.to_dict(gs)
    result["data_provenance"] = DataProvenance.live(
        "Multi-country monitors (Norway + Canada + Chile + Iceland + Faroe + Scotland)", confidence=0.80
    ).to_dict()
    return result


# ── Traffic Light Simulator ──────────────────────────────────────────
@router.get("/api/regulatory/traffic-light/current")
async def traffic_light_current():
    from core.market.traffic_light_simulator import traffic_light_simulator
    from core.market.data_provenance import DataProvenance
    result = await traffic_light_simulator.get_current_colors()
    result["data_provenance"] = DataProvenance.live(
        "BarentsWatch lice data + PA classification rules", confidence=0.85
    ).to_dict()
    return result


@router.get("/api/regulatory/traffic-light/simulate")
async def traffic_light_simulate(pa: int = 3, color: str = "red"):
    from core.market.data_provenance import DataProvenance
    from core.market.traffic_light_simulator import traffic_light_simulator
    result = await traffic_light_simulator.simulate_color_change(pa, color)
    if isinstance(result, dict):
        result.setdefault("data_provenance", DataProvenance.degraded(
            "Traffic-light simulator (hypothetical regulatory scenario)",
            reason=(
                "modelled effect of a counterfactual colour change — a scenario "
                "estimate, not an announced regulatory decision"
            ),
            confidence=0.4,
        ).to_dict())
    return result


@router.get("/api/regulatory/traffic-light/all-scenarios")
async def traffic_light_all_scenarios():
    from core.market.data_provenance import DataProvenance
    from core.market.traffic_light_simulator import traffic_light_simulator
    result = await traffic_light_simulator.simulate_all_pas()
    if isinstance(result, dict):
        result.setdefault("data_provenance", DataProvenance.degraded(
            "Traffic-light simulator (hypothetical regulatory scenario)",
            reason=(
                "modelled effects of counterfactual colour changes — scenario "
                "estimates, not announced regulatory decisions"
            ),
            confidence=0.4,
        ).to_dict())
    return result
