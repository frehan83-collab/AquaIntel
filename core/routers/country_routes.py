"""
Country-Specific Routes
========================
Extracted from core/api.py for maintainability.
Chile, Iceland, Canada, Scotland, Faroe Islands, China demand indicators.
"""
from __future__ import annotations

from fastapi import APIRouter

from core.market.data_provenance import DataProvenance
from core.cache import cached

router = APIRouter(prefix="/api", tags=["countries"])


# ── Chile ──────────────────────────────────────────────────────────────

@router.get("/chile/snapshot")
@cached(ttl=900, key_prefix="chile_snapshot")
async def chile_snapshot():
    """Get latest Chilean salmon supply snapshot."""
    from core.market.chile_monitor import chile_monitor
    snapshot = chile_monitor.get_latest_snapshot()
    if not snapshot:
        await chile_monitor.fetch_chile_data()
        snapshot = chile_monitor.get_latest_snapshot()
    result = snapshot or {"status": "no_data"}
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Sernapesca aquaculture authority", confidence=0.85).to_dict()
    return result


@router.get("/chile/signals")
async def chile_signals(days: int = 30):
    """Get cross-market arbitrage signals."""
    from core.market.chile_monitor import chile_monitor
    result = chile_monitor.get_signals(days)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Sernapesca aquaculture authority", confidence=0.85).to_dict()
    return result


@router.get("/chile/global-supply")
async def chile_global_supply():
    """Get global salmon supply balance model."""
    from core.market.chile_monitor import chile_monitor
    result = chile_monitor.get_global_supply_model()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Sernapesca aquaculture authority", confidence=0.85).to_dict()
    return result


@router.post("/chile/refresh")
async def chile_refresh():
    """Force refresh Chilean supply data."""
    from core.market.chile_monitor import chile_monitor
    snapshot = await chile_monitor.fetch_chile_data()
    return {
        "status": "refreshed",
        "disruption_score": snapshot.supply_disruption_score,
        "data_provenance": DataProvenance.live("Sernapesca aquaculture authority", confidence=0.85).to_dict(),
    }


@router.get("/chile/farms")
async def chile_farms():
    """Chilean production regions as GeoJSON."""
    from core.market.chile_monitor import chile_monitor
    result = chile_monitor.get_farms_geojson()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Sernapesca aquaculture authority", confidence=0.85).to_dict()
    return result


# ── Iceland ────────────────────────────────────────────────────────────

@router.get("/iceland/snapshot")
@cached(ttl=900, key_prefix="iceland_snapshot")
async def iceland_snapshot():
    """Full Iceland aquaculture snapshot — production, ocean, weather, disease, MAB."""
    from core.market.iceland_monitor import iceland_monitor
    snapshot = await iceland_monitor.get_snapshot()
    sea = snapshot.sea_conditions
    return {
        "sources": [
            "Statistics Iceland (Hagstofa) — production & exports",
            "Copernicus CMEMS Arctic — SST & chlorophyll",
            "Vedur.is — weather observations",
            "Fiskistofa — MAB licenses",
            "WOAH WAHIS — disease surveillance",
        ],
        "disease_status": snapshot.disease_status,
        "disease_events": snapshot.disease_events,
        "disruption": snapshot.disruption_level,
        "disruption_pct": snapshot.disruption_pct,
        "total_mab_tonnes": snapshot.total_mab_tonnes,
        "sea_conditions": {
            "westfjords": {
                "sst_c": sea.westfjords_sst,
                "chl_a_mg_m3": sea.westfjords_chl_a,
                "bloom_risk": sea.bloom_risk_westfjords,
                "air_temp_c": sea.westfjords_air_temp,
                "wind_ms": sea.westfjords_wind_ms,
            },
            "eastfjords": {
                "sst_c": sea.eastfjords_sst,
                "chl_a_mg_m3": sea.eastfjords_chl_a,
                "bloom_risk": sea.bloom_risk_eastfjords,
                "air_temp_c": sea.eastfjords_air_temp,
                "wind_ms": sea.eastfjords_wind_ms,
            },
        },
        "production_history": [
            {
                "year": p.year,
                "salmon_tonnes": p.salmon_tonnes,
                "arctic_char_tonnes": p.arctic_char_tonnes,
                "rainbow_trout_tonnes": p.rainbow_trout_tonnes,
                "total_tonnes": p.total_tonnes,
            }
            for p in snapshot.production_history[-10:]  # last 10 years
        ],
        "exports": [
            {"year": e.year, "value_isk_m": e.total_value_isk_millions, "weight_t": e.total_weight_tonnes}
            for e in snapshot.exports[-10:]
        ],
        "licenses": [
            {"company": l.company, "location": l.location, "region": l.region, "mab_tonnes": l.mab_tonnes}
            for l in snapshot.licenses
        ],
        "farms_count": len(snapshot.farms),
        "insights": snapshot.insights,
        "data_note": "Iceland data may be delayed. Annual production from Statistics Iceland. No public per-site lice data.",
        "data_provenance": DataProvenance.live("Statistics Iceland + CMEMS + Vedur.is", confidence=0.85).to_dict(),
    }


