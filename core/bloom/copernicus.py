"""
Copernicus Marine Service (CMEMS) client for chlorophyll-a satellite data.

Uses the Copernicus Marine Toolbox to fetch daily ocean-colour products
covering the Norwegian coast. The primary dataset is the global gap-free
Level 4 product at 4 km resolution (daily).

Free registration: https://data.marine.copernicus.eu/register
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# Norwegian coast bounding box
NORWAY_LAT_MIN = 57.0
NORWAY_LAT_MAX = 72.0
NORWAY_LON_MIN = 4.0
NORWAY_LON_MAX = 32.0

DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D"
VARIABLE = "CHL"  # chlorophyll-a concentration


@dataclass
class ChlGridPoint:
    """A single chlorophyll-a measurement at a grid location."""
    latitude: float
    longitude: float
    chl_a_mg_m3: float
    date: dt.date
    grid_cell_id: str  # "lat_lon" e.g. "60.50_5.25"


class CopernicusClient:
    """Fetches chlorophyll-a satellite data from Copernicus Marine Data Store."""

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self._configured = bool(username and password)
        self._lats: np.ndarray | None = None
        self._lons: np.ndarray | None = None

    async def fetch_chlorophyll(
        self,
        target_date: Optional[dt.date] = None,
        lat_min: float = NORWAY_LAT_MIN,
        lat_max: float = NORWAY_LAT_MAX,
        lon_min: float = NORWAY_LON_MIN,
        lon_max: float = NORWAY_LON_MAX,
    ) -> list[ChlGridPoint]:
        """
        Fetch daily chlorophyll-a for the Norwegian coast.

        Returns only ocean grid points (land/NaN pixels filtered out).
        Uses vectorized numpy extraction for performance on the 360x672 grid.
        """
        if not self._configured:
            log.warning("cmems.not_configured", hint="Set cmems_username and cmems_password in .env")
            return []

        if target_date is None:
            target_date = dt.date.today() - dt.timedelta(days=2)  # NRT has 1-2 day lag

        log.info("cmems.fetch_start", date=target_date.isoformat(), dataset=DATASET_ID)

        try:
            import copernicusmarine
        except ImportError:
            log.error("cmems.import_error", hint="pip install copernicusmarine")
            return []

        try:
            dataset = copernicusmarine.open_dataset(
                dataset_id=DATASET_ID,
                variables=[VARIABLE],
                minimum_longitude=lon_min,
                maximum_longitude=lon_max,
                minimum_latitude=lat_min,
                maximum_latitude=lat_max,
                start_datetime=f"{target_date}T00:00:00",
                end_datetime=f"{target_date}T00:00:00",
                username=self.username,
                password=self.password,
            )

            chl_data = dataset[VARIABLE]
            lats = chl_data.coords["latitude"].values
            lons = chl_data.coords["longitude"].values

            # Cache grid coordinates for nearest-cell lookups
            self._lats = lats
            self._lons = lons

            # Load the full 2D array at once (shape: [1, nlat, nlon])
            values = chl_data.values.squeeze()  # shape: [nlat, nlon]

            # Vectorized: find all valid (non-NaN, positive) ocean pixels
            valid_mask = np.isfinite(values) & (values > 0)
            valid_rows, valid_cols = np.where(valid_mask)

            points: list[ChlGridPoint] = []
            for r, c in zip(valid_rows, valid_cols):
                lat = float(lats[r])
                lon = float(lons[c])
                points.append(ChlGridPoint(
                    latitude=lat,
                    longitude=lon,
                    chl_a_mg_m3=float(values[r, c]),
                    date=target_date,
                    grid_cell_id=f"{lat:.2f}_{lon:.2f}",
                ))

            dataset.close()
            log.info("cmems.fetch_complete", points=len(points), date=target_date.isoformat())
            return points

        except Exception as exc:
            error_msg = str(exc)
            log.error("cmems.fetch_error", error=error_msg, date=target_date.isoformat())

            # Retry with earlier date if data not yet available
            if "exceed the dataset coordinates" in error_msg and target_date >= dt.date.today() - dt.timedelta(days=4):
                earlier = target_date - dt.timedelta(days=1)
                log.info("cmems.retry_earlier_date", new_date=earlier.isoformat())
                return await self.fetch_chlorophyll(
                    target_date=earlier,
                    lat_min=lat_min, lat_max=lat_max,
                    lon_min=lon_min, lon_max=lon_max,
                )
            return []

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance between two points in km."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def find_nearest_grid_cell(
        self, farm_lat: float, farm_lon: float, grid_points: list[ChlGridPoint]
    ) -> ChlGridPoint | None:
        """Find the CMEMS grid cell closest to a farm locality."""
        if not grid_points:
            return None

        # Fast path: use numpy arrays if grid is cached
        if self._lats is not None and self._lons is not None:
            lat_idx = int(np.argmin(np.abs(self._lats - farm_lat)))
            lon_idx = int(np.argmin(np.abs(self._lons - farm_lon)))
            target_id = f"{self._lats[lat_idx]:.2f}_{self._lons[lon_idx]:.2f}"

            for pt in grid_points:
                if pt.grid_cell_id == target_id:
                    dist = self.haversine_km(farm_lat, farm_lon, pt.latitude, pt.longitude)
                    return pt if dist <= 50.0 else None

        # Fallback: brute-force nearest neighbor
        best = None
        best_dist = float("inf")
        for pt in grid_points:
            d = self.haversine_km(farm_lat, farm_lon, pt.latitude, pt.longitude)
            if d < best_dist:
                best_dist = d
                best = pt

        if best_dist > 50.0:
            return None
        return best
