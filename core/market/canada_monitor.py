"""
Canada / British Columbia Aquaculture Monitor
================================================
Richest open aquaculture dataset of any country — DFO publishes per-farm
monthly lice counts, mortality events, disease audits, all as downloadable CSV.

Data sources (7 live, no auth needed):
  1. DFO Industry Sea Lice Counts — per-farm monthly lice with lat/lon (2011-2025)
  2. DFO Sea Lice Audits — independent government audit lice counts
  3. DFO Mortality Events — daily mortality per facility with cause
  4. DFO Fish Health Events — disease events requiring vet involvement
  5. DFO Fish Health Audits — PCR screening, bacterial pathogens, histopathology
  6. Statistics Canada 32-10-0107-01 — production volumes and value by province
  7. CMEMS Global — SST + chlorophyll for BC waters

All DFO data: Open Government Licence - Canada, CSV format, no auth.
Farm coordinates embedded in lice/mortality datasets.

BC aquaculture regions:
  - Discovery Islands (50.2°N, -125.3°W) — transitional zone
  - Broughton Archipelago (50.7°N, -126.7°W) — major cluster
  - Clayoquot Sound (49.2°N, -126.0°W) — west coast
  - Quatsino Sound (50.5°N, -128.0°W) — north Vancouver Island
  - Tofino/Nootka (49.6°N, -126.6°W) — central west coast
"""
from __future__ import annotations

import csv
import datetime as dt
import io
from dataclasses import dataclass, field

import httpx
import structlog

log = structlog.get_logger(__name__)

# ── DFO Open Data CSV URLs ──────────────────────────────────────────────────
DFO_LICE_CSV = "https://api-proxy.edh-cde.dfo-mpo.gc.ca/catalogue/records/3cafbe89-c98b-4b44-88f1-594e8d28838d/attachments/lice-count-dens-pou-2011-ongoing-rpt-pac-dfo-mpo-aquaculture-eng.csv"
DFO_LICE_AUDIT_CSV = "https://api-proxy.edh-cde.dfo-mpo.gc.ca/catalogue/records/5cfd93bd-b3ee-4b0b-8816-33d388f6811d/attachments/lice-audit-verif-pou-2011-ongoing-rpt-pac-dfo-mpo-aquaculture-eng.csv"
DFO_MORTALITY_CSV = "https://api-proxy.edh-cde.dfo-mpo.gc.ca/catalogue/records/7fbb2662-391a-4df7-99b4-3343fa68fc93/attachments/ep-mort-ev-2011-ongoing-rpt-pac-dfo-mpo-aquaculture-eng.csv"
DFO_HEALTH_EVENTS_CSV = "https://api-proxy.edh-cde.dfo-mpo.gc.ca/catalogue/records/deefd1d7-7184-44c7-83aa-ec0db91aad27/attachments/health-even-sante-2016-ongoing-rpt-pac-dfo-mpo-aquaculture-eng.csv"
DFO_HEALTH_AUDIT_CSV = "https://api-proxy.edh-cde.dfo-mpo.gc.ca/catalogue/records/6c891715-317c-4d4d-9fe8-ea425e01d9d2/attachments/health-audit-fac-verif-sante-inst-2011-ongoing-encours-rpt-pac-dfo-mpo-aquaculture-eng.csv"

# Statistics Canada WDS API
STATCAN_TABLE = "3210010701"

# CMEMS bounding box for BC
BC_BBOX = {"lat_min": 48.0, "lat_max": 54.0, "lon_min": -132.0, "lon_max": -125.0}

# Known BC aquaculture regions
BC_REGIONS = {
    "Discovery Islands":       {"lat": 50.20, "lng": -125.30, "n_farms": 15},
    "Broughton Archipelago":   {"lat": 50.70, "lng": -126.70, "n_farms": 25},
    "Clayoquot Sound":         {"lat": 49.20, "lng": -126.00, "n_farms": 12},
    "Quatsino Sound":          {"lat": 50.50, "lng": -128.00, "n_farms": 8},
    "Nootka Sound":            {"lat": 49.60, "lng": -126.60, "n_farms": 10},
    "Klemtu / Bella Bella":    {"lat": 52.30, "lng": -128.50, "n_farms": 6},
    "Campbell River":          {"lat": 50.05, "lng": -125.25, "n_farms": 8},
    "Tofino":                  {"lat": 49.15, "lng": -125.90, "n_farms": 5},
}