@router.get("/iceland/production")
async def iceland_production():
    """Iceland salmon production history from Statistics Iceland PxWeb API."""
    from core.market.iceland_monitor import iceland_monitor
    snapshot = await iceland_monitor.get_snapshot()
    return {
        "source": "Statistics Iceland (Hagstofa)",
        "production_history": [
            {
                "year": p.year,
                "salmon_tonnes": p.salmon_tonnes,
                "arctic_char_tonnes": p.arctic_char_tonnes,
                "rainbow_trout_tonnes": p.rainbow_trout_tonnes,
                "total_tonnes": p.total_tonnes,
            }
            for p in snapshot.production_history
        ],
        "data_provenance": DataProvenance.live("Statistics Iceland + CMEMS + Vedur.is", confidence=0.85).to_dict(),
    }


@router.get("/iceland/farms")
async def iceland_farms():
    """Iceland farm locations as GeoJSON with ocean condition overlays."""
    from core.market.iceland_monitor import iceland_monitor
    try:
        await iceland_monitor.get_snapshot()
    except Exception:
        pass  # farm locations work without snapshot
    result = iceland_monitor.get_farms_geojson()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Statistics Iceland + CMEMS + Vedur.is", confidence=0.85).to_dict()
    return result


@router.get("/iceland/exports")
async def iceland_exports():
    """Iceland aquaculture export data by year and destination country."""
    from core.market.iceland_monitor import iceland_monitor
    exports = await iceland_monitor.fetch_exports()
    by_country = await iceland_monitor.fetch_export_by_country()
    return {
        "source": "Statistics Iceland (Hagstofa) — SJA04905, SJA07003",
        "annual_totals": [
            {"year": e.year, "value_isk_m": e.total_value_isk_millions, "weight_t": e.total_weight_tonnes}
            for e in exports
        ],
        "by_destination": by_country[-50:],  # last 50 records
        "data_provenance": DataProvenance.live("Statistics Iceland + CMEMS + Vedur.is", confidence=0.85).to_dict(),
    }


# ── Canada / BC ────────────────────────────────────────────────────────

@router.get("/canada/snapshot")
@cached(ttl=900, key_prefix="canada_snapshot")
async def canada_snapshot():
    """Canada/BC aquaculture snapshot — DFO lice, mortality, disease, CMEMS."""
    from core.market.canada_monitor import canada_monitor
    s = await canada_monitor.get_snapshot()
    return {
        "sources": [
            "DFO Open Data (sea lice, mortality, fish health) — Open Government Licence Canada",
            "CMEMS Global (SST, chlorophyll)",
        ],
        "lice": {
            "avg_per_fish": s.avg_lice,
            "farms_above_threshold": s.farms_above_threshold,
            "total_farms_reporting": s.total_farms_reporting,
            "records_last_6m": len(s.lice_records),
        },
        "mortality_events_6m": s.recent_mortality_events,
        "disease_events_12m": s.disease_events,
        "sea_conditions": {
            "sst_c": s.avg_sst,
            "chl_a_mg_m3": s.avg_chl_a,
            "bloom_risk": s.bloom_risk,
        },
        "disruption": s.disruption_level,
        "disruption_pct": s.disruption_pct,
        "insights": s.insights,
        "data_note": "BC open-net pen licences expire 2029 under federal transition policy.",
        "data_provenance": DataProvenance.live("DFO Open Data (7 CSV datasets)", confidence=0.90).to_dict(),
    }


