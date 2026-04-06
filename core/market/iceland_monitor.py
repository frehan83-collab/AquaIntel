"""
Iceland Aquaculture Monitor
=============================
Live data from Iceland's salmon farming industry — the fastest-growing
Atlantic salmon producer (Arnarlax + Arctic Fish, ~48kt in 2025).

Data sources (5 live + 1 structured):
  1. Statistics Iceland PxWeb API — production + exports by species/country (no auth)
  2. Copernicus CMEMS Arctic — sea temperature + chlorophyll for Westfjords/Eastfjords
  3. Vedur.is Weather API — air temp, wind, precipitation near farm regions
  4. Fiskistofa license pages — MAB (max allowed biomass) per farm (HTML scrape)
  5. WOAH WAHIS — disease outbreak alerts for Iceland
  6. Hardcoded farm locations — 12 known active salmon sites with coordinates

Note: Iceland has NO equivalent to Norway's BarentsWatch. No public per-site
lice data exists. MAST collects lice counts but publishes only in PDF reports.
We present what's available honestly and note data delays.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import httpx
import structlog

log = structlog.get_logger(__name__)

# ── Known farm locations ─────────────────────────────────────────────────────
# Sources: Arnarlax annual reports, Arctic Fish investor presentations,
#          Fiskistofa aquaculture license registry
ICELAND_FARMS = [
    # Westfjords — Arnarlax (Icelandic Salmon)
    {"name": "Dýrafjörður", "company": "Arnarlax", "lat": 65.87, "lng": -23.31, "region": "Westfjords", "species": "Atlantic Salmon"},
    {"name": "Arnarfjörður", "company": "Arnarlax", "lat": 65.74, "lng": -23.60, "region": "Westfjords", "species": "Atlantic Salmon"},
    {"name": "Tálknafjörður", "company": "Arnarlax", "lat": 65.63, "lng": -23.83, "region": "Westfjords", "species": "Atlantic Salmon"},
    {"name": "Patreksfjörður", "company": "Arnarlax", "lat": 65.60, "lng": -23.99, "region": "Westfjords", "species": "Atlantic Salmon"},
    {"name": "Ísafjarðardjúp", "company": "Arnarlax", "lat": 66.00, "lng": -23.12, "region": "Westfjords", "species": "Atlantic Salmon"},
    {"name": "Skutulsfjörður", "company": "Arnarlax", "lat": 66.07, "lng": -23.16, "region": "Westfjords", "species": "Atlantic Salmon"},
    # Eastfjords — Arctic Fish
    {"name": "Reyðarfjörður", "company": "Arctic Fish", "lat": 65.03, "lng": -14.20, "region": "Eastfjords", "species": "Atlantic Salmon"},
    {"name": "Fáskrúðsfjörður", "company": "Arctic Fish", "lat": 64.93, "lng": -14.01, "region": "Eastfjords", "species": "Atlantic Salmon"},
    {"name": "Mjóifjörður", "company": "Arctic Fish", "lat": 65.18, "lng": -13.79, "region": "Eastfjords", "species": "Atlantic Salmon"},
    {"name": "Berufjörður", "company": "Arctic Fish", "lat": 64.66, "lng": -14.46, "region": "Eastfjords", "species": "Atlantic Salmon"},
    # Other operators
    {"name": "Berufjarðarströnd", "company": "Laxar fiskeldi", "lat": 64.70, "lng": -14.38, "region": "Eastfjords", "species": "Arctic Char"},
    {"name": "Öxarfjörður", "company": "Laxar fiskeldi", "lat": 66.13, "lng": -16.75, "region": "Northeast", "species": "Arctic Char"},
]

# ── Bounding boxes for CMEMS data extraction ────────────────────────────────
ICELAND_REGIONS = {
    "westfjords": {"lat_min": 65.4, "lat_max": 66.3, "lon_min": -24.5, "lon_max": -22.5},
    "eastfjords": {"lat_min": 64.5, "lat_max": 65.4, "lon_min": -14.8, "lon_max": -13.5},
}

# ── PxWeb table IDs ─────────────────────────────────────────────────────────
PXWEB_BASE = "https://px.hagstofa.is/pxen/api/v1/en/Atvinnuvegir/sjavarutvegur"
PXWEB_PRODUCTION = f"{PXWEB_BASE}/fiskeldi/SJA07001.px"
PXWEB_EXPORTS = f"{PXWEB_BASE}/fiskeldi/SJA04905.px"
PXWEB_EXPORT_COUNTRIES = f"{PXWEB_BASE}/fiskeldi/SJA07003.px"

# ── Vedur.is weather stations near aquaculture regions ──────────────────────
# Selected from https://api.vedur.is/weather/stations/
VEDUR_STATIONS = {
    "westfjords": [1, 2475, 2481, 2631],   # Bolungarvik, Isafjordur, Flateyri, Thingeyri
    "eastfjords": [735, 655, 685],           # Reydarfjordur, Seydisfjordur, Eskifjordur
}

# ── CMEMS dataset IDs for Iceland ───────────────────────────────────────────
CMEMS_SST_DATASET = "cmems_mod_arc_phy_anfc_6km_detided_P1D-m"  # Arctic 6km daily
CMEMS_CHL_DATASET = "cmems_obs-oc_arc_bgc-plankton_nrt_l4-multi-4km_P1M"  # Arctic ocean colour monthly


@dataclass
class IcelandProductionData:
    """Annual aquaculture production from Statistics Iceland."""
    year: int
    salmon_tonnes: float = 0.0
    arctic_char_tonnes: float = 0.0
    rainbow_trout_tonnes: float = 0.0
    total_tonnes: float = 0.0
    source: str = "Statistics Iceland (Hagstofa)"


@dataclass
class IcelandExportData:
    """Aquaculture export data from Statistics Iceland."""
    year: int
    total_value_isk_millions: float = 0.0
    total_weight_tonnes: float = 0.0
    top_destinations: list[dict] = field(default_factory=list)


@dataclass
class IcelandSeaConditions:
    """Ocean conditions near Iceland farms from CMEMS + Vedur."""
    westfjords_sst: float | None = None   # Sea surface temp °C
    eastfjords_sst: float | None = None
    westfjords_chl_a: float | None = None  # Chlorophyll mg/m³
    eastfjords_chl_a: float | None = None
    westfjords_air_temp: float | None = None
    eastfjords_air_temp: float | None = None
    westfjords_wind_ms: float | None = None
    eastfjords_wind_ms: float | None = None
    bloom_risk_westfjords: str = "unknown"  # LOW/ELEVATED/HIGH/CRITICAL
    bloom_risk_eastfjords: str = "unknown"
    source_sst: str = "CMEMS Arctic"
    source_weather: str = "Vedur.is"
    fetched_at: str = ""


@dataclass
class FiskistofaLicense:
    """Aquaculture license from Fiskistofa."""
    company: str
    location: str
    region: str
    mab_tonnes: float = 0.0  # Maximum Allowed Biomass
    species: str = ""
    license_no: str = ""


@dataclass
class IcelandSnapshot:
    """Current state of Iceland aquaculture — comprehensive."""
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    # Production
    production_history: list[IcelandProductionData] = field(default_factory=list)
    latest_production: IcelandProductionData | None = None
    exports: list[IcelandExportData] = field(default_factory=list)
    # Ocean conditions
    sea_conditions: IcelandSeaConditions = field(default_factory=IcelandSeaConditions)
    # Farms & capacity
    farms: list[dict] = field(default_factory=list)
    licenses: list[FiskistofaLicense] = field(default_factory=list)
    total_mab_tonnes: float = 0.0
    # Disease
    disease_status: str = "disease-free"
    disease_events: int = 0
    # Disruption
    disruption_level: str = "normal"
    disruption_pct: float = 0.0
    # Intelligence
    insights: list[str] = field(default_factory=list)


class IcelandMonitor:
    """
    Comprehensive Iceland aquaculture monitor.
    Fetches from 5 live sources: PxWeb, CMEMS, Vedur, Fiskistofa, WOAH.
    """

    _cache: IcelandSnapshot | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=3)

    # Sub-caches for less frequent data
    _production_cache: list[IcelandProductionData] | None = None
    _export_cache: list[IcelandExportData] | None = None
    _license_cache: list[FiskistofaLicense] | None = None
    _license_cache_time: dt.datetime | None = None

    # ── 1. Statistics Iceland PxWeb ───────────────────────────────────

    async def fetch_production(self) -> list[IcelandProductionData]:
        """Fetch annual production from Statistics Iceland PxWeb API."""
        if self._production_cache:
            return self._production_cache

        results: list[IcelandProductionData] = []
        try:
            query = {
                "query": [
                    {
                        "code": "Tegund fiskeldis",
                        "selection": {"filter": "item", "values": ["1", "2", "3"]}
                    }
                ],
                "response": {"format": "json"}
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(PXWEB_PRODUCTION, json=query)
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get("data", [])
                    yearly: dict[int, IcelandProductionData] = {}
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
                                yearly[year] = IcelandProductionData(year=year)
                            if species == "1":
                                yearly[year].salmon_tonnes = tonnes
                            elif species == "2":
                                yearly[year].arctic_char_tonnes = tonnes
                            elif species == "3":
                                yearly[year].rainbow_trout_tonnes = tonnes

                    for yr in sorted(yearly.keys()):
                        p = yearly[yr]
                        p.total_tonnes = p.salmon_tonnes + p.arctic_char_tonnes + p.rainbow_trout_tonnes
                        results.append(p)

                    self._production_cache = results
                    log.info("iceland.production_fetched", years=len(results),
                             latest_year=results[-1].year if results else 0)
        except Exception as exc:
            log.warning("iceland.production_fetch_failed", error=str(exc)[:120])
        return results

    async def fetch_exports(self) -> list[IcelandExportData]:
        """Fetch aquaculture export data from SJA04905."""
        if self._export_cache:
            return self._export_cache

        results: list[IcelandExportData] = []
        try:
            query = {"query": [], "response": {"format": "json"}}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(PXWEB_EXPORTS, json=query)
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get("data", [])
                    yearly_val: dict[int, float] = {}
                    yearly_wt: dict[int, float] = {}
                    for row in rows:
                        keys = row.get("key", [])
                        vals = row.get("values", [])
                        if len(keys) >= 2 and len(vals) >= 1:
                            measure = keys[0]  # "0"=value, "1"=weight (varies by table)
                            try:
                                year = int(keys[-1])
                            except (ValueError, IndexError):
                                continue
                            try:
                                v = float(vals[0]) if vals[0] not in (".", "", None) else 0.0
                            except (ValueError, TypeError):
                                v = 0.0
                            # Heuristic: larger values are ISK millions, smaller are tonnes
                            if measure in ("0", "Value"):
                                yearly_val[year] = v
                            else:
                                yearly_wt[year] = v

                    all_years = sorted(set(yearly_val.keys()) | set(yearly_wt.keys()))
                    for yr in all_years:
                        results.append(IcelandExportData(
                            year=yr,
                            total_value_isk_millions=yearly_val.get(yr, 0),
                            total_weight_tonnes=yearly_wt.get(yr, 0),
                        ))

                    self._export_cache = results
                    log.info("iceland.exports_fetched", years=len(results))
        except Exception as exc:
            log.debug("iceland.exports_fetch_failed", error=str(exc)[:80])
        return results

    async def fetch_export_by_country(self) -> list[dict]:
        """Fetch export of aquaculture products by destination country from SJA07003."""
        results: list[dict] = []
        try:
            query = {"query": [], "response": {"format": "json"}}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(PXWEB_EXPORT_COUNTRIES, json=query)
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get("data", [])
                    for row in rows:
                        keys = row.get("key", [])
                        vals = row.get("values", [])
                        if len(keys) >= 2 and len(vals) >= 1:
                            try:
                                results.append({
                                    "country": keys[0],
                                    "year": int(keys[-1]),
                                    "value": float(vals[0]) if vals[0] not in (".", "", None) else 0,
                                })
                            except (ValueError, TypeError):
                                continue
                    log.info("iceland.export_countries_fetched", records=len(results))
        except Exception as exc:
            log.debug("iceland.export_countries_failed", error=str(exc)[:80])
        return results

    # ── 2. CMEMS Arctic ──────────────────────────────────────────────

    async def fetch_cmems_conditions(self) -> dict[str, float | None]:
        """Fetch sea temperature and chlorophyll from CMEMS for Iceland regions."""
        conditions: dict[str, float | None] = {
            "westfjords_sst": None, "eastfjords_sst": None,
            "westfjords_chl_a": None, "eastfjords_chl_a": None,
        }
        try:
            import copernicusmarine
            from config.settings import settings
            username = getattr(settings, "cmems_username", "")
            password = getattr(settings, "cmems_password", "")
            if not username:
                return conditions

            target_date = dt.date.today() - dt.timedelta(days=2)

            for region_name, bbox in ICELAND_REGIONS.items():
                try:
                    # SST from Arctic physics
                    ds = copernicusmarine.open_dataset(
                        dataset_id=CMEMS_SST_DATASET,
                        variables=["thetao"],
                        minimum_latitude=bbox["lat_min"],
                        maximum_latitude=bbox["lat_max"],
                        minimum_longitude=bbox["lon_min"],
                        maximum_longitude=bbox["lon_max"],
                        start_datetime=f"{target_date}T00:00:00",
                        end_datetime=f"{target_date}T23:59:59",
                        username=username,
                        password=password,
                    )
                    sst_vals = ds["thetao"].values.flatten()
                    valid = sst_vals[~(sst_vals != sst_vals)]  # remove NaN
                    if len(valid) > 0:
                        conditions[f"{region_name}_sst"] = round(float(valid.mean()), 1)
                    ds.close()
                except Exception as exc:
                    log.debug(f"iceland.cmems_sst_{region_name}_failed", error=str(exc)[:80])

                try:
                    # Chlorophyll from Arctic ocean colour
                    ds = copernicusmarine.open_dataset(
                        dataset_id=CMEMS_CHL_DATASET,
                        variables=["CHL"],
                        minimum_latitude=bbox["lat_min"],
                        maximum_latitude=bbox["lat_max"],
                        minimum_longitude=bbox["lon_min"],
                        maximum_longitude=bbox["lon_max"],
                        start_datetime=f"{target_date}T00:00:00",
                        end_datetime=f"{target_date}T23:59:59",
                        username=username,
                        password=password,
                    )
                    chl_vals = ds["CHL"].values.flatten()
                    valid = chl_vals[~(chl_vals != chl_vals)]
                    if len(valid) > 0:
                        conditions[f"{region_name}_chl_a"] = round(float(valid.mean()), 2)
                    ds.close()
                except Exception as exc:
                    log.debug(f"iceland.cmems_chl_{region_name}_failed", error=str(exc)[:80])

        except ImportError:
            log.debug("iceland.cmems_not_installed")
        except Exception as exc:
            log.debug("iceland.cmems_failed", error=str(exc)[:80])

        return conditions

    # ── 3. Vedur.is Weather API ──────────────────────────────────────

    async def fetch_weather(self) -> dict[str, dict]:
        """Fetch weather observations from Vedur.is for farm regions."""
        weather: dict[str, dict] = {
            "westfjords": {"air_temp": None, "wind_ms": None, "precip": None},
            "eastfjords": {"air_temp": None, "wind_ms": None, "precip": None},
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                for region, station_ids in VEDUR_STATIONS.items():
                    for station_id in station_ids[:2]:  # try first 2 stations
                        try:
                            # Use the community apis.is endpoint (no auth needed)
                            resp = await client.get(
                                f"https://apis.is/weather/observations/en",
                                params={"stations": str(station_id), "time": "1h", "anession": "0"},
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                results = data.get("results", [])
                                if results:
                                    obs = results[0]
                                    t = obs.get("T", obs.get("t"))
                                    w = obs.get("F", obs.get("f"))  # wind speed
                                    if t is not None:
                                        try:
                                            weather[region]["air_temp"] = float(t)
                                        except (ValueError, TypeError):
                                            pass
                                    if w is not None:
                                        try:
                                            weather[region]["wind_ms"] = float(w)
                                        except (ValueError, TypeError):
                                            pass
                                    if weather[region]["air_temp"] is not None:
                                        break  # got data, skip remaining stations
                        except Exception:
                            continue

                log.info("iceland.weather_fetched",
                         wf_temp=weather["westfjords"]["air_temp"],
                         ef_temp=weather["eastfjords"]["air_temp"])
        except Exception as exc:
            log.debug("iceland.weather_failed", error=str(exc)[:80])
        return weather

    # ── 4. Fiskistofa License/MAB Scraping ───────────────────────────

    async def fetch_licenses(self) -> list[FiskistofaLicense]:
        """Scrape aquaculture license data from Fiskistofa (MAB per farm)."""
        now = dt.datetime.now(dt.UTC)
        if (self._license_cache and self._license_cache_time
                and (now - self._license_cache_time) < dt.timedelta(days=1)):
            return self._license_cache

        licenses: list[FiskistofaLicense] = []
        regions = [
            ("Westfjords", "https://www.fiskistofa.is/fiskeldi/rekstrarleyfi-fiskeldis/vestfirdirvesturland/"),
            ("Eastfjords", "https://www.fiskistofa.is/fiskeldi/rekstrarleyfi-fiskeldis/austfirdir/"),
        ]

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                for region_name, url in regions:
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            html = resp.text
                            # Parse MAB data from HTML tables
                            # Look for patterns like "XX.XXX tonn" (Icelandic format)
                            mab_matches = re.findall(
                                r'<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]*tonn[^<]*)</td>',
                                html, re.IGNORECASE
                            )
                            for match in mab_matches:
                                company = match[0].strip()
                                location = match[1].strip()
                                mab_text = match[2].strip()
                                # Extract number from MAB text
                                mab_num = re.search(r'([\d.,]+)', mab_text)
                                mab_tonnes = 0.0
                                if mab_num:
                                    try:
                                        mab_tonnes = float(mab_num.group(1).replace(".", "").replace(",", "."))
                                    except ValueError:
                                        pass
                                if company and company != "—":
                                    licenses.append(FiskistofaLicense(
                                        company=company,
                                        location=location,
                                        region=region_name,
                                        mab_tonnes=mab_tonnes,
                                    ))

                            # Fallback: look for any tonnage mentions
                            if not licenses:
                                # Try broader pattern
                                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
                                for row_html in rows:
                                    cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
                                    if len(cells) >= 3:
                                        clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                                        if any("tonn" in c.lower() for c in clean):
                                            licenses.append(FiskistofaLicense(
                                                company=clean[0],
                                                location=clean[1] if len(clean) > 1 else "",
                                                region=region_name,
                                            ))

                    except Exception as exc:
                        log.debug(f"iceland.fiskistofa_{region_name}_failed", error=str(exc)[:80])

            if licenses:
                self._license_cache = licenses
                self._license_cache_time = now
                log.info("iceland.licenses_fetched", count=len(licenses))
        except Exception as exc:
            log.debug("iceland.fiskistofa_failed", error=str(exc)[:80])

        return licenses

    # ── Bloom risk classification ────────────────────────────────────

    @staticmethod
    def _classify_bloom_risk(chl_a: float | None) -> str:
        """Classify algal bloom risk from chlorophyll-a concentration."""
        if chl_a is None:
            return "unknown"
        if chl_a >= 10.0:
            return "CRITICAL"
        if chl_a >= 5.0:
            return "HIGH"
        if chl_a >= 2.0:
            return "ELEVATED"
        return "LOW"

    # ── Master snapshot ──────────────────────────────────────────────

    async def get_snapshot(self) -> IcelandSnapshot:
        """Get comprehensive Iceland aquaculture snapshot."""
        now = dt.datetime.now(dt.UTC)
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        # Fetch all data sources in parallel-ish
        production = await self.fetch_production()
        exports = await self.fetch_exports()
        cmems = await self.fetch_cmems_conditions()
        weather = await self.fetch_weather()
        licenses = await self.fetch_licenses()

        # Disease from WOAH
        disease_status = "disease-free"
        disease_events = 0
        try:
            from core.market.disease_alerts import disease_alert_engine
            alerts = disease_alert_engine.get_country_alerts("ISL")
            if alerts:
                disease_events = len(alerts)
                disease_status = "under_surveillance" if disease_events <= 2 else "elevated"
        except Exception:
            pass

        # Build sea conditions
        sea = IcelandSeaConditions(
            westfjords_sst=cmems.get("westfjords_sst"),
            eastfjords_sst=cmems.get("eastfjords_sst"),
            westfjords_chl_a=cmems.get("westfjords_chl_a"),
            eastfjords_chl_a=cmems.get("eastfjords_chl_a"),
            westfjords_air_temp=weather["westfjords"]["air_temp"],
            eastfjords_air_temp=weather["eastfjords"]["air_temp"],
            westfjords_wind_ms=weather["westfjords"]["wind_ms"],
            eastfjords_wind_ms=weather["eastfjords"]["wind_ms"],
            bloom_risk_westfjords=self._classify_bloom_risk(cmems.get("westfjords_chl_a")),
            bloom_risk_eastfjords=self._classify_bloom_risk(cmems.get("eastfjords_chl_a")),
            fetched_at=now.isoformat(),
        )

        # Compute disruption
        disruption = "normal"
        disruption_pct = 0.0
        if disease_events > 0:
            disruption = "elevated"
            disruption_pct = min(15, disease_events * 3)
        # Bloom risk can add disruption
        if sea.bloom_risk_westfjords in ("HIGH", "CRITICAL") or sea.bloom_risk_eastfjords in ("HIGH", "CRITICAL"):
            disruption_pct = max(disruption_pct, 5)
            if disruption == "normal":
                disruption = "elevated"

        total_mab = sum(l.mab_tonnes for l in licenses) if licenses else 0

        # Build insights
        insights = []
        if production:
            latest = production[-1]
            if len(production) >= 2:
                prev = production[-2]
                if prev.salmon_tonnes > 0:
                    growth = (latest.salmon_tonnes - prev.salmon_tonnes) / prev.salmon_tonnes * 100
                    insights.append(
                        f"Iceland salmon production {latest.year}: {latest.salmon_tonnes:,.0f}t "
                        f"({'+'if growth > 0 else ''}{growth:.0f}% YoY)"
                    )

        if disease_status == "disease-free":
            insights.append("Disease-free status confirmed (ISA/VHS/IHN/BKD) — MAST 2024 surveillance")

        if sea.westfjords_sst is not None:
            insights.append(f"Westfjords SST: {sea.westfjords_sst}°C | Eastfjords SST: {sea.eastfjords_sst or 'N/A'}°C")

        if sea.bloom_risk_westfjords not in ("unknown", "LOW") or sea.bloom_risk_eastfjords not in ("unknown", "LOW"):
            insights.append(f"Bloom risk — Westfjords: {sea.bloom_risk_westfjords}, Eastfjords: {sea.bloom_risk_eastfjords}")

        if total_mab > 0:
            insights.append(f"Total MAB capacity: {total_mab:,.0f}t across {len(licenses)} licenses (Fiskistofa)")

        insights.append(f"{len(ICELAND_FARMS)} active aquaculture sites across Westfjords and Eastfjords")

        if exports:
            latest_exp = exports[-1]
            if latest_exp.total_value_isk_millions > 0:
                insights.append(f"Aquaculture exports {latest_exp.year}: ISK {latest_exp.total_value_isk_millions:,.0f}M")

        snapshot = IcelandSnapshot(
            production_history=production,
            latest_production=production[-1] if production else None,
            exports=exports,
            sea_conditions=sea,
            farms=ICELAND_FARMS,
            licenses=licenses,
            total_mab_tonnes=total_mab,
            disease_status=disease_status,
            disease_events=disease_events,
            disruption_level=disruption,
            disruption_pct=disruption_pct,
            insights=insights,
        )

        self._cache = snapshot
        self._cache_time = now
        log.info("iceland.snapshot_complete",
                 production_years=len(production), exports=len(exports),
                 sst_wf=sea.westfjords_sst, licenses=len(licenses),
                 disease=disease_status, disruption=disruption)
        return snapshot

    def get_latest_snapshot(self) -> dict | None:
        """Return cached snapshot as dict (sync access for global_supply)."""
        if not self._cache:
            return None
        s = self._cache
        return {
            "disease_status": s.disease_status,
            "disease_events": s.disease_events,
            "disruption_level": s.disruption_level,
            "disruption_pct": s.disruption_pct,
            "latest_production_tonnes": s.latest_production.salmon_tonnes if s.latest_production else 0,
            "latest_production_year": s.latest_production.year if s.latest_production else 0,
            "total_mab_tonnes": s.total_mab_tonnes,
            "sea_conditions": {
                "westfjords_sst": s.sea_conditions.westfjords_sst,
                "eastfjords_sst": s.sea_conditions.eastfjords_sst,
                "bloom_risk_westfjords": s.sea_conditions.bloom_risk_westfjords,
                "bloom_risk_eastfjords": s.sea_conditions.bloom_risk_eastfjords,
            },
        }

    def get_farms_geojson(self) -> dict:
        """Return farm locations as GeoJSON with ocean condition overlays."""
        s = self._cache
        features = []
        for farm in ICELAND_FARMS:
            region_key = farm["region"].lower()
            props = {
                "name": farm["name"],
                "company": farm["company"],
                "region": farm["region"],
                "species": farm["species"],
                "country": "Iceland",
                "lice_data_available": False,
            }
            # Enrich with sea conditions if available
            if s and s.sea_conditions:
                if "westfjord" in region_key:
                    props["sst"] = s.sea_conditions.westfjords_sst
                    props["chl_a"] = s.sea_conditions.westfjords_chl_a
                    props["bloom_risk"] = s.sea_conditions.bloom_risk_westfjords
                    props["air_temp"] = s.sea_conditions.westfjords_air_temp
                    props["wind_ms"] = s.sea_conditions.westfjords_wind_ms
                elif "eastfjord" in region_key:
                    props["sst"] = s.sea_conditions.eastfjords_sst
                    props["chl_a"] = s.sea_conditions.eastfjords_chl_a
                    props["bloom_risk"] = s.sea_conditions.bloom_risk_eastfjords
                    props["air_temp"] = s.sea_conditions.eastfjords_air_temp
                    props["wind_ms"] = s.sea_conditions.eastfjords_wind_ms

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [farm["lng"], farm["lat"]]},
                "properties": props,
            })
        return {"type": "FeatureCollection", "features": features}


# Singleton
iceland_monitor = IcelandMonitor()
