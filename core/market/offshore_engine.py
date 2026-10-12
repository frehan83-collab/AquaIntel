"""
Offshore Aquaculture Engine
============================
Analysis and risk assessment for offshore salmon farms.

Key insight: Offshore farms have 60-80% lower lice counts due to stronger
currents dispersing copepodid larvae away from the farm. However, they face
higher structural risk from waves and reduced access during weather windows.

Reference:
  - Oppedal et al. (2017) "Sea lice infestation levels decrease with deeper
    submergence of Atlantic salmon in sea-cages"
  - SalMar Ocean Farm 1: 250m diameter, 64m depth, Frohavet PA 4
  - SalMar Ocean Farm 2: 385m diameter, modular design, construction 2025+
  - Lovewell & Lovei (2022) "Offshore aquaculture environmental parameters"

Singleton: offshore_engine
"""
from __future__ import annotations

import datetime as dt

import structlog

from core.async_db import get_async_session
from core.cache import cache_manager

log = structlog.get_logger(__name__)


# ── Offshore parameter thresholds ─────────────────────────────────────
# Reference: DNV GL standards for offshore fish farming structures
WAVE_EXPOSURE_THRESHOLDS = {
    "sheltered": (0, 1.0),      # Hs < 1.0m (fjord-typical)
    "moderate": (1.0, 2.5),     # Hs 1.0-2.5m (semi-exposed)
    "exposed": (2.5, 5.0),      # Hs 2.5-5.0m (coastal)
    "ocean": (5.0, 15.0),       # Hs > 5.0m (open ocean, Ocean Farm class)
}

# Lice reduction factor for offshore vs inshore
# Reference: Oppedal et al. (2017) — 60-80% reduction in exposed locations
OFFSHORE_LICE_REDUCTION = {
    "inshore": 1.0,
    "semi_offshore": 0.6,
    "offshore": 0.3,  # 70% reduction
}


