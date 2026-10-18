"""
Smolt-to-Harvest Supply Forecaster
====================================
Projects salmon supply 12-18 months ahead by tracking cohort lifecycles
from smolt release to harvest weight.

This is the leading indicator that traders and investors need:
  - Smolt releases today → harvest volumes 14-18 months later
  - Temperature affects growth rate → shifts harvest timing
  - Disease/lice events → mortality losses and delayed harvests

Key constants (Mowi Industry Handbook 2025):
  - Yield per smolt: 3.28 kg GWT
  - Survival rate at sea: 85%
  - Typical grow-out: 14-18 months (temperature dependent)
  - Norwegian annual smolt releases: ~400M
  - Norwegian annual production: ~1.7M tonnes HOG
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────
YIELD_PER_SMOLT_KG = 3.28       # kg GWT per smolt (Mowi Handbook 2025)
SURVIVAL_RATE = 0.85             # 85% sea-phase survival
SMOLT_WEIGHT_KG = 0.10          # 100g at sea transfer
HARVEST_WEIGHT_KG = 5.0         # Target harvest weight
OPTIMAL_TEMP_C = 12.0           # Optimal growth temperature
THERMAL_TOLERANCE = 4.0         # Gaussian width
MAX_SGR_PCT = 1.2               # Max specific growth rate %/day
MORTALITY_RATE_DAILY = 0.00015  # Base daily mortality

# Norwegian annual smolt releases ~400M, production ~1.7M tonnes
ANNUAL_SMOLT_RELEASES = 400_000_000
ANNUAL_PRODUCTION_TONNES = 1_700_000

#: WS-36: the model's forward 12 months are checked against the national production
#: reference above. Outside this band the payload says the projection is uncalibrated
#: instead of presenting a model output as a supply forecast — on 2026-10-18 the model
#: projects roughly a third of the reference per year while SSB's weekly export volumes
#: imply ~120 000 t/month nationally, so the level is not yet usable as a forecast.
SMOLT_VALIDATION_TOLERANCE_PCT = 30.0

#: What the reference is, stated where the number lives.
SMOLT_REFERENCE_SOURCE = (
    "Norwegian annual production reference in this module (1.7 M t GWT) — see "
    "Fiskeridirektoratet aquaculture statistics; the 12-month model total is compared "
    "against it"
)

# Seasonal smolt release pattern (fraction of annual by month)
# 70% of releases happen April-June
SMOLT_RELEASE_PATTERN = {
    1: 0.02, 2: 0.03, 3: 0.05, 4: 0.18, 5: 0.28, 6: 0.24,
    7: 0.05, 8: 0.03, 9: 0.04, 10: 0.04, 11: 0.02, 12: 0.02,
}

# Average monthly SST by Norwegian coast (simplified, °C)
MONTHLY_SST = {
    1: 5.0, 2: 4.5, 3: 5.0, 4: 6.5, 5: 8.5, 6: 10.5,
    7: 12.5, 8: 13.0, 9: 12.0, 10: 10.0, 11: 8.0, 12: 6.0,
}

# Monthly demand proxy (relative, from SSB export seasonality)
DEMAND_SEASONALITY = {
    1: 0.85, 2: 0.80, 3: 0.90, 4: 0.95, 5: 1.00, 6: 1.05,
    7: 1.00, 8: 1.10, 9: 1.20, 10: 1.15, 11: 1.00, 12: 0.90,
}


@dataclass
class SmoltCohort:
    """A batch of smolts from release to harvest."""
    intake_month: int
    intake_year: int
    region: str = "Norway"
    n_smolt: int = 0
    avg_weight_kg: float = SMOLT_WEIGHT_KG
    months_at_sea: int = 0
    projected_harvest_month: int = 0
    projected_harvest_year: int = 0
    projected_harvest_tonnes: float = 0.0
    stage: str = "smolt"  # smolt, grower, pre-harvest, harvestable


@dataclass
class SupplyPoint:
    """One month in the supply pipeline."""
    year: int
    month: int
    projected_harvest_tonnes: float = 0.0
    lo80: float = 0.0
    hi80: float = 0.0
    demand_tonnes: float = 0.0
    balance: float = 0.0  # supply - demand
    n_cohorts_harvesting: int = 0


def _get_typical_utilization() -> float:
    """Import TYPICAL_UTILIZATION lazily to avoid circular imports."""
    try:
        from core.market.biomass_predictor import TYPICAL_UTILIZATION
        return TYPICAL_UTILIZATION
    except ImportError:
        return 0.935  # fallback


class SmoltModel:
    """
    Projects salmon supply 12-18 months ahead using cohort lifecycle modeling.
    """

    def __init__(self) -> None:
        self._cohorts: list[SmoltCohort] = []
        self._pipeline: list[dict] = []
        self._pipeline_time: dt.datetime | None = None
        self._pipeline_horizon: int | None = None

    def estimate_smolt_releases(self, year: int, month: int) -> int:
        """Estimate smolt releases for a given month based on seasonal pattern."""
        fraction = SMOLT_RELEASE_PATTERN.get(month, 0.04)
        # Allow slight year-over-year growth (~3%)
        growth = 1.0 + 0.03 * (year - 2024)
        return int(ANNUAL_SMOLT_RELEASES * fraction * growth)

    def _growth_rate(self, temp_c: float, weight_kg: float) -> float:
        """Temperature-dependent specific growth rate (fraction/day)."""
        temp_response = math.exp(-((temp_c - OPTIMAL_TEMP_C) ** 2) / (2 * THERMAL_TOLERANCE ** 2))
        # SGR decreases with fish size (allometric scaling)
        size_factor = (SMOLT_WEIGHT_KG / max(weight_kg, 0.01)) ** 0.3
        sgr = (MAX_SGR_PCT / 100.0) * temp_response * min(size_factor, 1.0)
        return sgr

    def project_harvest_timing(self, cohort: SmoltCohort) -> SmoltCohort:
        """Project when a cohort reaches harvest weight using temperature-dependent growth."""
        weight = cohort.avg_weight_kg
        n_fish = int(cohort.n_smolt * SURVIVAL_RATE)
        month = cohort.intake_month
        year = cohort.intake_year
        months_at_sea = 0

        while weight < HARVEST_WEIGHT_KG and months_at_sea < 24:
            temp = MONTHLY_SST.get(month, 8.0)
            sgr = self._growth_rate(temp, weight)
            # Monthly growth: compound daily growth over 30 days
            weight *= (1.0 + sgr) ** 30
            # Monthly mortality
            n_fish = int(n_fish * (1.0 - MORTALITY_RATE_DAILY) ** 30)
            months_at_sea += 1
            month = month % 12 + 1
            if month == 1:
                year += 1

        cohort.avg_weight_kg = weight
        cohort.months_at_sea = months_at_sea
        cohort.projected_harvest_month = month
        cohort.projected_harvest_year = year
        cohort.projected_harvest_tonnes = (n_fish * weight) / 1000.0
        cohort.stage = (
            "harvestable" if weight >= HARVEST_WEIGHT_KG else
            "pre-harvest" if weight >= 3.5 else
            "grower" if weight >= 1.0 else
            "smolt"
        )
        return cohort

    def get_supply_pipeline(self, horizon_months: int = 18) -> list[dict]:
        """
        Build month-by-month supply forecast for the next horizon_months.
        Returns list of SupplyPoint dicts with confidence intervals.
        """
        now = dt.datetime.now(dt.UTC)
        if (
            self._pipeline
            and self._pipeline_time
            and (now - self._pipeline_time) < dt.timedelta(minutes=30)
            and self._pipeline_horizon == horizon_months
        ):
            return self._pipeline
        pipeline: list[dict] = []

        # Generate cohorts for the last 24 months (they're growing now)
        # plus current month
        cohorts: list[SmoltCohort] = []
        for months_ago in range(24, -1, -1):
            m = now.month - months_ago
            y = now.year
            while m < 1:
                m += 12
                y -= 1
            while m > 12:
                m -= 12
                y += 1
            n_smolt = self.estimate_smolt_releases(y, m)
            c = SmoltCohort(
                intake_month=m,
                intake_year=y,
                n_smolt=n_smolt,
                avg_weight_kg=SMOLT_WEIGHT_KG,
            )
            self.project_harvest_timing(c)
            cohorts.append(c)

        self._cohorts = cohorts

        # Aggregate projected harvest by month
        harvest_by_month: dict[tuple[int, int], float] = {}
        cohort_count_by_month: dict[tuple[int, int], int] = {}

        for c in cohorts:
            key = (c.projected_harvest_year, c.projected_harvest_month)
            harvest_by_month[key] = harvest_by_month.get(key, 0) + c.projected_harvest_tonnes
            cohort_count_by_month[key] = cohort_count_by_month.get(key, 0) + 1

        # Build pipeline for next horizon_months
        for offset in range(horizon_months):
            m = now.month + offset
            y = now.year
            while m > 12:
                m -= 12
                y += 1

            harvest = harvest_by_month.get((y, m), 0)
            # Add confidence interval (±15% for near-term, ±30% for far-term)
            uncertainty = 0.15 + 0.15 * (offset / horizon_months)
            lo80 = harvest * (1 - uncertainty)
            hi80 = harvest * (1 + uncertainty)

            # Demand estimate
            monthly_demand = (ANNUAL_PRODUCTION_TONNES / 12) * DEMAND_SEASONALITY.get(m, 1.0)

            pipeline.append({
                "year": y,
                "month": m,
                "month_label": f"{y}-{m:02d}",
                "projected_harvest_tonnes": round(harvest, 0),
                "lo80": round(lo80, 0),
                "hi80": round(hi80, 0),
                "demand_tonnes": round(monthly_demand, 0),
                "balance": round(harvest - monthly_demand, 0),
                "n_cohorts": cohort_count_by_month.get((y, m), 0),
            })

        self._pipeline = pipeline
        self._pipeline_time = now
        self._pipeline_horizon = horizon_months
        log.info("smolt.pipeline_built", months=len(pipeline), total_harvest=sum(p["projected_harvest_tonnes"] for p in pipeline))
        return pipeline

    def get_cohort_timeline(self) -> list[dict]:
        """Return all active cohorts with their growth stage."""
        if not self._cohorts:
            self.get_supply_pipeline()
        return [
            {
                "intake": f"{c.intake_year}-{c.intake_month:02d}",
                "region": c.region,
                "n_smolt_millions": round(c.n_smolt / 1_000_000, 1),
                "current_weight_kg": round(c.avg_weight_kg, 2),
                "months_at_sea": c.months_at_sea,
                "stage": c.stage,
                "harvest_month": f"{c.projected_harvest_year}-{c.projected_harvest_month:02d}",
                "harvest_tonnes": round(c.projected_harvest_tonnes, 0),
            }
            for c in self._cohorts
        ]

    def get_demand_balance(self) -> dict:
        """Return supply-demand balance summary."""
        if not self._pipeline:
            self.get_supply_pipeline()

        total_supply = sum(p["projected_harvest_tonnes"] for p in self._pipeline[:6])
        total_demand = sum(p["demand_tonnes"] for p in self._pipeline[:6])
        balance = total_supply - total_demand

        return {
            "horizon_months": 6,
            "total_supply_tonnes": round(total_supply, 0),
            "total_demand_tonnes": round(total_demand, 0),
            "balance_tonnes": round(balance, 0),
            "balance_pct": round((balance / max(total_demand, 1)) * 100, 1),
            "signal": "oversupply" if balance > 10000 else "undersupply" if balance < -10000 else "balanced",
            "price_pressure": "bearish" if balance > 20000 else "bullish" if balance < -20000 else "neutral",
        }

    def validation(self) -> dict:
        """Compare the model's forward 12 months with the national production reference.

        WS-36. The pipeline is a model (smolt releases x survival x yield x growth), not
        a measurement. On 2026-10-18 it projects roughly a third of the 1.7 M t annual
        reference, while SSB's weekly export volumes imply about 120 000 t/month
        nationally — so the level is uncalibrated and a reader must be told before using
        it as a supply forecast. The ratio is published either way.
        """
        pipeline = self.get_supply_pipeline(12)
        model_12m = sum(p["projected_harvest_tonnes"] for p in pipeline)
        ratio = (model_12m / ANNUAL_PRODUCTION_TONNES) if ANNUAL_PRODUCTION_TONNES else None
        deviation_pct = round((ratio - 1.0) * 100, 1) if ratio is not None else None
        within = (
            None if deviation_pct is None
            else abs(deviation_pct) <= SMOLT_VALIDATION_TOLERANCE_PCT
        )
        return {
            "model_12m_tonnes": round(model_12m, 0),
            "reference_annual_tonnes": ANNUAL_PRODUCTION_TONNES,
            "reference_source": SMOLT_REFERENCE_SOURCE,
            "ratio_to_reference": round(ratio, 2) if ratio is not None else None,
            "deviation_pct": deviation_pct,
            "within_tolerance": within,
            "tolerance_pct": SMOLT_VALIDATION_TOLERANCE_PCT,
            "note": (
                "the 12-month pipeline is a model output; "
                + (
                    "it sits inside the reference band, so it can be read as a forecast "
                    "with the usual model caveats"
                    if within else
                    "it is far from the national production reference, so treat the LEVEL "
                    "as uncalibrated and use only its direction and seasonality (WS-36)"
                )
            ),
            "measurement": "model projection (smolt releases x survival x yield), not reported supply",
        }

    def get_summary(self) -> dict:
        """Get summary stats for KPIs."""
        pipeline = self.get_supply_pipeline(18)
        cohorts = self.get_cohort_timeline()
        balance = self.get_demand_balance()

        now = dt.datetime.now(dt.UTC)
        q1_start = now.month
        q1_end = min(q1_start + 2, 12)
        next_quarter = [p for p in pipeline if q1_start <= p["month"] <= q1_end and p["year"] == now.year]
        quarter_harvest = sum(p["projected_harvest_tonnes"] for p in next_quarter)

        smolt_ytd = sum(
            c.n_smolt for c in self._cohorts
            if c.intake_year == now.year and c.intake_month <= now.month
        )

        return {
            "next_quarter_harvest_tonnes": round(quarter_harvest, 0),
            "smolt_releases_ytd_millions": round(smolt_ytd / 1_000_000, 1),
            "supply_growth_yoy_pct": 3.0,  # Approximate, from smolt growth trend
            "mab_utilization_pct": round(_get_typical_utilization() * 100, 1),
            "validation": self.validation(),
            "price_pressure": balance["price_pressure"],
            "pipeline": pipeline,
            "cohorts": cohorts,
            "demand_balance": balance,
        }


# Singleton
smolt_model = SmoltModel()
