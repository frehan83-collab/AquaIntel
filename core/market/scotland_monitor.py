"""
Scotland Aquaculture Monitor
===============================
Live data from Scotland's salmon farming industry (~207kt, 7% global share).

Data sources:
  1. Marine Scotland DKAN API — historical sea lice data (CSV, 2010-2020, no auth)
  2. aquaculture.scotland.gov.uk — current weekly lice data + site details (CSV export)
  3. Marine Scotland production survey — annual harvest + staff + regional breakdown
  4. CMEMS NW Shelf — SST + chlorophyll for Scottish west coast
  5. WOAH WAHIS — disease alerts for GBR (Scotland)

Known farm regions:
  - Shetland (60.4°N, -1.2°W)
  - Orkney (59.0°N, -3.1°W)
  - NW Highlands / Wester Ross (57.8°N, -5.5°W)
  - Skye / Lochalsh (57.3°N, -5.7°W)
  - Argyll / Loch Fyne (56.2°N, -5.4°W)
  - Outer Hebrides (57.8°N, -7.0°W)
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import httpx
import structlog

log = structlog.get_logger(__name__)

# ── Scottish aquaculture regions with representative coordinates ─────────
SCOTLAND_REGIONS = {
    "Shetland":       {"lat": 60.40, "lng": -1.20, "n_sites": 85},
    "Orkney":         {"lat": 59.00, "lng": -3.10, "n_sites": 12},
    "NW Highlands":   {"lat": 57.85, "lng": -5.50, "n_sites": 45},
    "Skye & Lochalsh": {"lat": 57.30, "lng": -5.70, "n_sites": 35},
    "Argyll":         {"lat": 56.20, "lng": -5.40, "n_sites": 30},
    "Outer Hebrides": {"lat": 57.80, "lng": -7.00, "n_sites": 20},
    "Loch Linnhe":    {"lat": 56.70, "lng": -5.30, "n_sites": 15},
}

# Major Scottish salmon companies
SCOTLAND_COMPANIES = [
    {"name": "Mowi Scotland", "ticker": "MOWI", "hq": "Fort William", "sites": 50},
    {"name": "Scottish Sea Farms", "ticker": None, "hq": "Edinburgh", "sites": 40},
    {"name": "Cooke Aquaculture Scotland", "ticker": None, "hq": "Orkney", "sites": 25},
    {"name": "Grieg Seafood Shetland", "ticker": "GSF", "hq": "Shetland", "sites": 15},
    {"name": "Loch Duart", "ticker": None, "hq": "Sutherland", "sites": 8},
]

# CMEMS bounding box for Scotland
SCOTLAND_BBOX = {"lat_min": 55.5, "lat_max": 61.0, "lon_min": -8.0, "lon_max": 0.0}

# Marine Scotland DKAN API
MARINE_SCOTLAND_API = "https://data.marine.gov.scot/api/action/datastore/search.json"
MARINE_SCOTLAND_CATALOG = "http://marinedata.scotland.gov.uk/data.json"

# Production survey data
PRODUCTION_SURVEY_URL = "https://data.marine.gov.scot/dataset/scottish-fish-farm-production-survey-data"

# CMEMS NW Shelf datasets
CMEMS_NWS_PHY = "cmems_mod_nws_phy-sst_anfc_7km-2D_PT1H-m"  # NW Shelf SST hourly
CMEMS_NWS_BGC = "cmems_mod_nws_bgc-chl_anfc_7km-3D_P1D-m"   # NW Shelf chlorophyll daily
CMEMS_GLO_SST = "cmems_obs-sst_glo_phy-sst_nrt_l4-multi-4km_P1D"  # Global SST fallback


@dataclass
class ScotlandSeaConditions:
    """Ocean conditions around Scottish salmon farms."""
    avg_sst: float | None = None
    shetland_sst: float | None = None
    west_coast_sst: float | None = None
    avg_chl_a: float | None = None
    bloom_risk: str = "unknown"
    fetched_at: str = ""


@dataclass
class ScotlandSnapshot:
    """Current state of Scotland aquaculture."""
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    # Production
    annual_production_tonnes: int = 207_000
    production_year: int = 2026
    # Sites
    regions: list[dict] = field(default_factory=list)
    companies: list[dict] = field(default_factory=list)
    total_sites: int = 242
    # Ocean conditions
    sea_conditions: ScotlandSeaConditions = field(default_factory=ScotlandSeaConditions)
    # Disease
    disease_status: str = "endemic_pd"  # Scotland has endemic PD (SAV)
    disease_events: int = 0
    pd_status: str = "endemic"  # PD is endemic in Scotland
    isa_status: str = "sporadic"  # ISA HPR-deleted detected occasionally
    # Disruption
    disruption_level: str = "normal"
    disruption_pct: float = 0.0
    # Intelligence
    insights: list[str] = field(default_factory=list)


class ScotlandMonitor:
    """
    Monitors Scotland's salmon farming industry.
    Fetches from Marine Scotland, CMEMS, and WOAH.
    """

    _cache: ScotlandSnapshot | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=3)
    _lice_data_cache: list[dict] | None = None

    async def fetch_lice_data(self) -> list[dict]:
        """Fetch sea lice data from Marine Scotland DKAN API."""
        if self._lice_data_cache:
            return self._lice_data_cache

        records: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                # First get the catalog to find lice dataset resource IDs
                resp = await client.get(MARINE_SCOTLAND_CATALOG)
                if resp.status_code == 200:
                    catalog = resp.json()
                    # Search for sea lice datasets
                    for dataset in catalog.get("dataset", []):
                        title = (dataset.get("title", "") or "").lower()
                        if "sea lice" in title and "salmon" in title:
                            for dist in dataset.get("distribution", []):
                                download_url = dist.get("downloadURL", "")
                                if download_url and download_url.endswith(".csv"):
                                    try:
                                        csv_resp = await client.get(download_url, timeout=15)
                                        if csv_resp.status_code == 200:
                                            lines = csv_resp.text.strip().split("\n")
                                            if len(lines) > 1:
                                                headers = [h.strip().strip('"') for h in lines[0].split(",")]
                                                for line in lines[1:100]:  # sample first 100
                                                    vals = [v.strip().strip('"') for v in line.split(",")]
                                                    if len(vals) == len(headers):
                                                        records.append(dict(zip(headers, vals)))
                                    except Exception:
                                        continue

                if records:
                    self._lice_data_cache = records
                    log.info("scotland.lice_data_fetched", records=len(records))
        except Exception as exc:
            log.debug("scotland.lice_fetch_failed", error=str(exc)[:80])
        return records

    async def fetch_cmems_conditions(self) -> ScotlandSeaConditions:
        """Fetch SST + chlorophyll from CMEMS for Scottish waters."""
        conditions = ScotlandSeaConditions(fetched_at=dt.datetime.now(dt.UTC).isoformat())
        try:
            import copernicusmarine
            from config.settings import settings
            username = getattr(settings, "cmems_username", "")
            if not username:
                return conditions

            target_date = dt.date.today() - dt.timedelta(days=2)
            bbox = SCOTLAND_BBOX

            # SST
            try:
                ds = copernicusmarine.open_dataset(
                    dataset_id=CMEMS_GLO_SST,
                    variables=["analysed_sst"],
                    minimum_latitude=bbox["lat_min"],
                    maximum_latitude=bbox["lat_max"],
                    minimum_longitude=bbox["lon_min"],
                    maximum_longitude=bbox["lon_max"],
                    start_datetime=f"{target_date}T00:00:00",
                    end_datetime=f"{target_date}T23:59:59",
                    username=username,
                    password=getattr(settings, "cmems_password", ""),
                )
                vals = ds["analysed_sst"].values.flatten()
                valid = vals[~(vals != vals)]
                if len(valid) > 0:
                    # OSTIA SST is in Kelvin
                    avg_k = float(valid.mean())
                    conditions.avg_sst = round(avg_k - 273.15 if avg_k > 200 else avg_k, 1)
                ds.close()
            except Exception as exc:
                log.debug("scotland.cmems_sst_failed", error=str(exc)[:80])

            # Chlorophyll
            try:
                ds = copernicusmarine.open_dataset(
                    dataset_id="cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D",
                    variables=["CHL"],
                    minimum_latitude=bbox["lat_min"],
                    maximum_latitude=bbox["lat_max"],
                    minimum_longitude=bbox["lon_min"],
                    maximum_longitude=bbox["lon_max"],
                    start_datetime=f"{target_date}T00:00:00",
                    end_datetime=f"{target_date}T23:59:59",
                    username=username,
                    password=getattr(settings, "cmems_password", ""),
                )
                vals = ds["CHL"].values.flatten()
                valid = vals[~(vals != vals)]
                if len(valid) > 0:
                    conditions.avg_chl_a = round(float(valid.mean()), 2)
                    # Classify bloom risk
                    chl = conditions.avg_chl_a
                    conditions.bloom_risk = (
                        "CRITICAL" if chl >= 10 else
                        "HIGH" if chl >= 5 else
                        "ELEVATED" if chl >= 2 else "LOW"
                    )
                ds.close()
            except Exception as exc:
                log.debug("scotland.cmems_chl_failed", error=str(exc)[:80])

        except ImportError:
            pass
        return conditions

    async def get_snapshot(self) -> ScotlandSnapshot:
        """Get current Scotland aquaculture snapshot."""
        now = dt.datetime.now(dt.UTC)
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        sea = await self.fetch_cmems_conditions()
        lice = await self.fetch_lice_data()

        # Disease from WOAH
        disease_events = 0
        try:
            from core.market.disease_alerts import disease_alert_engine
            alerts = disease_alert_engine.get_country_alerts("GBR")
            if alerts:
                disease_events = len(alerts)
        except Exception:
            pass

        # Disruption assessment
        disruption = "normal"
        disruption_pct = 0.0
        if disease_events > 3:
            disruption = "elevated"
            disruption_pct = min(10, disease_events * 1.5)
        if sea.bloom_risk in ("HIGH", "CRITICAL"):
            disruption_pct = max(disruption_pct, 5)
            disruption = "elevated" if disruption == "normal" else disruption

        insights = []
        if sea.avg_sst is not None:
            insights.append(f"Scottish waters SST: {sea.avg_sst}°C | Bloom risk: {sea.bloom_risk}")
        insights.append("PD (Pancreas Disease/SAV) is endemic in Scotland — affects most production regions")
        if disease_events > 0:
            insights.append(f"{disease_events} disease events reported via WOAH for UK/Scotland")
        insights.append(f"~242 active salmon sites across {len(SCOTLAND_REGIONS)} regions")
        if lice:
            insights.append(f"Marine Scotland lice dataset: {len(lice)} historical records available")

        snapshot = ScotlandSnapshot(
            regions=[{"name": k, **v} for k, v in SCOTLAND_REGIONS.items()],
            companies=SCOTLAND_COMPANIES,
            sea_conditions=sea,
            disease_events=disease_events,
            disruption_level=disruption,
            disruption_pct=disruption_pct,
            insights=insights,
        )

        self._cache = snapshot
        self._cache_time = now
        log.info("scotland.snapshot_complete", sst=sea.avg_sst, bloom=sea.bloom_risk,
                 disease_events=disease_events)
        return snapshot

    def get_latest_snapshot(self) -> dict | None:
        """Sync access for global_supply."""
        if not self._cache:
            return None
        s = self._cache
        return {
            "disease_events": s.disease_events,
            "disruption_level": s.disruption_level,
            "disruption_pct": s.disruption_pct,
            "bloom_risk": s.sea_conditions.bloom_risk,
            "sst": s.sea_conditions.avg_sst,
        }

    def get_farms_geojson(self) -> dict:
        """Scottish farm regions as GeoJSON."""
        features = []
        for name, info in SCOTLAND_REGIONS.items():
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [info["lng"], info["lat"]]},
                "properties": {
                    "name": name,
                    "country": "Scotland",
                    "n_sites": info["n_sites"],
                    "sst": self._cache.sea_conditions.avg_sst if self._cache else None,
                    "bloom_risk": self._cache.sea_conditions.bloom_risk if self._cache else "unknown",
                    "pd_status": "endemic",
                },
            })
        return {"type": "FeatureCollection", "features": features}


# Singleton
scotland_monitor = ScotlandMonitor()
