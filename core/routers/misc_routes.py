"""
Miscellaneous routes: pairs, regime, esg, ras, contracts, macro, climate,
satellite, competitiveness, tiers, feed-cost, regulatory,
ocean, causal, ais, global-supply endpoints.
Extracted from core/api.py (Session 10). Bloom, market, supply, country,
traceability, and ML routes moved to dedicated router modules.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, func, case

from core.models import LiceRecord
from core.async_db import get_async_session

router = APIRouter(tags=["misc"])


# ══════════════════════════════════════════════════════════════════════
# TIERS & SUPPLY
# ══════════════════════════════════════════════════════════════════════

@router.get("/api/tiers")
async def list_tiers():
    """List available subscription tiers and pricing."""
    from core.valuechain.subscription import TIERS
    return {
        name: {
            "name": t.name,
            "monthly_price_nok": t.monthly_price_nok,
            "api_calls_limit": t.api_calls_limit,
            "features": t.features,
        }
        for name, t in TIERS.items()
    }






# ══════════════════════════════════════════════════════════════════════
# FEED COST, OCEAN, CAUSAL, REGIME, PAIRS, ESG, MACRO, etc.
# ══════════════════════════════════════════════════════════════════════

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


# ── Ocean ────────────────────────────────────────────────────────────

@router.get("/api/ocean/currents/status")
async def ocean_currents_status():
    from core.market.ocean_currents import ocean_currents
    return ocean_currents.get_status()

@router.post("/api/ocean/currents/refresh")
async def ocean_currents_refresh():
    from core.market.ocean_currents import ocean_currents
    try:
        await asyncio.to_thread(ocean_currents.fetch_currents)
        return {"status": "refreshed", **ocean_currents.get_status()}
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}

@router.get("/api/ocean/temperature")
async def ocean_temperature(lat: float, lon: float):
    from core.market.ocean_currents import ocean_currents
    temp = ocean_currents.get_temperature(lat, lon)
    return {"lat": lat, "lon": lon, "temp_c": temp,
            "source": "CMEMS NorKyst800" if temp is not None else "unavailable"}

@router.get("/api/ocean/forecast")
async def ocean_forecast(lat: float = 65.0, lon: float = 12.0):
    from core.market.met_ocean import met_ocean_client
    forecast = await met_ocean_client.get_ocean_forecast(lat, lon)
    if not forecast:
        return {"error": "Forecast unavailable", "lat": lat, "lon": lon}
    return {"lat": lat, "lon": lon, "forecasts": [
        {"time": f.forecast_time.isoformat(), "temperature_c": f.temperature_c, "hours_ahead": f.hours_ahead}
        for f in forecast
    ]}

@router.get("/api/ocean/forecast/pa/{pa}")
async def ocean_forecast_pa(pa: int):
    from core.market.met_ocean import met_ocean_client
    from core.market.data_provenance import DataProvenance
    summary = await met_ocean_client.get_pa_forecast(pa)
    if not summary:
        return {"production_area": pa, "error": "No forecast data",
                "data_provenance": DataProvenance.degraded("MET.no OceanForecast", "No data returned").to_dict()}
    summary["data_provenance"] = DataProvenance.live("MET.no OceanForecast 2.0", confidence=0.90).to_dict()
    return summary


# ── Causal ───────────────────────────────────────────────────────────

@router.get("/api/causal/summary")
async def causal_summary(max_lag: int = 16):
    from core.market.causal_engine import causal_engine
    from core.market.ssb_price_client import ssb_price_client

    async with get_async_session() as s:
        rows = (await s.execute(
            select(
                LiceRecord.year, LiceRecord.week,
                func.avg(LiceRecord.avg_adult_female_lice),
                func.sum(case((LiceRecord.avg_adult_female_lice > 0.5, 1), else_=0)),
                func.count(LiceRecord.id),
            ).where(LiceRecord.avg_adult_female_lice.isnot(None))
            .group_by(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year, LiceRecord.week)
        )).all()

    if not rows or len(rows) < 30:
        raise HTTPException(400, f"Insufficient lice data: {len(rows) if rows else 0} weeks (need >=30)")

    lice_series = [float(r[2] or 0) for r in rows]
    pct_above_series = [float((r[3] or 0) / max(r[4] or 1, 1)) for r in rows]

    try:
        ssb_data = await ssb_price_client.fetch_prices(n_weeks=len(rows) + 10)
        price_series = [float(p.price_nok_kg) for p in ssb_data.prices[-len(rows):]]
    except Exception:
        raise HTTPException(503, "SSB price data unavailable")

    n = min(len(lice_series), len(price_series), len(pct_above_series))
    causal_engine.load_data(lice_series=lice_series[-n:], price_series=price_series[-n:],
                            pct_above_series=pct_above_series[-n:])
    return causal_engine.get_causal_summary(max_lag=max_lag)

@router.get("/api/causal/granger")
async def causal_granger(max_lag: int = 16):
    from core.market.causal_engine import causal_engine
    if causal_engine._lice is None:
        raise HTTPException(400, "No data loaded. Call /api/causal/summary first.")
    results_dict = causal_engine.run_granger(max_lag=max_lag)
    results_list = [{"lag": lag, **vals} for lag, vals in sorted(results_dict.items())] if results_dict else []
    return {"results": results_list, "dominant_lag": causal_engine.find_dominant_lag(max_lag=max_lag)}


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
    return esg_scorer.get_all()

@router.get("/api/esg/summary")
async def esg_summary():
    from core.market.esg_scorer import esg_scorer
    return await esg_scorer.get_summary()

@router.get("/api/esg/company/{company_name}")
async def esg_company(company_name: str):
    import urllib.parse
    from core.market.esg_scorer import esg_scorer
    decoded = urllib.parse.unquote(company_name)
    result = esg_scorer.get_company(decoded)
    if not result:
        raise HTTPException(404, f"Company not found: {decoded}")
    return result


# ── Macro ────────────────────────────────────────────────────────────

@router.get("/api/macro/snapshot")
async def macro_snapshot():
    from core.market.macro_intelligence import macro_intelligence
    await macro_intelligence.fetch()
    return macro_intelligence.get_snapshot_dict() or {"error": "No data"}

@router.get("/api/macro/series/{name}")
async def macro_series(name: str, months: int = 60):
    from core.market.macro_intelligence import macro_intelligence
    await macro_intelligence.fetch()
    data = macro_intelligence.get_series_history(name, months)
    if not data:
        raise HTTPException(404, f"Series '{name}' not found")
    return {"name": name, "data": data, "months": months}


# ── Climate ──────────────────────────────────────────────────────────

@router.get("/api/climate/risk-scores")
async def climate_risk_scores():
    from core.market.climate_risk_engine import climate_risk_engine
    return await climate_risk_engine.get_dashboard()

@router.get("/api/climate/pa/{pa}")
async def climate_pa(pa: int):
    from core.market.climate_risk_engine import climate_risk_engine
    scores = await climate_risk_engine.compute_pa_scores()
    return next((s for s in scores if s.get("pa") == pa), {"error": f"PA {pa} not found"})

@router.get("/api/climate/projections")
async def climate_projections(pa: int = 3, years: int = 5):
    from core.market.climate_risk_engine import climate_risk_engine
    return await climate_risk_engine.get_projections(pa, years)

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


# ── Satellite ────────────────────────────────────────────────────────

@router.get("/api/satellite/status")
async def satellite_status():
    from core.market.satellite_engine import satellite_engine
    return satellite_engine.get_status()

@router.get("/api/satellite/products")
async def satellite_products():
    from core.market.satellite_engine import satellite_engine
    return satellite_engine.get_products()

@router.post("/api/satellite/scan")
async def satellite_scan(n_farms: int = 50):
    from core.market.satellite_engine import satellite_engine
    from dataclasses import asdict
    snapshot = await satellite_engine.scan_farms(n_farms=n_farms)
    return asdict(snapshot) if hasattr(snapshot, '__dataclass_fields__') else snapshot

@router.get("/api/satellite/anomalies")
async def satellite_anomalies():
    from core.market.satellite_engine import satellite_engine
    if satellite_engine._cache:
        return satellite_engine._cache.anomalies
    return []


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



# ── RAS ──────────────────────────────────────────────────────────────

@router.get("/api/ras/companies")
async def ras_companies():
    from core.market.ras_tracker import ras_tracker
    return ras_tracker.get_companies()

@router.get("/api/ras/summary")
async def ras_summary():
    from core.market.ras_tracker import ras_tracker
    return ras_tracker.get_global_summary()

@router.get("/api/ras/timeline")
async def ras_timeline():
    from core.market.ras_tracker import ras_tracker
    return ras_tracker.get_timeline()



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
    from core.market.traffic_light_simulator import traffic_light_simulator
    return await traffic_light_simulator.simulate_color_change(pa, color)

@router.get("/api/regulatory/traffic-light/all-scenarios")
async def traffic_light_all_scenarios():
    from core.market.traffic_light_simulator import traffic_light_simulator
    return await traffic_light_simulator.simulate_all_pas()


# ══════════════════════════════════════════════════════════════════════
# NORKYST v3 OCEAN MODEL
# ══════════════════════════════════════════════════════════════════════

@router.get("/api/ocean/norkyst/current")
async def norkyst_current(lat: float, lon: float):
    """Current ocean conditions from NorKyst800 v3 (MET.no THREDDS)."""
    from core.market.norkyst_client import norkyst_client
    from core.market.data_provenance import DataProvenance
    conditions = await norkyst_client.fetch_current_conditions(lat, lon)
    if not conditions:
        raise HTTPException(status_code=404, detail="No NorKyst data for location")
    result = conditions.to_dict()
    result["data_provenance"] = DataProvenance.live(
        "MET.no THREDDS NorKyst800 v3 (800m resolution)", confidence=0.90,
    ).to_dict()
    return result

@router.get("/api/ocean/norkyst/pa/{pa}")
async def norkyst_pa_summary(pa: int):
    """Ocean summary for a Norwegian Production Area from NorKyst800 v3."""
    from core.market.norkyst_client import norkyst_client, PA_CENTROIDS
    from core.market.data_provenance import DataProvenance
    if pa not in PA_CENTROIDS:
        raise HTTPException(status_code=400, detail=f"Invalid PA: {pa}. Valid: 1-13")
    summary = await norkyst_client.fetch_pa_ocean_summary(pa)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No NorKyst data for PA {pa}")
    result = summary.to_dict()
    result["data_provenance"] = DataProvenance.live(
        "MET.no THREDDS NorKyst800 v3 (800m resolution)", confidence=0.90,
    ).to_dict()
    return result


# ══════════════════════════════════════════════════════════════════════
# NASA PACE SATELLITE (HAB / CHLOROPHYLL)
# ══════════════════════════════════════════════════════════════════════

@router.get("/api/satellite/pace/chlorophyll")
async def pace_chlorophyll(lat: float, lon: float, date: str = ""):
    """Chlorophyll-a from NASA PACE OCI hyperspectral sensor."""
    from core.market.nasa_pace_client import nasa_pace_client
    from core.market.data_provenance import DataProvenance
    reading = await nasa_pace_client.fetch_chlorophyll(
        lat, lon, date if date else None
    )
    if not reading:
        raise HTTPException(status_code=404, detail="No PACE data for location/date")
    result = reading.to_dict()
    result["data_provenance"] = DataProvenance.live(
        "NASA PACE OCI L3m NRT (hyperspectral ocean color)", confidence=0.85,
    ).to_dict()
    return result

@router.get("/api/satellite/pace/hab-risk")
async def pace_hab_risk(lat: float, lon: float, date: str = ""):
    """Harmful algal bloom risk assessment from NASA PACE data."""
    from core.market.nasa_pace_client import nasa_pace_client
    from core.market.data_provenance import DataProvenance
    assessment = await nasa_pace_client.fetch_hab_risk(
        lat, lon, date if date else None
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="No PACE HAB data for location/date")
    result = assessment.to_dict()
    result["data_provenance"] = DataProvenance.live(
        "NASA PACE OCI L3m NRT + HAB species heuristics", confidence=0.75,
    ).to_dict()
    return result



