"""
Copernicus Marine Service (CMEMS) — Real Ocean Current Integration
===================================================================
Replaces the static CURRENT_DIRECTION_BOOST=1.5 in farm_graph.py with
real u/v current vectors from the NorKyst800 operational model.

Product:  NORSHELFS_ANALYSISFORECAST_PHY_003_058
Model:    NorKyst-800 (800 m resolution, Norwegian coast, hourly)
Variables:
  - eastward_sea_water_velocity   (u, m/s)
  - northward_sea_water_velocity  (v, m/s)
  - sea_water_temperature         (°C, surface layer)

Geographic domain:  lat 56–72 N, lon 4–31 E
Temporal window:    rolling 7-day window, refreshed every 6 hours
Depth level:        surface (index 0, ~0–2 m)

Auth:  free account at https://data.marine.copernicus.eu
       set CMEMS_USERNAME / CMEMS_PASSWORD in .env

Fallback:  if CMEMS is unavailable the module returns a static boost of
           FALLBACK_BOOST = 1.3 (slightly conservative vs. old 1.5).

Integration into farm_graph.py
-------------------------------
Replace the static directional-boost block:

    # OLD (lines ~249-251 in farm_graph.py)
    if node_b.latitude < node_a.latitude:
        weight *= CURRENT_DIRECTION_BOOST

With:

    from core.market.ocean_currents import ocean_currents
    boost = ocean_currents.get_current_boost(
        node_a.latitude, node_a.longitude,
        node_b.latitude, node_b.longitude,
    )
    weight *= boost

Data refresh cadence:
  - Lazy-loaded on first call
  - Automatically re-fetched when cache is older than 6 hours
  - Thread-safe (single in-process fetch lock)

Dependencies (add to requirements.txt if not present):
  copernicusmarine>=1.0
  xarray>=2023.1
  numpy>=1.24
"""
from __future__ import annotations

import datetime as dt
import math
import threading
from typing import Optional, TYPE_CHECKING

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

# CMEMS product and dataset identifiers (NorKyst800 operational)
CMEMS_DATASET_ID = "cmems_mod_nok_phy_anfc_nordic_P1D-m"
CMEMS_PRODUCT_ID = "NORSHELFS_ANALYSISFORECAST_PHY_003_058"

# Geographic bounding box — Norwegian salmon farming coast
LAT_MIN, LAT_MAX = 56.0, 72.0
LON_MIN, LON_MAX = 4.0, 31.0

# Fetch the last N days of data (7 days gives robust current averaging)
FETCH_DAYS = 7

# Surface depth slice (index 0 ≈ 0–2 m)
DEPTH_SURFACE_IDX = 0

# Cache time-to-live: re-fetch after 6 hours
CACHE_TTL_HOURS = 6

# Boost factor returned when CMEMS data is unavailable.
# Slightly below the old hard-coded 1.5 to be conservative.
FALLBACK_BOOST = 1.3

# Boost range clamp: prevent extreme values from corrupting dispersal weights
BOOST_MIN = 0.5
BOOST_MAX = 2.5

# Minimum current speed (m/s) below which we treat the current as neutral
MIN_CURRENT_SPEED = 0.05


# ── Helper: haversine bearing ─────────────────────────────────────────────────

def _bearing_vector(lat_a: float, lon_a: float,
                    lat_b: float, lon_b: float) -> tuple[float, float]:
    """
    Return the unit vector (east_component, north_component) pointing
    from point A to point B on the Earth's surface.

    Uses the equirectangular approximation — accurate enough for the
    short inter-farm distances (<30 km) we encounter here.
    """
    # Convert to radians
    lat_a_r = math.radians(lat_a)
    lat_b_r = math.radians(lat_b)
    lon_a_r = math.radians(lon_a)
    lon_b_r = math.radians(lon_b)

    # Approximate Cartesian deltas (metres, not needed — just proportions)
    mean_lat = (lat_a_r + lat_b_r) / 2.0
    dx = (lon_b_r - lon_a_r) * math.cos(mean_lat)  # eastward
    dy = lat_b_r - lat_a_r                           # northward

    magnitude = math.hypot(dx, dy)
    if magnitude < 1e-12:
        return (0.0, 0.0)  # same point

    return (dx / magnitude, dy / magnitude)


