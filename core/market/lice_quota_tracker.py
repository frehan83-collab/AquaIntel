"""
Lice Emission Quota Tracker
==============================
Architectural foundation for Norway's upcoming tradable lice emission quota system
(targeted 2026-2028, replacing the traffic light system).

Quotas are set per production area (PA 1-13) based on local carrying capacity.
Quotas CANNOT be traded across regions. A fee on lice emissions is also under
consideration. When the system activates, volume limitations in aquaculture
licences will be removed.

Emission model reference:
  - IMR (Havforskningsinstituttet) methodology for estimating wild salmonid
    lice pressure from farm emissions
  - Emission = avg_lice_per_fish x fish_count x water_volume_factor
  - Water volume factor captures local hydrographic conditions (flushing, currents)

IMPORTANT: All quotas shown are HYPOTHETICAL / PROJECTED.
The regulation is not finalized. Values are for planning and scenario analysis only.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import structlog

from core.market.traffic_light_simulator import PA_DEFINITIONS, PA_FARM_COUNTS, PA_MAB_ALLOCATION
from core.market.treatment_constants import REGULATORY_LIMIT
from core.market.data_provenance import DataProvenance
from core.cache import engine_cache

log = structlog.get_logger(__name__)

# Cache TTL: 30 minutes (1800 seconds)
CACHE_TTL = 1800

# ── Hypothetical quota allocations per PA (tonnes lice-equivalents / year) ──────
# These are PROJECTED values based on IMR carrying capacity assessments and
# current traffic light color assignments. NOT official regulation.
# Reference: Havforskningsinstituttet risikovurdering 2024
PA_HYPOTHETICAL_QUOTA: dict[int, float] = {
    1: 120.0, 2: 280.0, 3: 450.0, 4: 500.0, 5: 400.0,
    6: 520.0, 7: 350.0, 8: 460.0, 9: 380.0, 10: 300.0,
    11: 330.0, 12: 270.0, 13: 180.0,
}

# Water volume factor per PA (dimensionless, 0.5-2.0)
# Higher = more flushing/open coast = lower emission impact per louse
# Lower = fjord/enclosed = higher emission impact per louse
# Source: NorKyst800 hydrodynamic model averages
PA_WATER_VOLUME_FACTOR: dict[int, float] = {
    1: 1.4, 2: 0.9, 3: 1.1, 4: 0.8, 5: 1.0,
    6: 1.2, 7: 1.3, 8: 1.5, 9: 1.1, 10: 1.6,
    11: 1.4, 12: 1.7, 13: 1.8,
}

# Average fish weight (kg) — used for estimating fish count from biomass
AVG_FISH_WEIGHT_KG = 4.5  # mid-cycle average (Mowi Handbook 2024)


class LiceQuotaTracker:
    """
    Estimates lice emissions per farm and production area and compares
    against hypothetical emission quotas.

    All output is clearly marked as PROJECTED / ESTIMATED — the regulation
    is not yet finalized.
    """

    _instance = None

    def __new__(cls) -> "LiceQuotaTracker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

    async def _get_lice_data_for_locality(self, locality_no: int) -> dict[str, Any] | None:
        """Fetch latest lice record for a locality from DB."""
        try:
            from core.async_db import get_async_session
            from core.models import LiceRecord, Locality
            from sqlalchemy import select

            async with get_async_session() as s:
                # Latest lice record
                row = (await s.execute(
                    select(LiceRecord)
                    .where(LiceRecord.locality_no == locality_no)
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )).scalar_one_or_none()

                if not row:
                    return None

                # Get locality info
                loc = (await s.execute(
                    select(Locality).where(Locality.locality_no == locality_no)
                )).scalar_one_or_none()

                return {
                    "locality_no": locality_no,
                    "locality_name": loc.name if loc else f"Locality {locality_no}",
                    "production_area": loc.production_area if loc else None,
                    "company": loc.owner_company if loc else "Unknown",
                    "avg_adult_female_lice": float(row.avg_adult_female_lice) if row.avg_adult_female_lice else 0.0,
                    "sea_temp_c": float(row.sea_temp_c) if row.sea_temp_c else None,
                    "year": row.year,
                    "week": row.week,
                }
        except Exception as e:
            log.warning("lice_quota.db_fetch_failed", locality_no=locality_no, error=str(e))
            return None

    async def _get_pa_lice_data(self, pa: int) -> list[dict[str, Any]]:
        """Fetch latest lice data for all farms in a production area."""
        try:
            from core.async_db import get_async_session
            from core.models import LiceRecord, Locality
            from sqlalchemy import select, func

            async with get_async_session() as s:
                # Get latest year/week
                latest = (await s.execute(
                    select(func.max(LiceRecord.year), func.max(LiceRecord.week))
                )).one_or_none()

                if not latest or not latest[0]:
                    return []

                max_year = latest[0]

                # Get farms in this PA with latest data
                q = (
                    select(
                        LiceRecord.locality_no,
                        Locality.name,
                        Locality.owner_company,
                        func.avg(LiceRecord.avg_adult_female_lice).label("avg_lice"),
                    )
                    .join(Locality, Locality.locality_no == LiceRecord.locality_no)
                    .where(
                        Locality.production_area == pa,
                        LiceRecord.year == max_year,
                        LiceRecord.avg_adult_female_lice.isnot(None),
                    )
                    .group_by(LiceRecord.locality_no, Locality.name, Locality.owner_company)
                    .order_by(func.avg(LiceRecord.avg_adult_female_lice).desc())
                )
                rows = (await s.execute(q)).all()

                return [
                    {
                        "locality_no": r.locality_no,
                        "locality_name": r.name or f"Locality {r.locality_no}",
                        "company": r.owner_company or "Unknown",
                        "avg_lice": round(float(r.avg_lice), 3),
                    }
                    for r in rows
                ]
        except Exception as e:
            log.warning("lice_quota.pa_fetch_failed", pa=pa, error=str(e))
            return []

    def _estimate_farm_emission(
        self, avg_lice: float, biomass_tonnes: float, pa: int
    ) -> float:
        """
        Estimate lice emission from a single farm.

        Formula: emission = avg_lice_per_fish x fish_count x water_volume_factor
        Where fish_count = biomass_tonnes * 1000 / avg_fish_weight_kg

        Returns emission in lice-equivalent units (dimensionless annual rate).
        """
        fish_count = (biomass_tonnes * 1000) / AVG_FISH_WEIGHT_KG
        water_factor = PA_WATER_VOLUME_FACTOR.get(pa, 1.0)
        # Emission inversely related to water volume factor:
        # enclosed fjords (low factor) amplify emission impact
        emission = avg_lice * fish_count / water_factor
        return round(emission, 2)

    async def estimate_emission(self, locality_no: int) -> dict[str, Any]:
        """Estimate lice emission from a single farm."""
        cache_key = f"lice_emission:{locality_no}"
        cached = engine_cache.get(cache_key)
        if cached is not None:
            return cached

        now = dt.datetime.now(dt.UTC)
        data = await self._get_lice_data_for_locality(locality_no)

        if not data:
            return {
                "locality_no": locality_no,
                "error": "No lice data available for this locality",
                "data_provenance": DataProvenance.degraded(
                    "BarentsWatch lice records",
                    reason="No data found for locality",
                    confidence=0.0,
                ).to_dict(),
                "generated_at": now.isoformat(),
            }

        pa = data.get("production_area") or 1
        # Estimate biomass: use PA average per farm
        farm_count = PA_FARM_COUNTS.get(pa, 100)
        pa_mab = PA_MAB_ALLOCATION.get(pa, 80_000)
        avg_biomass_per_farm = pa_mab / max(farm_count, 1) * 0.935  # utilization factor

        avg_lice = data["avg_adult_female_lice"]
        emission = self._estimate_farm_emission(avg_lice, avg_biomass_per_farm, pa)

        # Quota share: what fraction of PA quota does this farm use?
        pa_quota = PA_HYPOTHETICAL_QUOTA.get(pa, 300.0)
        quota_utilization_pct = round((emission / max(pa_quota, 1)) * 100, 2)

        # Risk level
        if avg_lice >= REGULATORY_LIMIT:
            risk_level = "high"
        elif avg_lice >= 0.3:
            risk_level = "elevated"
        elif avg_lice >= 0.1:
            risk_level = "moderate"
        else:
            risk_level = "low"

        result = {
            "locality_no": locality_no,
            "locality_name": data["locality_name"],
            "company": data["company"],
            "production_area": pa,
            "avg_adult_female_lice": avg_lice,
            "estimated_biomass_tonnes": round(avg_biomass_per_farm, 1),
            "water_volume_factor": PA_WATER_VOLUME_FACTOR.get(pa, 1.0),
            "estimated_emission": emission,
            "pa_hypothetical_quota": pa_quota,
            "quota_utilization_pct": quota_utilization_pct,
            "risk_level": risk_level,
            "data_week": f"{data['year']}W{data['week']:02d}",
            "regulatory_status": "PROJECTED - regulation not yet finalized",
            "methodology": "IMR emission model: avg_lice x fish_count / water_volume_factor",
            "data_provenance": DataProvenance.live(
                "BarentsWatch lice + Fiskeridirektoratet biomass (estimated)",
                confidence=0.65,
            ).to_dict(),
            "generated_at": now.isoformat(),
        }

        engine_cache.set(cache_key, result, CACHE_TTL)
        return result

    async def pa_quota_status(self, pa: int) -> dict[str, Any]:
        """Current estimated emission vs hypothetical quota for a production area."""
        cache_key = f"lice_quota_pa:{pa}"
        cached = engine_cache.get(cache_key)
        if cached is not None:
            return cached

        now = dt.datetime.now(dt.UTC)

        if pa < 1 or pa > 13:
            return {"error": f"Invalid production area: {pa}. Must be 1-13."}

        pa_def = next((p for p in PA_DEFINITIONS if p["pa"] == pa), None)
        pa_quota = PA_HYPOTHETICAL_QUOTA.get(pa, 300.0)
        farm_count = PA_FARM_COUNTS.get(pa, 100)
        pa_mab = PA_MAB_ALLOCATION.get(pa, 80_000)
        avg_biomass_per_farm = pa_mab / max(farm_count, 1) * 0.935

        # Get farm-level lice data
        farms = await self._get_pa_lice_data(pa)

        total_emission = 0.0
        farm_emissions = []
        for f in farms:
            emission = self._estimate_farm_emission(f["avg_lice"], avg_biomass_per_farm, pa)
            total_emission += emission
            farm_emissions.append({
                "locality_no": f["locality_no"],
                "locality_name": f["locality_name"],
                "company": f["company"],
                "avg_lice": f["avg_lice"],
                "estimated_emission": emission,
            })

        utilization_pct = round((total_emission / max(pa_quota, 1)) * 100, 1)

        # Status classification
        if utilization_pct > 100:
            status = "over_quota"
            status_label = "Over Hypothetical Quota"
        elif utilization_pct > 80:
            status = "warning"
            status_label = "Approaching Quota"
        elif utilization_pct > 50:
            status = "moderate"
            status_label = "Moderate Utilization"
        else:
            status = "healthy"
            status_label = "Within Quota"

        # Top emitters
        top_emitters = sorted(farm_emissions, key=lambda x: x["estimated_emission"], reverse=True)[:10]

        result = {
            "production_area": pa,
            "name": pa_def["name"] if pa_def else f"PA {pa}",
            "region": pa_def["region"] if pa_def else "Unknown",
            "hypothetical_quota": pa_quota,
            "total_estimated_emission": round(total_emission, 1),
            "utilization_pct": utilization_pct,
            "status": status,
            "status_label": status_label,
            "farms_reporting": len(farms),
            "total_farms": farm_count,
            "pa_mab_tonnes": pa_mab,
            "water_volume_factor": PA_WATER_VOLUME_FACTOR.get(pa, 1.0),
            "top_emitters": top_emitters,
            "regulatory_status": "PROJECTED - regulation not yet finalized",
            "data_provenance": DataProvenance.live(
                "BarentsWatch lice + Fiskeridirektoratet biomass + IMR methodology",
                confidence=0.60,
            ).to_dict(),
            "generated_at": now.isoformat(),
        }

        engine_cache.set(cache_key, result, CACHE_TTL)
        return result

    async def national_emission_overview(self) -> dict[str, Any]:
        """All 13 PAs with emission estimates and utilization."""
        cache_key = "lice_quota_national"
        cached = engine_cache.get(cache_key)
        if cached is not None:
            return cached

        now = dt.datetime.now(dt.UTC)
        pa_results = []
        total_national_emission = 0.0
        total_national_quota = 0.0
        over_quota_count = 0

        for pa_def in PA_DEFINITIONS:
            pa = pa_def["pa"]
            pa_status = await self.pa_quota_status(pa)

            if "error" in pa_status:
                continue

            emission = pa_status.get("total_estimated_emission", 0.0)
            quota = pa_status.get("hypothetical_quota", 0.0)
            utilization = pa_status.get("utilization_pct", 0.0)

            total_national_emission += emission
            total_national_quota += quota

            if utilization > 100:
                over_quota_count += 1

            pa_results.append({
                "production_area": pa,
                "name": pa_def["name"],
                "region": pa_def["region"],
                "hypothetical_quota": quota,
                "estimated_emission": emission,
                "utilization_pct": utilization,
                "status": pa_status.get("status", "unknown"),
                "status_label": pa_status.get("status_label", "Unknown"),
                "farms_reporting": pa_status.get("farms_reporting", 0),
                "water_volume_factor": PA_WATER_VOLUME_FACTOR.get(pa, 1.0),
            })

        national_utilization = round(
            (total_national_emission / max(total_national_quota, 1)) * 100, 1
        )

        # Emission trend: compare to previous period (simplified: use current as baseline)
        # In production, this would compare to last month/quarter
        emission_trend = "stable"  # placeholder until historical comparison is built

        result = {
            "total_national_emission": round(total_national_emission, 1),
            "total_national_quota": round(total_national_quota, 1),
            "national_utilization_pct": national_utilization,
            "pas_over_quota": over_quota_count,
            "emission_trend": emission_trend,
            "production_areas": pa_results,
            "framework_note": (
                "Norway is transitioning from the traffic light system to tradable lice "
                "emission quotas per production area (targeted 2026-2028). Quotas are set "
                "based on local carrying capacity and CANNOT be traded across regions. "
                "A fee on lice emissions is also under consideration. When the system "
                "activates, volume limitations in aquaculture licences will be removed."
            ),
            "regulatory_status": "PROJECTED - regulation not yet finalized",
            "data_provenance": DataProvenance.live(
                "BarentsWatch lice + Fiskeridirektoratet + IMR carrying capacity",
                confidence=0.55,
            ).to_dict(),
            "generated_at": now.isoformat(),
        }

        engine_cache.set(cache_key, result, CACHE_TTL)
        return result


# Singleton
lice_quota_tracker = LiceQuotaTracker()
