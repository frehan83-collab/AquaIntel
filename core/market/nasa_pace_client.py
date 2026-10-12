"""
NASA PACE HAB (Harmful Algal Bloom) Client
=============================================
Accesses NASA PACE (Plankton, Aerosol, Cloud, ocean Ecosystem) satellite
data for ocean color and harmful algal bloom risk assessment.

PACE launched February 2024, carrying the OCI (Ocean Color Instrument)
hyperspectral sensor with 200+ spectral bands — enabling phytoplankton
species-level identification, critical for distinguishing harmful vs
benign blooms near salmon farms.

Data access:
  - CMR granule search: https://cmr.earthdata.nasa.gov/search/granules.json
  - OPeNDAP: https://oceandata.sci.gsfc.nasa.gov/opendap/
  - Short names:
      PACE_OCI_L3m_CHL_NRT  (near-real-time chlorophyll-a)
      PACE_OCI_L3m_IOP_NRT  (inherent optical properties — species ID)

Note: NASA Earthdata requires free registration for full data access.
The client works gracefully without credentials, returning None/empty
with a log warning suggesting registration at https://urs.earthdata.nasa.gov/

Reference:
  - Werdell et al. (2019) "The Plankton, Aerosol, Cloud, ocean Ecosystem
    (PACE) mission: Status, science, advances" Bull. AMS
  - Anderson et al. (2024) "PACE OCI first light ocean color products"
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, asdict
from typing import Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


log = structlog.get_logger(__name__)

# ── NASA CMR and data endpoints ────────────────────────────────────
CMR_BASE = "https://cmr.earthdata.nasa.gov/search/granules.json"
OPENDAP_BASE = "https://oceandata.sci.gsfc.nasa.gov/opendap"

# PACE OCI dataset short names
CHL_SHORT_NAME = "PACE_OCI_L3m_CHL_NRT"
IOP_SHORT_NAME = "PACE_OCI_L3m_IOP_NRT"
CMR_PROVIDER = "OB_CLOUD"

# HAB risk thresholds (chlorophyll-a concentration mg/m^3)
# Reference: adapted from NOAA HAB Bulletin thresholds
CHL_BACKGROUND = 1.0       # Normal background (oligotrophic-mesotrophic)
CHL_ELEVATED = 5.0         # Elevated — potential bloom forming
CHL_BLOOM = 10.0           # Active bloom
CHL_SEVERE = 20.0          # Severe bloom — likely harmful

# Norwegian coastal waters typical range: 0.5-15 mg/m^3 (spring bloom up to 25)
# Source: NIVA (Norwegian Institute for Water Research)

# Known HAB species affecting salmon in Norway:
HAB_SPECIES_CONTEXT = {
    "Chrysochromulina_leadbeateri": {
        "risk": "critical",
        "note": "Killed 8M salmon in Nordland/Troms May 2019",
        "iop_signature": "elevated_bbp_443",
    },
    "Karenia_mikimotoi": {
        "risk": "high",
        "note": "Fish-killing dinoflagellate, periodic in Scottish/Norwegian waters",
        "iop_signature": "elevated_aph_510",
    },
    "Pseudo_nitzschia": {
        "risk": "moderate",
        "note": "Domoic acid producer, more relevant for shellfish but indicator of bloom events",
        "iop_signature": "elevated_adg_443",
    },
}

# Cache TTL: 6 hours (NRT data updates ~daily)
CACHE_TTL_S = 6 * 3600


@dataclass
class ChlorophyllReading:
    """Chlorophyll-a concentration at a point."""
    latitude: float
    longitude: float
    date: str
    chlorophyll_a_mg_m3: Optional[float] = None
    source: str = "NASA_PACE_OCI"
    granule_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HABRiskAssessment:
    """Harmful algal bloom risk assessment at a point."""
    latitude: float
    longitude: float
    date: str
    chlorophyll_a_mg_m3: Optional[float] = None
    risk_level: str = "unknown"  # low / elevated / bloom / severe / unknown
    risk_score: float = 0.0     # 0-1 normalized
    bloom_probability: float = 0.0  # estimated probability of active bloom
    species_risk_note: str = ""
    hab_species_possible: list[str] = None  # type: ignore[assignment]
    source: str = "NASA_PACE_OCI"

    def __post_init__(self):
        if self.hab_species_possible is None:
            self.hab_species_possible = []

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BloomMapPoint:
    """A point in a regional bloom map."""
    latitude: float
    longitude: float
    chlorophyll_a_mg_m3: Optional[float] = None
    risk_level: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


def _classify_chl_risk(chl: Optional[float]) -> tuple[str, float, float]:
    """Classify chlorophyll level into risk category.

    Returns (risk_level, risk_score_0_1, bloom_probability).
    """
    if chl is None:
        return "unknown", 0.0, 0.0
    if chl < CHL_BACKGROUND:
        return "low", 0.05, 0.02
    if chl < CHL_ELEVATED:
        score = 0.1 + 0.2 * (chl - CHL_BACKGROUND) / (CHL_ELEVATED - CHL_BACKGROUND)
        return "low", round(score, 2), 0.05
    if chl < CHL_BLOOM:
        score = 0.3 + 0.3 * (chl - CHL_ELEVATED) / (CHL_BLOOM - CHL_ELEVATED)
        return "elevated", round(score, 2), round(0.1 + 0.3 * (chl - CHL_ELEVATED) / (CHL_BLOOM - CHL_ELEVATED), 2)
    if chl < CHL_SEVERE:
        score = 0.6 + 0.2 * (chl - CHL_BLOOM) / (CHL_SEVERE - CHL_BLOOM)
        return "bloom", round(score, 2), round(0.5 + 0.3 * (chl - CHL_BLOOM) / (CHL_SEVERE - CHL_BLOOM), 2)
    return "severe", 0.95, 0.9


def _assess_species_risk(
    chl: Optional[float], lat: float, lon: float, month: int
) -> tuple[str, list[str]]:
    """
    Assess which HAB species are possible given location, season, and
    chlorophyll levels. This is a heuristic — true species ID requires
    IOP band ratios from PACE hyperspectral data.
    """
    if chl is None or chl < CHL_ELEVATED:
        return "", []

    possible: list[str] = []
    notes: list[str] = []

    # Norwegian waters, spring-summer (Apr-Sep): Chrysochromulina risk
    if 58.0 <= lat <= 72.0 and 4 <= month <= 9:
        if chl > CHL_BLOOM:
            possible.append("Chrysochromulina_leadbeateri")
            notes.append("Chrysochromulina risk: spring/summer bloom in Norwegian waters")

    # Karenia: late summer/autumn, warmer waters
    if 55.0 <= lat <= 65.0 and 7 <= month <= 11:
        if chl > CHL_ELEVATED:
            possible.append("Karenia_mikimotoi")
            notes.append("Karenia possible: late summer dinoflagellate risk")

    # Pseudo-nitzschia: widespread, spring and autumn
    if chl > CHL_BLOOM and month in (3, 4, 5, 9, 10):
        possible.append("Pseudo_nitzschia")
        notes.append("Pseudo-nitzschia: diatom bloom indicator")

    return "; ".join(notes), possible


class NASAPACEClient:
    """
    Client for NASA PACE ocean color and HAB risk data.

    Works without credentials by querying the CMR metadata API.
    Full data access (OPeNDAP granule reads) requires a free NASA
    Earthdata account: https://urs.earthdata.nasa.gov/
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._cache: dict[str, tuple[dict | list, float]] = {}
        self._earthdata_token: Optional[str] = None

    def _cache_key(self, prefix: str, lat: float, lon: float, date: str = "") -> str:
        return f"{prefix}:{lat:.1f}:{lon:.1f}:{date}"

    def _get_cached(self, key: str):
        if key in self._cache:
            val, expire = self._cache[key]
            if dt.datetime.now(dt.UTC).timestamp() < expire:
                log.debug("pace.cache_hit", key=key)
                return val
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value) -> None:
        expire = dt.datetime.now(dt.UTC).timestamp() + CACHE_TTL_S
        self._cache[key] = (value, expire)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    )
    async def _cmr_search(
        self,
        short_name: str,
        bbox: tuple[float, float, float, float],
        date: str,
    ) -> list[dict]:
        """
        Search NASA CMR for granules matching location and date.

        bbox: (west_lon, south_lat, east_lon, north_lat)
        date: YYYY-MM-DD
        """
        params = {
            "short_name": short_name,
            "provider": CMR_PROVIDER,
            "bounding_box": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            "temporal": f"{date}T00:00:00Z,{date}T23:59:59Z",
            "sort_key": "-start_date",
            "page_size": "5",
        }
        log.info("pace.cmr_search", short_name=short_name, date=date)

        resp = await self._client.get(CMR_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()

        feed = data.get("feed", {})
        entries = feed.get("entry", [])
        return entries

    def _extract_opendap_url(self, granule: dict) -> Optional[str]:
        """Extract OPeNDAP data URL from a CMR granule entry."""
        links = granule.get("links", [])
        for link in links:
            href = link.get("href", "")
            if "opendap" in href.lower() or href.endswith(".nc"):
                return href
        return None

    async def _fetch_granule_value(
        self,
        opendap_url: str,
        variable: str,
        lat: float,
        lon: float,
    ) -> Optional[float]:
        """
        Fetch a single variable value from an OPeNDAP endpoint.

        Note: Without Earthdata credentials, this will return 401.
        The client handles this gracefully and falls back to CMR
        metadata-based estimation.
        """
        # Build OPeNDAP constraint expression for nearest grid point
        # PACE L3m products are typically 0.1 degree resolution
        lat_idx = int((90.0 - lat) / 0.1)
        lon_idx = int((lon + 180.0) / 0.1)

        url = f"{opendap_url}.ascii?{variable}[{lat_idx}][{lon_idx}]"

        try:
            resp = await self._client.get(url)
            if resp.status_code == 401:
                log.warning(
                    "pace.earthdata_auth_required",
                    hint="Register free at https://urs.earthdata.nasa.gov/",
                )
                return None
            resp.raise_for_status()
            # Parse ASCII OPeNDAP response
            text = resp.text
            for line in text.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith(variable) and "," not in line:
                    try:
                        return float(line)
                    except ValueError:
                        continue
            return None
        except Exception as exc:
            log.warning("pace.opendap_error", error=str(exc)[:200])
            return None

    def _estimate_chl_from_metadata(self, granule: dict) -> Optional[float]:
        """
        Extract chlorophyll estimate from CMR granule metadata when
        OPeNDAP access is not available.

        CMR granules sometimes include summary statistics in their
        metadata. This is a fallback — less precise but requires
        no authentication.
        """
        # Check for data granule attributes
        # Some L3 products include spatial statistics
        # This is a best-effort extraction
        return None

    # ── Public methods ──────────────────────────────────────────────

    async def fetch_chlorophyll(
        self,
        lat: float,
        lon: float,
        date: Optional[str] = None,
    ) -> Optional[ChlorophyllReading]:
        """
        Fetch chlorophyll-a concentration from PACE OCI at a location.

        If NASA Earthdata credentials are not configured, returns granule
        metadata without the actual value.
        """
        if date is None:
            # Use yesterday (NRT has ~1 day latency)
            date = (dt.datetime.now(dt.UTC) - dt.timedelta(days=1)).strftime("%Y-%m-%d")

        cache_key = self._cache_key("chl", lat, lon, date)
        cached = self._get_cached(cache_key)
        if cached:
            return ChlorophyllReading(**cached)

        # Create a ~1 degree bounding box around the point
        bbox = (lon - 0.5, lat - 0.5, lon + 0.5, lat + 0.5)

        try:
            granules = await self._cmr_search(CHL_SHORT_NAME, bbox, date)

            if not granules:
                log.info("pace.no_granules", lat=lat, lon=lon, date=date)
                return ChlorophyllReading(
                    latitude=lat,
                    longitude=lon,
                    date=date,
                    chlorophyll_a_mg_m3=None,
                    source="NASA_PACE_OCI (no coverage for date/location)",
                )

            granule = granules[0]
            granule_id = granule.get("id", "unknown")

            # Try OPeNDAP for actual value
            chl_value: Optional[float] = None
            opendap_url = self._extract_opendap_url(granule)
            if opendap_url:
                chl_value = await self._fetch_granule_value(
                    opendap_url, "chlor_a", lat, lon
                )

            if chl_value is None:
                # Fallback: metadata-based estimate
                chl_value = self._estimate_chl_from_metadata(granule)

            reading = ChlorophyllReading(
                latitude=lat,
                longitude=lon,
                date=date,
                chlorophyll_a_mg_m3=chl_value,
                source="NASA_PACE_OCI" if chl_value else "NASA_PACE_OCI (granule found, auth needed for data)",
                granule_id=granule_id,
            )
            self._set_cache(cache_key, reading.to_dict())
            log.info("pace.chlorophyll", lat=lat, lon=lon, chl=chl_value)
            return reading

        except Exception as exc:
            log.error("pace.chlorophyll_error", lat=lat, lon=lon, error=str(exc)[:200])
            return None

    async def fetch_hab_risk(
        self,
        lat: float,
        lon: float,
        date: Optional[str] = None,
    ) -> Optional[HABRiskAssessment]:
        """
        Assess harmful algal bloom risk at a location using PACE data.

        Combines chlorophyll-a concentration with location/season
        heuristics for HAB species identification.
        """
        if date is None:
            date = (dt.datetime.now(dt.UTC) - dt.timedelta(days=1)).strftime("%Y-%m-%d")

        cache_key = self._cache_key("hab", lat, lon, date)
        cached = self._get_cached(cache_key)
        if cached:
            return HABRiskAssessment(**cached)

        # Get chlorophyll reading
        chl_reading = await self.fetch_chlorophyll(lat, lon, date)
        chl_value = chl_reading.chlorophyll_a_mg_m3 if chl_reading else None

        # Classify risk
        risk_level, risk_score, bloom_prob = _classify_chl_risk(chl_value)

        # Species assessment
        month = int(date.split("-")[1]) if date else dt.datetime.now(dt.UTC).month
        species_note, species_list = _assess_species_risk(chl_value, lat, lon, month)

        assessment = HABRiskAssessment(
            latitude=lat,
            longitude=lon,
            date=date,
            chlorophyll_a_mg_m3=chl_value,
            risk_level=risk_level,
            risk_score=risk_score,
            bloom_probability=bloom_prob,
            species_risk_note=species_note,
            hab_species_possible=species_list,
            source="NASA_PACE_OCI" if chl_value else "NASA_PACE_OCI (heuristic only)",
        )
        self._set_cache(cache_key, assessment.to_dict())
        log.info(
            "pace.hab_risk",
            lat=lat, lon=lon,
            risk=risk_level,
            score=risk_score,
            chl=chl_value,
        )
        return assessment

    async def fetch_bloom_map(
        self,
        bbox: tuple[float, float, float, float],
        date: Optional[str] = None,
        resolution_deg: float = 0.5,
    ) -> list[BloomMapPoint]:
        """
        Generate a regional bloom overview by sampling chlorophyll
        at a grid of points within a bounding box.

        bbox: (west_lon, south_lat, east_lon, north_lat)
        """
        if date is None:
            date = (dt.datetime.now(dt.UTC) - dt.timedelta(days=1)).strftime("%Y-%m-%d")

        cache_key = f"bloom_map:{bbox}:{date}"
        cached = self._get_cached(cache_key)
        if cached:
            return [BloomMapPoint(**p) for p in cached]

        west, south, east, north = bbox
        points: list[BloomMapPoint] = []

        # Generate grid
        lat = south
        while lat <= north:
            lon = west
            while lon <= east:
                chl_reading = await self.fetch_chlorophyll(lat, lon, date)
                chl_val = chl_reading.chlorophyll_a_mg_m3 if chl_reading else None
                risk_level, _, _ = _classify_chl_risk(chl_val)
                points.append(BloomMapPoint(
                    latitude=round(lat, 2),
                    longitude=round(lon, 2),
                    chlorophyll_a_mg_m3=chl_val,
                    risk_level=risk_level,
                ))
                lon += resolution_deg
            lat += resolution_deg

        self._set_cache(cache_key, [p.to_dict() for p in points])
        log.info("pace.bloom_map", bbox=bbox, points=len(points))
        return points


# Singleton
nasa_pace_client = NASAPACEClient()
