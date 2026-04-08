"""
Feed Supply Chain Routes
========================
Endpoints for feed ingredient sourcing, EUDR compliance, and scenario modeling.
"""
from __future__ import annotations

from fastapi import APIRouter
from core.cache import cached

router = APIRouter(prefix="/api/feed-supply-chain", tags=["feed-supply-chain"])


@router.get("/summary")
@cached(ttl=1800, key_prefix="feed_supply_chain_summary")
async def feed_supply_chain_summary():
    """
    Get feed supply chain overview with EUDR compliance.

    Returns: composition breakdown, EUDR risk assessment, carbon footprint,
    cost scenarios, and Sankey flow data.
    """
    from core.market.feed_supply_chain import feed_supply_chain
    return feed_supply_chain.get_supply_chain_summary()


@router.get("/eudr-risk")
@cached(ttl=1800, key_prefix="feed_supply_chain_eudr")
async def eudr_risk_assessment():
    """
    Assess EU Deforestation Regulation (EUDR) compliance risk.

    Evaluates soy and other commodity origins against EUDR requirements.
    Returns risk level, factors, and remediation recommendations.
    """
    from core.market.feed_supply_chain import feed_supply_chain
    ingredients = feed_supply_chain.get_standard_feed_composition()
    risk = feed_supply_chain.assess_eudr_risk(ingredients)
    return {
        "risk_level": risk.risk_level,
        "eudr_status": risk.eudr_status,
        "deforestation_pct": risk.deforestation_pct,
        "risk_factors": risk.risk_factors,
        "recommendation": risk.recommendation,
        "assessed_at": risk.assessed_at.isoformat(),
    }


@router.get("/scenarios")
@cached(ttl=1800, key_prefix="feed_supply_chain_scenarios")
async def feed_cost_scenarios():
    """
    Model alternative feed sourcing scenarios.

    Compares current baseline against:
    - Soy price spike (+20%)
    - Fishmeal shortage (+40%)
    - Insect meal substitution (replace 50% soy with BSF larvae)
    - Algae oil substitution (replace fish oil with algae DHA/EPA)
    """
    from core.market.feed_supply_chain import feed_supply_chain
    ingredients = feed_supply_chain.get_standard_feed_composition()
    return feed_supply_chain.model_cost_scenarios(ingredients)


@router.get("/live")
@cached(ttl=600, key_prefix="feed_supply_chain_live")
async def feed_supply_chain_live():
    """
    Live feed supply chain data with FRED price overlay.

    Combines live commodity prices from FeedCostEngine with supply chain
    origin tracing and EUDR compliance assessment.
    """
    from core.market.feed_supply_chain import feed_supply_chain
    return await feed_supply_chain.get_feed_cost_with_supply_chain()
