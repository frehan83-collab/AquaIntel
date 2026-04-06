"""
Harvest Optimizer — RL Foundation
====================================
Gym-like environment + rule-based policy for optimal harvest timing.

All dynamic values come from LIVE data:
  - Fish weight growth: biomass_predictor.py growth model constants
  - Lice counts: LiceRecord table (BarentsWatch)
  - Sea temperature: met_ocean / LiceRecord.sea_temp_c
  - Market price: ssb_price_client (real SSB weekly prices)
  - Cage biomass: LiceRecord + Locality tables

Only structural constants are static:
  - HARVEST_WEIGHT_KG = 5.0 (target harvest weight from biomass_predictor)
  - Growth model params from biomass_predictor (OPTIMAL_TEMP_C, THERMAL_TOLERANCE, etc.)
  - Regulatory thresholds (lice limits from Mattilsynet)
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from enum import IntEnum

import numpy as np
import structlog

# Growth model constants from biomass_predictor.py (structural, not dynamic)
from core.market.biomass_predictor import (
    OPTIMAL_TEMP_C,
    THERMAL_TOLERANCE,
    MAX_SGR_PCT,
    SMOLT_WEIGHT_KG,
    HARVEST_WEIGHT_KG,
    MORTALITY_RATE_DAILY,
    STANDARD_SITE_MAB,
    _temperature_growth_factor,
    _sgr,
)

log = structlog.get_logger(__name__)


# ── Actions ──────────────────────────────────────────────────────────
class Action(IntEnum):
    HARVEST_NOW = 0
    WAIT_1_WEEK = 1
    TREAT_THEN_WAIT = 2


# ── Regulatory constants (Mattilsynet) ───────────────────────────────
LICE_LIMIT_ADULT_FEMALE = 0.5   # Regulatory threshold (adult female lice per fish)
LICE_TREATMENT_COST_NOK_PER_KG = 3.50   # Typical treatment cost per kg fish
LICE_MORTALITY_EXCESS_RATE = 0.001  # Extra daily mortality per 0.1 lice above threshold


# ── State dataclass ──────────────────────────────────────────────────
@dataclass
class HarvestState:
    """Current state of a farm cage for harvest decision-making."""
    locality_no: int
    locality_name: str = ""
    fish_weight_kg: float = 0.0        # LIVE: from DB or growth model
    lice_count: float = 0.0            # LIVE: from LiceRecord
    sea_temp_c: float = 10.0           # LIVE: from LiceRecord / met_ocean
    market_price_nok: float = 0.0      # LIVE: from ssb_price_client
    cage_biomass_tonnes: float = 0.0   # LIVE: estimated from DB
    n_fish: int = 200_000              # Estimated fish count
    days_to_mab_limit: int = 999       # Days until MAB limit reached
    week_number: int = 0               # Current week in simulation
    seasonal_price_p75: float = 0.0    # LIVE: 75th percentile from SSB history
    done: bool = False


# ── Harvest Environment (Gym-like) ───────────────────────────────────
class HarvestEnvironment:
    """
    Gym-like state machine for harvest timing decisions.

    State is initialized from LIVE farm data. step() advances by 1 week
    using growth model constants from biomass_predictor.py and LIVE
    temperature/lice data.
    """

    def __init__(self) -> None:
        self.state: HarvestState | None = None
        self._initial_price: float = 0.0

    async def reset(self, locality_no: int) -> HarvestState:
        """Initialize state from LIVE farm data in DB."""
        from sqlalchemy import select, func
        from core.models import LiceRecord, Locality
        from core.async_db import get_async_session

        state = HarvestState(locality_no=locality_no)

        async with get_async_session() as s:
            # Get locality info
            result = await s.execute(
                select(Locality).where(Locality.locality_no == locality_no)
            )
            loc = result.scalar_one_or_none()
            if loc:
                state.locality_name = loc.name or f"Farm {locality_no}"

            # Get latest lice data (LIVE)
            result = await s.execute(
                select(LiceRecord)
                .where(LiceRecord.locality_no == locality_no)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )
            latest = result.scalar_one_or_none()

            if latest:
                state.lice_count = float(latest.avg_adult_female_lice or 0)
                state.sea_temp_c = float(latest.sea_temp_c or 10.0)
                state.week_number = latest.week or 0
            else:
                # Fallback: try to get average from any recent data
                result = await s.execute(
                    select(func.avg(LiceRecord.avg_adult_female_lice))
                    .where(LiceRecord.locality_no == locality_no)
                )
                avg_lice = result.scalar() or 0.1
                state.lice_count = float(avg_lice)

            # Estimate fish weight from growth model
            # Use recent lice records to estimate how long fish have been in sea
            result = await s.execute(
                select(func.count(LiceRecord.id))
                .where(LiceRecord.locality_no == locality_no)
            )
            n_records = result.scalar() or 0

            # Rough estimate: each record ~1 week, grow from smolt weight
            weeks_in_sea = min(n_records, 80)  # cap at ~80 weeks
            weight = SMOLT_WEIGHT_KG
            for _ in range(weeks_in_sea):
                sgr = _sgr(state.sea_temp_c, weight)
                weight *= (1 + sgr / 100) ** 7
            state.fish_weight_kg = round(min(weight, 8.0), 2)

            # Estimate cage biomass
            state.n_fish = 200_000  # typical stocking
            state.cage_biomass_tonnes = round(
                state.n_fish * state.fish_weight_kg / 1000, 1
            )

            # MAB headroom
            mab_remaining = STANDARD_SITE_MAB - state.cage_biomass_tonnes
            weekly_growth_tonnes = state.cage_biomass_tonnes * (
                _sgr(state.sea_temp_c, state.fish_weight_kg) / 100 * 7
            )
            state.days_to_mab_limit = int(
                mab_remaining / max(weekly_growth_tonnes, 0.01) * 7
            ) if mab_remaining > 0 else 0

        # Get LIVE market price from SSB
        try:
            from core.market.ssb_price_client import ssb_price_client
            price_data = await ssb_price_client.fetch_prices(n_weeks=52)
            if price_data.latest_price > 0:
                state.market_price_nok = price_data.latest_price
            # Compute seasonal P75 from LIVE history
            prices = [p.price_nok_kg for p in price_data.prices if p.price_nok_kg > 0]
            if prices:
                state.seasonal_price_p75 = float(np.percentile(prices, 75))
        except Exception as e:
            log.warning("harvest.price_fetch_failed", error=str(e)[:80])

        self.state = state
        self._initial_price = state.market_price_nok
        log.info(
            "harvest.env_reset",
            locality=locality_no,
            weight=state.fish_weight_kg,
            lice=state.lice_count,
            price=state.market_price_nok,
        )
        return state

    def step(self, action: Action) -> tuple[HarvestState, float, bool]:
        """
        Advance state by 1 week under chosen action.
        Returns (next_state, reward, done).

        Growth model uses constants from biomass_predictor.py.
        """
        if self.state is None:
            raise RuntimeError("Must call reset() before step()")

        s = self.state
        reward = 0.0

        if action == Action.HARVEST_NOW:
            # Revenue = weight * LIVE price
            revenue_per_fish = s.fish_weight_kg * s.market_price_nok
            total_revenue = revenue_per_fish * s.n_fish
            reward = total_revenue / 1_000_000  # in millions NOK
            s.done = True
            return s, reward, True

        if action == Action.TREAT_THEN_WAIT:
            # Treatment cost (proportional to biomass)
            treatment_cost = s.cage_biomass_tonnes * 1000 * LICE_TREATMENT_COST_NOK_PER_KG
            reward -= treatment_cost / 1_000_000  # cost in millions NOK

            # Treatment reduces lice by ~80%
            s.lice_count = max(0.01, s.lice_count * 0.2)

            # Treatment stress mortality: ~0.5% of fish
            mortality_treatment = int(s.n_fish * 0.005)
            s.n_fish -= mortality_treatment

        # -- Advance 1 week (WAIT or post-treatment) --

        # Growth: use biomass_predictor SGR model (structural constants)
        sgr = _sgr(s.sea_temp_c, s.fish_weight_kg)
        daily_growth = sgr / 100
        s.fish_weight_kg *= (1 + daily_growth) ** 7
        s.fish_weight_kg = round(s.fish_weight_kg, 3)

        # Mortality: base + excess from lice
        lice_excess = max(0, s.lice_count - LICE_LIMIT_ADULT_FEMALE)
        daily_mortality = MORTALITY_RATE_DAILY + lice_excess * LICE_MORTALITY_EXCESS_RATE
        weekly_survival = (1 - daily_mortality) ** 7
        s.n_fish = int(s.n_fish * weekly_survival)

        # Lice natural growth (~5% per week if untreated, temp-dependent)
        lice_growth_factor = 1.05 * _temperature_growth_factor(s.sea_temp_c)
        s.lice_count = round(s.lice_count * lice_growth_factor, 3)

        # Temperature seasonal drift (simplified)
        s.sea_temp_c += 0.3 * math.sin(2 * math.pi * (s.week_number - 10) / 52)
        s.sea_temp_c = round(max(2, min(18, s.sea_temp_c)), 1)

        # Update biomass
        s.cage_biomass_tonnes = round(s.n_fish * s.fish_weight_kg / 1000, 1)

        # Update MAB headroom
        mab_remaining = STANDARD_SITE_MAB - s.cage_biomass_tonnes
        weekly_growth_tonnes = s.cage_biomass_tonnes * (sgr / 100 * 7)
        s.days_to_mab_limit = int(
            mab_remaining / max(weekly_growth_tonnes, 0.01) * 7
        ) if mab_remaining > 0 else 0

        # Mortality cost as negative reward
        mortality_cost = (200_000 - s.n_fish) * s.fish_weight_kg * s.market_price_nok
        reward -= mortality_cost / 1_000_000 * 0.01  # small penalty

        s.week_number += 1

        return s, round(reward, 4), s.done


# ── Simple Rule-Based Policy ─────────────────────────────────────────
class SimpleHarvestPolicy:
    """
    Rule-based harvest policy using LIVE data.

    Decision logic:
      - HARVEST when weight >= 5.0 kg AND (price > seasonal P75 OR lice > 0.4)
      - TREAT when lice > 0.3 AND weight < 4.5 kg (still growing)
      - WAIT otherwise
    """

    def decide(self, state: HarvestState) -> tuple[Action, str]:
        """Return (action, reasoning) based on LIVE state."""
        reasons = []

        # Harvest conditions
        harvest_weight_ok = state.fish_weight_kg >= HARVEST_WEIGHT_KG
        price_favorable = (
            state.market_price_nok > state.seasonal_price_p75
            and state.seasonal_price_p75 > 0
        )
        lice_pressure_high = state.lice_count > 0.4
        mab_pressure = state.days_to_mab_limit < 30

        if harvest_weight_ok and (price_favorable or lice_pressure_high or mab_pressure):
            if price_favorable:
                reasons.append(
                    f"Price NOK {state.market_price_nok:.1f}/kg above seasonal P75 "
                    f"(NOK {state.seasonal_price_p75:.1f}/kg)"
                )
            if lice_pressure_high:
                reasons.append(
                    f"Lice count {state.lice_count:.2f} exceeds pressure threshold (0.4)"
                )
            if mab_pressure:
                reasons.append(
                    f"Only {state.days_to_mab_limit} days to MAB limit"
                )
            reasons.append(
                f"Fish weight {state.fish_weight_kg:.2f} kg at/above harvest target "
                f"({HARVEST_WEIGHT_KG} kg)"
            )
            return Action.HARVEST_NOW, "; ".join(reasons)

        # Treatment conditions
        if state.lice_count > 0.3 and state.fish_weight_kg < 4.5:
            reasons.append(
                f"Lice {state.lice_count:.2f} above treatment threshold (0.3) "
                f"but fish only {state.fish_weight_kg:.2f} kg — still growing"
            )
            return Action.TREAT_THEN_WAIT, "; ".join(reasons)

        # Default: wait
        growth_potential = HARVEST_WEIGHT_KG - state.fish_weight_kg
        if growth_potential > 0:
            reasons.append(
                f"Fish {state.fish_weight_kg:.2f} kg, need {growth_potential:.2f} kg more "
                f"to reach harvest target ({HARVEST_WEIGHT_KG} kg)"
            )
        if state.lice_count <= 0.3:
            reasons.append(f"Lice {state.lice_count:.2f} within acceptable range")
        if not price_favorable and state.seasonal_price_p75 > 0:
            reasons.append(
                f"Price NOK {state.market_price_nok:.1f}/kg below seasonal P75 "
                f"(NOK {state.seasonal_price_p75:.1f}/kg) — wait for better price"
            )

        return Action.WAIT_1_WEEK, "; ".join(reasons) or "Conditions not met for harvest or treatment"


# ── Harvest Optimizer (wraps environment + policy) ────────────────────
class HarvestOptimizer:
    """
    Main interface combining HarvestEnvironment + SimpleHarvestPolicy.
    All data sourced from LIVE feeds.
    """

    def __init__(self) -> None:
        self.env = HarvestEnvironment()
        self.policy = SimpleHarvestPolicy()

    async def optimize(self, locality_no: int) -> dict:
        """Run policy for a specific farm using LIVE data."""
        state = await self.env.reset(locality_no)
        action, reasoning = self.policy.decide(state)

        # Revenue projections: current vs waiting
        current_revenue = state.fish_weight_kg * state.market_price_nok
        # Project 4 weeks forward for comparison
        projected_weight = state.fish_weight_kg
        for _ in range(4):
            sgr = _sgr(state.sea_temp_c, projected_weight)
            projected_weight *= (1 + sgr / 100) ** 7

        projected_revenue = projected_weight * state.market_price_nok  # conservative: same price

        return {
            "locality_no": locality_no,
            "locality_name": state.locality_name,
            "recommendation": {
                "action": action.name,
                "reasoning": reasoning,
            },
            "current_state": {
                "fish_weight_kg": state.fish_weight_kg,
                "lice_count": state.lice_count,
                "sea_temp_c": state.sea_temp_c,
                "market_price_nok": state.market_price_nok,
                "cage_biomass_tonnes": state.cage_biomass_tonnes,
                "n_fish": state.n_fish,
                "days_to_mab_limit": state.days_to_mab_limit,
            },
            "revenue_projection": {
                "harvest_now_nok_per_fish": round(current_revenue, 2),
                "harvest_4w_nok_per_fish": round(projected_revenue, 2),
                "difference_pct": round(
                    (projected_revenue - current_revenue) / max(current_revenue, 0.01) * 100, 1
                ),
                "harvest_now_total_mnok": round(
                    current_revenue * state.n_fish / 1_000_000, 2
                ),
                "harvest_4w_total_mnok": round(
                    projected_revenue * state.n_fish / 1_000_000, 2
                ),
            },
            "thresholds": {
                "harvest_weight_kg": HARVEST_WEIGHT_KG,
                "lice_treatment_trigger": 0.3,
                "lice_harvest_trigger": 0.4,
                "seasonal_price_p75_nok": round(state.seasonal_price_p75, 1),
            },
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        }

    async def simulate(self, locality_no: int, weeks: int = 12) -> dict:
        """Simulate N-week trajectory under policy."""
        state = await self.env.reset(locality_no)
        trajectory = []

        # Record initial state
        trajectory.append({
            "week": 0,
            "fish_weight_kg": state.fish_weight_kg,
            "lice_count": state.lice_count,
            "sea_temp_c": state.sea_temp_c,
            "market_price_nok": state.market_price_nok,
            "cage_biomass_tonnes": state.cage_biomass_tonnes,
            "n_fish": state.n_fish,
            "action": "START",
            "reward": 0.0,
        })

        total_reward = 0.0
        final_action = "WAIT_1_WEEK"

        for w in range(1, weeks + 1):
            action, reasoning = self.policy.decide(self.env.state)
            next_state, reward, done = self.env.step(action)
            total_reward += reward
            final_action = action.name

            trajectory.append({
                "week": w,
                "fish_weight_kg": round(next_state.fish_weight_kg, 3),
                "lice_count": round(next_state.lice_count, 3),
                "sea_temp_c": round(next_state.sea_temp_c, 1),
                "market_price_nok": round(next_state.market_price_nok, 1),
                "cage_biomass_tonnes": round(next_state.cage_biomass_tonnes, 1),
                "n_fish": next_state.n_fish,
                "action": action.name,
                "reward": round(reward, 4),
            })

            if done:
                break

        return {
            "locality_no": locality_no,
            "locality_name": state.locality_name,
            "weeks_simulated": len(trajectory) - 1,
            "trajectory": trajectory,
            "total_reward_mnok": round(total_reward, 4),
            "final_action": final_action,
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        }

    async def portfolio(self, company_name: str) -> dict:
        """Run optimizer across all farms for a company."""
        from sqlalchemy import select
        from core.models import Locality
        from core.async_db import get_async_session

        async with get_async_session() as s:
            result = await s.execute(
                select(Locality.locality_no, Locality.name)
                .where(Locality.owner_company.ilike(f"%{company_name}%"))
                .limit(50)
            )
            localities = result.all()

        if not localities:
            return {
                "company": company_name,
                "error": f"No farms found for company matching '{company_name}'",
                "farms": [],
                "summary": {},
            }

        farms = []
        harvest_count = 0
        treat_count = 0
        wait_count = 0
        total_current_mnok = 0.0
        total_projected_mnok = 0.0

        for loc_no, loc_name in localities:
            try:
                result = await self.optimize(loc_no)
                action = result["recommendation"]["action"]
                if action == "HARVEST_NOW":
                    harvest_count += 1
                elif action == "TREAT_THEN_WAIT":
                    treat_count += 1
                else:
                    wait_count += 1

                total_current_mnok += result["revenue_projection"]["harvest_now_total_mnok"]
                total_projected_mnok += result["revenue_projection"]["harvest_4w_total_mnok"]

                farms.append({
                    "locality_no": loc_no,
                    "name": loc_name or f"Farm {loc_no}",
                    "action": action,
                    "reasoning": result["recommendation"]["reasoning"],
                    "fish_weight_kg": result["current_state"]["fish_weight_kg"],
                    "lice_count": result["current_state"]["lice_count"],
                    "price_nok": result["current_state"]["market_price_nok"],
                    "current_revenue_mnok": result["revenue_projection"]["harvest_now_total_mnok"],
                    "projected_revenue_mnok": result["revenue_projection"]["harvest_4w_total_mnok"],
                })
            except Exception as e:
                log.warning("harvest.portfolio_farm_error", locality=loc_no, error=str(e)[:80])
                farms.append({
                    "locality_no": loc_no,
                    "name": loc_name or f"Farm {loc_no}",
                    "action": "ERROR",
                    "reasoning": str(e)[:100],
                    "fish_weight_kg": 0,
                    "lice_count": 0,
                    "price_nok": 0,
                    "current_revenue_mnok": 0,
                    "projected_revenue_mnok": 0,
                })

        return {
            "company": company_name,
            "n_farms": len(farms),
            "farms": farms,
            "summary": {
                "harvest_now": harvest_count,
                "treat_then_wait": treat_count,
                "wait": wait_count,
                "total_current_revenue_mnok": round(total_current_mnok, 2),
                "total_projected_revenue_mnok": round(total_projected_mnok, 2),
                "revenue_uplift_pct": round(
                    (total_projected_mnok - total_current_mnok)
                    / max(total_current_mnok, 0.01) * 100, 1
                ),
            },
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        }


# Singleton
harvest_optimizer = HarvestOptimizer()
