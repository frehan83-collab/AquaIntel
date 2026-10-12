"""
Digital Twin Core Engine
=========================
A live virtual replica of selected farms and production areas.

Extends population-tracing with:
  - Stage-specific lice dynamics (sessile → motile → adult)
  - Biomass growth modeling (SGR, FCR, temperature-dependent)
  - Treatment effect simulation (efficacy decay, resistance)
  - Cleaner-fish population dynamics
  - Mortality and welfare tracking
  - Harvest-quality prediction

The twin state updates every 15 minutes from BarentsWatch and can be
"forked" for what-if simulations without affecting the live state.
"""
from __future__ import annotations

import copy
import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import structlog

from core.predictors.infestation_pressure import compute_temperature_factor

log = structlog.get_logger(__name__)


@dataclass
class FishCohort:
    """A cohort of fish at a specific locality/cage."""
    cohort_id: str
    locality_no: int
    smolt_date: dt.date | None = None
    current_count: int = 200_000
    initial_count: int = 200_000
    avg_weight_kg: float = 3.5
    cumulative_mortality_pct: float = 5.0
    feed_conversion_ratio: float = 1.15
    generation_id: str = ""


@dataclass
class LiceState:
    """Current lice state per stage for a twin locality."""
    sessile: float = 0.0
    motile: float = 0.0
    adult_female: float = 0.0
    total: float = 0.0
    trend: str = "stable"
    weeks_above_threshold: int = 0


@dataclass
class CleanerFishState:
    """Cleaner fish population at a locality."""
    wrasse_count: int = 0
    lumpfish_count: int = 0
    efficacy_pct: float = 20.0  # current estimated lice reduction
    mortality_rate_weekly: float = 0.005


@dataclass
class TwinLocality:
    """Complete digital twin state for one locality."""
    locality_no: int
    name: str = ""
    ticker: str = ""
    production_area: int = 0
    lat: float = 0.0
    lon: float = 0.0

    # Current state
    sea_temp_c: float = 8.0
    lice: LiceState = field(default_factory=LiceState)
    cohort: FishCohort | None = None
    cleaner_fish: CleanerFishState = field(default_factory=CleanerFishState)

    # Treatment history
    treatments_this_cycle: int = 0
    last_treatment_week: int = 0
    treatment_resistance_factor: float = 1.0  # 1.0 = no resistance

    # Predictions (injected by prediction agents)
    predicted_lice_1w: float = 0.0
    predicted_lice_2w: float = 0.0
    predicted_harvest_week: int | None = None
    risk_score: float = 0.0

    # Economics
    estimated_biomass_tonnes: float = 0.0
    estimated_value_nok: float = 0.0

    # Timestamp
    last_updated: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))


@dataclass
class TwinSnapshot:
    """Complete twin state at a point in time (for forking/replay)."""
    timestamp: dt.datetime
    localities: dict[int, TwinLocality]
    national_avg_lice: float = 0.0
    total_biomass_tonnes: float = 0.0
    week: int = 0
    year: int = 0