def compute_current_boost(
    lat_a: float, lon_a: float,
    lat_b: float, lon_b: float,
    u_field: "np.ndarray | None",
    v_field: "np.ndarray | None",
    lats: "np.ndarray | None" = None,
    lons: "np.ndarray | None" = None,
) -> float:
    """
    Compute the multiplicative dispersal boost from A→B given ocean current fields.

    Parameters
    ----------
    lat_a, lon_a : source farm coordinates
    lat_b, lon_b : target farm coordinates
    u_field      : 2-D array of eastward current speed (m/s), shape (nlat, nlon)
    v_field      : 2-D array of northward current speed (m/s), shape (nlat, nlon)
    lats         : 1-D latitude axis matching u_field rows
    lons         : 1-D longitude axis matching u_field columns

    Returns
    -------
    float — multiplicative boost in [BOOST_MIN, BOOST_MAX]
        1.0  = current is perpendicular to A→B (neutral)
        >1.0 = current is downstream (aids dispersal)
        <1.0 = current is upstream (resists dispersal)

    Falls back to FALLBACK_BOOST if fields are unavailable or lookup fails.
    """
    if u_field is None or v_field is None or lats is None or lons is None:
        return FALLBACK_BOOST

    try:
        # Midpoint between farms — sample current there
        mid_lat = (lat_a + lat_b) / 2.0
        mid_lon = (lon_a + lon_b) / 2.0

        # Nearest-neighbour index lookup
        lat_idx = int(np.argmin(np.abs(lats - mid_lat)))
        lon_idx = int(np.argmin(np.abs(lons - mid_lon)))

        u = float(u_field[lat_idx, lon_idx])
        v = float(v_field[lat_idx, lon_idx])

        # Handle NaN / fill values
        if math.isnan(u) or math.isnan(v):
            return FALLBACK_BOOST

        current_speed = math.hypot(u, v)
        if current_speed < MIN_CURRENT_SPEED:
            # Essentially stagnant — no directional effect
            return 1.0

        # Unit current vector
        u_hat = u / current_speed
        v_hat = v / current_speed

        # Unit vector from farm A to farm B (east, north components)
        dir_east, dir_north = _bearing_vector(lat_a, lon_a, lat_b, lon_b)

        # Dot product: +1 = fully downstream, -1 = fully upstream
        dot = u_hat * dir_east + v_hat * dir_north

        # Scale to boost range: dot=+1 → BOOST_MAX, dot=-1 → BOOST_MIN
        # Using a smooth linear mapping centred at 1.0 (neutral)
        # Amplitude of effect scales with current speed (stronger currents = bigger boost)
        speed_factor = min(1.0, current_speed / 0.5)  # saturates at 0.5 m/s
        boost = 1.0 + dot * (BOOST_MAX - 1.0) * 0.5 * speed_factor

        return float(np.clip(boost, BOOST_MIN, BOOST_MAX))

    except Exception as exc:
        log.debug("current_boost.lookup_error", error=str(exc)[:80])
        return FALLBACK_BOOST


# ── Main class ────────────────────────────────────────────────────────────────

