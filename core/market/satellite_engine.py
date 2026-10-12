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


class SatelliteEngine:
    """
    Queries Sentinel-2 imagery for salmon farm locations.
    Falls back to simulated data if CDSE credentials not configured.
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

    def _simulate_reading(self, farm: dict, date: str) -> FarmSatelliteReading:
        """Generate realistic simulated satellite reading when CDSE not configured."""
        rng = np.random.default_rng(hash(farm["locality_no"]) % 2**31)

        # Realistic coastal water values
        ndwi = round(float(rng.normal(0.3, 0.08)), 4)  # Water-dominant
        ndvi = round(float(rng.normal(-0.15, 0.05)), 4)  # Low for water
        turbidity = round(float(rng.normal(0.6, 0.15)), 4)
        nir = round(float(rng.normal(0.05, 0.02)), 4)
        cloud_pct = round(float(rng.uniform(0, 40)), 1)

        # Detect anomalies
        anomaly = False
        anomaly_type = ""
        anomaly_detail = ""

        if ndvi > 0.05:  # Unusual vegetation signal in water = possible HAB
            anomaly = True
            anomaly_type = "possible_bloom"
            anomaly_detail = f"Elevated NDVI ({ndvi}) in water — possible algal bloom"
        elif turbidity > 0.9:  # High turbidity = vessel activity or mortality
            anomaly = True
            anomaly_type = "surface_disturbance"
            anomaly_detail = f"High turbidity ({turbidity}) — possible harvest/treatment activity"
        elif nir > 0.12:  # High NIR reflectance in water = surface material
            anomaly = True
            anomaly_type = "surface_anomaly"
            anomaly_detail = f"Elevated NIR ({nir}) — possible surface material (mortality/debris)"

        return FarmSatelliteReading(
            locality_no=farm["locality_no"],
            name=farm["name"],
            lat=farm["lat"],
            lon=farm["lon"],
            date=date,
            ndwi=ndwi,
            ndvi=ndvi,
            turbidity=turbidity,
            cloud_pct=cloud_pct,
            nir_reflectance=nir,
            anomaly_detected=anomaly,
            anomaly_type=anomaly_type,
            anomaly_detail=anomaly_detail,
        )

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
                    if result["ndvi"] > 0.05:
                        anomaly = True
                        anomaly_type = "possible_bloom"
                        anomaly_detail = f"Elevated NDVI ({result['ndvi']}) in water"
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

            # Fallback: simulated reading
            readings.append(self._simulate_reading(farm, date_str))

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
                "data_source": "Sentinel-2 L2A (CDSE)" if SH_CONFIGURED else "Simulated (configure CDSE credentials for live data)",
                "is_live": bool(SH_CONFIGURED),
                "data_quality": "live" if SH_CONFIGURED else "simulated",
                "confidence": 0.9 if SH_CONFIGURED else 0.0,
            },
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
        return [
            {
                "id": "hab_confirmation",
                "name": "HAB Bloom Confirmation",
                "description": "Confirm CMEMS chlorophyll alerts with Sentinel-2 RGB true-color imagery",
                "index": "NDVI > 0.05 in water",
                "resolution": "10m",
                "revisit": "5 days",
            },
            {
                "id": "harvest_detection",
                "name": "Harvest Activity Detection",
                "description": "Detect vessel activity and surface disturbance near farm cages",
                "index": "Turbidity > 0.9",
                "resolution": "10m",
                "revisit": "5 days",
            },
            {
                "id": "mortality_surface",
                "name": "Surface Mortality Detection",
                "description": "Detect fish at surface via elevated NIR reflectance",
                "index": "NIR B08 > 0.12",
                "resolution": "10m",
                "revisit": "5 days",
            },
            {
                "id": "cage_census",
                "name": "Cage Infrastructure Census",
                "description": "Verify cage presence and count at licensed farm locations",
                "index": "Object detection (future: YOLO)",
                "resolution": "10m",
                "revisit": "Monthly",
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
            "cached_anomalies": self._cache.n_anomalies if self._cache else 0,
            "note": "Set SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET for live imagery" if not SH_CONFIGURED else "Live Sentinel-2 access active",
        }


# Singleton
satellite_engine = SatelliteEngine()