class DigitalTwinEngine:
    """
    Manages the live digital twin and supports forking for simulations.
    """

    _cached_spot: float = 65.0
    _spot_ts: dt.datetime | None = None

    def __init__(self) -> None:
        self.localities: dict[int, TwinLocality] = {}
        self.history: list[TwinSnapshot] = []
        self.last_sync: dt.datetime | None = None

    def _get_spot_price(self) -> float:
        """Get SSB spot price, cached for 1 hour."""
        now = dt.datetime.now(dt.UTC)
        if self._spot_ts and (now - self._spot_ts).total_seconds() < 3600:
            return self._cached_spot
        try:
            import asyncio
            from core.market.ssb_price_client import ssb_price_client
            spot = asyncio.get_event_loop().run_until_complete(ssb_price_client.get_current_spot())
            if spot > 0:
                self._cached_spot = spot
                self._spot_ts = now
        except Exception:
            pass
        return self._cached_spot

    async def sync_from_db(self) -> int:
        """Sync twin state from the database (called every 15 min)."""
        from sqlalchemy import select
        from core.models import (
            Locality, LiceRecord, CompanyExposure,
        )
        from core.async_db import get_async_session

        async with get_async_session() as s:
            # Find latest week
            result = await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )
            latest = result.first()

            if not latest:
                return 0

            year, week = latest

            # Get all lice records with locality info
            result = await s.execute(
                select(LiceRecord, Locality)
                .join(Locality, LiceRecord.locality_no == Locality.locality_no)
                .where(LiceRecord.year == year, LiceRecord.week == week)
                .where(LiceRecord.avg_adult_female_lice.isnot(None))
            )
            records = result.all()

            # Get company mappings
            result = await s.execute(select(CompanyExposure))
            exposures = result.scalars().all()
            company_map = {e.locality_no: e.ticker for e in exposures}

        updated = 0
        for lice_rec, loc in records:
            ln = lice_rec.locality_no

            if ln not in self.localities:
                self.localities[ln] = TwinLocality(
                    locality_no=ln,
                    name=loc.name or "",
                    ticker=company_map.get(ln, ""),
                    production_area=loc.production_area or 0,
                    lat=loc.latitude or 0,
                    lon=loc.longitude or 0,
                )

            twin = self.localities[ln]
            twin.sea_temp_c = lice_rec.sea_temp_c or 8.0
            twin.lice = LiceState(
                sessile=lice_rec.avg_stationary_lice or 0,
                motile=lice_rec.avg_mobile_lice or 0,
                adult_female=lice_rec.avg_adult_female_lice or 0,
                total=(lice_rec.avg_stationary_lice or 0) +
                      (lice_rec.avg_mobile_lice or 0) +
                      (lice_rec.avg_adult_female_lice or 0),
            )

            # Track threshold breaches
            if twin.lice.adult_female > 0.5:
                twin.lice.weeks_above_threshold += 1
            else:
                twin.lice.weeks_above_threshold = 0

            # Estimate biomass
            if twin.cohort:
                twin.estimated_biomass_tonnes = (
                    twin.cohort.current_count * twin.cohort.avg_weight_kg / 1000
                )
            else:
                twin.estimated_biomass_tonnes = 200_000 * 3.5 / 1000  # default

            # Valuation: use SSB spot price when available, else conservative 65 NOK/kg
            _nok_per_kg = self._get_spot_price()
            twin.estimated_value_nok = twin.estimated_biomass_tonnes * (_nok_per_kg * 1000)
            twin.last_updated = dt.datetime.now(dt.UTC)
            updated += 1

        self.last_sync = dt.datetime.now(dt.UTC)

        # Save snapshot
        self._save_snapshot(year, week)

        log.info("twin.sync", updated=updated, total=len(self.localities))
        return updated

    def _save_snapshot(self, year: int, week: int) -> None:
        """Save current state as a historical snapshot."""
        snapshot = TwinSnapshot(
            timestamp=dt.datetime.now(dt.UTC),
            localities={k: copy.deepcopy(v) for k, v in self.localities.items()},
            national_avg_lice=np.mean([
                t.lice.adult_female for t in self.localities.values()
            ]) if self.localities else 0,
            total_biomass_tonnes=sum(
                t.estimated_biomass_tonnes for t in self.localities.values()
            ),
            week=week,
            year=year,
        )
        self.history.append(snapshot)
        # Keep last 52 snapshots (1 year of weekly)
        if len(self.history) > 52:
            self.history = self.history[-52:]

    def fork(self) -> dict[int, TwinLocality]:
        """Create a deep copy for simulation without affecting live state."""
        return {k: copy.deepcopy(v) for k, v in self.localities.items()}

    def simulate_step(
        self,
        state: dict[int, TwinLocality],
        weeks: int = 1,
        interventions: dict | None = None,
    ) -> dict[int, TwinLocality]:
        """
        Advance a forked twin state by `weeks` steps.

        interventions: {
            "treat_localities": [list of locality_nos],
            "treatment_type": "mechanical" | "thermal" | "medicinal",
            "add_cleaner_fish": {locality_no: count, ...},
            "temp_delta_c": float,
            "harvest_localities": [list of locality_nos],
        }
        """
        interventions = interventions or {}

        for _ in range(weeks):
            for ln, twin in state.items():
                temp = twin.sea_temp_c + interventions.get("temp_delta_c", 0)
                tf = compute_temperature_factor(temp)

                # ── Lice dynamics (simplified stage-structured) ──────
                # Development: sessile → motile → adult (temp-dependent)
                dev_rate = tf * 0.15  # fraction developing per week

                new_sessile = twin.lice.sessile * (1 - dev_rate) + np.random.exponential(0.02)
                new_motile = twin.lice.motile * (1 - dev_rate) + twin.lice.sessile * dev_rate
                new_adult = twin.lice.adult_female * 0.9 + twin.lice.motile * dev_rate

                # Cleaner fish reduction
                if twin.cleaner_fish.wrasse_count + twin.cleaner_fish.lumpfish_count > 0:
                    reduction = twin.cleaner_fish.efficacy_pct / 100
                    new_sessile *= (1 - reduction * 0.5)
                    new_motile *= (1 - reduction * 0.8)
                    new_adult *= (1 - reduction)

                # Treatment effect
                if ln in interventions.get("treat_localities", []):
                    efficacy = {"mechanical": 0.88, "thermal": 0.94, "medicinal": 0.80}
                    eff = efficacy.get(interventions.get("treatment_type", "mechanical"), 0.88)
                    eff *= twin.treatment_resistance_factor
                    new_sessile *= (1 - eff * 0.7)
                    new_motile *= (1 - eff * 0.9)
                    new_adult *= (1 - eff)
                    twin.treatments_this_cycle += 1
                    # Resistance builds
                    twin.treatment_resistance_factor *= 0.97

                twin.lice = LiceState(
                    sessile=max(0, new_sessile),
                    motile=max(0, new_motile),
                    adult_female=max(0, new_adult),
                    total=max(0, new_sessile + new_motile + new_adult),
                )

                # ── Biomass growth ───────────────────────────────────
                if twin.cohort and ln not in interventions.get("harvest_localities", []):
                    # Specific growth rate (SGR) — temperature and lice dependent
                    sgr_base = 0.008  # ~0.8% per week at optimal
                    sgr_temp_adj = min(1.0, tf / 1.0)  # reduced in cold
                    sgr_lice_penalty = min(0.5, twin.lice.adult_female * 0.1)
                    sgr = sgr_base * sgr_temp_adj * (1 - sgr_lice_penalty)

                    twin.cohort.avg_weight_kg *= (1 + sgr)
                    # Mortality
                    mort = 0.001 + twin.lice.adult_female * 0.002
                    twin.cohort.current_count = int(twin.cohort.current_count * (1 - mort))

                    twin.estimated_biomass_tonnes = (
                        twin.cohort.current_count * twin.cohort.avg_weight_kg / 1000
                    )

                # Add cleaner fish
                extra = interventions.get("add_cleaner_fish", {}).get(ln, 0)
                if extra:
                    twin.cleaner_fish.lumpfish_count += extra
                    twin.cleaner_fish.efficacy_pct = min(
                        40, twin.cleaner_fish.efficacy_pct + extra * 0.01
                    )

        return state

    def get_summary(self) -> dict:
        """Return a summary of the live twin state."""
        if not self.localities:
            return {"status": "empty", "localities": 0}

        lice_vals = [t.lice.adult_female for t in self.localities.values()]
        above = sum(1 for v in lice_vals if v > 0.5)

        by_company = {}
        for t in self.localities.values():
            tk = t.ticker or "unmapped"
            if tk not in by_company:
                by_company[tk] = {"count": 0, "avg_lice": [], "biomass": 0}
            by_company[tk]["count"] += 1
            by_company[tk]["avg_lice"].append(t.lice.adult_female)
            by_company[tk]["biomass"] += t.estimated_biomass_tonnes

        company_summary = {}
        for tk, data in by_company.items():
            company_summary[tk] = {
                "localities": data["count"],
                "avg_lice": round(np.mean(data["avg_lice"]), 4),
                "max_lice": round(max(data["avg_lice"]), 4),
                "total_biomass_t": round(data["biomass"], 0),
            }

        return {
            "status": "live",
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "total_localities": len(self.localities),
            "national_avg_lice": round(float(np.mean(lice_vals)), 4),
            "above_threshold": above,
            "total_biomass_tonnes": round(sum(
                t.estimated_biomass_tonnes for t in self.localities.values()
            ), 0),
            "companies": company_summary,
            "snapshots_stored": len(self.history),
        }


# Singleton
digital_twin = DigitalTwinEngine()