class OceanCurrents:
    """
    Manages CMEMS NorKyst800 current + temperature data for OpenClaw.

    Responsibilities:
    - Authenticate with CMEMS via `copernicusmarine` Python client
    - Fetch u, v, temperature as xarray DataArrays
    - Cache the result for 6 hours (TTL-based, thread-safe)
    - Provide `get_current_boost()` and `get_temperature()` for farm_graph.py
    - Fall back gracefully if CMEMS is unavailable

    Usage
    -----
        from core.market.ocean_currents import ocean_currents

        boost = ocean_currents.get_current_boost(62.1, 5.3, 61.8, 5.4)
        temp  = ocean_currents.get_temperature(62.1, 5.3)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_fetch: Optional[dt.datetime] = None

        # Cached numpy arrays (time-averaged over FETCH_DAYS)
        self._u: Optional[np.ndarray] = None   # shape (nlat, nlon)
        self._v: Optional[np.ndarray] = None
        self._temp: Optional[np.ndarray] = None

        # Coordinate axes
        self._lats: Optional[np.ndarray] = None
        self._lons: Optional[np.ndarray] = None

        # Track whether we have ever succeeded
        self._ever_fetched = False

    # ── Fetch ─────────────────────────────────────────────────────────────

    def fetch_currents(self) -> bool:
        """
        Fetch NorKyst800 u, v, temperature from CMEMS.

        Uses `copernicusmarine.open_dataset()` which returns an xarray Dataset.
        Time-averages the FETCH_DAYS window to a single 2-D field per variable.

        Returns True on success, False on any failure.
        """
        try:
            import copernicusmarine  # type: ignore[import]
        except ImportError:
            log.warning(
                "ocean_currents.copernicusmarine_not_installed",
                hint="pip install copernicusmarine>=1.0",
            )
            return False

        try:
            from config.settings import settings
            username = settings.cmems_username
            password = settings.cmems_password
        except Exception:
            username = ""
            password = ""

        if not username or not password:
            log.warning(
                "ocean_currents.no_credentials",
                hint="Set CMEMS_USERNAME and CMEMS_PASSWORD in .env",
            )
            return False

        # Rolling 7-day window ending now (UTC)
        end_dt = dt.datetime.now(dt.UTC)
        start_dt = end_dt - dt.timedelta(days=FETCH_DAYS)

        start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
        end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

        log.info(
            "ocean_currents.fetching",
            dataset=CMEMS_DATASET_ID,
            start=start_str,
            end=end_str,
        )

        try:
            ds = copernicusmarine.open_dataset(
                dataset_id=CMEMS_DATASET_ID,
                username=username,
                password=password,
                minimum_longitude=LON_MIN,
                maximum_longitude=LON_MAX,
                minimum_latitude=LAT_MIN,
                maximum_latitude=LAT_MAX,
                start_datetime=start_str,
                end_datetime=end_str,
                # Request only the surface depth level (index 0)
                minimum_depth=0.0,
                maximum_depth=2.0,
                variables=[
                    "eastward_sea_water_velocity",
                    "northward_sea_water_velocity",
                    "sea_water_temperature",
                ],
            )
        except Exception as exc:
            log.warning("ocean_currents.fetch_failed", error=str(exc)[:200])
            # Rate-limit retries — set a backoff timestamp so the next
            # attempt is ~1 hour away instead of every call.
            # _ensure_fresh() already holds _lock, so no re-acquire.
            if self._last_fetch is None:
                self._last_fetch = dt.datetime.now(dt.UTC) - dt.timedelta(
                    hours=max(0, CACHE_TTL_HOURS - 1)
                )
            return False

        try:
            # Resolve variable names (CMEMS datasets use different short names)
            u_name = self._resolve_varname(
                ds, ["eastward_sea_water_velocity", "u", "uo", "vozocrtx"]
            )
            v_name = self._resolve_varname(
                ds, ["northward_sea_water_velocity", "v", "vo", "vomecrty"]
            )
            t_name = self._resolve_varname(
                ds, ["sea_water_temperature", "thetao", "temp", "temperature"]
            )

            # Select surface slice if depth dimension exists, then time-average
            u_da = ds[u_name]
            v_da = ds[v_name]
            t_da = ds[t_name]

            # Drop depth axis if present (we requested surface only, but be safe)
            for dim in ("depth", "depthu", "depthv", "depthw", "z", "lev"):
                if dim in u_da.dims:
                    u_da = u_da.isel({dim: 0})
                if dim in v_da.dims:
                    v_da = v_da.isel({dim: 0})
                if dim in t_da.dims:
                    t_da = t_da.isel({dim: 0})

            # Time-average: mean over all hourly/daily steps in the window
            for time_dim in ("time", "valid_time"):
                if time_dim in u_da.dims:
                    u_da = u_da.mean(dim=time_dim)
                    v_da = v_da.mean(dim=time_dim)
                    t_da = t_da.mean(dim=time_dim)
                    break

            # Extract coordinate axes (handle both 'lat'/'latitude', 'lon'/'longitude')
            lat_axis = self._resolve_coord(ds, ["latitude", "lat", "y"])
            lon_axis = self._resolve_coord(ds, ["longitude", "lon", "x"])

            with self._lock:
                self._u = u_da.values.astype(np.float32)
                self._v = v_da.values.astype(np.float32)
                self._temp = t_da.values.astype(np.float32)
                self._lats = np.array(ds[lat_axis].values, dtype=np.float64)
                self._lons = np.array(ds[lon_axis].values, dtype=np.float64)
                self._last_fetch = dt.datetime.now(dt.UTC)
                self._ever_fetched = True

            log.info(
                "ocean_currents.fetched",
                shape=str(self._u.shape),
                lat_range=f"{float(self._lats.min()):.1f}–{float(self._lats.max()):.1f}",
                lon_range=f"{float(self._lons.min()):.1f}–{float(self._lons.max()):.1f}",
                u_mean=f"{float(np.nanmean(self._u)):.4f} m/s",
                temp_mean=f"{float(np.nanmean(self._temp)):.1f} °C",
            )
            return True

        except Exception as exc:
            log.warning("ocean_currents.parse_failed", error=str(exc)[:200])
            # Mark as "attempted" so repeated calls within the same TTL window
            # don't hammer the network. Set directly — _ensure_fresh() already
            # holds the lock, so we must NOT re-acquire it here.
            if self._last_fetch is None:
                # Back-date by (TTL - 1 hour) so next retry is in ~1 hour
                self._last_fetch = dt.datetime.now(dt.UTC) - dt.timedelta(
                    hours=max(0, CACHE_TTL_HOURS - 1)
                )
            return False

        finally:
            try:
                ds.close()
            except Exception:
                pass

    # ── Cache logic ───────────────────────────────────────────────────────

    def _is_stale(self) -> bool:
        """Return True if the cache is absent or older than CACHE_TTL_HOURS."""
        if self._last_fetch is None:
            return True
        age = dt.datetime.now(dt.UTC) - self._last_fetch
        return age.total_seconds() > CACHE_TTL_HOURS * 3600

    def _ensure_fresh(self) -> None:
        """Refresh cache if stale. Thread-safe: only one fetch runs at a time."""
        if not self._is_stale():
            return
        # Only one thread fetches; others will use stale (or fallback) data
        if self._lock.acquire(blocking=False):
            try:
                # Re-check inside lock (another thread may have just fetched)
                if self._is_stale():
                    self.fetch_currents()
            finally:
                self._lock.release()

    # ── Public API ────────────────────────────────────────────────────────

    def get_current_boost(
        self,
        lat_a: float, lon_a: float,
        lat_b: float, lon_b: float,
    ) -> float:
        """
        Return the multiplicative lice dispersal boost for the A→B edge.

        Boost > 1.0  ocean current aids dispersal from A to B (downstream)
        Boost = 1.0  current is perpendicular — no directional effect
        Boost < 1.0  current opposes dispersal from A to B (upstream)

        Falls back to FALLBACK_BOOST when CMEMS data is unavailable.

        Parameters
        ----------
        lat_a, lon_a : source farm latitude/longitude (decimal degrees)
        lat_b, lon_b : target farm latitude/longitude (decimal degrees)

        Returns
        -------
        float in [BOOST_MIN, BOOST_MAX]
        """
        self._ensure_fresh()

        with self._lock:
            u = self._u
            v = self._v
            lats = self._lats
            lons = self._lons

        return compute_current_boost(lat_a, lon_a, lat_b, lon_b, u, v, lats, lons)

    def get_temperature(self, lat: float, lon: float) -> Optional[float]:
        """
        Return the 7-day mean sea surface temperature (°C) at the given location.

        Returns None when data is unavailable.

        Parameters
        ----------
        lat, lon : location in decimal degrees

        Returns
        -------
        float (°C) or None
        """
        self._ensure_fresh()

        with self._lock:
            temp = self._temp
            lats = self._lats
            lons = self._lons

        if temp is None or lats is None or lons is None:
            return None

        try:
            lat_idx = int(np.argmin(np.abs(lats - lat)))
            lon_idx = int(np.argmin(np.abs(lons - lon)))
            val = float(temp[lat_idx, lon_idx])
            return None if math.isnan(val) else round(val, 2)
        except Exception as exc:
            log.debug("ocean_currents.temp_lookup_error", error=str(exc)[:80])
            return None

    def get_status(self) -> dict:
        """Return a status dict for health-check / dashboard display."""
        return {
            "last_fetch": self._last_fetch.isoformat() if self._last_fetch else None,
            "cache_age_hours": (
                round(
                    (dt.datetime.now(dt.UTC) - self._last_fetch).total_seconds() / 3600, 1
                )
                if self._last_fetch else None
            ),
            "is_stale": self._is_stale(),
            "ever_fetched": self._ever_fetched,
            "field_shape": list(self._u.shape) if self._u is not None else None,
            "fallback_boost": FALLBACK_BOOST,
            "cache_ttl_hours": CACHE_TTL_HOURS,
            "dataset_id": CMEMS_DATASET_ID,
        }

    # ── Internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_varname(ds: "object", candidates: list[str]) -> str:
        """Return the first variable name from `candidates` present in ds."""
        for name in candidates:
            if name in ds:
                return name
        raise KeyError(
            f"None of {candidates} found in dataset. "
            f"Available: {list(ds.data_vars)}"
        )

    @staticmethod
    def _resolve_coord(ds: "object", candidates: list[str]) -> str:
        """Return the first coordinate name from `candidates` present in ds."""
        for name in candidates:
            if name in ds.coords or name in ds:
                return name
        raise KeyError(
            f"None of {candidates} found as a coordinate. "
            f"Available: {list(ds.coords)}"
        )


# ── Module-level singleton ────────────────────────────────────────────────────

ocean_currents = OceanCurrents()
