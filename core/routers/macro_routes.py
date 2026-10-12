"""
Macro intelligence routes: /api/ais/*, /api/regime/*, /api/pairs/*,
/api/esg/*, /api/macro/*, /api/contracts/*.
Extracted from misc_routes.py (Session 39 decomposition).
"""
from __future__ import annotations

import datetime as dt
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["macro"])


# ── AIS ──────────────────────────────────────────────────────────────
@router.get("/api/ais/tracks")
async def ais_tracks():
    from core.market.ais_tracker import ais_tracker
    await ais_tracker.poll_ais_positions()
    return ais_tracker.get_active_tracks()


@router.get("/api/ais/harvest-signals")
async def ais_harvest_signals(hours: int = 72):
    from core.market.ais_tracker import ais_tracker
    return ais_tracker.get_harvest_signals(hours)


@router.get("/api/ais/treatment-signals")
async def ais_treatment_signals(hours: int = 72):
    from core.market.ais_tracker import ais_tracker
    return ais_tracker.get_treatment_signals(hours)


@router.get("/api/ais/supply-intelligence")
async def ais_supply_intelligence():
    from core.market.ais_tracker import ais_tracker
    return ais_tracker.get_supply_intelligence()


@router.get("/api/ais/harvest-intelligence")
async def ais_harvest_intelligence():
    from core.market.ais_tracker import ais_tracker
    tracks = ais_tracker.get_active_tracks()
    harvest_signals = ais_tracker.get_harvest_signals(72)
    treatment_signals = ais_tracker.get_treatment_signals(72)
    at_farm = [t for t in tracks if t.get("activity") == "at_farm"]
    harvesting = [t for t in tracks if t.get("activity") == "harvest_run"]
    treating = [t for t in tracks if t.get("activity") == "treatment_run"]
    transiting = [t for t in tracks if t.get("activity") not in ("at_farm", "harvest_run", "treatment_run")]
    n_harvest = len(harvesting) + len(harvest_signals)
    supply_pressure = "high" if n_harvest >= 5 else "moderate" if n_harvest >= 2 else "low"
    treatment_pressure = "high" if len(treating) >= 3 else "moderate" if len(treating) >= 1 else "low"
    return {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "total_vessels": len(tracks),
        "summary": {"at_farm": len(at_farm), "harvesting": len(harvesting), "treating": len(treating), "transiting": len(transiting)},
        "supply_pressure": supply_pressure, "treatment_pressure": treatment_pressure,
        "harvest_signals_72h": [{"vessel": s.get("name", s.get("mmsi")), "farm": s.get("near_farm"),
                                  "detected_at": s.get("detected_at"), "confidence": s.get("confidence", "medium")}
                                 for s in harvest_signals[:10]],
        "treatment_signals_72h": [{"vessel": s.get("name", s.get("mmsi")), "farm": s.get("near_farm"),
                                    "detected_at": s.get("detected_at"), "type": s.get("treatment_type", "unknown")}
                                   for s in treatment_signals[:10]],
        "price_signal": "bearish" if supply_pressure == "high" else "neutral",
        "signal_rationale": (f"{n_harvest} harvest vessel(s) detected -> increased supply pressure -> potential short-term price pressure"
                             if supply_pressure != "low" else "No significant harvest activity detected"),
    }


# ── Regime ───────────────────────────────────────────────────────────
@router.get("/api/regime/states")
async def regime_states():
    from core.market.regime_detector import regime_detector
    return regime_detector.get_all_states()


@router.get("/api/regime/alerts")
async def regime_alerts():
    from core.market.regime_detector import regime_detector
    return regime_detector.get_alerts()


@router.get("/api/regime/pa/{pa}")
async def regime_pa_detail(pa: int):
    from core.market.regime_detector import regime_detector
    result = regime_detector.get_pa_detail(pa)
    if not result:
        raise HTTPException(404, f"PA {pa} not found")
    return result


@router.get("/api/regime/company-risk")
async def regime_company_risk():
    from core.market.regime_detector import regime_detector
    return regime_detector.get_company_regulatory_risk()


# ── Pairs ────────────────────────────────────────────────────────────
@router.get("/api/pairs/all")
async def pairs_all():
    from core.market.pairs_engine import pairs_engine
    return pairs_engine.get_all_pairs()


@router.get("/api/pairs/signals")
async def pairs_signals(days: int = 7):
    from core.market.pairs_engine import pairs_engine
    return pairs_engine.get_signals(days)


@router.get("/api/pairs/{pair_name}")
async def pairs_detail(pair_name: str):
    from core.market.pairs_engine import pairs_engine
    result = pairs_engine.get_pair_detail(pair_name)
    if not result:
        raise HTTPException(404, f"Pair {pair_name} not found")
    return result


# ── ESG ──────────────────────────────────────────────────────────────
@router.get("/api/esg/scores")
async def esg_scores():
    from core.market.esg_scorer import esg_scorer
    return await esg_scorer.get_all()


@router.get("/api/esg/summary")
async def esg_summary():
    from core.market.esg_scorer import esg_scorer
    return await esg_scorer.get_summary()


@router.get("/api/esg/company/{company_name}")
async def esg_company(company_name: str):
    import urllib.parse
    from core.market.esg_scorer import esg_scorer
    decoded = urllib.parse.unquote(company_name)
    result = await esg_scorer.get_company(decoded)
    if not result:
        raise HTTPException(404, f"Company not found: {decoded}")
    return result


# ── Macro ────────────────────────────────────────────────────────────
@router.get("/api/macro/snapshot")
async def macro_snapshot():
    from core.market.macro_intelligence import macro_intelligence
    await macro_intelligence.fetch()
    snapshot = macro_intelligence.get_snapshot_dict()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Macro intelligence data not available")
    return snapshot


@router.get("/api/macro/series/{name}")
async def macro_series(name: str, months: int = 60):
    from core.market.macro_intelligence import macro_intelligence
    await macro_intelligence.fetch()
    data = macro_intelligence.get_series_history(name, months)
    if not data:
        raise HTTPException(404, f"Series '{name}' not found")
    return {"name": name, "data": data, "months": months}


# ── Contracts ────────────────────────────────────────────────────────
@router.post("/api/contracts/evaluate")
async def contracts_evaluate(request: Request):
    from core.market.contract_risk_engine import contract_risk_engine
    body = await request.json()
    return await contract_risk_engine.evaluate_contract(body)


@router.post("/api/contracts/portfolio")
async def contracts_portfolio(request: Request):
    from core.market.contract_risk_engine import contract_risk_engine
    body = await request.json()
    return await contract_risk_engine.get_portfolio_risk(body.get("positions", []))


@router.get("/api/contracts/hedge-signals")
async def contracts_hedge_signals():
    from core.market.contract_risk_engine import contract_risk_engine
    return await contract_risk_engine.get_market_context()
