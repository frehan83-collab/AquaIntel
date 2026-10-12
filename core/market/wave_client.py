"""
CMEMS Wave Client — significant wave height & period for Norwegian PAs
======================================================================
Fetches the WAM global analysis/forecast (3-hourly, 1/12°) and serves a
per-Production-Area wave risk band used for:
  - operational safety (net cleaning, de-licing, wellboat operations)
  - storm-damage risk (mooring/cage stress)
  - insurance / parametric wave cover triggers

Access: Copernicus Marine Data Store (free registration).
  Env: CMEMS_USERNAME / CMEMS_PASSWORD (already used by ocean_currents.py)

Product: GLOBAL_ANALYSISFORECAST_WAV_001_027
Dataset: cmems_mod_glo_wav_anfc_0.083deg_PT3H-i   (verified live in catalogue,
Session 41 — docs/summit/REPORT_SATELLITE.md)

Philosophy (Session 40+): no heavy new dependencies; the existing
`copernicusmarine` package runs in a worker thread; on any failure the client
returns a *simulated* field with honest provenance (data-honesty contract).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import threading
from typing import Optional

import structlog

log = structlog.get_logger(__name__)

WAV_PRODUCT_ID = "GLOBAL_ANALYSISFORECAST_WAV_001_027"
WAV_DATASET_ID = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"

# Norway salmon-farming coast
LAT_MIN, LAT_MAX = 57.0, 71.5
LON_MIN, LON_MAX = 4.0, 31.0

FETCH_DAYS = 2          # recent window averaged for a stable field
FORECAST_DAYS = 5       # daily-mean timeline horizon (WAM has ~10d forecast)
CACHE_TTL_HOURS = 6

# Wave risk bands on significant wave height (Hs, metres).
# Operational thresholds used by Norwegian site operators for light vessels.
WAVE_BANDS = [
    (0.5, "low", "Calm — safe for all operations incl. net cleaning"),
    (1.5, "moderate", "Workable — monitor small vessels and net changes"),
    (3.0, "high", "Restrict operations — de-licing/wellboat windows limited"),
    (float("inf"), "severe", "Structural risk — mooring/cage stress expected"),
]


def wave_risk_band(hs_m: float) -> dict:
    """Map significant wave height to a risk band (pure function, testable)."""
    for upper, level, note in WAVE_BANDS:
        if hs_m < upper:
            return {"level": level, "note": note}
    return {"level": "severe", "note": WAVE_BANDS[-1][2]}


class CMEMSWaveClient:
    """Singleton wave-field client with TTL cache + simulated fallback."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: Optional[dict] = None
        self._cache_time: Optional[dt.datetime] = None
        self._forecast_cache: Optional[dict] = None
        self._forecast_time: Optional[dt.datetime] = None
        self._last_error: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────

    async def fetch_waves(self) -> bool:
        """Fetch Hs/direction/period fields from CMEMS (worker thread)."""
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> bool:
        try:
            import copernicusmarine  # noqa: F401
        except ImportError:
            self._last_error = "copernicusmarine not installed"
            log.warning("wave.copernicusmarine_not_installed")
            return False

        try:
            from config.settings import settings
            username = settings.cmems_username
            password = settings.cmems_password
        except Exception:
            username = password = ""

        if not username or not password:
            self._last_error = "no CMEMS credentials"
            log.info("wave.no_credentials", hint="Set CMEMS_USERNAME/CMEMS_PASSWORD in .env")
            return False

        import copernicusmarine
        import numpy as np

        end = dt.datetime.now(dt.UTC)
        start = end - dt.timedelta(days=FETCH_DAYS)
        try:
            ds = copernicusmarine.open_dataset(
                dataset_id=WAV_DATASET_ID,
                username=username,
                password=password,
                minimum_longitude=LON_MIN,
                maximum_longitude=LON_MAX,
                minimum_latitude=LAT_MIN,
                maximum_latitude=LAT_MAX,
                start_datetime=start.strftime("%Y-%m-%dT%H:%M:%S"),
                end_datetime=end.strftime("%Y-%m-%dT%H:%M:%S"),
            )
        except Exception as exc:  # network, auth, dataset changes
            self._last_error = str(exc)[:200]
            log.warning("wave.fetch_failed", error=self._last_error)
            return False

        try:
            def _mean(name_candidates: list[str]):
                for name in name_candidates:
                    if name in ds.data_vars:
                        return ds[name].mean(dim="time").values
                return None

            hs = _mean(["VHM0", "swh", "significant_wave_height"])
            direction = _mean(["VMDR", "mwd", "wave_direction"])
            period = _mean(["VTPK", "VTM02", "mwp", "wave_period"])
            if hs is None:
                self._last_error = f"no Hs variable in {list(ds.data_vars)}"
                return False

            with self._lock:
                self._cache = {
                    "hs": np.asarray(hs, dtype=float),
                    "direction": np.asarray(direction, dtype=float) if direction is not None else None,
                    "period": np.asarray(period, dtype=float) if period is not None else None,
                    "lat": ds["latitude"].values if "latitude" in ds.coords else ds["lat"].values,
                    "lon": ds["longitude"].values if "longitude" in ds.coords else ds["lon"].values,
                    "fetched_at": end.isoformat(),
                    "window_days": FETCH_DAYS,
                }
                self._cache_time = dt.datetime.now(dt.UTC)
            self._last_error = None
            log.info("wave.fetched", window_days=FETCH_DAYS, n_lat=len(self._cache["lat"]))
            return True
        except Exception as exc:
            self._last_error = str(exc)[:200]
            log.warning("wave.parse_failed", error=self._last_error)
            return False

    # ── PA lookup & fallback ──────────────────────────────────────────

    def get_pa_wave(self, pa: int) -> dict:
        """Wave conditions at a PA centroid, with simulated fallback."""
        from core.market.norkyst_client import PA_CENTROIDS

        if pa not in PA_CENTROIDS:
            return {"error": f"PA {pa} not in 1-13"}
        lat, lon = PA_CENTROIDS[pa]

        field = self._fresh_field()
        if field is not None:
            try:
                import numpy as np
                i = int(np.argmin(np.abs(field["lat"] - lat)))
                j = int(np.argmin(np.abs(field["lon"] - lon)))
                hs = float(field["hs"][i, j])
                band = wave_risk_band(hs)
                return {
                    "production_area": pa,
                    "lat": lat, "lon": lon,
                    "hs_m": round(hs, 2),
                    "wave_direction_deg": round(float(field["direction"][i, j]), 0) if field["direction"] is not None else None,
                    "peak_period_s": round(float(field["period"][i, j]), 1) if field["period"] is not None else None,
                    "risk": band["level"],
                    "operational_note": band["note"],
                    "is_live": True,
                    "source": "CMEMS GLOBAL_ANALYSISFORECAST_WAV_001_027 (WAM 1/12 deg)",
                    "fetched_at": field["fetched_at"],
                }
            except Exception as exc:
                log.warning("wave.lookup_failed", error=str(exc)[:120])

        # Simulated fallback — deterministic per PA, clearly marked
        import random
        rng = random.Random(pa * 7919)
        base = 0.4 + rng.random() * 2.6
        band = wave_risk_band(base)
        return {
            "production_area": pa,
            "lat": lat, "lon": lon,
            "hs_m": round(base, 2),
            "wave_direction_deg": None,
            "peak_period_s": None,
            "risk": band["level"],
            "operational_note": band["note"],
            "is_live": False,
            "source": "simulated (CMEMS WAV unavailable)",
            "fallback_reason": self._last_error or "credentials or data unavailable",
        }

    # ── Forecast (5-day daily-mean timeline) ──────────────────────────

    async def fetch_forecast(self) -> bool:
        """Fetch the daily-mean wave timeline for the next FORECAST_DAYS."""
        return await asyncio.to_thread(self._fetch_forecast_sync)

    def _fetch_forecast_sync(self) -> bool:
        try:
            import copernicusmarine  # noqa: F401
        except ImportError:
            self._last_error = "copernicusmarine not installed"
            return False

        try:
            from config.settings import settings
            username = settings.cmems_username
            password = settings.cmems_password
        except Exception:
            username = password = ""

        if not username or not password:
            self._last_error = "no CMEMS credentials"
            return False

        import copernicusmarine
        import numpy as np

        now = dt.datetime.now(dt.UTC)
        start = now - dt.timedelta(hours=6)
        end = now + dt.timedelta(days=FORECAST_DAYS)
        try:
            ds = copernicusmarine.open_dataset(
                dataset_id=WAV_DATASET_ID,
                username=username,
                password=password,
                minimum_longitude=LON_MIN,
                maximum_longitude=LON_MAX,
                minimum_latitude=LAT_MIN,
                maximum_latitude=LAT_MAX,
                start_datetime=start.strftime("%Y-%m-%dT%H:%M:%S"),
                end_datetime=end.strftime("%Y-%m-%dT%H:%M:%S"),
            )
        except Exception as exc:
            self._last_error = str(exc)[:200]
            log.warning("wave.forecast_fetch_failed", error=self._last_error)
            return False

        try:
            hs_name = next(
                (n for n in ("VHM0", "swh", "significant_wave_height") if n in ds.data_vars),
                None,
            )
            if hs_name is None:
                self._last_error = f"no Hs variable in {list(ds.data_vars)}"
                return False

            hs_ts = ds[hs_name].values.astype(float)          # (time, lat, lon)
            times = np.asarray(ds["time"].values)
            day_ids = times.astype("datetime64[D]")

            days: list[dict] = []
            for day in np.unique(day_ids):
                mask = day_ids == day
                days.append({"date": str(day), "hs": hs_ts[mask].mean(axis=0)})

            with self._lock:
                self._forecast_cache = {
                    "days": days,
                    "lat": ds["latitude"].values if "latitude" in ds.coords else ds["lat"].values,
                    "lon": ds["longitude"].values if "longitude" in ds.coords else ds["lon"].values,
                    "fetched_at": now.isoformat(),
                }
                self._forecast_time = dt.datetime.now(dt.UTC)
            self._last_error = None
            log.info("wave.forecast_fetched", n_days=len(days))
            return True
        except Exception as exc:
            self._last_error = str(exc)[:200]
            log.warning("wave.forecast_parse_failed", error=self._last_error)
            return False

    def get_pa_wave_forecast(self, pa: int, days: int = FORECAST_DAYS) -> dict:
        """Daily-mean Hs + risk band timeline for a PA, simulated fallback."""
        from core.market.norkyst_client import PA_CENTROIDS

        if pa not in PA_CENTROIDS:
            return {"error": f"PA {pa} not in 1-13"}
        days = max(1, min(int(days), FORECAST_DAYS))
        lat, lon = PA_CENTROIDS[pa]

        field = self._fresh_forecast()
        if field is not None:
            try:
                import numpy as np
                i = int(np.argmin(np.abs(field["lat"] - lat)))
                j = int(np.argmin(np.abs(field["lon"] - lon)))
                timeline = []
                for d in field["days"][:days]:
                    hs = float(d["hs"][i, j])
                    band = wave_risk_band(hs)
                    timeline.append({
                        "date": d["date"],
                        "hs_m": round(hs, 2),
                        "risk": band["level"],
                        "operational_note": band["note"],
                    })
                return {
                    "production_area": pa,
                    "lat": lat, "lon": lon,
                    "days": timeline,
                    "is_live": True,
                    "source": "CMEMS GLOBAL_ANALYSISFORECAST_WAV_001_027 daily means",
                    "fetched_at": field["fetched_at"],
                }
            except Exception as exc:
                log.warning("wave.forecast_lookup_failed", error=str(exc)[:120])

        # Simulated fallback — deterministic per PA
        import random
        rng = random.Random(pa * 7919)
        base = 0.4 + rng.random() * 2.6
        drift = random.Random(pa * 104729)
        today = dt.date.today()
        timeline = []
        for k in range(days):
            hs = max(0.05, base + (drift.random() - 0.5) * 0.8)
            band = wave_risk_band(hs)
            timeline.append({
                "date": (today + dt.timedelta(days=k)).isoformat(),
                "hs_m": round(hs, 2),
                "risk": band["level"],
                "operational_note": band["note"],
            })
        return {
            "production_area": pa,
            "lat": lat, "lon": lon,
            "days": timeline,
            "is_live": False,
            "source": "simulated (CMEMS WAV unavailable)",
            "fallback_reason": self._last_error or "credentials or data unavailable",
        }

    def _fresh_forecast(self) -> Optional[dict]:
        ttl = dt.timedelta(hours=CACHE_TTL_HOURS)
        with self._lock:
            if (
                self._forecast_cache
                and self._forecast_time
                and (dt.datetime.now(dt.UTC) - self._forecast_time) < ttl
            ):
                return self._forecast_cache
        return None

    # ── Internals ─────────────────────────────────────────────────────

    def _fresh_field(self) -> Optional[dict]:
        ttl = dt.timedelta(hours=CACHE_TTL_HOURS)
        with self._lock:
            if self._cache and self._cache_time and (dt.datetime.now(dt.UTC) - self._cache_time) < ttl:
                return self._cache
        return None

    def clear_cache(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_time = None
            self._forecast_cache = None
            self._forecast_time = None

    def get_status(self) -> dict:
        fresh = self._fresh_field() is not None
        return {
            "provider": "Copernicus Marine Service (CMEMS)",
            "product": WAV_PRODUCT_ID,
            "dataset": WAV_DATASET_ID,
            "cache_ttl_hours": CACHE_TTL_HOURS,
            "cached": fresh,
            "cached_at": self._cache_time.isoformat() if self._cache_time else None,
            "forecast_cached": self._fresh_forecast() is not None,
            "forecast_days": FORECAST_DAYS,
            "last_error": self._last_error,
        }


wave_client = CMEMSWaveClient()

