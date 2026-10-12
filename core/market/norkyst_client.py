"""
NorKyst v3 Ocean Model Client
================================
High-resolution (800m) Norwegian coastal ocean data from the NorKyst800
model, served by MET.no THREDDS.

Replaces the broken CMEMS NorKyst800 dataset (cmems_mod_nok_phy_anfc_nordic_P1D-m)
which returns 404 since late 2025.

Access method: THREDDS NetCDF Subset Service (NCSS) — returns CSV/JSON
over plain HTTP (no xarray/netCDF4 dependency required).

Base URL: https://thredds.met.no/thredds/ncss/sea/norkyst800m/1h/aggregate_be
Docs: https://thredds.met.no/thredds/catalog/sea/norkyst800m/1h/catalog.html

Variables available:
  - temperature (sea_water_temperature)
  - salinity (sea_water_salinity)
  - u (eastward_sea_water_velocity)
  - v (northward_sea_water_velocity)

Reference: Albretsen et al. (2011) "NorKyst-800 Report No. 1"
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, asdict
from typing import Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


log = structlog.get_logger(__name__)

# ── THREDDS NCSS endpoint ──────────────────────────────────────────
NCSS_BASE = "https://thredds.met.no/thredds/ncss/sea/norkyst800m/1h/aggregate_be"

# Variables to request
VARS = ["temperature", "salinity", "u", "v"]

# ── Norwegian Production Area centroids ─────────────────────────────
PA_CENTROIDS: dict[int, tuple[float, float]] = {
    1: (58.5, 6.0),
    2: (59.5, 5.5),
    3: (60.3, 5.2),
    4: (62.5, 6.5),
    5: (63.5, 8.5),
    6: (64.5, 11.0),
    7: (66.0, 13.0),
    8: (67.5, 14.5),
    9: (68.5, 16.0),
    10: (69.5, 18.0),
    11: (70.0, 20.0),
    12: (70.5, 25.0),
    13: (71.0, 28.0),
}

PA_NAMES: dict[int, str] = {
    1: "Rogaland",
    2: "Hordaland South",
    3: "Hordaland North",
    4: "Sogn & Hardanger",
    5: "More og Romsdal",
    6: "Trondelag South",
    7: "Trondelag North",
    8: "Helgeland",
    9: "Salten / Bodo",
    10: "Lofoten / Vesteralen",
    11: "Troms South",
    12: "Troms North",
    13: "Finnmark",
}

# Cache TTL: 6 hours (model updates ~hourly, but conditions change slowly)
CACHE_TTL_S = 6 * 3600


@dataclass
class OceanConditions:
    """Ocean conditions at a single point and time."""
    latitude: float
    longitude: float
    timestamp: str  # ISO 8601
    temperature_c: Optional[float] = None
    salinity_psu: Optional[float] = None
    current_u_ms: Optional[float] = None  # eastward velocity m/s
    current_v_ms: Optional[float] = None  # northward velocity m/s
    current_speed_ms: Optional[float] = None  # magnitude
    current_direction_deg: Optional[float] = None  # oceanographic convention

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PAOceanSummary:
    """Aggregated ocean summary for a Production Area."""
    pa_number: int
    pa_name: str
    latitude: float
    longitude: float
    timestamp: str
    temperature_c: Optional[float] = None
    salinity_psu: Optional[float] = None
    current_speed_ms: Optional[float] = None
    current_direction_deg: Optional[float] = None
    conditions_assessment: str = "unknown"  # optimal / warm / cold / strong_current

    def to_dict(self) -> dict:
        return asdict(self)


def _current_speed_and_dir(
    u: Optional[float], v: Optional[float]
) -> tuple[Optional[float], Optional[float]]:
    """Compute current speed (m/s) and direction (degrees) from u,v components."""
    if u is None or v is None:
        return None, None
    speed = math.sqrt(u * u + v * v)
    direction = (math.degrees(math.atan2(u, v)) + 360) % 360
    return round(speed, 3), round(direction, 1)


def _assess_conditions(
    temp: Optional[float], speed: Optional[float]
) -> str:
    """Simple assessment of ocean conditions for salmon farming."""
    if temp is None:
        return "unknown"
    if temp < 4.0:
        return "cold_stress"
    if temp > 18.0:
        return "warm_stress"
    if temp > 14.0:
        return "warm"
    if speed is not None and speed > 0.5:
        return "strong_current"
    if 8.0 <= temp <= 14.0:
        return "optimal"
    return "suboptimal"


class NorKystClient:
    """
    Client for MET.no THREDDS NorKyst800 v3 ocean model.

    Uses the NetCDF Subset Service (NCSS) which returns CSV data
    over plain HTTP -- no binary NetCDF parsing needed.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._cache: dict[str, tuple[dict, float]] = {}

    def _cache_key(self, prefix: str, lat: float, lon: float, hours: int = 0) -> str:
        # Round to ~1km grid for cache dedup
        return f"{prefix}:{lat:.2f}:{lon:.2f}:{hours}"

    def _get_cached(self, key: str) -> Optional[dict]:
        if key in self._cache:
            val, expire = self._cache[key]
            if dt.datetime.now(dt.UTC).timestamp() < expire:
                log.debug("norkyst.cache_hit", key=key)
                return val
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: dict) -> None:
        expire = dt.datetime.now(dt.UTC).timestamp() + CACHE_TTL_S
        self._cache[key] = (value, expire)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    )
    async def _ncss_request(
        self,
        lat: float,
        lon: float,
        time_start: Optional[str] = None,
        time_end: Optional[str] = None,
        variables: Optional[list[str]] = None,
    ) -> Optional[str]:
        """
        Make a point query to THREDDS NCSS, returning CSV text.

        NCSS point query parameters:
          var=temperature&var=salinity&var=u&var=v
          latitude=63.5&longitude=8.5
          time_start=...&time_end=...
          accept=csv
        """
        params: dict[str, str] = {
            "latitude": str(lat),
            "longitude": str(lon),
            "accept": "csv",
        }
        for v in (variables or VARS):
            params.setdefault("var", v)

        # NCSS wants repeated var= parameters; httpx supports list values
        var_list = variables or VARS
        # Build params manually for repeated keys
        param_str = "&".join(
            [f"var={v}" for v in var_list]
            + [f"latitude={lat}", f"longitude={lon}", "accept=csv"]
        )
        if time_start:
            param_str += f"&time_start={time_start}"
        if time_end:
            param_str += f"&time_end={time_end}"
        else:
            # Default: latest available time
            param_str += "&time=present"

        url = f"{NCSS_BASE}?{param_str}"
        log.info("norkyst.ncss_request", url=url[:120])

        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.text

    def _parse_ncss_csv(self, csv_text: str) -> list[dict]:
        """
        Parse NCSS CSV response into list of dicts.

        Expected format:
          date,latitude[unit="degrees_north"],longitude[unit="degrees_east"],temperature[unit="Celsius"],salinity[unit="1e-3"],...
          2026-04-11T12:00:00Z,63.5,8.5,7.23,34.1,0.05,-0.02
        """
        lines = csv_text.strip().split("\n")
        if len(lines) < 2:
            return []

        # Clean header: strip unit annotations
        raw_header = lines[0]
        headers: list[str] = []
        for col in raw_header.split(","):
            # "temperature[unit=\"Celsius\"]" -> "temperature"
            name = col.split("[")[0].strip()
            headers.append(name)

        rows = []
        for line in lines[1:]:
            vals = line.split(",")
            if len(vals) != len(headers):
                continue
            row: dict = {}
            for h, v in zip(headers, vals):
                v = v.strip()
                if h == "date":
                    row["date"] = v
                else:
                    try:
                        row[h] = float(v)
                    except (ValueError, TypeError):
                        row[h] = None
            rows.append(row)
        return rows

    # ── Public methods ──────────────────────────────────────────────

    async def fetch_current_conditions(
        self, lat: float, lon: float
    ) -> Optional[OceanConditions]:
        """
        Fetch latest ocean conditions (temperature, salinity, currents)
        at a specific lat/lon from NorKyst800 v3.
        """
        cache_key = self._cache_key("current", lat, lon)
        cached = self._get_cached(cache_key)
        if cached:
            return OceanConditions(**cached)

        try:
            csv_text = await self._ncss_request(lat, lon)
            if not csv_text:
                return None

            rows = self._parse_ncss_csv(csv_text)
            if not rows:
                log.warning("norkyst.empty_response", lat=lat, lon=lon)
                return None

            # Take the latest row
            row = rows[-1]
            speed, direction = _current_speed_and_dir(
                row.get("u"), row.get("v")
            )

            cond = OceanConditions(
                latitude=lat,
                longitude=lon,
                timestamp=row.get("date", dt.datetime.now(dt.UTC).isoformat()),
                temperature_c=row.get("temperature"),
                salinity_psu=row.get("salinity"),
                current_u_ms=row.get("u"),
                current_v_ms=row.get("v"),
                current_speed_ms=speed,
                current_direction_deg=direction,
            )
            self._set_cache(cache_key, cond.to_dict())
            log.info(
                "norkyst.current_conditions",
                lat=lat, lon=lon,
                temp=cond.temperature_c,
                speed=speed,
            )
            return cond

        except Exception as exc:
            log.error("norkyst.fetch_error", lat=lat, lon=lon, error=str(exc)[:200])
            return None

    async def fetch_pa_ocean_summary(self, pa_number: int) -> Optional[PAOceanSummary]:
        """
        Fetch average ocean conditions for a Norwegian Production Area.
        Uses the PA centroid coordinate.
        """
        if pa_number not in PA_CENTROIDS:
            log.warning("norkyst.invalid_pa", pa=pa_number)
            return None

        cache_key = f"pa_summary:{pa_number}"
        cached = self._get_cached(cache_key)
        if cached:
            return PAOceanSummary(**cached)

        lat, lon = PA_CENTROIDS[pa_number]
        conditions = await self.fetch_current_conditions(lat, lon)
        if not conditions:
            return None

        assessment = _assess_conditions(
            conditions.temperature_c, conditions.current_speed_ms
        )

        summary = PAOceanSummary(
            pa_number=pa_number,
            pa_name=PA_NAMES.get(pa_number, f"PA {pa_number}"),
            latitude=lat,
            longitude=lon,
            timestamp=conditions.timestamp,
            temperature_c=conditions.temperature_c,
            salinity_psu=conditions.salinity_psu,
            current_speed_ms=conditions.current_speed_ms,
            current_direction_deg=conditions.current_direction_deg,
            conditions_assessment=assessment,
        )
        self._set_cache(cache_key, summary.to_dict())
        log.info(
            "norkyst.pa_summary",
            pa=pa_number,
            temp=summary.temperature_c,
            assessment=assessment,
        )
        return summary

    async def fetch_current_forecast(
        self, lat: float, lon: float, hours: int = 120
    ) -> list[OceanConditions]:
        """
        Fetch forecast ocean conditions for the next N hours at a point.

        NorKyst800 provides hourly data. We request a time range from
        now to now + hours.
        """
        hours = max(1, min(240, hours))  # cap at 10 days
        cache_key = self._cache_key("forecast", lat, lon, hours)
        cached = self._get_cached(cache_key)
        if cached:
            return [OceanConditions(**r) for r in cached]

        now = dt.datetime.now(dt.UTC)
        time_start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        time_end = (now + dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            csv_text = await self._ncss_request(
                lat, lon, time_start=time_start, time_end=time_end
            )
            if not csv_text:
                return []

            rows = self._parse_ncss_csv(csv_text)
            if not rows:
                return []

            results: list[OceanConditions] = []
            for row in rows:
                speed, direction = _current_speed_and_dir(
                    row.get("u"), row.get("v")
                )
                results.append(OceanConditions(
                    latitude=lat,
                    longitude=lon,
                    timestamp=row.get("date", ""),
                    temperature_c=row.get("temperature"),
                    salinity_psu=row.get("salinity"),
                    current_u_ms=row.get("u"),
                    current_v_ms=row.get("v"),
                    current_speed_ms=speed,
                    current_direction_deg=direction,
                ))

            self._set_cache(cache_key, [r.to_dict() for r in results])
            log.info(
                "norkyst.forecast",
                lat=lat, lon=lon,
                hours=hours,
                points=len(results),
            )
            return results

        except Exception as exc:
            log.error(
                "norkyst.forecast_error",
                lat=lat, lon=lon, hours=hours,
                error=str(exc)[:200],
            )
            return []


# Singleton
norkyst_client = NorKystClient()
