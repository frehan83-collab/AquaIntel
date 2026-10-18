"""
# FROZEN: No new features — complexity vs. value tradeoff (Session 9 decision)
Sentinel-2 Satellite Intelligence Engine
==========================================
Queries 10m-resolution Sentinel-2 imagery from Copernicus Data Space Ecosystem
for salmon farm locations. Computes water quality indices and detects surface
anomalies (bloom confirmation, harvest activity, infrastructure changes).

Data source: Copernicus Sentinel-2 L2A via Sentinel Hub Process API
Resolution: 10m (B02/B03/B04/B08), 20m (B05/B06/B07/B8A/B11/B12)
Revisit: 5 days (twin satellite constellation)
Cost: Free tier — 10,000 openEO credits/month

Setup:
  1. Register at https://dataspace.copernicus.eu
  2. Create OAuth client at https://shapps.dataspace.copernicus.eu/dashboard/
  3. Set env vars: SENTINEL_HUB_CLIENT_ID, SENTINEL_HUB_CLIENT_SECRET
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# ── Configuration ──────────────────────────────────────────────────
from config.settings import settings

# CDSE credentials (from .env via settings, env-var fallback)
SH_CLIENT_ID = settings.sentinel_hub_client_id or os.environ.get("SENTINEL_HUB_CLIENT_ID", "")
SH_CLIENT_SECRET = settings.sentinel_hub_client_secret or os.environ.get("SENTINEL_HUB_CLIENT_SECRET", "")
SH_CONFIGURED = bool(SH_CLIENT_ID and SH_CLIENT_SECRET)

# Evalscript: returns RGB + NIR + NDWI + cloud mask
EVALSCRIPT_WATER_QUALITY = """
//VERSION=3
function setup() {
  return {
    input: [{bands: ["B02","B03","B04","B08","B11","SCL"], units: "DN"}],
    output: {bands: 6, sampleType: "FLOAT32"}
  };
}
function evaluatePixel(s) {
  // NDWI = (Green - NIR) / (Green + NIR)
  let ndwi = (s.B03 - s.B08) / (s.B03 + s.B08 + 0.0001);
  // NDVI = (NIR - Red) / (NIR + Red)
  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 0.0001);
  return [s.B04, s.B03, s.B02, s.B08, ndwi, ndvi];
}
"""

# Simplified evalscript for statistics (mean values over AOI)
EVALSCRIPT_STATS = """
//VERSION=3
function setup() {
  return {
    input: [{bands: ["B02","B03","B04","B08","B11","SCL"]}],
    output: {bands: 5, sampleType: "FLOAT32"}
  };
}
function evaluatePixel(s) {
  let ndwi = (s.B03 - s.B08) / (s.B03 + s.B08 + 0.0001);
  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 0.0001);
  let turbidity = s.B04 / (s.B03 + 0.0001);
  let cloud = (s.SCL == 8 || s.SCL == 9 || s.SCL == 3) ? 1.0 : 0.0;
  return [ndwi, ndvi, turbidity, cloud, s.B08];
}
"""


@dataclass
class FarmSatelliteReading:
    """Satellite-derived metrics for a single farm location."""
    locality_no: int
    name: str
    lat: float
    lon: float
    date: str
    ndwi: float  # Normalized Difference Water Index (water presence)
    ndvi: float  # Normalized Difference Vegetation Index (chlorophyll proxy)
    turbidity: float  # Red/Green ratio (surface disturbance)
    cloud_pct: float  # Cloud contamination percentage
    nir_reflectance: float  # Near-infrared (B08)
    anomaly_detected: bool = False
    anomaly_type: str = ""
    anomaly_detail: str = ""


@dataclass
class SatelliteSnapshot:
    """Collection of farm readings from a single satellite pass."""
    generated_at: str
    date_range: str
    n_farms_queried: int
    n_readings: int
    n_anomalies: int
    cloud_free_pct: float
    readings: list[dict] = field(default_factory=list)
    anomalies: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    # WS-32: a reading exists only where a scene was actually returned. These fields
    # let a caller tell "no scene" from "no anomaly" — the engine used to invent
    # readings with a seeded RNG when CDSE was unconfigured.
    n_readings_verified: int = 0
    n_readings_unverified: int = 0
    scene_dates: list[str] = field(default_factory=list)
    missing_reason: str | None = None


class SatelliteEngine:
    """
    Queries Sentinel-2 imagery for salmon farm locations.

    WS-32 (2026-10-18): there is no simulated fallback. A farm without a real scene
    produces no reading and the snapshot names why (``missing_reason``). Sentinel-2
    NDVI is a surface-scum/vegetation signal, not a chlorophyll or toxicity
    measurement, and the anomaly labels now say that instead of calling a bloom.
    """

    def __init__(self) -> None:
        self._cache: SatelliteSnapshot | None = None
        self._cache_time: dt.datetime | None = None
        self._cache_ttl = dt.timedelta(hours=6)  # Sentinel-2 revisit is 5 days
        self._sh_config = None

    def _get_sh_config(self):
        """Deprecated: kept for compatibility.

        The sentinelhub package is no longer used — queries go through
        core.satellite.cdse_client (pure httpx + OAuth). Returns None always.
        """
        return None

    async def _get_farm_locations(self, limit: int = 50) -> list[dict]:
        """Get farm locations from database."""
        try:
            from core.models import Locality
            from core.async_db import get_async_session
            from sqlalchemy import select
            async with get_async_session() as session:
                locs = (await session.execute(
                    select(Locality)
                    .where(Locality.latitude.isnot(None))
                    .limit(limit)
                )).scalars().all()
                return [
                    {
                        "locality_no": l.locality_no,
                        "name": l.name,
                        "lat": l.latitude,
                        "lon": l.longitude,
                        "pa": l.production_area,
                    }
                    for l in locs
                ]
        except Exception as e:
            log.warning("satellite.db_error", error=str(e)[:80])
            return []

    async def query_farm(self, lat: float, lon: float, days_back: int = 10) -> dict | None:
        """Query Sentinel-2 for a single farm location via CDSE Statistical API."""
        if not SH_CONFIGURED:
            return None

        try:
            from core.satellite.cdse_client import cdse_client
            stats = await cdse_client.fetch_farm_stats(lat, lon, days_back)
            if not stats or "data" not in stats:
                return None

            # Find the most recent valid day
            for day_data in reversed(stats["data"]):
                outputs = day_data.get("outputs", {}).get("default", {}).get("bands", {})
                if not outputs:
                    continue
                # B3 is cloud mask from evalscript (index 3)
                cloud_stats = outputs.get("B3", {}).get("stats", {})
                cloud_pct = cloud_stats.get("mean", 1.0)
                if cloud_pct < 0.5:
                    ndwi = outputs.get("B0", {}).get("stats", {}).get("mean", 0)
                    ndvi = outputs.get("B1", {}).get("stats", {}).get("mean", 0)
                    turb = outputs.get("B2", {}).get("stats", {}).get("mean", 0)
                    nir = outputs.get("B4", {}).get("stats", {}).get("mean", 0)
                    return {
                        "ndwi": round(ndwi, 4),
                        "ndvi": round(ndvi, 4),
                        "turbidity": round(turb, 4),
                        "nir_reflectance": round(nir, 4),
                        "cloud_pct": round(cloud_pct * 100, 1),
                        "date": day_data["interval"]["to"][:10],
                    }
            return None
        except Exception as e:
            log.warning("satellite.query_failed", lat=lat, lon=lon, error=str(e)[:100])
            return None
        return None

    async def scan_farms(self, n_farms: int = 50) -> SatelliteSnapshot:
        """Scan farm locations for satellite anomalies."""
        now = dt.datetime.now(dt.UTC)

        # Use cache if fresh
        if (
            self._cache
            and self._cache_time
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._cache

        farms = await self._get_farm_locations(limit=n_farms)
        if not farms:
            return SatelliteSnapshot(
                generated_at=now.isoformat(),
                date_range="",
                n_farms_queried=0,
                n_readings=0,
                n_anomalies=0,
                cloud_free_pct=0,
            )

        date_str = now.strftime("%Y-%m-%d")
        readings: list[FarmSatelliteReading] = []
        unverified = 0
        if not SH_CONFIGURED:
            # Without credentials no scene was requested at all: return an empty,
            # explicitly unavailable snapshot rather than invented values.
            snapshot = SatelliteSnapshot(
                generated_at=now.isoformat(),
                date_range="",
                n_farms_queried=len(farms),
                n_readings=0,
                n_anomalies=0,
                cloud_free_pct=0.0,
                readings=[],
                anomalies=[],
                summary={
                    "data_source": "none (CDSE credentials not configured)",
                    "is_live": False,
                    "data_quality": "unavailable",
                    "confidence": 0.0,
                    # Sentinel-2 NDVI is not a chlorophyll measurement; say what the
                    # product would be if it existed.
                    "measurement": "surface NDVI/turbidity (Sentinel-2), not chlorophyll",
                },
                n_readings_verified=0,
                n_readings_unverified=0,
                scene_dates=[],
                missing_reason=(
                    "CDSE credentials are not configured, so no Sentinel-2 scene was "
                    "requested; there is no reading to show"
                ),
            )
            self._cache = snapshot
            self._cache_time = now
            log.info("satellite.scan_unconfigured", n_farms=len(farms))
            return snapshot

        for farm in farms:
            if SH_CONFIGURED:
                # Live CDSE Statistical API query (pure-httpx client; no
                # sentinelhub C-deps — they are blocked by Device Guard and
                # unused since Session 40)
                result = await self.query_farm(farm["lat"], farm["lon"])
                if result:
                    anomaly = False
                    anomaly_type = ""
                    anomaly_detail = ""
                    # WS-32: NDVI over water is a surface scum/vegetation signal,
                    # not a bloom confirmation. The label must not imply a species,
                    # toxicity or a harmful algal bloom.
                    if result["ndvi"] > 0.05:
                        anomaly = True
                        anomaly_type = "surface_scum_or_vegetation"
                        anomaly_detail = (
                            f"Elevated NDVI ({result['ndvi']}) over water — possible surface "
                            "scum or floating vegetation; not a chlorophyll or toxicity "
                            "measurement"
                        )
                    elif result["turbidity"] > 0.9:
                        anomaly = True
                        anomaly_type = "surface_disturbance"
                        anomaly_detail = f"High turbidity ({result['turbidity']})"

                    readings.append(FarmSatelliteReading(
                        locality_no=farm["locality_no"],
                        name=farm["name"],
                        lat=farm["lat"],
                        lon=farm["lon"],
                        date=result["date"],
                        ndwi=result["ndwi"],
                        ndvi=result["ndvi"],
                        turbidity=result["turbidity"],
                        cloud_pct=result["cloud_pct"],
                        nir_reflectance=result["nir_reflectance"],
                        anomaly_detected=anomaly,
                        anomaly_type=anomaly_type,
                        anomaly_detail=anomaly_detail,
                    ))
                    continue

            # No scene for this farm: no reading. Counting it keeps "no scene" apart
            # from "no anomaly" in the summary.
            unverified += 1

        # Build snapshot
        anomalies = [r for r in readings if r.anomaly_detected]
        cloud_vals = [r.cloud_pct for r in readings]
        avg_cloud = np.mean(cloud_vals) if cloud_vals else 0

        # Summary statistics
        ndwi_vals = [r.ndwi for r in readings]
        ndvi_vals = [r.ndvi for r in readings]
        turb_vals = [r.turbidity for r in readings]

        from dataclasses import asdict

        snapshot = SatelliteSnapshot(
            generated_at=now.isoformat(),
            date_range=f"{(now - dt.timedelta(days=10)).strftime('%Y-%m-%d')} to {date_str}",
            n_farms_queried=len(farms),
            n_readings=len(readings),
            n_anomalies=len(anomalies),
            cloud_free_pct=round(100 - float(avg_cloud), 1),
            readings=[asdict(r) for r in readings],
            anomalies=[asdict(a) for a in anomalies],
            summary={
                "avg_ndwi": round(float(np.mean(ndwi_vals)), 4) if ndwi_vals else 0,
                "avg_ndvi": round(float(np.mean(ndvi_vals)), 4) if ndvi_vals else 0,
                "avg_turbidity": round(float(np.mean(turb_vals)), 4) if turb_vals else 0,
                "anomaly_rate_pct": round(len(anomalies) / max(len(readings), 1) * 100, 1),
                "data_source": "Sentinel-2 L2A (CDSE)" if readings else "none",
                # Live means a scene with a date, never that credentials exist.
                "is_live": bool(readings),
                "data_quality": "live" if readings else "unavailable",
                "confidence": 0.6 if readings else 0.0,
                "measurement": "surface NDVI/turbidity (Sentinel-2), not chlorophyll",
                "anomaly_meaning": (
                    "surface scum / turbidity / surface material — not a harmful algal "
                    "bloom confirmation, species identification or toxicity measurement"
                ),
            },
            n_readings_verified=len(readings),
            n_readings_unverified=unverified,
            scene_dates=sorted({r.date for r in readings}),
            missing_reason=(
                None if readings
                else "no farm returned a Sentinel-2 scene for this window"
            ),
        )

        self._cache = snapshot
        self._cache_time = now
        log.info(
            "satellite.scan_complete",
            n_farms=len(farms),
            n_readings=len(readings),
            n_anomalies=len(anomalies),
            live=bool(SH_CONFIGURED),
        )
        return snapshot

    def get_products(self) -> list[dict]:
        """List available satellite intelligence products."""
        # WS-32: what Sentinel-2 can actually show at 10-20 m. It cannot confirm a
        # harmful algal bloom, identify a species or measure toxicity; a surface
        # anomaly is a pointer to look, not a diagnosis. The cage-census product was
        # removed: no object detection is implemented and it returned no imagery.
        return [
            {
                "id": "surface_scum_signal",
                "name": "Surface scum / vegetation signal",
                "description": (
                    "Elevated NDVI over water points at surface scum or floating "
                    "vegetation. It is not a chlorophyll measurement, a species "
                    "identification or a toxicity test — confirm with cell counts."
                ),
                "index": "NDVI > 0.05 over water",
                "resolution": "10m",
                "revisit": "~5 days at Norwegian latitudes",
                "validated": False,
            },
            {
                "id": "turbidity_disturbance",
                "name": "Turbidity / surface disturbance",
                "description": (
                    "A red/green ratio change can indicate vessel activity, a "
                    "treatment, or sediment. It does not identify which."
                ),
                "index": "Red/Green > 0.9",
                "resolution": "10m",
                "revisit": "~5 days at Norwegian latitudes",
                "validated": False,
            },
            {
                "id": "surface_material_signal",
                "name": "Surface material signal",
                "description": (
                    "Elevated near-infrared reflectance over water can indicate "
                    "floating material. It is an unvalidated indicator, not a "
                    "mortality detection."
                ),
                "index": "NIR B08 > 0.12",
                "resolution": "10m",
                "revisit": "~5 days at Norwegian latitudes",
                "validated": False,
            },
        ]

    def get_status(self) -> dict:
        """Get satellite engine status."""
        return {
            "configured": SH_CONFIGURED,
            "provider": "Copernicus Data Space Ecosystem (CDSE)",
            "satellite": "Sentinel-2 L2A",
            "resolution": "10m (RGB+NIR)",
            "revisit_days": 5,
            "free_tier": "10,000 credits/month",
            "last_scan": self._cache.generated_at if self._cache else None,
            "cached_readings": self._cache.n_readings if self._cache else 0,
            "cached_readings_verified": self._cache.n_readings_verified if self._cache else 0,
            "cached_anomalies": self._cache.n_anomalies if self._cache else 0,
            "scene_dates": self._cache.scene_dates if self._cache else [],
            "missing_reason": (self._cache.missing_reason if self._cache else "no scan has run yet"),
            # "Live" is a property of the data, never of the configuration.
            "is_live": bool(self._cache and self._cache.n_readings_verified),
            "measurement": "surface NDVI/turbidity (Sentinel-2), not chlorophyll",
            "note": (
                "Set SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET to request "
                "imagery; without them the platform shows no reading rather than a "
                "simulated one"
                if not SH_CONFIGURED
                else "CDSE credentials are configured; a scan returns only the scenes it "
                     "actually receives"
            ),
        }


# Singleton
satellite_engine = SatelliteEngine()
