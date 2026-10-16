"""
Fiskeridirektoratet Biomass Tracker
=====================================
Fetches standing biomass data from the Norwegian Directorate of Fisheries.
Source: https://www.fiskeridir.no/Akvakultur/Tall-og-analyse/Apne-data

Standing biomass is THE key supply indicator — when biomass is below
historical norms, prices rise. When above, prices fall.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import httpx
import structlog

from core.market.data_provenance import DataProvenance

log = structlog.get_logger(__name__)


@dataclass
class BiomassRecord:
    year: int
    month: int
    production_area: int
    standing_biomass_tonnes: float
    harvest_tonnes: float = 0.0
    mortality_tonnes: float = 0.0
    smolt_released: int = 0


@dataclass
class BiomassSupplyModel:
    """National supply model derived from biomass data."""
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))

    # Current state
    total_standing_biomass_tonnes: float = 0.0
    biomass_vs_historical_pct: float = 100.0  # 100 = normal
    estimated_harvestable_tonnes: float = 0.0

    # Per-PA breakdown
    pa_biomass: dict[int, float] = field(default_factory=dict)

    # Forward estimates
    estimated_weekly_harvest: float = 0.0
    days_of_supply: float = 0.0
    supply_outlook: str = "normal"  # tight / normal / abundant

    # Historical comparison
    yoy_change_pct: float = 0.0


# Historical average monthly biomass (approximate, tonnes × 1000)
# Based on typical standing biomass pattern 2020-2025
HISTORICAL_BIOMASS = {
    1: 780, 2: 810, 3: 850, 4: 890, 5: 920, 6: 940,
    7: 930, 8: 910, 9: 880, 10: 840, 11: 800, 12: 770,
}

# Average weekly harvest by month (tonnes)
HISTORICAL_HARVEST_WEEKLY = {
    1: 25000, 2: 23000, 3: 26000, 4: 29000, 5: 32000, 6: 35000,
    7: 33000, 8: 37000, 9: 40000, 10: 38000, 11: 34000, 12: 28000,
}


class BiomassTracker:
    """Tracks Norwegian salmon standing biomass and supply dynamics."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self.records: list[BiomassRecord] = []
        self.last_source: str = "unset"
        self.last_is_live: bool = False

    async def fetch_biomass_data(self) -> list[BiomassRecord]:
        """Fetch standing biomass, preferring REAL Fiskeridirektoratet data.

        The ArcGIS Biomass Status client (core.market.fiskeridir_biomass) is the
        authoritative source; only when it yields no usable records do we fall
        back to the historical-pattern estimate. Which path ran is recorded on
        `last_source` / `last_is_live` so callers can tag provenance honestly
        (AGENTS.md rules 1 and 3) instead of presenting placeholders as reported
        biomass (this function previously *always* returned the estimate while
        the docstring claimed it fetched from Fiskeridirektoratet).
        """
        try:
            from core.market.fiskeridir_biomass import fiskeridir_biomass

            real = await fiskeridir_biomass.fetch_all()
            usable = [r for r in real if not r.is_synthetic and r.standing_biomass_tonnes > 0]
            if usable:
                self.records = [
                    BiomassRecord(
                        year=r.report_year,
                        month=r.report_month,
                        production_area=r.production_area,
                        standing_biomass_tonnes=r.standing_biomass_tonnes,
                    )
                    for r in usable
                ]
                self.last_source = "Fiskeridirektoratet Biomass Status (ArcGIS)"
                self.last_is_live = True
                log.info("biomass.real_fetch_ok", n_localities=len(self.records))
                return self.records
            log.warning("biomass.real_fetch_empty")
        except Exception as exc:  # noqa: BLE001 - fall back honestly, never raise
            log.warning("biomass.real_fetch_failed", error=str(exc)[:120])

        self.records = self._generate_current_estimate()
        self.last_source = "historical-pattern estimate"
        self.last_is_live = False
        return self.records

    def provenance(self) -> DataProvenance:
        """Honest provenance for the supply model (rule 1/3).

        Even with a live biomass base, the supply metrics themselves are model
        estimates (harvestable = 60% of biomass; weekly harvest and the seasonal
        norm come from hardcoded profiles), so the result is never `live`.
        """
        if self.last_is_live:
            return DataProvenance.degraded(
                self.last_source,
                reason=(
                    "base standing biomass is live; harvestable, weekly-harvest, "
                    "days-of-supply, outlook and yoy are model estimates derived from a "
                    "hardcoded seasonal profile, not reported figures"
                ),
                confidence=0.6,
            )
        return DataProvenance.simulated(
            "Fiskeridirektoratet feed unavailable — figures are a synthetic "
            "historical-pattern placeholder, not reported biomass"
        )

    def _generate_current_estimate(self) -> list[BiomassRecord]:
        """Generate current biomass estimate from historical patterns."""
        now = dt.datetime.now(dt.UTC)
        records = []

        for pa in range(1, 14):
            # PA share of total biomass (approximate)
            pa_shares = {
                1: 0.04, 2: 0.06, 3: 0.12, 4: 0.13, 5: 0.11, 6: 0.10,
                7: 0.09, 8: 0.08, 9: 0.07, 10: 0.06, 11: 0.06, 12: 0.05, 13: 0.03,
            }
            share = pa_shares.get(pa, 0.05)
            total = HISTORICAL_BIOMASS.get(now.month, 850) * 1000

            records.append(BiomassRecord(
                year=now.year,
                month=now.month,
                production_area=pa,
                standing_biomass_tonnes=total * share,
                harvest_tonnes=HISTORICAL_HARVEST_WEEKLY.get(now.month, 30000) * share * 4,
            ))

        self.records = records
        return records

    def compute_supply_model(
        self,
        lice_disruption_pct: float = 0.0,
    ) -> BiomassSupplyModel:
        """
        Compute the national supply model.

        lice_disruption_pct: estimated supply reduction from lice events (0-100)
        """
        if not self.records:
            self._generate_current_estimate()

        now = dt.datetime.now(dt.UTC)
        month = now.month

        total_biomass = sum(r.standing_biomass_tonnes for r in self.records)
        historical_norm = HISTORICAL_BIOMASS.get(month, 850) * 1000
        biomass_vs_hist = (total_biomass / historical_norm * 100) if historical_norm > 0 else 100

        # Harvestable = fish above ~4kg (approximately 60% of biomass)
        harvestable = total_biomass * 0.6

        # Weekly harvest rate
        weekly_harvest = HISTORICAL_HARVEST_WEEKLY.get(month, 30000)
        # Adjust for lice disruption
        effective_harvest = weekly_harvest * (1 - lice_disruption_pct / 100)

        # Days of supply
        daily_harvest = effective_harvest / 7
        days_of_supply = harvestable / daily_harvest if daily_harvest > 0 else 999

        # Supply outlook
        if biomass_vs_hist < 90 or days_of_supply < 120:
            outlook = "tight"
        elif biomass_vs_hist > 110 or days_of_supply > 200:
            outlook = "abundant"
        else:
            outlook = "normal"

        # YoY change (simplified)
        prev_month_hist = HISTORICAL_BIOMASS.get(max(1, month - 1), 850) * 1000
        yoy = (total_biomass - prev_month_hist) / prev_month_hist * 100

        pa_biomass = {r.production_area: r.standing_biomass_tonnes for r in self.records}

        return BiomassSupplyModel(
            total_standing_biomass_tonnes=round(total_biomass, 0),
            biomass_vs_historical_pct=round(biomass_vs_hist, 1),
            estimated_harvestable_tonnes=round(harvestable, 0),
            pa_biomass=pa_biomass,
            estimated_weekly_harvest=round(effective_harvest, 0),
            days_of_supply=round(days_of_supply, 0),
            supply_outlook=outlook,
            yoy_change_pct=round(yoy, 1),
        )

    async def close(self) -> None:
        await self._client.aclose()


biomass_tracker = BiomassTracker()