@router.get("/canada/farms")
async def canada_farms():
    """BC farm locations as GeoJSON — extracted from DFO per-farm lice data."""
    from core.market.canada_monitor import canada_monitor
    try:
        await canada_monitor.get_snapshot()
    except Exception:
        pass  # fallback to BC_REGIONS hardcoded
    result = canada_monitor.get_farms_geojson()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("DFO Open Data (7 CSV datasets)", confidence=0.90).to_dict()
    return result


@router.get("/canada/lice")
async def canada_lice():
    """Recent DFO sea lice monitoring data for BC salmon farms."""
    from core.market.canada_monitor import canada_monitor
    s = await canada_monitor.get_snapshot()
    return {
        "source": "DFO Industry Sea Lice Counts (open.canada.ca)",
        "avg_lice_per_fish": s.avg_lice,
        "farms_above_threshold": s.farms_above_threshold,
        "total_records": len(s.lice_records),
        "records": [
            {"facility": r.facility, "company": r.company, "lat": r.lat, "lng": r.lng,
             "date": r.date, "avg_lice": r.avg_lice_per_fish}
            for r in s.lice_records[:100]
        ],
        "data_provenance": DataProvenance.live("DFO Open Data (7 CSV datasets)", confidence=0.90).to_dict(),
    }


@router.get("/canada/lice-by-region")
async def canada_lice_by_region():
    """DFO lice data grouped by 8 BC regions with monthly averages for trend charting."""
    from core.market.canada_monitor import canada_monitor
    try:
        await canada_monitor.get_snapshot()
    except Exception:
        pass
    result = canada_monitor.get_lice_by_region()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("DFO Open Data (7 CSV datasets)", confidence=0.90).to_dict()
    return result


# ── Scotland ───────────────────────────────────────────────────────────

@router.get("/scotland/snapshot")
@cached(ttl=900, key_prefix="scotland_snapshot")
async def scotland_snapshot():
    """Scotland aquaculture snapshot — CMEMS ocean conditions, disease, production."""
    from core.market.scotland_monitor import scotland_monitor
    s = await scotland_monitor.get_snapshot()
    return {
        "sources": ["Marine Scotland", "CMEMS NW Shelf", "WOAH WAHIS"],
        "production_tonnes": s.annual_production_tonnes,
        "total_sites": s.total_sites,
        "disease_events": s.disease_events,
        "pd_status": s.pd_status,
        "disruption": s.disruption_level,
        "sea_conditions": {
            "sst_c": s.sea_conditions.avg_sst,
            "chl_a_mg_m3": s.sea_conditions.avg_chl_a,
            "bloom_risk": s.sea_conditions.bloom_risk,
        },
        "regions": s.regions,
        "insights": s.insights,
        "data_provenance": DataProvenance.live("Marine Scotland DKAN", confidence=0.80).to_dict(),
    }


@router.get("/scotland/farms")
async def scotland_farms():
    """Scottish farm regions as GeoJSON."""
    from core.market.scotland_monitor import scotland_monitor
    try:
        await scotland_monitor.get_snapshot()
    except Exception:
        pass
    result = scotland_monitor.get_farms_geojson()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Marine Scotland DKAN", confidence=0.80).to_dict()
    return result


# ── Faroe Islands ──────────────────────────────────────────────────────

@router.get("/faroe/snapshot")
@cached(ttl=900, key_prefix="faroe_snapshot")
async def faroe_snapshot():
    """Faroe Islands aquaculture snapshot — Hagstova production, CMEMS, disease."""
    from core.market.faroe_monitor import faroe_monitor
    s = await faroe_monitor.get_snapshot()
    return {
        "sources": ["Hagstova Føroya (PxWeb)", "CMEMS Global", "WOAH WAHIS"],
        "production_history": [
            {"year": p.year, "salmon_t": p.salmon_tonnes, "trout_t": p.trout_tonnes, "total_t": p.total_tonnes}
            for p in s.production_history[-10:]
        ],
        "sst_c": s.avg_sst,
        "chl_a_mg_m3": s.avg_chl_a,
        "bloom_risk": s.bloom_risk,
        "disease_events": s.disease_events,
        "disruption": s.disruption_level,
        "regions": s.regions,
        "insights": s.insights,
        "data_provenance": DataProvenance.live("Hagstova Føroya", confidence=0.80).to_dict(),
    }


