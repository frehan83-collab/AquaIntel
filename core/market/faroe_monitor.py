"""
Faroe Islands Aquaculture Monitor
====================================
Live data from Faroe Islands salmon industry (~92kt, 3% global share).
Dominated by Bakkafrost (world's largest single-origin salmon farmer).

Data sources:
  1. Hagstova Føroya (Statistics Faroe Islands) PxWeb API — harvest volumes (no auth)
  2. CMEMS Global — SST + chlorophyll for Faroese waters
  3. WOAH WAHIS — disease alerts for FRO
  4. Known farm regions — Faroese fjord coordinates

Farm regions: Single-generation single-fjord strategy with mandatory 2-month fallowing.
Mandatory ISA vaccination since 2016. Bakkafrost operates ~95% of production.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import httpx
import structlog

log = structlog.get_logger(__name__)

# ── Faroese farm regions ─────────────────────────────────────────────────
FAROE_REGIONS = {
    "Vestmanna":     {"lat": 62.15, "lng": -7.17, "company": "Bakkafrost"},
    "Fuglafjørður":  {"lat": 62.24, "lng": -6.81, "company": "Bakkafrost"},
    "Hvannasund":    {"lat": 62.30, "lng": -6.52, "company": "Bakkafrost"},
    "Kunoy":         {"lat": 62.30, "lng": -6.62, "company": "Bakkafrost"},
    "Bordoy":        {"lat": 62.15, "lng": -6.60, "company": "Bakkafrost"},
    "Eysturoy":      {"lat": 62.17, "lng": -6.93, "company": "Bakkafrost"},
    "Streymoy":      {"lat": 62.05, "lng": -6.95, "company": "Bakkafrost"},
    "Vágar":         {"lat": 62.10, "lng": -7.20, "company": "Bakkafrost"},
    "Suðuroy":       {"lat": 61.55, "lng": -6.90, "company": "Bakkafrost"},
    "Sandoy":        {"lat": 61.85, "lng": -6.80, "company": "Bakkafrost"},
}

# CMEMS bounding box
FAROE_BBOX = {"lat_min": 61.3, "lat_max": 62.5, "lon_min": -7.5, "lon_max": -6.2}

# Hagstova PxWeb API
HAGSTOVA_API = "https://statbank.hagstova.fo/api/v1/en/H2/VV/VV02/hav_tikin.px"


@dataclass
class FaroeProductionData:
    """Annual harvest from Hagstova."""
    year: int
    salmon_tonnes: float = 0.0
    trout_tonnes: float = 0.0
    total_tonnes: float = 0.0


@dataclass
class FaroeSnapshot:
    """Current state of Faroe Islands aquaculture."""
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    production_history: list[FaroeProductionData] = field(default_factory=list)
    latest_production: FaroeProductionData | None = None
    regions: list[dict] = field(default_factory=list)
    avg_sst: float | None = None
    avg_chl_a: float | None = None
    bloom_risk: str = "unknown"
    disease_status: str = "vaccinated"  # Mandatory ISA vaccination
    disease_events: int = 0
    disruption_level: str = "normal"
    disruption_pct: float = 0.0
    insights: list[str] = field(default_factory=list)


class FaroeMonitor:
    """Monitors Faroe Islands salmon farming."""

    _cache: FaroeSnapshot | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=6)
    _production_cache: list[FaroeProductionData] | None = None

    async def fetch_production(self) -> list[FaroeProductionData]:
        """Fetch harvest data from Hagstova PxWeb."""
        if self._production_cache:
            return self._production_cache

        results: list[FaroeProductionData] = []
        try:
            query = {"query": [], "response": {"format": "json"}}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(HAGSTOVA_API, json=query)
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get("data", [])
                    yearly: dict[int, FaroeProductionData] = {}
                    for row in rows:
                        keys = row.get("key", [])
                        vals = row.get("values", [])
                        if len(keys) >= 2 and len(vals) >= 1:
                            species = keys[0]
                            try:
                                year = int(keys[-1])
                            except (ValueError, IndexError):
                                continue
                            try:
                                tonnes = float(vals[0]) if vals[0] not in (".", "", None) else 0.0
                            except (ValueError, TypeError):
                                tonnes = 0.0
                            if year not in yearly:
                                yearly[year] = FaroeProductionData(year=year)
                            if "lax" in species.lower() or "salmon" in species.lower() or species == "01":
                                yearly[year].salmon_tonnes = tonnes
                            else:
                                yearly[year].trout_tonnes = tonnes

                    for yr in sorted(yearly.keys()):
                        p = yearly[yr]
                        p.total_tonnes = p.salmon_tonnes + p.trout_tonnes
                        results.append(p)

                    self._production_cache = results
                    log.info("faroe.production_fetched", years=len(results))
        except Exception as exc:
            log.warning("faroe.production_fetch_failed", error=str(exc)[:120])
        return results

    async def fetch_cmems_conditions(self) -> dict:
        """Fetch SST + chlorophyll from CMEMS for Faroese waters."""
        conditions: dict = {"sst": None, "chl_a": None, "bloom_risk": "unknown"}
        try:
            import copernicusmarine
            from config.settings import settings
            username = getattr(settings, "cmems_username", "")
            if not username:
                return conditions

            target_date = dt.date.today() - dt.timedelta(days=2)
            bbox = FAROE_BBOX

            # SST (global product, works for Faroes)
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
                log.debug("faroe.cmems_sst_failed", error=str(exc)[:80])

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
                    chl = round(float(valid.mean()), 2)
                    conditions["chl_a"] = chl
                    conditions["bloom_risk"] = (
                        "CRITICAL" if chl >= 10 else "HIGH" if chl >= 5 else
                        "ELEVATED" if chl >= 2 else "LOW"
                    )
                ds.close()
            except Exception as exc:
                log.debug("faroe.cmems_chl_failed", error=str(exc)[:80])

        except ImportError:
            pass
        return conditions

    async def get_snapshot(self) -> FaroeSnapshot:
        """Get current Faroe Islands snapshot."""
        now = dt.datetime.now(dt.UTC)
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        production = await self.fetch_production()
        cmems = await self.fetch_cmems_conditions()

        # Disease from WOAH
        disease_events = 0
        try:
            from core.market.disease_alerts import disease_alert_engine
            alerts = disease_alert_engine.get_country_alerts("FRO")
            if alerts:
                disease_events = len(alerts)
        except Exception:
            pass

        disruption = "normal"
        disruption_pct = 0.0
        if disease_events > 2:
            disruption = "elevated"
            disruption_pct = min(10, disease_events * 2)

        insights = []
        if production:
            latest = production[-1]
            if len(production) >= 2 and production[-2].salmon_tonnes > 0:
                growth = (latest.salmon_tonnes - production[-2].salmon_tonnes) / production[-2].salmon_tonnes * 100
                insights.append(f"Faroe salmon harvest {latest.year}: {latest.salmon_tonnes:,.0f}t GWT ({'+' if growth > 0 else ''}{growth:.0f}% YoY)")

        if cmems["sst"] is not None:
            insights.append(f"Faroese waters SST: {cmems['sst']}°C | Bloom risk: {cmems['bloom_risk']}")

        insights.append("Mandatory ISA vaccination since 2016 — single-generation single-fjord strategy")
        insights.append(f"Bakkafrost dominates ~95% of Faroese salmon production ({len(FAROE_REGIONS)} farm regions)")

        snapshot = FaroeSnapshot(
            production_history=production,
            latest_production=production[-1] if production else None,
            regions=[{"name": k, **v} for k, v in FAROE_REGIONS.items()],
            avg_sst=cmems["sst"],
            avg_chl_a=cmems["chl_a"],
            bloom_risk=cmems["bloom_risk"],
            disease_events=disease_events,
            disruption_level=disruption,
            disruption_pct=disruption_pct,
            insights=insights,
        )

        self._cache = snapshot
        self._cache_time = now
        log.info("faroe.snapshot_complete", sst=cmems["sst"], bloom=cmems["bloom_risk"])
        return snapshot

    def get_latest_snapshot(self) -> dict | None:
        if not self._cache:
            return None
        s = self._cache
        return {
            "disease_events": s.disease_events,
            "disruption_level": s.disruption_level,
            "disruption_pct": s.disruption_pct,
            "bloom_risk": s.bloom_risk,
            "sst": s.avg_sst,
            "latest_production_tonnes": s.latest_production.salmon_tonnes if s.latest_production else 0,
        }

    def get_farms_geojson(self) -> dict:
        features = []
        for name, info in FAROE_REGIONS.items():
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [info["lng"], info["lat"]]},
                "properties": {
                    "name": name,
                    "company": info["company"],
                    "country": "Faroe Islands",
                    "sst": self._cache.avg_sst if self._cache else None,
                    "bloom_risk": self._cache.bloom_risk if self._cache else "unknown",
                    "isa_vaccinated": True,
                },
            })
        return {"type": "FeatureCollection", "features": features}


# Singleton
faroe_monitor = FaroeMonitor()
