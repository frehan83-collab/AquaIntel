"""
SEPA Scotland Water Quality Client
=====================================
Fetches water quality data from the Scottish Environment Protection Agency (SEPA)
Time Series API (KiWIS) for monitoring conditions near salmon farming regions.

SEPA monitors water temperature, dissolved oxygen, and other parameters across
Scotland's river and coastal network. This data supplements CMEMS satellite SST
with in-situ measurements near aquaculture sites.

API documentation: https://timeseriesdoc.sepa.org.uk/api-documentation/
Base URL: https://timeseriesdoc.sepa.org.uk/KiWIS/KiWIS

Scottish salmon farming regions (7):
  - Shetland, Orkney, NW Highlands, Skye, Argyll, Outer Hebrides, Loch Linnhe

Data licence: Open Government Licence (Scotland)
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.market.data_provenance import DataProvenance

log = structlog.get_logger(__name__)

# ── SEPA KiWIS API ─────────────────────────────────────────────────────
SEPA_BASE_URL = "https://timeseriesdoc.sepa.org.uk/KiWIS/KiWIS"
SEPA_TIMEOUT = 20.0

# ── Scottish aquaculture regions with representative coordinates ───────
# Used for proximity matching to SEPA monitoring stations
SCOTLAND_REGIONS = {
    "Shetland":       {"lat": 60.40, "lng": -1.20, "search_radius_km": 50},
    "Orkney":         {"lat": 59.00, "lng": -3.10, "search_radius_km": 40},
    "NW Highlands":   {"lat": 57.85, "lng": -5.50, "search_radius_km": 60},
    "Skye":           {"lat": 57.30, "lng": -5.70, "search_radius_km": 40},
    "Argyll":         {"lat": 56.20, "lng": -5.40, "search_radius_km": 50},
    "Outer Hebrides": {"lat": 57.80, "lng": -7.00, "search_radius_km": 50},
    "Loch Linnhe":    {"lat": 56.70, "lng": -5.30, "search_radius_km": 30},
}

# KiWIS parameter type names for water quality measurements
PARAM_WATER_TEMPERATURE = "Water Temperature"
PARAM_DISSOLVED_OXYGEN = "Dissolved Oxygen"

# Station groups relevant to coastal/marine aquaculture monitoring
# SEPA station_no patterns for coastal stations near farming regions
SEPA_REGION_STATION_HINTS = {
    "Shetland":       ["Shetland", "Lerwick"],
    "Orkney":         ["Orkney", "Kirkwall"],
    "NW Highlands":   ["Loch Broom", "Ullapool", "Wester Ross", "Loch Ewe"],
    "Skye":           ["Skye", "Portree", "Lochalsh"],
    "Argyll":         ["Loch Fyne", "Oban", "Argyll", "Loch Etive"],
    "Outer Hebrides": ["Stornoway", "Lewis", "Harris"],
    "Loch Linnhe":    ["Loch Linnhe", "Fort William", "Loch Leven"],
}


@dataclass
class SEPAStation:
    """A SEPA monitoring station."""
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    station_no: str = ""
    catchment: str = ""
    region: str = ""


@dataclass
class SEPATimeSeries:
    """A time series measurement from a SEPA station."""
    station_id: str
    station_name: str
    parameter: str
    unit: str
    timestamps: list[str] = field(default_factory=list)
    values: list[float] = field(default_factory=list)


@dataclass
class RegionWaterQuality:
    """Aggregated water quality for a Scottish salmon farming region."""
    region: str
    avg_temperature_c: Optional[float] = None
    min_temperature_c: Optional[float] = None
    max_temperature_c: Optional[float] = None
    avg_dissolved_oxygen_mgl: Optional[float] = None
    min_dissolved_oxygen_mgl: Optional[float] = None
    n_temperature_stations: int = 0
    n_do_stations: int = 0
    stations: list[dict] = field(default_factory=list)
    period: str = ""
    assessment: str = "unknown"


class SEPAClient:
    """
    Fetches water quality data from SEPA Time Series API (KiWIS).

    SEPA's KiWIS endpoint provides access to hydrometric and water quality
    monitoring stations across Scotland. We query for water temperature and
    dissolved oxygen near the 7 major salmon farming regions.

    Cache: 6 hours (SEPA data updates hourly but we aggregate)
    """

    def __init__(self) -> None:
        self._station_cache: Optional[list[SEPAStation]] = None
        self._station_cache_time: Optional[dt.datetime] = None
        self._quality_cache: Optional[dict[str, RegionWaterQuality]] = None
        self._quality_cache_time: Optional[dt.datetime] = None
        self._cache_ttl = dt.timedelta(hours=6)

    def _cache_valid(self, cache_time: Optional[dt.datetime]) -> bool:
        if cache_time is None:
            return False
        return (dt.datetime.now(dt.UTC) - cache_time) < self._cache_ttl

    # ── Station discovery ──────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def _kiwis_request(self, params: dict) -> dict | list | None:
        """Make a request to the SEPA KiWIS API."""
        params["service"] = "kisters"
        params["type"] = "queryServices"
        params["format"] = "json"
        async with httpx.AsyncClient(timeout=SEPA_TIMEOUT) as client:
            resp = await client.get(SEPA_BASE_URL, params=params)
            if resp.status_code == 200:
                return resp.json()
            log.debug("sepa.kiwis_request_error", status=resp.status_code,
                      request=params.get("request", ""))
        return None

    async def fetch_water_quality_stations(self, region: Optional[str] = None) -> list[SEPAStation]:
        """
        List SEPA monitoring stations near Scottish salmon farming regions.

        Args:
            region: Optional region name to filter (e.g. "Shetland", "Argyll").
                    If None, returns stations for all 7 farming regions.

        Returns:
            List of SEPAStation objects near aquaculture sites.
        """
        if self._cache_valid(self._station_cache_time) and self._station_cache:
            stations = self._station_cache
            if region:
                stations = [s for s in stations if s.region == region]
            return stations

        all_stations: list[SEPAStation] = []
        try:
            # Query SEPA for station list with water temperature parameter
            data = await self._kiwis_request({
                "request": "getStationList",
                "parametertype_name": PARAM_WATER_TEMPERATURE,
                "returnfields": "station_id,station_name,station_latitude,station_longitude,station_no,catchment_name",
            })

            if data and isinstance(data, list) and len(data) > 1:
                # First row is header, subsequent rows are data
                headers = data[0] if isinstance(data[0], list) else []
                for row in data[1:]:
                    if not isinstance(row, list) or len(row) < 4:
                        continue
                    try:
                        lat = float(row[2]) if row[2] else 0.0
                        lng = float(row[3]) if row[3] else 0.0
                        name = str(row[1]) if row[1] else ""
                        station_no = str(row[4]) if len(row) > 4 and row[4] else ""
                        catchment = str(row[5]) if len(row) > 5 and row[5] else ""

                        # Match to farming region by name hints
                        matched_region = self._match_station_to_region(name, catchment, lat, lng)
                        if matched_region:
                            all_stations.append(SEPAStation(
                                station_id=str(row[0]),
                                station_name=name,
                                latitude=lat,
                                longitude=lng,
                                station_no=station_no,
                                catchment=catchment,
                                region=matched_region,
                            ))
                    except (ValueError, TypeError, IndexError):
                        continue

            self._station_cache = all_stations
            self._station_cache_time = dt.datetime.now(dt.UTC)
            log.info("sepa.stations_fetched", total=len(all_stations),
                     regions=len(set(s.region for s in all_stations)))

        except Exception as exc:
            log.warning("sepa.station_fetch_failed", error=str(exc)[:120])

        if region:
            return [s for s in all_stations if s.region == region]
        return all_stations

    def _match_station_to_region(self, name: str, catchment: str, lat: float, lng: float) -> Optional[str]:
        """Match a SEPA station to a salmon farming region by name or proximity."""
        name_lower = (name + " " + catchment).lower()

        # First try name-based matching
        for region, hints in SEPA_REGION_STATION_HINTS.items():
            for hint in hints:
                if hint.lower() in name_lower:
                    return region

        # Fall back to proximity-based matching
        if lat != 0 and lng != 0:
            import math
            best_dist = float("inf")
            best_region = None
            for region, info in SCOTLAND_REGIONS.items():
                # Approximate distance in km using equirectangular projection
                dlat = math.radians(lat - info["lat"])
                dlng = math.radians(lng - info["lng"]) * math.cos(math.radians(lat))
                dist_km = math.sqrt(dlat**2 + dlng**2) * 6371
                if dist_km < info["search_radius_km"] and dist_km < best_dist:
                    best_dist = dist_km
                    best_region = region
            return best_region

        return None

    # ── Time series data ───────────────────────────────────────────────

    async def fetch_water_temperature(
        self,
        station_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[SEPATimeSeries]:
        """
        Fetch water temperature time series for a specific station.

        Args:
            station_id: SEPA station ID.
            start_date: Start date (ISO format, e.g. "2026-01-01"). Defaults to 7 days ago.
            end_date: End date (ISO format). Defaults to today.

        Returns:
            SEPATimeSeries with temperature readings, or None if unavailable.
        """
        if not start_date:
            start_date = (dt.date.today() - dt.timedelta(days=7)).isoformat()
        if not end_date:
            end_date = dt.date.today().isoformat()

        return await self._fetch_ts(station_id, PARAM_WATER_TEMPERATURE, "°C", start_date, end_date)

    async def fetch_dissolved_oxygen(
        self,
        station_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[SEPATimeSeries]:
        """
        Fetch dissolved oxygen time series for a specific station.

        Args:
            station_id: SEPA station ID.
            start_date: Start date (ISO format). Defaults to 7 days ago.
            end_date: End date (ISO format). Defaults to today.

        Returns:
            SEPATimeSeries with DO readings, or None if unavailable.
        """
        if not start_date:
            start_date = (dt.date.today() - dt.timedelta(days=7)).isoformat()
        if not end_date:
            end_date = dt.date.today().isoformat()

        return await self._fetch_ts(station_id, PARAM_DISSOLVED_OXYGEN, "mg/l", start_date, end_date)

    async def _fetch_ts(
        self, station_id: str, param_name: str, unit: str,
        start_date: str, end_date: str,
    ) -> Optional[SEPATimeSeries]:
        """Fetch a time series from KiWIS for a given station and parameter."""
        try:
            # First get the time series ID for this station + parameter
            ts_list = await self._kiwis_request({
                "request": "getTimeseriesList",
                "station_id": station_id,
                "parametertype_name": param_name,
                "returnfields": "ts_id,ts_name,station_name",
            })

            if not ts_list or not isinstance(ts_list, list) or len(ts_list) < 2:
                return None

            ts_id = None
            station_name = ""
            for row in ts_list[1:]:
                if isinstance(row, list) and len(row) >= 2:
                    ts_id = str(row[0])
                    station_name = str(row[2]) if len(row) > 2 else ""
                    break

            if not ts_id:
                return None

            # Fetch the actual values
            values_data = await self._kiwis_request({
                "request": "getTimeseriesValues",
                "ts_id": ts_id,
                "from": start_date,
                "to": end_date,
                "returnfields": "Timestamp,Value",
            })

            if not values_data or not isinstance(values_data, list):
                return None

            timestamps: list[str] = []
            values: list[float] = []

            # KiWIS returns data in nested structure
            for series in values_data:
                if isinstance(series, dict):
                    for point in series.get("data", []):
                        if isinstance(point, list) and len(point) >= 2:
                            ts_str = str(point[0]) if point[0] else ""
                            val = point[1]
                            if ts_str and val is not None:
                                try:
                                    timestamps.append(ts_str)
                                    values.append(float(val))
                                except (ValueError, TypeError):
                                    continue
                elif isinstance(series, list):
                    # Alternative format: flat list of [timestamp, value] pairs
                    for point in series:
                        if isinstance(point, list) and len(point) >= 2:
                            ts_str = str(point[0]) if point[0] else ""
                            val = point[1]
                            if ts_str and val is not None:
                                try:
                                    timestamps.append(ts_str)
                                    values.append(float(val))
                                except (ValueError, TypeError):
                                    continue

            if not values:
                return None

            return SEPATimeSeries(
                station_id=station_id,
                station_name=station_name,
                parameter=param_name,
                unit=unit,
                timestamps=timestamps,
                values=values,
            )

        except Exception as exc:
            log.debug("sepa.ts_fetch_failed", station_id=station_id,
                      param=param_name, error=str(exc)[:100])
            return None

    # ── Aggregate summaries ────────────────────────────────────────────

    async def get_scottish_aquaculture_summary(self) -> dict:
        """
        Aggregate water quality near all major Scottish salmon farming regions.

        Returns a summary dict with per-region water temperature and dissolved
        oxygen averages, plus an overall assessment of farming conditions.
        """
        if self._cache_valid(self._quality_cache_time) and self._quality_cache:
            return self._format_summary(self._quality_cache, from_cache=True)

        stations = await self.fetch_water_quality_stations()
        regions: dict[str, RegionWaterQuality] = {}

        end_date = dt.date.today().isoformat()
        start_date = (dt.date.today() - dt.timedelta(days=7)).isoformat()

        for region_name in SCOTLAND_REGIONS:
            region_stations = [s for s in stations if s.region == region_name]
            rq = RegionWaterQuality(
                region=region_name,
                period=f"{start_date} to {end_date}",
            )

            temp_values: list[float] = []
            do_values: list[float] = []

            for station in region_stations[:5]:  # limit to 5 stations per region
                # Temperature
                temp_ts = await self.fetch_water_temperature(
                    station.station_id, start_date, end_date
                )
                if temp_ts and temp_ts.values:
                    avg_t = sum(temp_ts.values) / len(temp_ts.values)
                    temp_values.append(avg_t)
                    rq.stations.append({
                        "station_id": station.station_id,
                        "name": station.station_name,
                        "lat": station.latitude,
                        "lng": station.longitude,
                        "avg_temp_c": round(avg_t, 1),
                        "n_readings": len(temp_ts.values),
                    })

                # Dissolved oxygen
                do_ts = await self.fetch_dissolved_oxygen(
                    station.station_id, start_date, end_date
                )
                if do_ts and do_ts.values:
                    avg_do = sum(do_ts.values) / len(do_ts.values)
                    do_values.append(avg_do)

            if temp_values:
                rq.avg_temperature_c = round(sum(temp_values) / len(temp_values), 1)
                rq.min_temperature_c = round(min(temp_values), 1)
                rq.max_temperature_c = round(max(temp_values), 1)
                rq.n_temperature_stations = len(temp_values)

            if do_values:
                rq.avg_dissolved_oxygen_mgl = round(sum(do_values) / len(do_values), 1)
                rq.min_dissolved_oxygen_mgl = round(min(do_values), 1)
                rq.n_do_stations = len(do_values)

            # Assess conditions for salmon farming
            rq.assessment = self._assess_conditions(rq)
            regions[region_name] = rq

        self._quality_cache = regions
        self._quality_cache_time = dt.datetime.now(dt.UTC)
        log.info("sepa.summary_complete",
                 regions_with_data=sum(1 for r in regions.values()
                                       if r.avg_temperature_c is not None))
        return self._format_summary(regions, from_cache=False)

    async def get_region_water_quality(self, region: str) -> dict:
        """
        Get water quality for a specific Scottish salmon farming region.

        Args:
            region: Region name (e.g. "Shetland", "Argyll", "NW Highlands").

        Returns:
            Dict with temperature, DO, station details, and assessment.
        """
        # Normalize region name
        region_match = None
        for r in SCOTLAND_REGIONS:
            if r.lower() == region.lower() or r.lower().startswith(region.lower()):
                region_match = r
                break

        if not region_match:
            return {
                "error": f"Unknown region: {region}",
                "valid_regions": list(SCOTLAND_REGIONS.keys()),
            }

        # Try cache first
        if self._cache_valid(self._quality_cache_time) and self._quality_cache:
            rq = self._quality_cache.get(region_match)
            if rq:
                return self._format_region(rq, from_cache=True)

        # Fetch fresh for this region
        stations = await self.fetch_water_quality_stations(region=region_match)
        end_date = dt.date.today().isoformat()
        start_date = (dt.date.today() - dt.timedelta(days=7)).isoformat()

        rq = RegionWaterQuality(
            region=region_match,
            period=f"{start_date} to {end_date}",
        )

        temp_values: list[float] = []
        do_values: list[float] = []

        for station in stations[:5]:
            temp_ts = await self.fetch_water_temperature(
                station.station_id, start_date, end_date
            )
            if temp_ts and temp_ts.values:
                avg_t = sum(temp_ts.values) / len(temp_ts.values)
                temp_values.append(avg_t)
                rq.stations.append({
                    "station_id": station.station_id,
                    "name": station.station_name,
                    "lat": station.latitude,
                    "lng": station.longitude,
                    "avg_temp_c": round(avg_t, 1),
                    "n_readings": len(temp_ts.values),
                })

            do_ts = await self.fetch_dissolved_oxygen(
                station.station_id, start_date, end_date
            )
            if do_ts and do_ts.values:
                avg_do = sum(do_ts.values) / len(do_ts.values)
                do_values.append(avg_do)

        if temp_values:
            rq.avg_temperature_c = round(sum(temp_values) / len(temp_values), 1)
            rq.min_temperature_c = round(min(temp_values), 1)
            rq.max_temperature_c = round(max(temp_values), 1)
            rq.n_temperature_stations = len(temp_values)

        if do_values:
            rq.avg_dissolved_oxygen_mgl = round(sum(do_values) / len(do_values), 1)
            rq.min_dissolved_oxygen_mgl = round(min(do_values), 1)
            rq.n_do_stations = len(do_values)

        rq.assessment = self._assess_conditions(rq)
        return self._format_region(rq, from_cache=False)

    # ── Assessment logic ───────────────────────────────────────────────

    @staticmethod
    def _assess_conditions(rq: RegionWaterQuality) -> str:
        """
        Assess water quality conditions for salmon farming.

        Atlantic salmon thrive in 8-14C water with DO > 7 mg/l.
        Stress occurs at >18C or DO < 6 mg/l.
        Lethal conditions at >22C or DO < 4 mg/l.
        """
        if rq.avg_temperature_c is None:
            return "no_data"

        temp = rq.avg_temperature_c
        do = rq.avg_dissolved_oxygen_mgl

        # Temperature assessment
        if temp > 22:
            return "critical_high_temp"
        if temp > 18:
            return "stress_high_temp"
        if temp < 2:
            return "stress_low_temp"

        # DO assessment (if available)
        if do is not None:
            if do < 4:
                return "critical_low_oxygen"
            if do < 6:
                return "stress_low_oxygen"

        # Optimal range
        if 8 <= temp <= 14:
            if do is None or do >= 7:
                return "optimal"
            return "suboptimal_oxygen"

        return "acceptable"

    # ── Response formatting ────────────────────────────────────────────

    def _format_summary(self, regions: dict[str, RegionWaterQuality], from_cache: bool) -> dict:
        """Format the full summary for API response."""
        is_live = not from_cache and any(
            r.avg_temperature_c is not None for r in regions.values()
        )
        prov = (
            DataProvenance.live("SEPA KiWIS Time Series API", confidence=0.80)
            if is_live
            else DataProvenance.degraded(
                "SEPA KiWIS Time Series API",
                "SEPA API returned no data for farming regions" if not from_cache
                else "Cached SEPA data",
                confidence=0.60 if from_cache else 0.30,
            )
        )

        region_list = []
        for name, rq in regions.items():
            region_list.append({
                "region": name,
                "avg_temperature_c": rq.avg_temperature_c,
                "min_temperature_c": rq.min_temperature_c,
                "max_temperature_c": rq.max_temperature_c,
                "avg_dissolved_oxygen_mgl": rq.avg_dissolved_oxygen_mgl,
                "n_temperature_stations": rq.n_temperature_stations,
                "n_do_stations": rq.n_do_stations,
                "assessment": rq.assessment,
                "period": rq.period,
            })

        # Overall summary stats
        temps = [r.avg_temperature_c for r in regions.values() if r.avg_temperature_c is not None]
        dos = [r.avg_dissolved_oxygen_mgl for r in regions.values() if r.avg_dissolved_oxygen_mgl is not None]

        return {
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "n_regions": len(regions),
            "n_regions_with_data": sum(1 for r in regions.values() if r.avg_temperature_c is not None),
            "overall": {
                "avg_temperature_c": round(sum(temps) / len(temps), 1) if temps else None,
                "temp_range_c": [round(min(temps), 1), round(max(temps), 1)] if temps else None,
                "avg_dissolved_oxygen_mgl": round(sum(dos) / len(dos), 1) if dos else None,
            },
            "regions": region_list,
            "source": "SEPA (Scottish Environment Protection Agency) KiWIS API",
            "reference": "Atlantic salmon optimal: 8-14C, DO > 7 mg/l. Stress: >18C or DO < 6 mg/l.",
            "data_provenance": prov.to_dict(),
        }

    def _format_region(self, rq: RegionWaterQuality, from_cache: bool) -> dict:
        """Format a single region for API response."""
        is_live = not from_cache and rq.avg_temperature_c is not None
        prov = (
            DataProvenance.live("SEPA KiWIS Time Series API", confidence=0.80)
            if is_live
            else DataProvenance.degraded(
                "SEPA KiWIS Time Series API",
                "No SEPA stations found or no recent data for this region",
                confidence=0.30,
            )
        )

        return {
            "region": rq.region,
            "avg_temperature_c": rq.avg_temperature_c,
            "min_temperature_c": rq.min_temperature_c,
            "max_temperature_c": rq.max_temperature_c,
            "avg_dissolved_oxygen_mgl": rq.avg_dissolved_oxygen_mgl,
            "min_dissolved_oxygen_mgl": rq.min_dissolved_oxygen_mgl,
            "n_temperature_stations": rq.n_temperature_stations,
            "n_do_stations": rq.n_do_stations,
            "stations": rq.stations,
            "assessment": rq.assessment,
            "period": rq.period,
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "source": "SEPA (Scottish Environment Protection Agency) KiWIS API",
            "data_provenance": prov.to_dict(),
        }


# ── Singleton ──────────────────────────────────────────────────────────
sepa_client = SEPAClient()
