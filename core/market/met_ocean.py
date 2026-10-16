"""
MET.no Sea Temperature Integration
====================================
Two APIs:
  1. Frost API — historical observations from 500+ coastal weather stations
  2. OceanForecast API — sea temperature forecasts (2.5 day horizon)

Registration: https://frost.met.no/ (free, needs client ID)
Docs: https://frost.met.no/api.html
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import numpy as np
import structlog

from config.settings import settings

log = structlog.get_logger(__name__)

# Coastal stations near major production areas
# Source: frost.met.no/sources/v0.jsonld?types=SensorSystem&elements=sea_water_temperature
COASTAL_STATIONS = {
    "PA-1": ["SN44640", "SN44560"],   # Rogaland
    "PA-2": ["SN50540", "SN50500"],   # Hordaland south
    "PA-3": ["SN55700", "SN56420"],   # Hordaland north
    "PA-4": ["SN58070", "SN59110"],   # Sogn/Hardanger
    "PA-5": ["SN60990", "SN62270"],   # Møre og Romsdal
    "PA-6": ["SN65310", "SN64550"],   # Trøndelag south
    "PA-7": ["SN68860", "SN69100"],   # Trøndelag north
    "PA-8": ["SN71000", "SN71550"],   # Helgeland
    "PA-9": ["SN75410", "SN76450"],   # Salten/Bodø
    "PA-10": ["SN80610", "SN82290"],  # Lofoten/Vesterålen
    "PA-11": ["SN84070", "SN85380"],  # Troms south
    "PA-12": ["SN87110", "SN89350"],  # Troms north
    "PA-13": ["SN93700", "SN95350"],  # Finnmark
}


@dataclass
class SeaTempObservation:
    station_id: str
    production_area: str
    timestamp: dt.datetime
    temperature_c: float
    source: str = "frost"


@dataclass
class SeaTempForecast:
    latitude: float
    longitude: float
    forecast_time: dt.datetime
    temperature_c: float
    hours_ahead: int = 0


class METOceanClient:
    """Client for MET.no Frost and OceanForecast APIs."""

    def __init__(self) -> None:
        self._frost_id = getattr(settings, "met_frost_client_id", "")
        self._client = httpx.AsyncClient(timeout=30.0)

    # ── Frost API (historical observations) ──────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
    async def _frost_request(self, chunk: list[str], ref_time: str, now_str: str) -> list[dict]:
        """One Frost observations request. Retries transient failures
        (network errors, 5xx) with exponential backoff, matching the
        BarentsWatch/SSB client pattern. 412 = no data, not an error."""
        resp = await self._client.get(
            "https://frost.met.no/observations/v0.jsonld",
            params={
                "sources": ",".join(chunk),
                "elements": "sea_water_temperature",
                "referencetime": f"{ref_time}/{now_str}",
                "timeresolutions": "PT1H",
            },
            auth=(self._frost_id, ""),
        )
        if resp.status_code == 200:
            return resp.json().get("data", [])
        if resp.status_code == 412:
            return []  # no data for these stations
        raise RuntimeError(f"frost_http_{resp.status_code}")

    async def get_sea_temperatures(
        self,
        station_ids: list[str] | None = None,
        hours_back: int = 168,  # 1 week default
    ) -> list[SeaTempObservation]:
        """
        Fetch sea water temperature observations from Frost API.
        GET https://frost.met.no/observations/v0.jsonld
        """
        if not self._frost_id:
            log.warning("met.no_frost_id_configured")
            return []

        stations = station_ids or [s for slist in COASTAL_STATIONS.values() for s in slist]
        now = dt.datetime.now(dt.UTC)
        ref_time = (now - dt.timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%S")
        now_str = now.strftime("%Y-%m-%dT%H:%M:%S")

        # Frost API limits sources to 50 per request
        observations = []
        for chunk_start in range(0, len(stations), 20):
            chunk = stations[chunk_start:chunk_start + 20]

            try:
                for item in await self._frost_request(chunk, ref_time, now_str):
                    station = item.get("sourceId", "").split(":")[0]
                    ref = item.get("referenceTime", "")
                    for obs in item.get("observations", []):
                        if obs.get("elementId") == "sea_water_temperature":
                            pa = self._station_to_pa(station)
                            observations.append(SeaTempObservation(
                                station_id=station,
                                production_area=pa,
                                timestamp=dt.datetime.fromisoformat(ref.replace("Z", "+00:00")),
                                temperature_c=float(obs["value"]),
                            ))

            except Exception as exc:
                log.warning("frost.error", error=str(exc)[:100])

        log.info("frost.fetched", observations=len(observations))
        return observations

    # ── OceanForecast API (predictions) ──────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
    async def _ocean_forecast_request(self, lat: float, lon: float) -> list[dict]:
        """One OceanForecast request. Retries transient failures (network
        errors, 5xx) with exponential backoff, matching the other clients."""
        resp = await self._client.get(
            "https://api.met.no/weatherapi/oceanforecast/2.0/complete",
            params={"lat": round(lat, 4), "lon": round(lon, 4)},
            headers={"User-Agent": "AquaIntel/1.0 github.com/frehan83-collab/AquaIntel"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"oceanforecast_http_{resp.status_code}")
        return resp.json().get("properties", {}).get("timeseries", [])

    async def get_ocean_forecast(
        self,
        lat: float,
        lon: float,
    ) -> list[SeaTempForecast]:
        """
        Fetch ocean forecast for a specific location.
        GET https://api.met.no/weatherapi/oceanforecast/2.0/complete
        """
        forecasts = []
        try:
            timeseries = await self._ocean_forecast_request(lat, lon)

            for i, ts in enumerate(timeseries):
                time_str = ts.get("time", "")
                details = ts.get("data", {}).get("instant", {}).get("details", {})
                temp = details.get("sea_water_temperature")

                if temp is not None:
                    forecasts.append(SeaTempForecast(
                        latitude=lat,
                        longitude=lon,
                        forecast_time=dt.datetime.fromisoformat(time_str.replace("Z", "+00:00")),
                        temperature_c=float(temp),
                        hours_ahead=i,
                    ))

        except Exception as exc:
            log.warning("ocean_forecast.error", error=str(exc)[:100])

        log.info("ocean_forecast.fetched", location=f"{lat},{lon}", points=len(forecasts))
        return forecasts

    # ── Convenience ──────────────────────────────────────────────────
    async def get_pa_temperatures(self) -> dict[str, float]:
        """Get latest sea temperature per production area."""
        obs = await self.get_sea_temperatures(hours_back=48)

        pa_temps: dict[str, list[float]] = {}
        for o in obs:
            if o.production_area:
                pa_temps.setdefault(o.production_area, []).append(o.temperature_c)

        return {pa: round(np.mean(temps), 1) for pa, temps in pa_temps.items()}

    @staticmethod
    def _station_to_pa(station_id: str) -> str:
        for pa, stations in COASTAL_STATIONS.items():
            if station_id in stations:
                return pa
        return ""

    async def get_pa_forecast(self, pa: int) -> dict | None:
        """Get sea temperature forecast summary for a production area."""
        pa_key = f"PA-{pa}"
        stations = COASTAL_STATIONS.get(pa_key)
        if not stations:
            return None

        # Use station coordinates as proxy for PA center
        # For simplicity, use the OceanForecast at representative lat/lon per PA
        PA_CENTERS = {
            1: (58.5, 6.0), 2: (59.3, 5.7), 3: (59.8, 5.3), 4: (61.0, 5.2),
            5: (61.8, 5.5), 6: (62.8, 7.0), 7: (63.5, 10.0), 8: (65.5, 12.0),
            9: (67.5, 14.5), 10: (68.8, 16.0), 11: (69.8, 19.0), 12: (70.5, 23.0),
            13: (70.0, 28.0),
        }
        center = PA_CENTERS.get(pa, (65.0, 12.0))
        forecasts = await self.get_ocean_forecast(center[0], center[1])
        if not forecasts:
            return {"production_area": pa, "error": "No forecast data available"}

        temps = [f.temperature_c for f in forecasts if f.temperature_c is not None]
        return {
            "production_area": pa,
            "pa_name": pa_key,
            "center_lat": center[0],
            "center_lon": center[1],
            "n_forecasts": len(forecasts),
            "current_temp_c": round(temps[0], 1) if temps else None,
            "min_temp_c": round(min(temps), 1) if temps else None,
            "max_temp_c": round(max(temps), 1) if temps else None,
            "avg_temp_c": round(sum(temps) / len(temps), 1) if temps else None,
            "forecasts": [
                {"time": f.forecast_time.isoformat(), "temp_c": f.temperature_c}
                for f in forecasts[:20]
            ],
        }

    async def close(self) -> None:
        await self._client.aclose()


# Singleton
met_ocean_client = METOceanClient()
