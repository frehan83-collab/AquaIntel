"""
RAS (Recirculating Aquaculture Systems) Land-Based Salmon Production Tracker
=============================================================================
Tracks the global land-based salmon farming revolution — companies, capacities,
timelines, and the reality gap between announced targets and actual output.

All company data lives in a single RAS_COMPANIES list at the top.
Derived values (% of global supply, growth rates, utilization) are computed
dynamically from this data + live global production from the global_supply engine.

Data sourced from: annual reports, press releases, investor presentations,
IntraFish, SalmonBusiness, Undercurrent News, company websites.
Last updated: 2026-03 (update entries as new data becomes available).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger(__name__)

# ══════════════════════════════════════════════════════════════════════
# COMPANY DATA — single source of truth, easy to update
# ══════════════════════════════════════════════════════════════════════
# Fields:
#   name              — company name
#   country           — primary country of operation
#   country_flag      — emoji flag for display
#   technology        — RAS variant (hybrid, full RAS, flow-through, etc.)
#   planned_capacity  — ultimate announced capacity (tonnes/year HOG)
#   actual_2024       — actual harvest 2024 (tonnes HOG, 0 if pre-production)
#   actual_2025       — actual/estimated 2025 harvest
#   target_2026       — company guidance for 2026
#   target_2030       — company target for 2030
#   status            — operational | ramping | construction | delayed | abandoned | planning
#   funding_usd       — total funding raised (USD, approximate)
#   first_harvest_year — year of first commercial harvest (None if not yet)
#   notes             — key context (public information)

RAS_COMPANIES: list[dict[str, Any]] = [
    {
        "name": "Atlantic Sapphire",
        "country": "USA",
        "country_flag": "US",
        "technology": "Bluehouse (full RAS)",
        "planned_capacity": 220_000,
        "actual_2024": 4_500,
        "actual_2025": 6_800,
        "target_2026": 10_000,
        "target_2030": 220_000,
        "status": "ramping",
        "funding_usd": 550_000_000,
        "first_harvest_year": 2020,
        "notes": "Miami facility. Repeated mass mortality events. Filed Chapter 11 in 2023, emerged 2024. Scaling remains challenging.",
    },
    {
        "name": "Salmon Evolution",
        "country": "Norway",
        "country_flag": "NO",
        "technology": "Hybrid flow-through RAS",
        "planned_capacity": 36_000,
        "actual_2024": 5_200,
        "actual_2025": 8_500,
        "target_2026": 15_000,
        "target_2030": 36_000,
        "status": "ramping",
        "funding_usd": 300_000_000,
        "first_harvest_year": 2022,
        "notes": "Indre Haroya Phase 1 operational. Hybrid concept uses fjord water. Phase 2 construction underway. South Korea JV announced.",
    },
    {
        "name": "Andfjord Salmon",
        "country": "Norway",
        "country_flag": "NO",
        "technology": "Flow-through pool (Andfjord concept)",
        "planned_capacity": 40_000,
        "actual_2024": 1_000,
        "actual_2025": 2_500,
        "target_2026": 8_000,
        "target_2030": 40_000,
        "status": "ramping",
        "funding_usd": 200_000_000,
        "first_harvest_year": 2023,
        "notes": "Kvalnes facility on Andoya island. Unique flow-through pool design using natural seawater current. First harvest Q4 2023.",
    },
    {
        "name": "Nordic Aquafarms",
        "country": "USA",
        "country_flag": "US",
        "technology": "Full RAS",
        "planned_capacity": 33_000,
        "actual_2024": 0,
        "actual_2025": 0,
        "target_2026": 0,
        "target_2030": 0,
        "status": "abandoned",
        "funding_usd": 50_000_000,
        "first_harvest_year": None,
        "notes": "Belfast, Maine project abandoned after years of permitting battles and community opposition. California project also shelved.",
    },
    {
        "name": "Proximar Seafood",
        "country": "Japan",
        "country_flag": "JP",
        "technology": "Full RAS",
        "planned_capacity": 5_300,
        "actual_2024": 500,
        "actual_2025": 1_500,
        "target_2026": 3_000,
        "target_2030": 5_300,
        "status": "ramping",
        "funding_usd": 120_000_000,
        "first_harvest_year": 2024,
        "notes": "Oyama facility near Mt. Fuji. First harvest 2024. Targeting premium Japanese market. Norwegian-founded.",
    },
    {
        "name": "Whole Oceans",
        "country": "USA",
        "country_flag": "US",
        "technology": "Full RAS",
        "planned_capacity": 25_000,
        "actual_2024": 0,
        "actual_2025": 0,
        "target_2026": 0,
        "target_2030": 15_000,
        "status": "delayed",
        "funding_usd": 180_000_000,
        "first_harvest_year": None,
        "notes": "Bucksport, Maine. Construction delayed multiple times. Emerald Harvest partnership. Permits secured but financing uncertain.",
    },
    {
        "name": "Mowi Ireland RAS",
        "country": "Ireland",
        "country_flag": "IE",
        "technology": "Full RAS (smolt + post-smolt)",
        "planned_capacity": 10_000,
        "actual_2024": 2_000,
        "actual_2025": 3_500,
        "target_2026": 5_000,
        "target_2030": 10_000,
        "status": "operational",
        "funding_usd": 100_000_000,
        "first_harvest_year": 2021,
        "notes": "Mowi integrated RAS for smolt/post-smolt. Supplements sea-cage production. Part of Mowi's broader freshwater strategy.",
    },
    {
        "name": "Bakkafrost Scotland RAS",
        "country": "Scotland",
        "country_flag": "GB",
        "technology": "Full RAS (post-smolt)",
        "planned_capacity": 12_000,
        "actual_2024": 1_500,
        "actual_2025": 3_000,
        "target_2026": 6_000,
        "target_2030": 12_000,
        "status": "operational",
        "funding_usd": 150_000_000,
        "first_harvest_year": 2022,
        "notes": "Applecross and other Scottish sites. Post-smolt strategy to reduce sea phase. Part of Bakkafrost's Scottish Salmon operations.",
    },
    {
        "name": "Superior Fresh",
        "country": "USA",
        "country_flag": "US",
        "technology": "Aquaponics + RAS",
        "planned_capacity": 2_500,
        "actual_2024": 1_800,
        "actual_2025": 2_200,
        "target_2026": 2_500,
        "target_2030": 5_000,
        "status": "operational",
        "funding_usd": 50_000_000,
        "first_harvest_year": 2018,
        "notes": "Hixton, Wisconsin. World's largest aquaponics facility. Atlantic salmon + leafy greens. Profitable at small scale.",
    },
    {
        "name": "Kuterra",
        "country": "Canada",
        "country_flag": "CA",
        "technology": "Full RAS",
        "planned_capacity": 1_000,
        "actual_2024": 500,
        "actual_2025": 600,
        "target_2026": 800,
        "target_2030": 1_000,
        "status": "operational",
        "funding_usd": 15_000_000,
        "first_harvest_year": 2013,
        "notes": "Namgis First Nation, Vancouver Island. Pioneer land-based salmon facility. Small scale but operational since 2013. Proof of concept.",
    },
]


# ══════════════════════════════════════════════════════════════════════
# ENGINE
# ══════════════════════════════════════════════════════════════════════

class RASTracker:
    """Track global RAS (land-based) salmon production projects."""

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _growth_rate(old: float, new: float) -> float | None:
        """Compute YoY growth rate. Returns None if old is 0."""
        if old <= 0:
            return None
        return round((new - old) / old * 100, 1)

    @staticmethod
    def _utilization(actual: float, planned: float) -> float:
        """Compute capacity utilization %."""
        if planned <= 0:
            return 0.0
        return round(actual / planned * 100, 1)

    # ── live global production ──────────────────────────────────────

    def _get_global_production_tonnes(self) -> tuple[int, bool]:
        """Fetch total global Atlantic salmon production from the live global_supply engine.
        Returns (tonnes, is_live) tuple. Falls back to static estimate if engine unavailable."""
        try:
            from core.market.global_supply import TOTAL_GLOBAL
            return TOTAL_GLOBAL, True  # ~2.9M-3.1M tonnes
        except Exception:
            log.warning("ras_tracker.global_supply_fallback", reason="global_supply import failed")
            return 3_000_000, False  # static fallback

    # ── public API ──────────────────────────────────────────────────

    def get_companies(self) -> list[dict[str, Any]]:
        """Return all RAS companies with computed growth rates and utilization."""
        global_total, global_is_live = self._get_global_production_tonnes()
        results = []
        for c in RAS_COMPANIES:
            actual_latest = c["actual_2025"]
            growth_24_25 = self._growth_rate(c["actual_2024"], c["actual_2025"])
            growth_25_26 = self._growth_rate(c["actual_2025"], c["target_2026"])
            utilization = self._utilization(actual_latest, c["planned_capacity"])
            pct_global = round(actual_latest / global_total * 100, 4) if global_total > 0 else 0.0

            results.append({
                **c,
                "actual_latest": actual_latest,
                "growth_24_25_pct": growth_24_25,
                "growth_25_26_pct": growth_25_26,
                "utilization_pct": utilization,
                "pct_of_global_supply": pct_global,
            })
        return results

    def get_global_summary(self) -> dict[str, Any]:
        """Aggregate RAS metrics vs live global supply."""
        global_total, global_is_live = self._get_global_production_tonnes()
        companies = RAS_COMPANIES

        total_planned = sum(c["planned_capacity"] for c in companies)
        total_actual_2024 = sum(c["actual_2024"] for c in companies)
        total_actual_2025 = sum(c["actual_2025"] for c in companies)
        total_target_2026 = sum(c["target_2026"] for c in companies)
        total_target_2030 = sum(c["target_2030"] for c in companies)
        total_funding = sum(c["funding_usd"] for c in companies)

        active = [c for c in companies if c["status"] not in ("abandoned", "delayed")]
        operational = [c for c in companies if c["status"] == "operational"]
        ramping = [c for c in companies if c["status"] == "ramping"]

        avg_utilization = 0.0
        active_with_capacity = [c for c in active if c["planned_capacity"] > 0 and c["actual_2025"] > 0]
        if active_with_capacity:
            avg_utilization = round(
                sum(c["actual_2025"] / c["planned_capacity"] for c in active_with_capacity)
                / len(active_with_capacity) * 100,
                1,
            )

        ras_share_2025 = round(total_actual_2025 / global_total * 100, 2) if global_total > 0 else 0
        ras_share_2026 = round(total_target_2026 / global_total * 100, 2) if global_total > 0 else 0
        ras_share_2030 = round(total_target_2030 / global_total * 100, 2) if global_total > 0 else 0

        growth_yoy = self._growth_rate(total_actual_2024, total_actual_2025)

        # Reality check: ratio of actual output to total announced capacity
        reality_ratio = round(total_actual_2025 / total_planned * 100, 1) if total_planned > 0 else 0

        return {
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "global_production_tonnes": global_total,
            "global_production_is_live": global_is_live,
            "global_production_data_quality": "live" if global_is_live else "stale_fallback",
            "total_ras_planned_capacity": total_planned,
            "total_ras_actual_2024": total_actual_2024,
            "total_ras_actual_2025": total_actual_2025,
            "total_ras_target_2026": total_target_2026,
            "total_ras_target_2030": total_target_2030,
            "total_funding_usd": total_funding,
            "ras_share_of_global_2025_pct": ras_share_2025,
            "ras_share_of_global_2026_pct": ras_share_2026,
            "ras_share_of_global_2030_pct": ras_share_2030,
            "growth_2024_to_2025_pct": growth_yoy,
            "avg_utilization_pct": avg_utilization,
            "reality_ratio_pct": reality_ratio,
            "project_counts": {
                "total": len(companies),
                "operational": len(operational),
                "ramping": len(ramping),
                "active": len(active),
                "abandoned_or_delayed": len(companies) - len(active),
            },
            "insights": self._generate_insights(
                total_actual_2025, total_planned, global_total,
                ras_share_2025, reality_ratio, growth_yoy,
            ),
        }

    def get_timeline(self) -> dict[str, Any]:
        """Year-by-year projected RAS capacity 2024-2030, aggregated from company data."""
        global_total, _ = self._get_global_production_tonnes()
        active = [c for c in RAS_COMPANIES if c["status"] not in ("abandoned",)]

        years = list(range(2024, 2031))
        timeline = []

        for year in years:
            year_data: dict[str, Any] = {"year": year, "companies": [], "total": 0}
            for c in active:
                if year == 2024:
                    val = c["actual_2024"]
                elif year == 2025:
                    val = c["actual_2025"]
                elif year == 2026:
                    val = c["target_2026"]
                elif year == 2030:
                    val = c["target_2030"]
                else:
                    # Interpolate between 2026 target and 2030 target
                    t26 = c["target_2026"]
                    t30 = c["target_2030"]
                    if t30 > t26 and t26 > 0:
                        progress = (year - 2026) / (2030 - 2026)
                        val = int(t26 + (t30 - t26) * progress)
                    else:
                        val = t26  # flat if no 2030 target or already at target

                year_data["companies"].append({
                    "name": c["name"],
                    "tonnes": val,
                    "status": c["status"],
                })
                year_data["total"] += val

            year_data["pct_of_global"] = round(
                year_data["total"] / global_total * 100, 2
            ) if global_total > 0 else 0.0
            timeline.append(year_data)

        return {
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "global_production_tonnes": global_total,
            "timeline": timeline,
        }

    # ── insights ────────────────────────────────────────────────────

    @staticmethod
    def _generate_insights(
        actual_2025: int, total_planned: int, global_total: int,
        ras_share: float, reality_ratio: float, growth_yoy: float | None,
    ) -> list[str]:
        insights = []
        if reality_ratio < 10:
            insights.append(
                f"Reality check: RAS facilities are producing only {reality_ratio}% "
                f"of their total announced capacity ({actual_2025:,}t vs {total_planned:,}t planned)."
            )
        if ras_share < 1:
            insights.append(
                f"Land-based salmon represents just {ras_share}% of global production "
                f"({actual_2025:,}t out of {global_total:,}t). Sea-cage farming remains dominant."
            )
        if growth_yoy and growth_yoy > 20:
            insights.append(
                f"RAS production grew {growth_yoy}% YoY (2024-2025), showing momentum despite scaling challenges."
            )
        insights.append(
            "Multiple high-profile failures (Nordic Aquafarms abandoned, Atlantic Sapphire Chapter 11) "
            "highlight the gap between RAS ambition and execution."
        )
        insights.append(
            "Hybrid approaches (Salmon Evolution, Andfjord) using natural seawater appear more viable "
            "than full inland RAS facilities far from the coast."
        )
        return insights


# ── singleton ───────────────────────────────────────────────────────
ras_tracker = RASTracker()
