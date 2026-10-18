"""
Feed cost routes: all /api/feed-cost/* endpoints.
Extracted from misc_routes.py (Session 39 decomposition).
"""
from __future__ import annotations

import datetime as dt
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["feed-cost"])


# ══════════════════════════════════════════════════════════════════════
# FEED COST ENGINES (FRED commodities, Peru anchovy, composite index)
# ══════════════════════════════════════════════════════════════════════
@router.get("/api/feed-cost/latest")
async def feed_cost_latest():
    """Latest feed cost snapshot — with provenance (WS-29).

    The KPI row on `/feed-cost` used to show a production cost and a margin with no
    provenance at all, while the feed legs behind them are a model on a monthly series
    that lags. The snapshot now carries the same verdict the margin bridge uses
    (``FeedCostSnapshot.price_provenance``): dated, defaulted or undated baskets are
    degraded with the reason, never silently current.
    """
    from core.market.feed_cost_engine import feed_cost_engine
    await feed_cost_engine.fetch_prices()
    latest = feed_cost_engine.get_latest()
    if not latest:
        raise HTTPException(status_code=404, detail="Feed cost data not available")
    return latest


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
    from core.market.data_provenance import from_records
    from core.market.feed_cost_engine import FeedCostEngine
    history = FeedCostEngine.get_official_cost_history()
    return {
        "source": "Fiskeridirektoratet lonnsomhetsundersokelse 2008-2024",
        "unit": "NOK/kg (round weight)",
        "data": history,
        "data_provenance": from_records(
            history,
            live_source="Fiskeridirektoratet lonnsomhetsundersokelse 2008-2024",
            degraded_source="Fiskeridirektoratet lonnsomhetsundersokelse",
            reason="official feed-cost series not loaded",
        ).to_dict(),
    }


# ══════════════════════════════════════════════════════════════════════
# MARGIN BRIDGE — the money view over the price and cost feeds
#
# The one surface that turns "feed cost" and "export price" into a margin per kg
# with every leg dated and sourced, the change decomposed, break-even stated and
# the levers ranked. See core/market/margin_bridge.py for the honesty rules.
# ══════════════════════════════════════════════════════════════════════

@router.get("/api/margin/bridge")
async def margin_bridge_industry(
    fcr: float | None = Query(None, gt=0.5, le=3.0),
    delivered_feed_nok_per_kg: float | None = Query(None, gt=0.0, le=100.0),
    spot_nok_per_kg: float | None = Query(None, gt=0.0, le=500.0),
    annual_tonnes: float | None = Query(None, gt=0.0, le=1_000_000.0),
    standing_tonnes: float | None = Query(None, gt=0.0, le=1_000_000.0),
):
    """Margin per kg on the modelled industry cost base, with what moved and the levers.

    Overrides (``fcr``, ``delivered_feed_nok_per_kg``, ``spot_nok_per_kg``) let a
    producer see their own numbers; only the feed leg moves with them and the
    payload says so. No volume is assumed — NOK totals appear only when
    ``annual_tonnes`` or ``standing_tonnes`` is supplied.
    """
    from core.market.margin_bridge import margin_bridge

    return await margin_bridge.build(
        fcr=fcr,
        delivered_feed_nok_per_kg=delivered_feed_nok_per_kg,
        spot_nok_per_kg=spot_nok_per_kg,
        annual_tonnes=annual_tonnes,
        standing_tonnes=standing_tonnes,
    )


@router.get("/api/margin/bridge/{locality_no}")
async def margin_bridge_farm(
    locality_no: int,
    fcr: float | None = Query(None, gt=0.5, le=3.0),
    delivered_feed_nok_per_kg: float | None = Query(None, gt=0.0, le=100.0),
    spot_nok_per_kg: float | None = Query(None, gt=0.0, le=500.0),
    annual_tonnes: float | None = Query(None, gt=0.0, le=1_000_000.0),
    standing_tonnes: float | None = Query(None, gt=0.0, le=1_000_000.0),
):
    """The industry bridge plus this farm's lice limit for the week and its position.

    The position is ``measured`` only from verified, current lice rows; otherwise it
    is ``unknown`` with the lineage reason. The limit itself is a dated official fact
    (``core.regulatory_facts``), so it is always available.
    """
    from core.market.margin_bridge import margin_bridge

    return await margin_bridge.for_farm(
        locality_no,
        fcr=fcr,
        delivered_feed_nok_per_kg=delivered_feed_nok_per_kg,
        spot_nok_per_kg=spot_nok_per_kg,
        annual_tonnes=annual_tonnes,
        standing_tonnes=standing_tonnes,
    )