# Major BC salmon farming companies
BC_COMPANIES = [
    {"name": "Mowi Canada West", "sites": 25, "species": "Atlantic Salmon"},
    {"name": "Cermaq Canada", "sites": 20, "species": "Atlantic Salmon"},
    {"name": "Grieg Seafood BC", "sites": 15, "species": "Atlantic Salmon"},
    {"name": "Creative Salmon", "sites": 5, "species": "Chinook Salmon"},
]


@dataclass
class DFOLiceRecord:
    """A single lice count record from DFO open data."""
    facility: str
    company: str
    lat: float
    lng: float
    date: str
    avg_lice_per_fish: float
    species: str = ""


@dataclass
class DFOMortalityEvent:
    """A mortality event from DFO open data."""
    facility: str
    date: str
    cause: str
    count: int = 0


@dataclass
class CanadaSnapshot:
    """Current state of Canadian aquaculture."""
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    # Lice
    lice_records: list[DFOLiceRecord] = field(default_factory=list)
    avg_lice: float = 0.0
    farms_above_threshold: int = 0
    total_farms_reporting: int = 0
    # Farm locations extracted from DFO data
    farm_locations: list[dict] = field(default_factory=list)
    # Mortality
    recent_mortality_events: int = 0
    # Disease
    disease_events: int = 0
    # Ocean
    avg_sst: float | None = None
    avg_chl_a: float | None = None
    bloom_risk: str = "unknown"
    # Production
    annual_production_tonnes: int = 115_000
    # Disruption
    disruption_level: str = "normal"
    disruption_pct: float = 0.0
    # Intelligence
    insights: list[str] = field(default_factory=list)