class OffshoreEngine:
    """
    Offshore farm analysis — wave exposure, structural risk, lice dynamics.

    Provides risk assessments specific to offshore aquaculture operations
    including structural stress, weather window analysis, and comparison
    between inshore and offshore lice dynamics.
    """

    async def get_offshore_farms(self) -> list[dict]:
        """Return all farms with farm_type != 'inshore'."""
        cached = cache_manager.get("offshore_engine", "offshore_farms")
        if cached is not None:
            return cached

        from sqlalchemy import select
        from core.models import Locality

        async with get_async_session() as session:
            result = await session.execute(
                select(Locality).where(Locality.farm_type != "inshore")
            )
            farms = result.scalars().all()

        data = [
            {
                "locality_no": f.locality_no,
                "name": f.name,
                "farm_type": f.farm_type,
                "production_area": f.production_area,
                "latitude": f.latitude,
                "longitude": f.longitude,
                "max_depth_m": f.max_depth_m,
                "current_speed_avg_ms": f.current_speed_avg_ms,
                "wave_exposure_class": f.wave_exposure_class,
                "structural_stress_rating": f.structural_stress_rating,
                "cage_volume_m3": f.cage_volume_m3,
                "distance_to_shore_km": f.distance_to_shore_km,
                "company": f.owner_company,
            }
            for f in farms
        ]

        cache_manager.set("offshore_engine", "offshore_farms", data, category="standard")
        return data

    async def compute_structural_risk(self, locality_no: int) -> dict:
        """
        Compute structural risk assessment for an offshore farm.

        Factors:
          - Wave exposure class (from Hs significant wave height)
          - Current speed stress on mooring
          - Distance to shore (supply/maintenance access)
          - Cage depth vs wave reach

        Returns risk score 0.0 (minimal) to 1.0 (extreme).
        Reference: DNV GL STANDARD FOR CERTIFICATION No. 2.1
        """
        from sqlalchemy import select
        from core.models import Locality

        async with get_async_session() as session:
            result = await session.execute(
                select(Locality).where(Locality.locality_no == locality_no)
            )
            farm = result.scalar_one_or_none()

        if not farm:
            return {"error": "Farm not found", "locality_no": locality_no}

        if farm.farm_type == "inshore":
            return {
                "locality_no": locality_no,
                "farm_type": "inshore",
                "structural_risk": 0.0,
                "risk_level": "minimal",
                "note": "Inshore farms have minimal structural risk from waves",
            }

        # ── Compute risk components ──
        wave_risk = self._wave_risk(farm.wave_exposure_class or "sheltered")
        current_risk = self._current_risk(farm.current_speed_avg_ms or 0.0)
        access_risk = self._access_risk(farm.distance_to_shore_km or 0.0)
        depth_risk = self._depth_risk(farm.max_depth_m or 0.0)

        # Weighted composite — waves are the dominant structural risk offshore
        composite = (
            0.40 * wave_risk +
            0.25 * current_risk +
            0.20 * access_risk +
            0.15 * depth_risk
        )
        composite = round(min(1.0, max(0.0, composite)), 3)

        risk_level = (
            "low" if composite < 0.25 else
            "moderate" if composite < 0.50 else
            "high" if composite < 0.75 else
            "extreme"
        )

        return {
            "locality_no": locality_no,
            "name": farm.name,
            "farm_type": farm.farm_type,
            "structural_risk": composite,
            "risk_level": risk_level,
            "components": {
                "wave_risk": round(wave_risk, 3),
                "current_risk": round(current_risk, 3),
                "access_risk": round(access_risk, 3),
                "depth_risk": round(depth_risk, 3),
            },
            "parameters": {
                "wave_exposure_class": farm.wave_exposure_class,
                "current_speed_avg_ms": farm.current_speed_avg_ms,
                "distance_to_shore_km": farm.distance_to_shore_km,
                "max_depth_m": farm.max_depth_m,
            },
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        }

    async def offshore_lice_comparison(self) -> dict:
        """
        Compare lice dynamics between inshore and offshore farms.

        Offshore farms typically have 60-80% lower lice due to stronger
        currents dispersing copepodid larvae.
        Reference: Oppedal et al. (2017), Samsing et al. (2015)
        """
        from sqlalchemy import select, func
        from core.models import Locality, LiceRecord

        async with get_async_session() as session:
            # Get average lice for inshore farms
            inshore_result = await session.execute(
                select(func.avg(LiceRecord.avg_adult_female_lice))
                .join(Locality, Locality.locality_no == LiceRecord.locality_no)
                .where(
                    (Locality.farm_type == "inshore") | (Locality.farm_type.is_(None))
                )
            )
            inshore_avg = inshore_result.scalar() or 0.0

            # Get average lice for offshore farms
            offshore_result = await session.execute(
                select(func.avg(LiceRecord.avg_adult_female_lice))
                .join(Locality, Locality.locality_no == LiceRecord.locality_no)
                .where(Locality.farm_type.in_(["offshore", "semi_offshore"]))
            )
            offshore_avg = offshore_result.scalar() or 0.0

            # Count farms by type
            type_counts_result = await session.execute(
                select(Locality.farm_type, func.count())
                .group_by(Locality.farm_type)
            )
            type_counts = {row[0] or "inshore": row[1] for row in type_counts_result.all()}

        reduction_pct = (
            round((1 - offshore_avg / inshore_avg) * 100, 1)
            if inshore_avg > 0 and offshore_avg > 0
            else None
        )

        return {
            "inshore": {
                "avg_adult_female_lice": round(inshore_avg, 3),
                "farm_count": type_counts.get("inshore", 0),
            },
            "offshore": {
                "avg_adult_female_lice": round(offshore_avg, 3),
                "farm_count": type_counts.get("offshore", 0) + type_counts.get("semi_offshore", 0),
            },
            "lice_reduction_pct": reduction_pct,
            "expected_reduction_pct": "60-80%",
            "reference": "Oppedal et al. (2017)",
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "data_provenance": {
                "source": "BarentsWatch lice data + offshore classification",
                "is_live": True,
                "freshness": "weekly",
                "confidence": 0.75,
            },
        }

    # ── Private risk computation helpers ──

    @staticmethod
    def _wave_risk(exposure_class: str) -> float:
        """Map wave exposure class to 0-1 risk.
        Reference: DNV GL wave exposure categories."""
        return {
            "sheltered": 0.05,
            "moderate": 0.25,
            "exposed": 0.55,
            "ocean": 0.85,
        }.get(exposure_class, 0.1)

    @staticmethod
    def _current_risk(speed_ms: float) -> float:
        """Map current speed to 0-1 risk.
        >1.5 m/s creates significant mooring stress."""
        if speed_ms < 0.3:
            return 0.05
        elif speed_ms < 0.8:
            return 0.2
        elif speed_ms < 1.5:
            return 0.5
        else:
            return 0.85

    @staticmethod
    def _access_risk(distance_km: float) -> float:
        """Map distance to shore to access difficulty risk.
        >20 km = helicopter-dependent for emergencies."""
        if distance_km < 2:
            return 0.05
        elif distance_km < 5:
            return 0.15
        elif distance_km < 15:
            return 0.35
        elif distance_km < 30:
            return 0.6
        else:
            return 0.85

    @staticmethod
    def _depth_risk(depth_m: float) -> float:
        """Map net pen depth to 0-1 risk.
        Deeper pens are harder to inspect and maintain."""
        if depth_m < 20:
            return 0.05
        elif depth_m < 40:
            return 0.15
        elif depth_m < 60:
            return 0.3
        elif depth_m < 100:
            return 0.5
        else:
            return 0.75


# Singleton
offshore_engine = OffshoreEngine()
