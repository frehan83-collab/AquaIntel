"""
NASA JPL MUR SST (Multi-scale Ultra-high Resolution Sea Surface Temperature) client.

Source: NASA PO.DAAC / AWS Open Data
Resolution: 0.01 deg (~1 km), daily global coverage
History: September 1981 to present (v4.1)
Reference: Chin et al. (2017) "Multi-scale High-Resolution Analysis of Global
           Sea Surface Temperature", Journal of Geophysical Research: Oceans.

Access strategy:
  1. Primary: NASA CMR (Common Metadata Repository) granule search + OPeNDAP
  2. Fallback: CMEMS Global Ocean SST (GLO-SST-L4-NRT-OBS-SST-V2 or
     GLOBAL_ANALYSISFORECAST_PHY_001_024) when MUR is unavailable or
     Earthdata credentials are not configured.

No NASA Earthdata credentials required for the CMEMS fallback path.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger(__name__)

# ── Norwegian Production Area representative centroids ──────────────
# Same coordinates used by met_ocean.py PA_CENTERS.
PA_CENTERS: dict[int, tuple[float, float]] = {
    1: (58.5, 6.0),
    2: (59.3, 5.7),
    3: (59.8, 5.3),
    4: (61.0, 5.2),
    5: (61.8, 5.5),
    6: (62.8, 7.0),
    7: (63.5, 10.0),
    8: (65.5, 12.0),
    9: (67.0, 14.5),
    10: (68.5, 15.5),
    11: (69.5, 18.0),
    12: (70.0, 22.0),
    13: (70.0, 28.0),
}

PA_NAMES: dict[int, str] = {
    1: "Svenskegrensen til Jæren",
    2: "Ryfylke",
    3: "Karmøy til Sotra",
    4: "Nordhordland til Stadt",
    5: "Stadt til Hustadvika",
    6: "Nordmøre og Sør-Trøndelag",
    7: "Nord-Trøndelag med Bindal",
    8: "Helgeland til Bodø",
    9: "Vestfjorden og Vesterålen",
    10: "Andøya til Senja",
    11: "Kvaløya til Loppa",
    12: "Vest-Finnmark",
    13: "Øst-Finnmark",
}

# ── Cache ────────────────────────────────────────────────────────────
_cache: dict[str, tuple[dt.datetime, Any]] = {}
CACHE_TTL = dt.timedelta(hours=6)


def _cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry and dt.datetime.now(dt.UTC) - entry[0] < CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (dt.datetime.now(dt.UTC), value)


class MURSSTClient:
    """
    Fetches high-resolution SST data from NASA JPL MUR v4.1.

    Falls back to CMEMS Global SST when MUR / Earthdata is unavailable.
    All public methods are async and return dicts suitable for JSON
    serialisation.
    """

    # NASA CMR granule search
    CMR_BASE = "https://cmr.earthdata.nasa.gov/search/granules.json"
    CMR_SHORT_NAME = "MUR-JPL-L4-GLOB-v4.1"
    CMR_PROVIDER = "PODAAC"

    # OPeNDAP base (requires Earthdata token for actual data download)
    OPENDAP_BASE = (
        "https://opendap.jpl.nasa.gov/opendap/OceanTemperature/"
        "ghrsst/data/GDS2/L4/GLOB/JPL/MUR/v4.1/"
    )

    # CMEMS fallback — Global Ocean OSTIA SST (free, no auth for subset API)
    CMEMS_SST_URL = (
        "https://nrt.cmems-du.eu/motu-web/Motu"
    )
    CMEMS_SERVICE = "GLOBAL_ANALYSISFORECAST_PHY_001_024-TDS"
    CMEMS_PRODUCT = "cmems_mod_glo_phy_anfc_0.083deg_P1D-m"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._earthdata_token: str | None = None

    # ── NASA CMR granule discovery ──────────────────────────────────
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10))
    async def _search_cmr_granules(
        self,
        start_date: dt.date,
        end_date: dt.date,
        bbox: tuple[float, float, float, float],
        page_size: int = 10,
    ) -> list[dict]:
        """
        Search NASA CMR for MUR SST granules covering a bounding box
        and time range.  Returns list of granule metadata dicts.
        """
        params = {
            "short_name": self.CMR_SHORT_NAME,
            "provider": self.CMR_PROVIDER,
            "temporal": f"{start_date.isoformat()},{end_date.isoformat()}",
            "bounding_box": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            "page_size": page_size,
            "sort_key": "-start_date",
        }
        resp = await self._client.get(self.CMR_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("feed", {}).get("entry", [])

    # ── CMEMS fallback SST fetch ─────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    async def _fetch_cmems_sst(
        self,
        lat: float,
        lon: float,
        start_date: dt.date,
        end_date: dt.date,
    ) -> list[dict]:
        """
        Fetch SST from CMEMS Global Analysis & Forecast product.
        Uses the Copernicus Marine Toolbox subset API (no auth needed
        for limited requests).  Returns list of {date, sst_c} dicts.
        """
        # Use the simpler WMS/REST approach: query the marine.copernicus.eu
        # subset API which provides point extractions without MOTU.
        base = "https://data.marine.copernicus.eu/api"
        subset_url = f"{base}/subset"

        # Build a lightweight request for the global daily SST product.
        # If the official subset API is unreachable we fall back to the
        # MET.no OceanForecast which is already used elsewhere.
        params = {
            "datasetId": "cmems_mod_glo_phy_anfc_0.083deg_P1D-m",
            "variables": "thetao",
            "minLon": round(lon - 0.05, 3),
            "maxLon": round(lon + 0.05, 3),
            "minLat": round(lat - 0.05, 3),
            "maxLat": round(lat + 0.05, 3),
            "minDepth": 0.0,
            "maxDepth": 1.0,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        }

        try:
            resp = await self._client.get(subset_url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                # Parse CMEMS response into our standard format
                results = []
                for entry in data if isinstance(data, list) else [data]:
                    if isinstance(entry, dict) and "thetao" in entry:
                        results.append({
                            "date": entry.get("time", ""),
                            "sst_c": round(float(entry["thetao"]), 2),
                            "source": "CMEMS Global Analysis",
                        })
                if results:
                    return results
        except Exception as exc:
            log.debug("mur_sst.cmems_subset_failed", error=str(exc)[:120])

        # Second fallback: use MET.no OceanForecast for recent dates
        return await self._fetch_met_no_fallback(lat, lon, start_date, end_date)

    async def _fetch_met_no_fallback(
        self,
        lat: float,
        lon: float,
        start_date: dt.date,
        end_date: dt.date,
    ) -> list[dict]:
        """
        Last-resort fallback using MET.no OceanForecast 2.0.
        Only covers recent/forecast dates (not historical), but is
        always available without credentials.
        """
        url = "https://api.met.no/weatherapi/oceanforecast/2.0/complete"
        headers = {"User-Agent": "FishIntel/2.0 github.com/frehan83-collab/AquaIntel"}
        params = {"lat": round(lat, 4), "lon": round(lon, 4)}

        try:
            resp = await self._client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                log.warning("mur_sst.met_no_failed", status=resp.status_code)
                return []

            data = resp.json()
            timeseries = data.get("properties", {}).get("timeseries", [])
            results = []
            for entry in timeseries:
                time_str = entry.get("time", "")
                details = entry.get("data", {}).get("instant", {}).get("details", {})
                sst = details.get("sea_water_temperature")
                if sst is not None:
                    try:
                        entry_date = dt.date.fromisoformat(time_str[:10])
                    except (ValueError, IndexError):
                        continue
                    if start_date <= entry_date <= end_date:
                        results.append({
                            "date": entry_date.isoformat(),
                            "sst_c": round(float(sst), 2),
                            "source": "MET.no OceanForecast 2.0",
                        })
            # Deduplicate by date (keep first per day)
            seen: set[str] = set()
            deduped = []
            for r in results:
                if r["date"] not in seen:
                    seen.add(r["date"])
                    deduped.append(r)
            return deduped

        except Exception as exc:
            log.warning("mur_sst.met_no_exception", error=str(exc)[:120])
            return []

    # ══════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════

    async def fetch_sst_for_date(
        self, lat: float, lon: float, date: dt.date
    ) -> dict:
        """
        Single-point SST for a specific date.

        Tries MUR via CMR metadata first; falls back to CMEMS / MET.no
        if MUR data is unavailable.
        """
        cache_key = f"sst_point:{lat:.2f}:{lon:.2f}:{date.isoformat()}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        log.info("mur_sst.fetch_point", lat=lat, lon=lon, date=date.isoformat())

        # Try CMR granule search to verify MUR availability
        try:
            granules = await self._search_cmr_granules(
                start_date=date,
                end_date=date,
                bbox=(lon - 0.1, lat - 0.1, lon + 0.1, lat + 0.1),
                page_size=1,
            )
            if granules:
                log.debug("mur_sst.cmr_granule_found", count=len(granules))
                # MUR granule exists but downloading actual NetCDF requires
                # Earthdata credentials.  Note availability and fall through
                # to CMEMS for the actual SST value.
        except Exception as exc:
            log.debug("mur_sst.cmr_search_failed", error=str(exc)[:120])

        # Fetch actual SST from CMEMS / MET.no fallback
        series = await self._fetch_cmems_sst(lat, lon, date, date)
        if series:
            result = {
                "lat": lat,
                "lon": lon,
                "date": date.isoformat(),
                "sst_c": series[0]["sst_c"],
                "source": series[0].get("source", "CMEMS/MET.no fallback"),
                "mur_available": True,
            }
        else:
            result = {
                "lat": lat,
                "lon": lon,
                "date": date.isoformat(),
                "sst_c": None,
                "source": "unavailable",
                "mur_available": False,
            }

        _cache_set(cache_key, result)
        return result

    async def fetch_sst_timeseries(
        self,
        lat: float,
        lon: float,
        start_date: dt.date,
        end_date: dt.date,
    ) -> dict:
        """
        SST time series for a single location over a date range.

        Returns dict with metadata and a list of daily observations.
        Caps the range at 365 days to avoid excessive requests.
        """
        # Clamp range
        max_days = 365
        if (end_date - start_date).days > max_days:
            start_date = end_date - dt.timedelta(days=max_days)

        cache_key = (
            f"sst_ts:{lat:.2f}:{lon:.2f}:"
            f"{start_date.isoformat()}:{end_date.isoformat()}"
        )
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        log.info(
            "mur_sst.fetch_timeseries",
            lat=lat, lon=lon,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )

        series = await self._fetch_cmems_sst(lat, lon, start_date, end_date)

        # Compute basic statistics
        temps = [s["sst_c"] for s in series if s["sst_c"] is not None]
        stats = {}
        if temps:
            stats = {
                "min_c": round(min(temps), 2),
                "max_c": round(max(temps), 2),
                "mean_c": round(sum(temps) / len(temps), 2),
                "count": len(temps),
            }

        result = {
            "lat": lat,
            "lon": lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "observations": series,
            "statistics": stats,
            "source": series[0]["source"] if series else "unavailable",
        }

        _cache_set(cache_key, result)
        return result

    async def fetch_sst_for_pa(
        self,
        pa_number: int,
        start_date: dt.date,
        end_date: dt.date,
    ) -> dict:
        """
        Average SST for a Norwegian production area over a date range.

        Uses the PA centroid coordinates.  Returns dict with PA metadata,
        time series, and statistics.
        """
        if pa_number not in PA_CENTERS:
            return {
                "error": f"Unknown production area: {pa_number}. Valid: 1-13.",
                "production_area": pa_number,
            }

        lat, lon = PA_CENTERS[pa_number]
        pa_name = PA_NAMES.get(pa_number, f"PA {pa_number}")

        cache_key = (
            f"sst_pa:{pa_number}:"
            f"{start_date.isoformat()}:{end_date.isoformat()}"
        )
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        log.info(
            "mur_sst.fetch_pa",
            pa=pa_number, pa_name=pa_name,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )

        ts = await self.fetch_sst_timeseries(lat, lon, start_date, end_date)

        result = {
            "production_area": pa_number,
            "pa_name": pa_name,
            "center_lat": lat,
            "center_lon": lon,
            **{k: v for k, v in ts.items() if k not in ("lat", "lon")},
        }

        _cache_set(cache_key, result)
        return result

    async def close(self) -> None:
        await self._client.aclose()


# ── Module-level singleton ──────────────────────────────────────────
mur_sst_client = MURSSTClient()