@router.get("/faroe/farms")
async def faroe_farms():
    """Faroese farm regions as GeoJSON."""
    from core.market.faroe_monitor import faroe_monitor
    try:
        await faroe_monitor.get_snapshot()
    except Exception:
        pass
    result = faroe_monitor.get_farms_geojson()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Hagstova Føroya", confidence=0.80).to_dict()
    return result


# ── China Demand Indicators ───────────────────────────────────────────


def _china_provenance(result: dict) -> DataProvenance:
    """Honest provenance for the China demand routes (R10).

    LIVE only when the SSB 08799 Norwegian export series actually came
    through; otherwise the payload is built on curated GACC/Comtrade
    estimates and must say so instead of claiming live data.
    """
    norway = (result or {}).get("norway_exports_to_china") or {}
    if result.get("monthly_series") or norway.get("tonnes_12m"):
        return DataProvenance.live("SSB 08799 (Norway exports) + customs data", confidence=0.75)
    return DataProvenance.degraded(
        "GACC/Comtrade estimates (SSB 08799 unavailable)",
        reason="live Norwegian export series unavailable — using curated estimates",
        confidence=0.5,
    )


@router.get("/china/demand")
async def china_demand_snapshot():
    """China demand snapshot: LIVE Norwegian exports (SSB) + structured global estimates."""
    from core.market.china_demand import china_demand_engine
    result = await china_demand_engine.get_snapshot()
    if isinstance(result, dict):
        result["data_provenance"] = _china_provenance(result).to_dict()
    return result


@router.get("/china/demand-signals")
async def china_demand_signals():
    """China demand momentum: YoY growth, acceleration, seasonal, composite signal."""
    from core.market.china_demand import china_demand_engine
    result = await china_demand_engine.get_demand_signals()
    if isinstance(result, dict):
        snap = await china_demand_engine.get_snapshot()
        result["data_provenance"] = _china_provenance(snap).to_dict()
    return result


@router.get("/china/demand-impact")
async def china_demand_impact():
    """How China demand growth affects Norwegian spot price (correlation + assessment)."""
    from core.market.china_demand import china_demand_engine
    result = await china_demand_engine.get_supply_impact()
    if isinstance(result, dict):
        snap = await china_demand_engine.get_snapshot()
        result["data_provenance"] = _china_provenance(snap).to_dict()
    return result


# ── Scotland Water Quality (SEPA) ────────────────────────────────────

@router.get("/scotland/water-quality")
@cached(ttl=21600)
async def scotland_water_quality():
    """Aggregated water quality near Scottish salmon farming regions from SEPA."""
    from core.market.sepa_client import sepa_client
    summary = await sepa_client.get_scottish_aquaculture_summary()
    return {**summary, "data_provenance": DataProvenance.live("SEPA Time Series API", confidence=0.7).to_dict()}


@router.get("/scotland/water-quality/{region}")
@cached(ttl=21600)
async def scotland_water_quality_region(region: str):
    """Water quality for a specific Scottish farming region."""
    from core.market.sepa_client import sepa_client
    data = await sepa_client.get_region_water_quality(region)
    return {**data, "data_provenance": DataProvenance.live("SEPA Time Series API", confidence=0.7).to_dict()}


# ── Chile Historical Data (Sernapesca) ───────────────────────────────

@router.get("/chile/production-history")
@cached(ttl=86400)
async def chile_production_history():
    """Chilean salmon production history (23 years, Sernapesca yearbooks)."""
    from core.market.sernapesca_historical import sernapesca_historical
    return await sernapesca_historical.fetch_production_history()


@router.get("/chile/disease-history")
@cached(ttl=86400)
async def chile_disease_history():
    """Chilean ISA/SRS disease outbreak history."""
    from core.market.sernapesca_historical import sernapesca_historical
    return await sernapesca_historical.fetch_disease_history()


@router.get("/chile/export-history")
@cached(ttl=86400)
async def chile_export_history():
    """Chilean salmon export volume and value history."""
    from core.market.sernapesca_historical import sernapesca_historical
    return await sernapesca_historical.fetch_export_history()
