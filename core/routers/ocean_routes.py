"""
Ocean & satellite routes: /api/ocean/*, /api/satellite/*, NorKyst800 v3, NASA PACE.
Extracted from misc_routes.py (Session 39 decomposition).
"""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["ocean", "satellite"])


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
    from core.market.data_provenance import from_records
    from core.market.met_ocean import met_ocean_client
    forecast = await met_ocean_client.get_ocean_forecast(lat, lon)
    if not forecast:
        raise HTTPException(status_code=503, detail=f"Ocean forecast unavailable for lat={lat}, lon={lon}")
    return {
        "lat": lat,
        "lon": lon,
        "forecasts": [
            {"time": f.forecast_time.isoformat(), "temperature_c": f.temperature_c, "hours_ahead": f.hours_ahead}
            for f in forecast
        ],
        "data_provenance": from_records(
            forecast,
            live_source="MET.no OceanForecast 2.0",
            degraded_source="MET.no OceanForecast 2.0",
            reason="MET.no returned no forecast points for this location",
        ).to_dict(),
    }


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


@router.get("/api/ocean/waves/pa/{pa}/forecast")
async def waves_pa_forecast(pa: int, days: int = 5):
    """Daily-mean significant wave height + risk timeline for a Production Area.

    Source: CMEMS GLOBAL_ANALYSISFORECAST_WAV_001_027 (WAM 1/12 deg) daily
    means, up to 5 days ahead. Simulated fallback with is_live=false when
    credentials/data are unavailable (data-honesty contract).
    """
    from core.market.wave_client import wave_client
    from core.market.data_provenance import DataProvenance
    if not 1 <= pa <= 13:
        raise HTTPException(status_code=400, detail="Production area must be 1-13")
    await wave_client.fetch_forecast()  # no-op when cache is fresh
    result = wave_client.get_pa_wave_forecast(pa, days=days)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    if result.get("is_live"):
        result["data_provenance"] = DataProvenance.live(
            "CMEMS WAV (WAM 1/12°, daily means)", confidence=0.8
        ).to_dict()
    else:
        result["data_provenance"] = DataProvenance.simulated(
            result.get("fallback_reason", "CMEMS WAV unavailable")
        ).to_dict()
    return result


# ── CMEMS Wave Field (Session 41) ────────────────────────────────────

@router.get("/api/ocean/waves/status")
async def waves_status():
    """Wave client status: product, dataset, cache freshness, last error."""
    from core.market.wave_client import wave_client
    return wave_client.get_status()


@router.get("/api/ocean/waves/pa/{pa}")
async def waves_pa(pa: int):
    """Significant wave height + operational risk band for a Production Area.

    Source: CMEMS GLOBAL_ANALYSISFORECAST_WAV_001_027 (WAM 1/12 deg), free tier.
    Falls back to a deterministic simulated field with is_live=false when
    credentials/data are unavailable (data-honesty contract).
    """
    from core.market.wave_client import wave_client
    from core.market.data_provenance import DataProvenance
    if not 1 <= pa <= 13:
        raise HTTPException(status_code=400, detail="Production area must be 1-13")
    await wave_client.fetch_waves()  # no-op when cache is fresh
    result = wave_client.get_pa_wave(pa)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    if result.get("is_live"):
        result["data_provenance"] = DataProvenance.live(
            "CMEMS WAV (WAM 1/12°, VHM0)", confidence=0.85
        ).to_dict()
    else:
        result["data_provenance"] = DataProvenance.simulated(
            result.get("fallback_reason", "CMEMS WAV unavailable")
        ).to_dict()
    return result