class CanadaMonitor:
    """
    Comprehensive Canada/BC aquaculture monitor.
    DFO provides the richest open aquaculture data of any country.
    """

    _cache: CanadaSnapshot | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=3)
    _lice_cache: list[DFOLiceRecord] | None = None
    _farm_locations_cache: list[dict] | None = None

    async def fetch_dfo_lice(self, recent_months: int = 6) -> list[DFOLiceRecord]:
        """Fetch per-farm lice counts from DFO open data CSV."""
        if self._lice_cache:
            return self._lice_cache

        records: list[DFOLiceRecord] = []
        cutoff = (dt.date.today() - dt.timedelta(days=recent_months * 30)).isoformat()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(DFO_LICE_CSV)
                if resp.status_code == 200:
                    reader = csv.DictReader(io.StringIO(resp.text))
                    for row in reader:
                        try:
                            date_str = row.get("Year-Month", row.get("DATE", ""))
                            if date_str and date_str >= cutoff:
                                lat = float(row.get("Latitude", row.get("LAT", 0)) or 0)
                                lng = float(row.get("Longitude", row.get("LONG", 0)) or 0)
                                lice = float(row.get("Lep_Avg_Per_Fish",
                                             row.get("L_SALMONIS_AVG", 0)) or 0)
                                if lat != 0 and lng != 0:
                                    records.append(DFOLiceRecord(
                                        facility=row.get("Facility", row.get("FACILITY_NAME", "")),
                                        company=row.get("Company", row.get("COMPANY", "")),
                                        lat=lat,
                                        lng=lng,
                                        date=date_str,
                                        avg_lice_per_fish=lice,
                                    ))
                        except (ValueError, TypeError):
                            continue

                    self._lice_cache = records
                    log.info("canada.dfo_lice_fetched", records=len(records))
                else:
                    log.warning("canada.dfo_lice_error", status=resp.status_code)

        except Exception as exc:
            log.warning("canada.dfo_lice_failed", error=str(exc)[:120])
        return records

    async def fetch_mortality_events(self, recent_months: int = 6) -> int:
        """Fetch recent mortality event count from DFO."""
        count = 0
        cutoff = (dt.date.today() - dt.timedelta(days=recent_months * 30)).isoformat()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(DFO_MORTALITY_CSV)
                if resp.status_code == 200:
                    reader = csv.DictReader(io.StringIO(resp.text))
                    for row in reader:
                        date_str = row.get("Event_Start_Date", row.get("DATE", ""))
                        if date_str and date_str >= cutoff:
                            count += 1
                    log.info("canada.mortality_fetched", recent_events=count)
        except Exception as exc:
            log.debug("canada.mortality_failed", error=str(exc)[:80])
        return count

    async def fetch_health_events(self, recent_months: int = 12) -> int:
        """Fetch recent disease events from DFO Fish Health Events."""
        count = 0
        cutoff = (dt.date.today() - dt.timedelta(days=recent_months * 30)).isoformat()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(DFO_HEALTH_EVENTS_CSV)
                if resp.status_code == 200:
                    reader = csv.DictReader(io.StringIO(resp.text))
                    for row in reader:
                        date_str = row.get("Event_Start_Date", row.get("DATE", ""))
                        if date_str and date_str >= cutoff:
                            count += 1
                    log.info("canada.health_events_fetched", recent=count)
        except Exception as exc:
            log.debug("canada.health_events_failed", error=str(exc)[:80])
        return count

    async def fetch_cmems_conditions(self) -> dict:
        """Fetch SST + chlorophyll from CMEMS for BC waters."""
        conditions: dict = {"sst": None, "chl_a": None, "bloom_risk": "unknown"}
        try:
            import copernicusmarine
            from config.settings import settings
            username = getattr(settings, "cmems_username", "")
            if not username:
                return conditions

            target_date = dt.date.today() - dt.timedelta(days=2)
            bbox = BC_BBOX

            try:
                ds = copernicusmarine.open_dataset(
                    dataset_id="cmems_obs-sst_glo_phy-sst_nrt_l4-multi-4km_P1D",
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
                    avg_k = float(valid.mean())
                    conditions["sst"] = round(avg_k - 273.15 if avg_k > 200 else avg_k, 1)
                ds.close()
            except Exception as exc:
                log.debug("canada.cmems_sst_failed", error=str(exc)[:80])

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
                    chl = round(float(valid.mean()), 2)
                    conditions["chl_a"] = chl
                    conditions["bloom_risk"] = (
                        "CRITICAL" if chl >= 10 else "HIGH" if chl >= 5 else
                        "ELEVATED" if chl >= 2 else "LOW"
                    )
                ds.close()
            except Exception as exc:
                log.debug("canada.cmems_chl_failed", error=str(exc)[:80])

        except ImportError:
            pass
        return conditions

    def _extract_farm_locations(self, records: list[DFOLiceRecord]) -> list[dict]:
        """Extract unique farm locations from DFO lice data."""
        if self._farm_locations_cache:
            return self._farm_locations_cache

        seen: dict[str, dict] = {}
        for r in records:
            key = f"{r.lat:.3f}_{r.lng:.3f}"
            if key not in seen:
                seen[key] = {
                    "name": r.facility,
                    "company": r.company,
                    "lat": r.lat,
                    "lng": r.lng,
                    "latest_lice": r.avg_lice_per_fish,
                    "latest_date": r.date,
                }
            else:
                if r.date > seen[key]["latest_date"]:
                    seen[key]["latest_lice"] = r.avg_lice_per_fish
                    seen[key]["latest_date"] = r.date

        locations = list(seen.values())
        self._farm_locations_cache = locations
        return locations

    async def get_snapshot(self) -> CanadaSnapshot:
        """Get comprehensive Canada/BC aquaculture snapshot."""
        now = dt.datetime.now(dt.UTC)
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        lice = await self.fetch_dfo_lice(recent_months=6)
        mortality = await self.fetch_mortality_events(recent_months=6)
        disease = await self.fetch_health_events(recent_months=12)
        cmems = await self.fetch_cmems_conditions()
        farms = self._extract_farm_locations(lice)

        # Compute lice stats
        if lice:
            avg_lice = sum(r.avg_lice_per_fish for r in lice) / len(lice)
            above_threshold = sum(1 for r in lice if r.avg_lice_per_fish > 3.0)  # BC threshold is 3 motile lice
        else:
            avg_lice = 0
            above_threshold = 0

        # Disruption assessment
        disruption = "normal"
        disruption_pct = 0.0
        if disease > 10:
            disruption = "elevated"
            disruption_pct = min(10, disease * 0.5)
        if avg_lice > 5:
            disruption_pct = max(disruption_pct, 5)
            disruption = "elevated"
        if cmems["bloom_risk"] in ("HIGH", "CRITICAL"):
            disruption_pct = max(disruption_pct, 5)

        insights = []
        if lice:
            insights.append(f"DFO lice monitoring: {len(lice)} records, avg {avg_lice:.1f} lice/fish, {above_threshold} farms above threshold")
        if farms:
            insights.append(f"{len(farms)} unique farm locations extracted from DFO open data")
        if mortality > 0:
            insights.append(f"{mortality} mortality events reported in last 6 months")
        if disease > 0:
            insights.append(f"{disease} fish health events in last 12 months")
        if cmems["sst"] is not None:
            insights.append(f"BC waters SST: {cmems['sst']}°C | Bloom risk: {cmems['bloom_risk']}")
        insights.append("BC salmon farming transition: open-net pen licences expire 2029 (federal policy)")

        snapshot = CanadaSnapshot(
            lice_records=lice,
            avg_lice=round(avg_lice, 2),
            farms_above_threshold=above_threshold,
            total_farms_reporting=len(farms),
            farm_locations=farms,
            recent_mortality_events=mortality,
            disease_events=disease,
            avg_sst=cmems["sst"],
            avg_chl_a=cmems["chl_a"],
            bloom_risk=cmems["bloom_risk"],
            disruption_level=disruption,
            disruption_pct=disruption_pct,
            insights=insights,
        )

        self._cache = snapshot
        self._cache_time = now
        log.info("canada.snapshot_complete", farms=len(farms), lice_records=len(lice),
                 avg_lice=round(avg_lice, 2), mortality=mortality, disease=disease)
        return snapshot

    def get_latest_snapshot(self) -> dict | None:
        """Sync access for global_supply."""
        if not self._cache:
            return None
        s = self._cache
        return {
            "avg_lice": s.avg_lice,
            "farms_above_threshold": s.farms_above_threshold,
            "disease_events": s.disease_events,
            "mortality_events": s.recent_mortality_events,
            "disruption_level": s.disruption_level,
            "disruption_pct": s.disruption_pct,
            "bloom_risk": s.bloom_risk,
            "sst": s.avg_sst,
            "total_farms": s.total_farms_reporting,
        }

    def get_lice_by_region(self) -> dict:
        """Group lice data by BC region for trend charting."""
        if not self._cache or not self._cache.lice_records:
            # Return region stubs with empty data
            return {
                "data_quality": "source_unavailable",
                "regions": {name: [] for name in BC_REGIONS},
            }

        import math
        result: dict[str, list[dict]] = {name: [] for name in BC_REGIONS}

        # Assign each record to nearest region
        for record in self._cache.lice_records:
            min_dist = float("inf")
            nearest = "Broughton Archipelago"
            for rname, rinfo in BC_REGIONS.items():
                dist = math.sqrt((record.lat - rinfo["lat"])**2 + (record.lng - rinfo["lng"])**2)
                if dist < min_dist:
                    min_dist = dist
                    nearest = rname
            result[nearest].append({
                "date": record.date,
                "lice": record.avg_lice_per_fish,
                "facility": record.facility,
            })

        # Aggregate to monthly averages per region
        monthly: dict[str, list[dict]] = {}
        for region, records in result.items():
            by_month: dict[str, list[float]] = {}
            for r in records:
                month = r["date"][:7] if len(r["date"]) >= 7 else r["date"]
                if month not in by_month:
                    by_month[month] = []
                by_month[month].append(r["lice"])
            monthly[region] = [
                {"month": m, "avg_lice": round(sum(vals)/len(vals), 2), "n_records": len(vals)}
                for m, vals in sorted(by_month.items())
            ]

        return monthly

    def get_farms_geojson(self) -> dict:
        """BC farm locations as GeoJSON — extracted from DFO open data."""
        s = self._cache
        features = []

        # Use DFO-extracted farm locations if available
        if s and s.farm_locations:
            for farm in s.farm_locations:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [farm["lng"], farm["lat"]]},
                    "properties": {
                        "name": farm["name"],
                        "company": farm["company"],
                        "country": "Canada",
                        "latest_lice": farm["latest_lice"],
                        "latest_date": farm["latest_date"],
                        "sst": s.avg_sst,
                        "bloom_risk": s.bloom_risk,
                    },
                })
        else:
            # Fallback to known region centroids
            for name, info in BC_REGIONS.items():
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [info["lng"], info["lat"]]},
                    "properties": {
                        "name": name,
                        "country": "Canada",
                        "n_farms": info["n_farms"],
                        "sst": s.avg_sst if s else None,
                        "bloom_risk": s.bloom_risk if s else "unknown",
                    },
                })

        return {"type": "FeatureCollection", "features": features}


# Singleton
canada_monitor = CanadaMonitor()
