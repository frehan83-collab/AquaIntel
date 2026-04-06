"""
What-If Scenario Simulator
============================
LLM-orchestrated simulations for user-defined interventions.
Combines statistical predictions with qualitative reasoning.

Example scenarios:
  "What if sea temperature rises 1°C across PA 3-6?"
  "What if we deploy 20% more cleaner fish in Mowi sites?"
  "What if the traffic-light turns red for PA 4?"
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import select, func

from core.llm.client import llm_client
from core.llm.prompts import SYSTEM_AQUACULTURE_EXPERT, SCENARIO_SIMULATOR_PROMPT
from core.models import LiceRecord, CompanyExposure
from core.async_db import get_async_session
from core.predictors.infestation_pressure import compute_temperature_factor

import structlog

log = structlog.get_logger(__name__)


@dataclass
class ScenarioResult:
    scenario: str
    analysis: str  # LLM narrative
    quantitative_estimates: dict = field(default_factory=dict)
    confidence: str = "medium"


class ScenarioSimulator:
    """Run what-if scenarios combining stats and LLM reasoning."""

    async def simulate(self, scenario_description: str) -> ScenarioResult:
        """Run a complete what-if scenario simulation."""
        baseline = await self._build_baseline()

        prompt = SCENARIO_SIMULATOR_PROMPT.format(
            baseline=json.dumps(baseline, indent=2, default=str),
            scenario_description=scenario_description,
        )

        resp = await llm_client.complete(
            prompt=prompt,
            system=SYSTEM_AQUACULTURE_EXPERT,
            max_tokens=2500,
            temperature=0.4,
        )

        # Run quick quantitative estimates for common scenarios
        quant = self._quantitative_estimate(scenario_description, baseline)

        return ScenarioResult(
            scenario=scenario_description,
            analysis=resp.content,
            quantitative_estimates=quant,
        )

    @staticmethod
    async def _build_baseline() -> dict:
        """Build baseline state from current data."""
        async with get_async_session() as s:
            result = await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )
            latest = result.first()

            if not latest:
                return {"status": "no data"}

            year, week = latest

            result = await s.execute(
                select(
                    func.avg(LiceRecord.avg_adult_female_lice),
                    func.max(LiceRecord.avg_adult_female_lice),
                    func.count(LiceRecord.id),
                    func.avg(LiceRecord.sea_temp_c),
                ).where(
                    LiceRecord.year == year,
                    LiceRecord.week == week,
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )
            )
            stats = result.one()

            company_data = {}
            for ticker in ["MOWI", "SALM", "LSG", "GSF"]:
                result = await s.execute(
                    select(CompanyExposure.locality_no)
                    .where(CompanyExposure.ticker == ticker)
                )
                locs = result.scalars().all()

                if locs:
                    result = await s.execute(
                        select(
                            func.avg(LiceRecord.avg_adult_female_lice),
                            func.count(LiceRecord.id),
                        ).where(
                            LiceRecord.year == year,
                            LiceRecord.week == week,
                            LiceRecord.locality_no.in_(list(locs)),
                            LiceRecord.avg_adult_female_lice.isnot(None),
                        )
                    )
                    c_stats = result.one()
                    company_data[ticker] = {
                        "avg_lice": round(c_stats[0] or 0, 3),
                        "active_sites": c_stats[1],
                    }

        return {
            "week": f"{year}-W{week:02d}",
            "national_avg_lice": round(stats[0] or 0, 3),
            "national_max_lice": round(stats[1] or 0, 3),
            "active_sites": stats[2],
            "avg_sea_temp_c": round(stats[3] or 0, 1),
            "companies": company_data,
        }

    @staticmethod
    def _quantitative_estimate(scenario: str, baseline: dict) -> dict:
        """Quick statistical estimates for common scenario types."""
        estimates = {}
        s_lower = scenario.lower()

        avg_temp = baseline.get("avg_sea_temp_c", 8)
        avg_lice = baseline.get("national_avg_lice", 0.15)

        # Temperature change scenario
        if "temperature" in s_lower or "temp" in s_lower:
            for delta in [0.5, 1.0, 1.5, 2.0]:
                if str(delta) in scenario or f"{delta:.0f}" in scenario:
                    new_temp = avg_temp + delta
                    old_factor = compute_temperature_factor(avg_temp)
                    new_factor = compute_temperature_factor(new_temp)
                    if old_factor > 0:
                        lice_increase_pct = (new_factor / old_factor - 1) * 100
                    else:
                        lice_increase_pct = new_factor * 100
                    estimates["temperature_delta_c"] = delta
                    estimates["new_avg_temp_c"] = new_temp
                    estimates["development_rate_change_pct"] = round(lice_increase_pct, 1)
                    estimates["estimated_new_avg_lice"] = round(
                        avg_lice * (1 + lice_increase_pct / 200), 3
                    )
                    break

        # Cleaner fish scenario
        if "cleaner" in s_lower:
            for pct in [10, 15, 20, 25, 30, 50]:
                if str(pct) in scenario:
                    reduction = pct * 0.3 / 100  # cleaner fish ~30% efficient
                    estimates["cleaner_fish_increase_pct"] = pct
                    estimates["estimated_lice_reduction_pct"] = round(reduction * 100, 1)
                    estimates["estimated_new_avg_lice"] = round(
                        avg_lice * (1 - reduction), 3
                    )
                    break

        # Traffic light scenario
        if "red" in s_lower and ("traffic" in s_lower or "light" in s_lower):
            estimates["production_capacity_cut_pct"] = 6
            estimates["estimated_harvest_reduction_tonnes"] = round(
                1_700_000 * 0.06 / 13, 0  # rough per-PA
            )

        return estimates


scenario_simulator = ScenarioSimulator()
