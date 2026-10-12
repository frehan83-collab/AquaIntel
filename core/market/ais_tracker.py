"""
AIS Vessel Tracking — Harvest & Wellboat Intelligence
========================================================
Tracks salmon industry vessels (wellboats, harvest vessels, feed barges)
via BarentsWatch AIS API to detect:
  1. Harvest runs: vessel→slaughter plant routes = supply signal
  2. Treatment runs: wellboat visiting multiple farms = cascade signal
  3. Smolt deliveries: broodstock vessel movements = future supply
  4. Feed deliveries: feed barge activity = biomass proxy

Data source: BarentsWatch AIS API (NLOD 2.0, free for Norwegian waters)
Vessel identification: MMSI + vessel name matching against known fleet

Alpha: Harvest vessel activity predicts supply volumes 1-3 days before
public data, enabling trading signals ahead of SSB/company reports.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
import structlog

from core.barentswatch import get_barentswatch_token

log = structlog.get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


class VesselType(str, Enum):
    WELLBOAT = "wellboat"
    HARVEST = "harvest_vessel"
    FEED_BARGE = "feed_barge"
    SERVICE = "service_vessel"
    UNKNOWN = "unknown"


class ActivityType(str, Enum):
    HARVEST_RUN = "harvest_run"
    TREATMENT_RUN = "treatment_run"
    SMOLT_DELIVERY = "smolt_delivery"
    FEED_DELIVERY = "feed_delivery"
    TRANSIT = "transit"
    AT_FARM = "at_farm"
    AT_PORT = "at_port"
    UNKNOWN = "unknown"


@dataclass
class VesselPosition:
    """Single AIS position report."""
    mmsi: int
    name: str
    latitude: float
    longitude: float
    speed_knots: float
    course: float
    timestamp: dt.datetime
    vessel_type: VesselType = VesselType.UNKNOWN
    destination: str = ""
    ship_type: int = 0


@dataclass
class VesselTrack:
    """Vessel movement track with inferred activity."""
    mmsi: int
    name: str
    vessel_type: VesselType
    positions: list[VesselPosition] = field(default_factory=list)
    current_activity: ActivityType = ActivityType.UNKNOWN
    near_farms: list[int] = field(default_factory=list)  # locality_nos
    near_slaughter_plants: list[str] = field(default_factory=list)


@dataclass
class HarvestSignal:
    """Inferred harvest event from AIS data."""
    detected_at: dt.datetime
    vessel_name: str
    vessel_mmsi: int
    origin_farm_locality: Optional[int]
    origin_farm_name: str
    destination_plant: str
    estimated_tonnes: float  # inferred from vessel capacity + dwell time
    company: str
    production_area: int
    confidence: float  # 0-1
    signal_type: str = "harvest_detected"


@dataclass
class TreatmentSignal:
    """Inferred treatment cascade from wellboat movements."""
    detected_at: dt.datetime
    vessel_name: str
    vessel_mmsi: int
    farms_visited: list[int]  # locality_nos in sequence
    treatment_type: str  # inferred from vessel + pattern
    production_area: int
    n_farms: int
    estimated_duration_days: float
    company: str
    confidence: float


# ── Known Vessel Fleet ────────────────────────────────────────────
# Major wellboat and harvest vessel operators in Norway
# MMSI numbers and vessel names for the salmon industry fleet
KNOWN_FLEET: dict[int, dict] = {
    # Sølvtrans fleet (largest wellboat operator)
    257_000_100: {"name": "Ronja Storm", "type": VesselType.WELLBOAT, "capacity_t": 600, "operator": "Sølvtrans"},
    257_000_101: {"name": "Ronja Huon", "type": VesselType.WELLBOAT, "capacity_t": 450, "operator": "Sølvtrans"},
    257_000_102: {"name": "Ronja Commander", "type": VesselType.WELLBOAT, "capacity_t": 550, "operator": "Sølvtrans"},
    257_000_103: {"name": "Ronja Carrier", "type": VesselType.WELLBOAT, "capacity_t": 500, "operator": "Sølvtrans"},
    257_000_104: {"name": "Ronja Explorer", "type": VesselType.WELLBOAT, "capacity_t": 460, "operator": "Sølvtrans"},
    # Frøy fleet
    257_000_200: {"name": "Frøy Fjord", "type": VesselType.WELLBOAT, "capacity_t": 400, "operator": "Frøy"},
    257_000_201: {"name": "Frøy Arctic", "type": VesselType.WELLBOAT, "capacity_t": 420, "operator": "Frøy"},
    # Seistar fleet
    257_000_300: {"name": "Seistar", "type": VesselType.WELLBOAT, "capacity_t": 380, "operator": "Seistar"},
    257_000_301: {"name": "Seifjord", "type": VesselType.WELLBOAT, "capacity_t": 350, "operator": "Seistar"},
    # Harvest vessels (dedicated slaughter transport)
    257_000_400: {"name": "Harvest Nordic", "type": VesselType.HARVEST, "capacity_t": 300, "operator": "Nordic Harvest"},
    257_000_401: {"name": "Harvest Fjord", "type": VesselType.HARVEST, "capacity_t": 280, "operator": "Nordic Harvest"},
}

# Known slaughter plants with coordinates
SLAUGHTER_PLANTS = {
    "Mowi Eggesbønes": {"lat": 62.47, "lon": 6.14, "company": "MOWI", "capacity_t_day": 400},
    "Mowi Herøy": {"lat": 62.43, "lon": 5.86, "company": "MOWI", "capacity_t_day": 350},
    "SalMar InnovaMar": {"lat": 63.76, "lon": 9.41, "company": "SALM", "capacity_t_day": 500},
    "SalMar Frøya": {"lat": 63.72, "lon": 8.65, "company": "SALM", "capacity_t_day": 300},
    "Lerøy Sjømatbedriften": {"lat": 60.39, "lon": 5.32, "company": "LSG", "capacity_t_day": 450},
    "Lerøy Aurora": {"lat": 69.65, "lon": 18.95, "company": "LSG", "capacity_t_day": 250},
    "NRS Wilsgård": {"lat": 69.26, "lon": 17.39, "company": "NRS", "capacity_t_day": 200},
    "Cermaq Hammerfest": {"lat": 70.66, "lon": 23.68, "company": "CERMAQ", "capacity_t_day": 180},
}

# Proximity thresholds (in degrees, ~1km = 0.009°)
FARM_PROXIMITY_DEG = 0.02  # ~2.2km — within this = at farm
PLANT_PROXIMITY_DEG = 0.03  # ~3.3km — within this = at plant
STATIONARY_SPEED_KTS = 1.5  # below this = stationary/loading


class AISTracker:
    """
    Real-time AIS vessel tracking for salmon industry intelligence.

    Polls BarentsWatch AIS API, identifies salmon industry vessels,
    infers activities (harvest runs, treatments, deliveries), and
    generates trading signals from vessel movement patterns.
    """

    def __init__(self) -> None:
        self._tracks: dict[int, VesselTrack] = {}
        self._harvest_signals: list[HarvestSignal] = []
        self._treatment_signals: list[TreatmentSignal] = []
        self._farm_coords: dict[int, tuple[float, float]] = {}  # locality_no → (lat, lon)
        self._farm_companies: dict[int, str] = {}
        self._farm_pas: dict[int, int] = {}
        self._last_poll: Optional[dt.datetime] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def _load_farm_coordinates(self) -> None:
        """Load farm coordinates from database for proximity matching."""
        try:
            from core.models import Locality
            from core.async_db import get_async_session
            from sqlalchemy import select

            async with get_async_session() as s:
                localities = (await s.execute(
                    select(
                        Locality.locality_no,
                        Locality.latitude,
                        Locality.longitude,
                        Locality.owner_company,
                        Locality.production_area,
                    ).where(
                        Locality.latitude.isnot(None),
                        Locality.longitude.isnot(None),
                    )
                )).all()

            for loc_no, lat, lon, company, pa in localities:
                self._farm_coords[loc_no] = (lat, lon)
                self._farm_companies[loc_no] = company or ""
                self._farm_pas[loc_no] = pa or 0

            log.info("ais.farms_loaded", n_farms=len(self._farm_coords))
        except Exception as e:
            log.warning("ais.farm_load_error", error=str(e)[:100])

    async def poll_ais_positions(self) -> list[VesselPosition]:
        """
        Fetch latest AIS positions from BarentsWatch for tracked vessels.

        BarentsWatch AIS endpoint: /ais/combined
        Returns positions for vessels in Norwegian waters.
        """
        if not self._farm_coords:
            await self._load_farm_coordinates()

        try:
            token = await get_barentswatch_token()
            if not token:
                log.warning("ais.no_token")
                return []

            client = await self._ensure_client()

            # Fetch positions for known fleet MMSIs
            mmsi_list = list(KNOWN_FLEET.keys())
            positions: list[VesselPosition] = []

            # BarentsWatch AIS API — batch request
            resp = await client.post(
                "https://www.barentswatch.no/bwapi/v2/geodata/ais/combined",
                headers={"Authorization": f"Bearer {token}"},
                json={"mmsi": mmsi_list},
            )

            if resp.status_code != 200:
                # Fallback: try open AIS endpoint
                resp = await client.get(
                    "https://www.barentswatch.no/bwapi/v1/geodata/ais/openpositions",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"xmin": 3, "xmax": 32, "ymin": 58, "ymax": 72},
                )

            if resp.status_code == 200:
                data = resp.json()
                ais_list = data if isinstance(data, list) else data.get("features", data.get("aisPositions", []))

                for entry in ais_list:
                    props = entry.get("properties", entry)
                    mmsi = props.get("mmsi", 0)

                    # Check if this vessel is in our fleet or matches salmon vessel names
                    fleet_info = KNOWN_FLEET.get(mmsi)
                    name = props.get("name", props.get("shipName", ""))

                    if not fleet_info and not self._is_salmon_vessel(name):
                        continue

                    geom = entry.get("geometry", {})
                    coords = geom.get("coordinates", [0, 0]) if geom else [0, 0]
                    lon = coords[0] if len(coords) > 0 else props.get("longitude", 0)
                    lat = coords[1] if len(coords) > 1 else props.get("latitude", 0)

                    pos = VesselPosition(
                        mmsi=mmsi,
                        name=name or (fleet_info["name"] if fleet_info else "Unknown"),
                        latitude=lat,
                        longitude=lon,
                        speed_knots=props.get("speedOverGround", props.get("sog", 0)),
                        course=props.get("courseOverGround", props.get("cog", 0)),
                        timestamp=dt.datetime.now(dt.UTC),
                        vessel_type=fleet_info["type"] if fleet_info else VesselType.UNKNOWN,
                        destination=props.get("destination", ""),
                        ship_type=props.get("shipType", 0),
                    )
                    positions.append(pos)

                    # Update track
                    self._update_track(pos, fleet_info)

                self._last_poll = dt.datetime.now(dt.UTC)
                log.info("ais.polled", n_positions=len(positions))

            return positions

        except Exception as e:
            log.warning("ais.poll_error", error=str(e)[:150])
            return []

    def _is_salmon_vessel(self, name: str) -> bool:
        """Check if vessel name matches salmon industry patterns."""
        if not name:
            return False
        name_lower = name.lower()
        salmon_keywords = [
            "ronja", "frøy", "froy", "seistar", "sei", "wellboat",
            "harvest", "bris", "brage", "viking", "norsk sjøtransport",
            "sølvtrans", "solvtrans", "aqua", "salmon", "brønn",
            "bronn", "polar", "north", "fjord", "ocean",
        ]
        return any(kw in name_lower for kw in salmon_keywords)

    def _update_track(self, pos: VesselPosition, fleet_info: Optional[dict]) -> None:
        """Update vessel track and infer activity."""
        if pos.mmsi not in self._tracks:
            self._tracks[pos.mmsi] = VesselTrack(
                mmsi=pos.mmsi,
                name=pos.name,
                vessel_type=fleet_info["type"] if fleet_info else VesselType.UNKNOWN,
            )

        track = self._tracks[pos.mmsi]
        track.positions.append(pos)

        # Keep only last 200 positions per vessel (~3 days at 5min intervals)
        if len(track.positions) > 200:
            track.positions = track.positions[-200:]

        # Determine proximity to farms and plants
        near_farms = self._find_nearby_farms(pos.latitude, pos.longitude)
        near_plants = self._find_nearby_plants(pos.latitude, pos.longitude)

        track.near_farms = near_farms
        track.near_slaughter_plants = near_plants

        # Infer activity
        prev_activity = track.current_activity
        track.current_activity = self._infer_activity(track, pos, near_farms, near_plants)

        # Detect harvest signal: vessel was at farm, now heading to/at plant
        if (prev_activity == ActivityType.AT_FARM
                and track.current_activity in (ActivityType.HARVEST_RUN, ActivityType.AT_PORT)):
            self._generate_harvest_signal(track, fleet_info)

        # Detect treatment cascade: wellboat visiting multiple farms
        if (track.vessel_type == VesselType.WELLBOAT
                and track.current_activity == ActivityType.AT_FARM):
            self._check_treatment_cascade(track, fleet_info)

    def _find_nearby_farms(self, lat: float, lon: float) -> list[int]:
        """Find farm localities within proximity threshold."""
        nearby = []
        for loc_no, (f_lat, f_lon) in self._farm_coords.items():
            dist = np.sqrt((lat - f_lat) ** 2 + (lon - f_lon) ** 2)
            if dist < FARM_PROXIMITY_DEG:
                nearby.append(loc_no)
        return nearby

    def _find_nearby_plants(self, lat: float, lon: float) -> list[str]:
        """Find slaughter plants within proximity threshold."""
        nearby = []
        for name, info in SLAUGHTER_PLANTS.items():
            dist = np.sqrt((lat - info["lat"]) ** 2 + (lon - info["lon"]) ** 2)
            if dist < PLANT_PROXIMITY_DEG:
                nearby.append(name)
        return nearby

    def _infer_activity(
        self,
        track: VesselTrack,
        pos: VesselPosition,
        near_farms: list[int],
        near_plants: list[str],
    ) -> ActivityType:
        """Infer vessel activity from position, speed, and proximity."""
        is_stationary = pos.speed_knots < STATIONARY_SPEED_KTS

        if near_plants and is_stationary:
            return ActivityType.AT_PORT

        if near_farms and is_stationary:
            return ActivityType.AT_FARM

        if near_plants and not is_stationary:
            return ActivityType.HARVEST_RUN

        # Check if transitioning from farm toward a plant
        if len(track.positions) >= 2:
            prev = track.positions[-2]
            prev_near_farms = self._find_nearby_farms(prev.latitude, prev.longitude)
            if prev_near_farms and not near_farms and pos.speed_knots > 3:
                # Left a farm, moving fast — likely heading somewhere
                if track.vessel_type == VesselType.HARVEST:
                    return ActivityType.HARVEST_RUN
                elif track.vessel_type == VesselType.WELLBOAT:
                    # Could be treatment run or transport
                    return ActivityType.TREATMENT_RUN

        if pos.speed_knots > 5:
            return ActivityType.TRANSIT

        return ActivityType.UNKNOWN

    def _generate_harvest_signal(
        self, track: VesselTrack, fleet_info: Optional[dict]
    ) -> None:
        """Generate a harvest detection signal."""
        if not track.near_farms and not track.near_slaughter_plants:
            return

        # Find the farm it was at (use the most recent near_farm from positions)
        origin_farm = None
        for pos in reversed(track.positions[:-1]):
            farms = self._find_nearby_farms(pos.latitude, pos.longitude)
            if farms:
                origin_farm = farms[0]
                break

        if not origin_farm:
            return

        capacity = fleet_info.get("capacity_t", 300) if fleet_info else 300
        company = self._farm_companies.get(origin_farm, "Unknown")
        pa = self._farm_pas.get(origin_farm, 0)

        # Estimate tonnage from vessel capacity and dwell time
        dwell_positions = sum(
            1 for p in track.positions
            if p.speed_knots < STATIONARY_SPEED_KTS
            and self._find_nearby_farms(p.latitude, p.longitude)
        )
        dwell_hours = dwell_positions * 5 / 60  # 5-min intervals
        # Loading rate ~50t/hour for wellboats
        estimated_tonnes = min(capacity, dwell_hours * 50) if dwell_hours > 0 else capacity * 0.7

        signal = HarvestSignal(
            detected_at=dt.datetime.now(dt.UTC),
            vessel_name=track.name,
            vessel_mmsi=track.mmsi,
            origin_farm_locality=origin_farm,
            origin_farm_name=self._farm_companies.get(origin_farm, "Unknown farm"),
            destination_plant=track.near_slaughter_plants[0] if track.near_slaughter_plants else "Unknown",
            estimated_tonnes=round(estimated_tonnes, 0),
            company=company,
            production_area=pa,
            confidence=0.7 if origin_farm else 0.4,
        )

        self._harvest_signals.append(signal)
        # Keep last 100 signals
        if len(self._harvest_signals) > 100:
            self._harvest_signals = self._harvest_signals[-100:]

        log.info(
            "ais.harvest_detected",
            vessel=track.name,
            farm=origin_farm,
            company=company,
            tonnes=estimated_tonnes,
        )

    def _check_treatment_cascade(
        self, track: VesselTrack, fleet_info: Optional[dict]
    ) -> None:
        """Detect if a wellboat is performing a treatment cascade."""
        # Count unique farms visited in last 48 hours
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=48)
        recent_positions = [p for p in track.positions if p.timestamp > cutoff]

        visited_farms: list[int] = []
        for pos in recent_positions:
            if pos.speed_knots < STATIONARY_SPEED_KTS:
                farms = self._find_nearby_farms(pos.latitude, pos.longitude)
                for f in farms:
                    if f not in visited_farms:
                        visited_farms.append(f)

        if len(visited_farms) >= 3:
            # Treatment cascade detected — 3+ farms in 48h
            pa = self._farm_pas.get(visited_farms[0], 0)
            company = self._farm_companies.get(visited_farms[0], "Unknown")

            signal = TreatmentSignal(
                detected_at=dt.datetime.now(dt.UTC),
                vessel_name=track.name,
                vessel_mmsi=track.mmsi,
                farms_visited=visited_farms,
                treatment_type="mechanical" if "hydrolicer" in track.name.lower() else "unknown",
                production_area=pa,
                n_farms=len(visited_farms),
                estimated_duration_days=2.0,
                company=company,
                confidence=0.6,
            )

            self._treatment_signals.append(signal)
            if len(self._treatment_signals) > 50:
                self._treatment_signals = self._treatment_signals[-50:]

            log.info(
                "ais.treatment_cascade",
                vessel=track.name,
                n_farms=len(visited_farms),
                pa=pa,
            )

    # ── Public API ───────────────────────────────────────────────

    def get_active_tracks(self) -> list[dict]:
        """Get all active vessel tracks with current activity."""
        result = []
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=12)

        for track in self._tracks.values():
            if not track.positions:
                continue
            latest = track.positions[-1]
            if latest.timestamp < cutoff:
                continue

            result.append({
                "mmsi": track.mmsi,
                "name": track.name,
                "vessel_type": track.vessel_type.value,
                "latitude": latest.latitude,
                "longitude": latest.longitude,
                "speed_knots": round(latest.speed_knots, 1),
                "course": round(latest.course, 0),
                "activity": track.current_activity.value,
                "near_farms": track.near_farms[:5],
                "near_plants": track.near_slaughter_plants,
                "last_update": latest.timestamp.isoformat(),
                "n_positions": len(track.positions),
            })

        return result

    def get_harvest_signals(self, hours: int = 72) -> list[dict]:
        """Get recent harvest detection signals."""
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=hours)
        return [
            {
                "detected_at": s.detected_at.isoformat(),
                "vessel": s.vessel_name,
                "mmsi": s.vessel_mmsi,
                "farm_locality": s.origin_farm_locality,
                "farm_name": s.origin_farm_name,
                "destination": s.destination_plant,
                "estimated_tonnes": s.estimated_tonnes,
                "company": s.company,
                "production_area": s.production_area,
                "confidence": s.confidence,
                "signal_type": s.signal_type,
            }
            for s in self._harvest_signals
            if s.detected_at > cutoff
        ]

    def get_treatment_signals(self, hours: int = 72) -> list[dict]:
        """Get recent treatment cascade signals."""
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=hours)
        return [
            {
                "detected_at": s.detected_at.isoformat(),
                "vessel": s.vessel_name,
                "mmsi": s.vessel_mmsi,
                "farms_visited": s.farms_visited,
                "treatment_type": s.treatment_type,
                "production_area": s.production_area,
                "n_farms": s.n_farms,
                "duration_days": s.estimated_duration_days,
                "company": s.company,
                "confidence": s.confidence,
            }
            for s in self._treatment_signals
            if s.detected_at > cutoff
        ]

    def get_supply_intelligence(self) -> dict:
        """
        Aggregate AIS-derived supply intelligence.

        Returns estimated harvest volumes by company and PA,
        active treatment cascades, and fleet utilization.
        """
        now = dt.datetime.now(dt.UTC)
        week_ago = now - dt.timedelta(days=7)

        # Aggregate weekly harvest estimates by company
        weekly_harvests: dict[str, float] = {}
        weekly_pa_harvests: dict[int, float] = {}

        for s in self._harvest_signals:
            if s.detected_at > week_ago:
                weekly_harvests[s.company] = weekly_harvests.get(s.company, 0) + s.estimated_tonnes
                weekly_pa_harvests[s.production_area] = (
                    weekly_pa_harvests.get(s.production_area, 0) + s.estimated_tonnes
                )

        # Active treatment cascades
        active_treatments = [
            s for s in self._treatment_signals
            if s.detected_at > now - dt.timedelta(hours=48)
        ]

        # Fleet utilization
        active_vessels = sum(
            1 for t in self._tracks.values()
            if t.positions and t.positions[-1].timestamp > now - dt.timedelta(hours=6)
        )

        return {
            "generated_at": now.isoformat(),
            "weekly_harvest_by_company": weekly_harvests,
            "weekly_harvest_by_pa": {str(k): v for k, v in weekly_pa_harvests.items()},
            "total_weekly_harvest_t": round(sum(weekly_harvests.values()), 0),
            "active_treatment_cascades": len(active_treatments),
            "treatment_cascade_pas": list({s.production_area for s in active_treatments}),
            "active_vessels": active_vessels,
            "total_tracked_vessels": len(self._tracks),
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
            "harvest_signals_7d": len([
                s for s in self._harvest_signals if s.detected_at > week_ago
            ]),
        }

    async def shutdown(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton
ais_tracker = AISTracker()
