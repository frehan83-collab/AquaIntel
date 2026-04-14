"""
Feed cost routes: all /api/feed-cost/* endpoints.
Extracted from misc_routes.py (Session 39 decomposition).
"""
from __future__ import annotations

import datetime as dt
from fastapi import APIRouter

router = APIRouter(tags=["feed-cost"])


@router.get("/api/feed-cost/latest")
async def feed_cost_latest():
    from core.market.feed_cost_engine import feed_cost_engine
    snapshot = await feed_cost_engine.fetch_prices()
    return feed_cost_engine.get_latest() or {"error": "No data available"}

@router.get("/api/feed-cost/history")
async def feed_cost_history(n: int = 50):
    from core.market.feed_cost_engine import feed_cost_engine
    await feed_cost_engine.fetch_prices()
    return feed_cost_engine.get_history(n)

@router.get("/api/feed-cost/historical-prices")
async def feed_cost_historical(years: int = 5):
    from core.market.feed_cost_engine import feed_cost_engine
    years = max(1, min(10, years))
    return await feed_cost_engine.fetch_historical_prices(years)

@router.get("/api/feed-cost/composite-index")
async def feed_cost_composite_index(years: int = 5):
    from core.market.feed_cost_engine import feed_cost_engine
    from core.market.data_provenance import DataProvenance
    years = max(1, min(10, years))
    result = await feed_cost_engine.compute_composite_index(years)
    result["data_provenance"] = DataProvenance.live(
        "FRED commodity APIs (fishmeal, soy, wheat, rapeseed, fish oil)", confidence=0.90,
    ).to_dict()
    return result

@router.get("/api/feed-cost/peru-anchovy")
async def feed_cost_peru_anchovy():
    from core.market.feed_cost_engine import feed_cost_engine
    return await feed_cost_engine.peru_anchovy_watch()

@router.get("/api/feed-cost/enhanced-anchovy")
async def enhanced_anchovy_watch():
    from core.market.feed_cost_engine import feed_cost_engine
    return await feed_cost_engine.enhanced_anchovy_watch()

@router.get("/api/feed-cost/alerts")
async def feed_cost_alerts():
    from core.market.feed_cost_engine import feed_cost_engine
    anchovy = await feed_cost_engine.enhanced_anchovy_watch()
    try:
        composite = await feed_cost_engine.compute_composite_index()
    except Exception:
        composite = None
    alerts = []
    if anchovy.get("alert_level") in ("warning", "critical"):
        alerts.append({"type": "anchovy_disruption", "severity": anchovy["alert_level"],
                       "message": f"Peru anchovy {anchovy.get('season_status', 'unknown')}: {anchovy.get('fishmeal_price_signal', 'unknown')} for fishmeal",
                       "expected_impact_weeks": anchovy.get("expected_impact_weeks")})
    if composite and composite.get("volatility_alert"):
        alerts.append({"type": "feed_cost_volatility", "severity": "warning",
                       "message": "Feed cost index volatility above 1.5x baseline"})
    return {"alerts": alerts, "anchovy": anchovy, "generated_at": dt.datetime.now(dt.UTC).isoformat()}

@router.get("/api/feed-cost/official-history")
async def feed_cost_official_history():
    from core.market.feed_cost_engine import FeedCostEngine
    return {"source": "Fiskeridirektoratet lonnsomhetsundersokelse 2008-2024",
            "unit": "NOK/kg (round weight)", "data": FeedCostEngine.get_official_cost_history()}
