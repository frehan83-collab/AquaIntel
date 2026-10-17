"""
Lice Emission Quota Tracker
==============================
Architectural foundation for the tradable lice-emission quota system proposed in
Meld. St. 24 (2024-2025) to replace the traffic-light system. It has not been
adopted; no timeline or allocations are published, so every quota here is
hypothetical.

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
from core.source_lineage import (
    merge_lineages,
    parse_timestamp,
    provenance_for,
    summarise_lineage,
)

log = structlog.get_logger(__name__)

# Cache TTL: 30 minutes (1800 seconds)
CACHE_TTL = 1800


def _provenance_for(lineage: dict | None, label: str, confidence: float) -> dict:
    """Live only when the lineage of the rows actually used supports it (WS-1).

    Thin alias: the implementation lives in ``core.source_lineage.provenance_for``
    so every lice consumer shares one rule (WS-14).
    """
    return provenance_for(lineage, label, confidence)


def _refresh_cached_lineage(cached: dict, label: str, confidence: float) -> None:
    """Re-evaluate a cached payload's lineage against the current time (WS-1).

    Staleness is a property of *now*, not of when the cache entry was built: a
    lineage that crosses the cadence during the TTL must not keep being served
    (and mirrored) as live. Mutates the cached dict in place only when the verdict
    changed.
    """
    lineage = cached.get("lineage")
    if not lineage:
        return
    fresh = merge_lineages([lineage])
    if fresh.get("note") != lineage.get("note") or fresh.get("is_live") != lineage.get("is_live"):
        cached["lineage"] = fresh
        cached["data_provenance"] = _provenance_for(fresh, label, confidence)


# Provenance labels. Biomass here is an ESTIMATE from the PA_MAB_ALLOCATION /
# PA_FARM_COUNTS constants (Fiskeridirektoratet Table 8), not a biomass row read
# at runtime — a label must never claim a source the code does not consult.
_LOCALITY_LABEL = "BarentsWatch lice + estimated PA biomass (Fiskeridir Table 8 constants)"
_PA_LABEL = (
    "BarentsWatch lice + estimated PA biomass (Fiskeridir Table 8 constants) + IMR methodology"
)
_NATIONAL_LABEL = (
    "BarentsWatch lice + estimated PA biomass (Fiskeridir Table 8 constants) "
    "+ IMR carrying capacity"
)

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

    # WS-1 lineage mirror (biomass_tracker precedent): the lineage of the rows the
    # last national overview used. The same block travels inside the cached
    # payloads, so a cache hit re-mirrors it instead of going stale.
    last_lineage: dict | None = None
    last_source: str = "unset"
    last_is_live: bool = False

    def _mirror_lineage(self, lineage: dict | None) -> None:
        self.last_lineage = lineage
        self.last_source = (lineage or {}).get("source") or "unset"
        self.last_is_live = bool((lineage or {}).get("is_live"))

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
                    "source": row.source,
                    "fetched_at": row.fetched_at,
                }
        except Exception as e:
            log.warning("lice_quota.db_fetch_failed", locality_no=locality_no, error=str(e))
            return None

    async def _get_pa_lice_data(self, pa: int) -> tuple[list[dict[str, Any]], dict]:
        """Latest-year lice data for all farms in a PA, plus the lineage of those rows.

        WS-1: the lineage is counted under the SAME predicates as the data query,
        so the provenance describes exactly the rows the value was built from. A
        failed fetch is reported as such (never as "no rows").
        """
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
                    return [], summarise_lineage(
                        {}, year=None, pas=[{"pa": pa, "rows_used": 0, "fetch_failed": False}]
                    )

                max_year = latest[0]
                predicates = (
                    Locality.production_area == pa,
                    LiceRecord.year == max_year,
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )

                # Get farms in this PA with latest data
                q = (
                    select(
                        LiceRecord.locality_no,
                        Locality.name,
                        Locality.owner_company,
                        func.avg(LiceRecord.avg_adult_female_lice).label("avg_lice"),
                    )
                    .join(Locality, Locality.locality_no == LiceRecord.locality_no)
                    .where(*predicates)
                    .group_by(LiceRecord.locality_no, Locality.name, Locality.owner_company)
                    .order_by(func.avg(LiceRecord.avg_adult_female_lice).desc())
                )
                rows = (await s.execute(q)).all()

                lineage_rows = (await s.execute(
                    select(
                        LiceRecord.source,
                        func.count(LiceRecord.id),
                        func.max(LiceRecord.fetched_at),
                    )
                    .join(Locality, Locality.locality_no == LiceRecord.locality_no)
                    .where(*predicates)
                    .group_by(LiceRecord.source)
                )).all()
                counts = {r[0]: int(r[1] or 0) for r in lineage_rows}
                stamps = [t for t in (parse_timestamp(r[2]) for r in lineage_rows) if t]
                newest_fetch = max(stamps) if stamps else None
                # Newest OBSERVATION week among the rows used (max(week) alone would
                # mix years — the W52 trap); fetched_at is only the write time.
                newest = (await s.execute(
                    select(LiceRecord.year, LiceRecord.week)
                    .join(Locality, Locality.locality_no == LiceRecord.locality_no)
                    .where(*predicates)
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )).first()
                newest_week = [int(newest[0]), int(newest[1])] if newest else None
                lineage = summarise_lineage(
                    counts,
                    year=max_year,
                    latest_fetched_at=newest_fetch,
                    latest_week=newest_week,
                    pas=[{
                        "pa": pa,
                        "rows_used": sum(counts.values()),
                        "fetch_failed": False,
                        "latest_fetched_at": newest_fetch.isoformat() if newest_fetch else None,
                        "latest_week": newest_week,
                    }],
                )

                return [
                    {
                        "locality_no": r.locality_no,
                        "locality_name": r.name or f"Locality {r.locality_no}",
                        "company": r.owner_company or "Unknown",
                        "avg_lice": round(float(r.avg_lice), 3),
                    }
                    for r in rows
                ], lineage
        except Exception as e:
            log.warning("lice_quota.pa_fetch_failed", pa=pa, error=str(e))
            return [], summarise_lineage(
                {}, year=None, pas=[{"pa": pa, "rows_used": 0, "fetch_failed": True}]
            )

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
            _refresh_cached_lineage(cached, _LOCALITY_LABEL, 0.65)
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

        lineage = summarise_lineage(
            {data.get("source"): 1},
            year=data.get("year"),
            latest_fetched_at=data.get("fetched_at"),
            latest_week=(data.get("year"), data.get("week")),
            pas=[],
        )

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
            "lineage": lineage,
            "data_provenance": _provenance_for(lineage, _LOCALITY_LABEL, 0.65),
            "generated_at": now.isoformat(),
        }

        engine_cache.set(cache_key, result, CACHE_TTL)
        return result

    async def pa_quota_status(self, pa: int) -> dict[str, Any]:
        """Current estimated emission vs hypothetical quota for a production area."""
        cache_key = f"lice_quota_pa:{pa}"
        cached = engine_cache.get(cache_key)
        if cached is not None:
            _refresh_cached_lineage(cached, _PA_LABEL, 0.60)
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
        farms, lineage = await self._get_pa_lice_data(pa)

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
            "lineage": lineage,
            "data_provenance": _provenance_for(lineage, _PA_LABEL, 0.60),
            "generated_at": now.isoformat(),
        }

        engine_cache.set(cache_key, result, CACHE_TTL)
        return result

    async def national_emission_overview(self) -> dict[str, Any]:
        """All 13 PAs with emission estimates and utilization."""
        cache_key = "lice_quota_national"
        cached = engine_cache.get(cache_key)
        if cached is not None:
            _refresh_cached_lineage(cached, _NATIONAL_LABEL, 0.55)
            self._mirror_lineage(cached.get("lineage"))
            return cached

        self._mirror_lineage(None)  # nothing recorded until this computation succeeds
        now = dt.datetime.now(dt.UTC)
        pa_results = []
        pa_lineages: list[dict | None] = []
        total_national_emission = 0.0
        total_national_quota = 0.0
        over_quota_count = 0

        for pa_def in PA_DEFINITIONS:
            pa = pa_def["pa"]
            pa_status = await self.pa_quota_status(pa)
            pa_lineages.append(pa_status.get("lineage"))

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

        lineage = merge_lineages(pa_lineages)

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
                "Meld. St. 24 (2024-2025) proposes replacing the traffic-light system with "
                "tradable lice-emission quotas per production area. It has not been adopted, "
                "and no timeline or quota allocations have been published. All quotas here "
                "are hypothetical."
            ),
            "regulatory_status": "PROJECTED - regulation not yet finalized",
            "lineage": lineage,
            "data_provenance": _provenance_for(lineage, _NATIONAL_LABEL, 0.55),
            "generated_at": now.isoformat(),
        }

        engine_cache.set(cache_key, result, CACHE_TTL)
        self._mirror_lineage(lineage)
        return result


# Singleton
lice_quota_tracker = LiceQuotaTracker()
