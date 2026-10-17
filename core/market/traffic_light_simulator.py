"""
Traffic Light Simulator
=========================
Models the financial impact of production area colour changes under
Norway's aquaculture traffic-light system (produksjonsområdeforskriften, 2017).

Current colours are the latest OFFICIAL decision (core/regulatory_facts.py), never
a model output. Green offers up to +6% capacity, yellow no change, red -6%.
A replacement of the system is proposed in Meld. St. 24 (2024-2025), not adopted.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import structlog

from core.market.biomass_predictor import (
    TRAFFIC_LIGHT_ADJUSTMENTS,
    STANDARD_SITE_MAB,
    NATIONAL_MAB_TONNES,
    TYPICAL_UTILIZATION,
)

log = structlog.get_logger(__name__)


def _now() -> dt.datetime:
    """The clock (a seam for tests)."""
    return dt.datetime.now(dt.UTC)

# ── Production Area definitions (PA 1-13) ────────────────────────────────────
# Source: Nærings- og fiskeridepartementet, produksjonsområdeforskriften
PA_DEFINITIONS: list[dict[str, Any]] = [
    {"pa": 1, "name": "Svenskegrensen til Jæren", "region": "South"},
    {"pa": 2, "name": "Ryfylke", "region": "South"},
    {"pa": 3, "name": "Karmøy til Sotra", "region": "West"},
    {"pa": 4, "name": "Nordhordland til Stadt", "region": "West"},
    {"pa": 5, "name": "Stadt til Hustadvika", "region": "Mid-West"},
    {"pa": 6, "name": "Nordmøre og Sør-Trøndelag", "region": "Mid"},
    {"pa": 7, "name": "Nord-Trøndelag med Bindal", "region": "Mid"},
    {"pa": 8, "name": "Helgeland til Bodø", "region": "North"},
    {"pa": 9, "name": "Vestfjorden og Vesterålen", "region": "North"},
    {"pa": 10, "name": "Andøya til Senja", "region": "North"},
    {"pa": 11, "name": "Kvaløya til Loppa", "region": "Troms"},
    {"pa": 12, "name": "Vest-Finnmark", "region": "Finnmark"},
    {"pa": 13, "name": "Øst-Finnmark", "region": "Finnmark"},
]

# Estimated farm counts per PA (from Fiskeridirektoratet locality register ~2024)
PA_FARM_COUNTS: dict[int, int] = {
    1: 35, 2: 85, 3: 140, 4: 155, 5: 130,
    6: 160, 7: 110, 8: 145, 9: 120, 10: 95,
    11: 100, 12: 80, 13: 60,
}

# Estimated MAB allocation per PA (tonnes, from Fiskeridirektoratet Table 8)
PA_MAB_ALLOCATION: dict[int, float] = {
    1: 25_000, 2: 55_000, 3: 92_000, 4: 102_000, 5: 85_000,
    6: 105_000, 7: 72_000, 8: 95_000, 9: 78_000, 10: 62_000,
    11: 68_000, 12: 55_000, 13: 38_000,
}

# Major operators by PA (top companies per area)
PA_MAJOR_OPERATORS: dict[int, list[dict[str, Any]]] = {
    1: [{"company": "Mowi", "farms": 10}, {"company": "Lerøy Seafood", "farms": 8}, {"company": "Grieg Seafood", "farms": 7}],
    2: [{"company": "Mowi", "farms": 22}, {"company": "Grieg Seafood", "farms": 18}, {"company": "Lerøy Seafood", "farms": 15}],
    3: [{"company": "Mowi", "farms": 35}, {"company": "Lerøy Seafood", "farms": 30}, {"company": "Grieg Seafood", "farms": 25}, {"company": "Bremnes Seashore", "farms": 20}],
    4: [{"company": "Lerøy Seafood", "farms": 40}, {"company": "Mowi", "farms": 35}, {"company": "Cermaq", "farms": 22}],
    5: [{"company": "Mowi", "farms": 30}, {"company": "SalMar", "farms": 28}, {"company": "Lerøy Seafood", "farms": 22}],
    6: [{"company": "SalMar", "farms": 45}, {"company": "Mowi", "farms": 35}, {"company": "Lerøy Seafood", "farms": 25}],
    7: [{"company": "SalMar", "farms": 35}, {"company": "NTS ASA", "farms": 25}, {"company": "Mowi", "farms": 18}],
    8: [{"company": "Cermaq", "farms": 35}, {"company": "Mowi", "farms": 30}, {"company": "Nova Sea", "farms": 28}],
    9: [{"company": "Cermaq", "farms": 30}, {"company": "Nordlaks", "farms": 25}, {"company": "Mowi", "farms": 22}],
    10: [{"company": "Mowi", "farms": 25}, {"company": "Nordlaks", "farms": 20}, {"company": "Cermaq", "farms": 18}],
    11: [{"company": "Mowi", "farms": 28}, {"company": "Lerøy Seafood", "farms": 22}, {"company": "Grieg Seafood", "farms": 15}],
    12: [{"company": "Mowi", "farms": 25}, {"company": "Grieg Seafood", "farms": 18}, {"company": "Cermaq", "farms": 15}],
    13: [{"company": "Grieg Seafood", "farms": 20}, {"company": "Cermaq", "farms": 15}, {"company": "Mowi", "farms": 10}],
}

class TrafficLightSimulator:
    """
    Simulates the financial and operational impact of traffic light
    color changes across Norway's 13 production areas.
    """

    def __init__(self) -> None:
        pass

    def _get_spot_price_nok(self) -> float:
        """Get current SSB salmon spot price in NOK/kg."""
        try:
            from core.market.ssb_price_client import ssb_price_client
            latest = ssb_price_client.latest()
            if latest and latest.get("price_nok"):
                return float(latest["price_nok"])
        except Exception:
            pass
        return 85.0  # fallback

    async def get_current_colors(self) -> dict[str, Any]:
        """Current traffic-light status for all 13 PAs: the latest official decision."""
        from core.regulatory_facts import (
            CUT_LAG_NOTE,
            PRODUCTION_AREA_REGULATION_URL,
            capacity_pct,
            scheduled_capacity,
            traffic_light_decision,
        )

        now = _now()
        decision = traffic_light_decision(now)
        colors = decision.colours

        pa_list = []
        for pa_def in PA_DEFINITIONS:
            pa = pa_def["pa"]
            color = colors[pa]
            adj = TRAFFIC_LIGHT_ADJUSTMENTS.get(color, 0.0)
            base_mab = PA_MAB_ALLOCATION.get(pa, STANDARD_SITE_MAB * PA_FARM_COUNTS.get(pa, 100))
            cap_now = capacity_pct(pa, now)
            # Usable capacity in force today; offered green growth is not counted
            # (uptake is unknown), and a decided cut counts only once it applies.
            effective_mab = base_mab * cap_now / 100.0
            pa_list.append({
                "production_area": pa,
                "name": pa_def["name"],
                "region": pa_def["region"],
                "current_color": color,
                "mab_adjustment_pct": round(adj * 100, 1),
                "base_mab_tonnes": round(base_mab, 0),
                "effective_mab_tonnes": round(effective_mab, 0),
                "farms": PA_FARM_COUNTS.get(pa, 0),
                "capacity_pct_in_force": cap_now,
                "capacity_change_scheduled": scheduled_capacity(pa, now),
                "growth_offered_pct": round(adj * 100, 1) if adj > 0 else 0.0,
            })

        green_count = sum(1 for p in pa_list if p["current_color"] == "green")
        yellow_count = sum(1 for p in pa_list if p["current_color"] == "yellow")
        red_count = sum(1 for p in pa_list if p["current_color"] == "red")

        return {
            "total_pas": 13,
            "green": green_count,
            "yellow": yellow_count,
            "red": red_count,
            "national_mab_tonnes": NATIONAL_MAB_TONNES,
            "production_areas": pa_list,
            "assessment_basis": "Lice-induced wild salmon mortality",
            "framework": "Produksjonsområdeforskriften (FOR-2017-01-16-61); a replacement is proposed in Meld. St. 24 (2024-2025), not adopted",
            "framework_url": PRODUCTION_AREA_REGULATION_URL,
            "decision": decision.as_dict(),
            "capacity_rule": CUT_LAG_NOTE,
            "mab_basis": "estimated PA allocation (Fiskeridirektoratet Table 8, estimate) x capacity in force",
            "generated_at": now.isoformat(),
        }

    async def simulate_color_change(self, pa: int, new_color: str) -> dict[str, Any]:
        """Simulate the impact of changing a production area's traffic light color."""
        now = _now()
        new_color = new_color.lower().strip()

        if pa < 1 or pa > 13:
            return {"error": f"Invalid production area: {pa}. Must be 1-13."}
        if new_color not in TRAFFIC_LIGHT_ADJUSTMENTS:
            return {"error": f"Invalid color: {new_color}. Must be green, yellow, or red."}

        # Get current colors
        current_status = await self.get_current_colors()
        current_pa = next(
            (p for p in current_status["production_areas"] if p["production_area"] == pa),
            None,
        )
        if not current_pa:
            return {"error": f"PA {pa} not found"}

        current_color = current_pa["current_color"]
        pa_name = current_pa["name"]

        # Calculate MAB impact
        base_mab = PA_MAB_ALLOCATION.get(pa, STANDARD_SITE_MAB * PA_FARM_COUNTS.get(pa, 100))
        current_adj = TRAFFIC_LIGHT_ADJUSTMENTS.get(current_color, 0.0)
        new_adj = TRAFFIC_LIGHT_ADJUSTMENTS.get(new_color, 0.0)

        current_mab = base_mab * (1 + current_adj)
        new_mab = base_mab * (1 + new_adj)
        mab_change = new_mab - current_mab
        mab_change_pct = (new_adj - current_adj) * 100

        # Production impact (using typical utilization)
        production_impact = mab_change * TYPICAL_UTILIZATION
        farms_affected = PA_FARM_COUNTS.get(pa, 0)

        # Revenue impact at current spot price
        spot_price = self._get_spot_price_nok()
        # Annual production approximation: standing biomass turns over ~2x per year
        annual_turnover = 2.0
        revenue_impact_nok = production_impact * annual_turnover * spot_price
        revenue_impact_mnok = revenue_impact_nok / 1_000_000

        # Per-company impact
        operators = PA_MAJOR_OPERATORS.get(pa, [])
        total_operator_farms = sum(op["farms"] for op in operators) or 1
        affected_companies = []
        for op in operators:
            share = op["farms"] / total_operator_farms
            affected_companies.append({
                "company": op["company"],
                "farms": op["farms"],
                "share_pct": round(share * 100, 1),
                "impact_tonnes": round(production_impact * share, 1),
                "revenue_impact_mnok": round(revenue_impact_mnok * share, 1),
            })

        # Reasoning
        if new_color == current_color:
            reasoning = f"No change: PA {pa} remains {current_color}."
        elif new_adj > current_adj:
            reasoning = (
                f"Upgrading PA {pa} ({pa_name}) from {current_color} to {new_color} "
                f"allows +{mab_change_pct:+.1f}% MAB growth, adding ~{abs(production_impact):.0f} tonnes "
                f"standing biomass capacity. Positive for producers in this area."
            )
        else:
            reasoning = (
                f"Downgrading PA {pa} ({pa_name}) from {current_color} to {new_color} "
                f"requires {mab_change_pct:+.1f}% MAB reduction, removing ~{abs(production_impact):.0f} tonnes "
                f"standing biomass capacity. Producers must reduce stocking or accelerate harvest."
            )

        return {
            "production_area": pa,
            "production_area_name": pa_name,
            "current_color": current_color,
            "simulated_color": new_color,
            "mab_change_pct": round(mab_change_pct, 1),
            "farms_affected": farms_affected,
            "current_mab_tonnes": round(current_mab, 0),
            "new_mab_tonnes": round(new_mab, 0),
            "production_impact_tonnes": round(production_impact, 1),
            "revenue_impact_mnok": round(revenue_impact_mnok, 1),
            "spot_price_nok_kg": round(spot_price, 2),
            "affected_companies": affected_companies,
            "effective_date": "A red decision's cut applies 6 months after the cut regulation enters into force (produksjonsområdeforskriften § 9); growth in green areas is offered at a fixed price and by auction",
            "current_decision": current_status.get("decision"),
            "reasoning": reasoning,
            "generated_at": now.isoformat(),
        }

    async def simulate_all_pas(self) -> dict[str, Any]:
        """Generate what-if scenarios for all 13 PAs under each color."""
        now = _now()
        current_status = await self.get_current_colors()
        spot_price = self._get_spot_price_nok()

        scenarios = []
        for pa_info in current_status["production_areas"]:
            pa = pa_info["production_area"]
            current_color = pa_info["current_color"]
            base_mab = PA_MAB_ALLOCATION.get(pa, STANDARD_SITE_MAB * PA_FARM_COUNTS.get(pa, 100))

            pa_scenarios = {
                "production_area": pa,
                "name": pa_info["name"],
                "region": pa_info["region"],
                "current_color": current_color,
                "farms": PA_FARM_COUNTS.get(pa, 0),
                "base_mab_tonnes": round(base_mab, 0),
                "scenarios": {},
            }

            for color in ["green", "yellow", "red"]:
                adj = TRAFFIC_LIGHT_ADJUSTMENTS[color]
                new_mab = base_mab * (1 + adj)
                current_adj = TRAFFIC_LIGHT_ADJUSTMENTS.get(current_color, 0.0)
                mab_delta = (adj - current_adj) * base_mab
                production_delta = mab_delta * TYPICAL_UTILIZATION
                revenue_delta = production_delta * 2.0 * spot_price / 1_000_000

                pa_scenarios["scenarios"][color] = {
                    "mab_tonnes": round(new_mab, 0),
                    "mab_change_pct": round((adj - current_adj) * 100, 1),
                    "production_delta_tonnes": round(production_delta, 1),
                    "revenue_delta_mnok": round(revenue_delta, 1),
                    "is_current": color == current_color,
                }

            scenarios.append(pa_scenarios)

        # National totals
        total_if_green = sum(
            PA_MAB_ALLOCATION.get(i, 0) * (1 + TRAFFIC_LIGHT_ADJUSTMENTS["green"])
            for i in range(1, 14)
        )
        total_if_red = sum(
            PA_MAB_ALLOCATION.get(i, 0) * (1 + TRAFFIC_LIGHT_ADJUSTMENTS["red"])
            for i in range(1, 14)
        )
        total_current = sum(
            PA_MAB_ALLOCATION.get(pa_info["production_area"], 0)
            * (1 + TRAFFIC_LIGHT_ADJUSTMENTS.get(pa_info["current_color"], 0.0))
            for pa_info in current_status["production_areas"]
        )

        return {
            "scenarios": scenarios,
            "current_decision": current_status.get("decision"),
            "national_summary": {
                "current_effective_mab": round(total_current, 0),
                "all_green_mab": round(total_if_green, 0),
                "all_red_mab": round(total_if_red, 0),
                "max_upside_tonnes": round((total_if_green - total_current) * TYPICAL_UTILIZATION, 0),
                "max_downside_tonnes": round((total_if_red - total_current) * TYPICAL_UTILIZATION, 0),
                "spot_price_nok_kg": round(spot_price, 2),
            },
            "framework_note": (
                "Scenarios are hypothetical. The current colours are the latest official "
                "decision; a replacement of the system is proposed in Meld. St. 24 "
                "(2024-2025) and has not been adopted."
            ),
            "generated_at": now.isoformat(),
        }


# Singleton
traffic_light_simulator = TrafficLightSimulator()
