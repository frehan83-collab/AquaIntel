"""
IMR-Style Infestation Pressure Index
=====================================
Approximates the Institute of Marine Research (IMR) salmon lice
infestation pressure model.

The infestation pressure at a locality depends on:
  1. Adult female lice density at nearby farms (source strength)
  2. Sea temperature (drives larval development rate)
  3. Distance-weighted contributions from neighbouring farms
  4. Current/salinity-based dispersal (simplified proxy)

Reference: Stige et al. (2025) — joint count-data model for
salmon lice developmental stages.

Key biological parameters:
  - Egg production rate: ~30 eggs/pair/degree-day above 3°C
  - Nauplius to copepodid: ~40 degree-days above 3°C
  - Copepodid survival: ~10 days at 10°C (temperature-dependent)
  - Infectious window: copepodids viable for ~150 degree-days
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# ── Biological constants ─────────────────────────────────────────────
BASE_TEMP_THRESHOLD = 3.0       # °C — no development below this
DEGREE_DAYS_NAUPLIUS = 40.0     # degree-days for nauplius -> copepodid
EGG_PRODUCTION_RATE = 30.0      # eggs per pair per degree-day
COPEPODID_VIABILITY_DD = 150.0  # degree-days copepodid remains infectious
MAX_DISPERSAL_KM = 30.0         # max kernel distance for pressure calc
DISPERSAL_DECAY_RATE = 0.15     # exponential decay per km


@dataclass
class InfestationPressure:
    """Computed infestation pressure for a locality."""
    locality_no: int
    pressure_index: float = 0.0         # composite 0-100
    local_contribution: float = 0.0     # from own-farm lice
    external_contribution: float = 0.0  # from neighboring farms
    larval_production_rate: float = 0.0 # estimated larvae/day
    temperature_factor: float = 0.0     # development rate multiplier
    degree_days_weekly: float = 0.0     # accumulated degree-days this week
    risk_level: str = "low"             # low/moderate/high/critical


@dataclass
class LocalityLiceState:
    """Current lice state for pressure calculations."""
    locality_no: int
    lat: float
    lon: float
    avg_adult_female: float = 0.0
    avg_mobile: float = 0.0
    sea_temp: float = 8.0
    estimated_fish_count: int = 200_000  # default stocking density
    has_cleaner_fish: bool = False


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def compute_temperature_factor(temp_c: float) -> float:
    """
    Temperature-dependent development rate multiplier.
    Based on Stien et al. (2005) — Bělehrádek function for lice development.
    Returns 0 below 3°C, scales roughly linearly 3-18°C.
    """
    if temp_c <= BASE_TEMP_THRESHOLD:
        return 0.0
    effective = temp_c - BASE_TEMP_THRESHOLD
    # Normalized so factor=1.0 at 10°C
    return min(effective / 7.0, 2.5)


def compute_degree_days(temp_c: float, days: int = 7) -> float:
    """Accumulated degree-days above base threshold for a period."""
    effective = max(0.0, temp_c - BASE_TEMP_THRESHOLD)
    return effective * days


def estimate_larval_production(
    adult_female_lice: float,
    fish_count: int,
    temp_c: float,
) -> float:
    """
    Estimate daily larval production from a farm.

    Total larvae/day = (avg_lice * fish_count) * eggs_per_pair_per_dd * temp_factor
    """
    if temp_c <= BASE_TEMP_THRESHOLD or adult_female_lice <= 0:
        return 0.0

    total_gravid_females = adult_female_lice * fish_count
    temp_factor = compute_temperature_factor(temp_c)
    daily_dd = max(0, temp_c - BASE_TEMP_THRESHOLD)

    # Egg production scaled by degree-days
    daily_eggs = total_gravid_females * EGG_PRODUCTION_RATE * daily_dd / DEGREE_DAYS_NAUPLIUS

    return daily_eggs * temp_factor


def dispersal_weight(distance_km: float) -> float:
    """
    Distance-decay kernel for larval dispersal.
    Exponential decay with cutoff at MAX_DISPERSAL_KM.
    Based on simplified coastal current model.
    """
    if distance_km > MAX_DISPERSAL_KM or distance_km < 0:
        return 0.0
    return math.exp(-DISPERSAL_DECAY_RATE * distance_km)


def compute_pressure(
    target: LocalityLiceState,
    neighbours: list[LocalityLiceState],
) -> InfestationPressure:
    """
    Compute the full infestation pressure index for a target locality.

    Combines:
      1. Local lice load (own farm contribution)
      2. External pressure from neighboring farms (distance-weighted)
      3. Temperature-driven development dynamics
    """
    temp_factor = compute_temperature_factor(target.sea_temp)
    dd_weekly = compute_degree_days(target.sea_temp, days=7)

    # Local contribution
    local_larvae = estimate_larval_production(
        target.avg_adult_female, target.estimated_fish_count, target.sea_temp
    )
    # Cleaner fish reduce effective lice by ~20-40%
    if target.has_cleaner_fish:
        local_larvae *= 0.65

    local_pressure = local_larvae / 1e6  # normalize to millions

    # External contribution from neighbors
    external_pressure = 0.0
    for nb in neighbours:
        if nb.locality_no == target.locality_no:
            continue

        dist = haversine_km(target.lat, target.lon, nb.lat, nb.lon)
        weight = dispersal_weight(dist)
        if weight < 0.01:
            continue

        nb_larvae = estimate_larval_production(
            nb.avg_adult_female, nb.estimated_fish_count, nb.sea_temp
        )
        if nb.has_cleaner_fish:
            nb_larvae *= 0.65

        external_pressure += (nb_larvae / 1e6) * weight

    # Composite pressure index (0-100 scale)
    raw_pressure = local_pressure + external_pressure
    # Log-transform and scale — typical range 0-50 for Norwegian coast
    pressure_index = min(100, max(0, 15 * math.log1p(raw_pressure)))

    # Risk classification
    if pressure_index >= 60:
        risk = "critical"
    elif pressure_index >= 35:
        risk = "high"
    elif pressure_index >= 15:
        risk = "moderate"
    else:
        risk = "low"

    return InfestationPressure(
        locality_no=target.locality_no,
        pressure_index=pressure_index,
        local_contribution=local_pressure,
        external_contribution=external_pressure,
        larval_production_rate=local_larvae,
        temperature_factor=temp_factor,
        degree_days_weekly=dd_weekly,
        risk_level=risk,
    )


def compute_pressure_field(
    states: list[LocalityLiceState],
) -> list[InfestationPressure]:
    """Compute infestation pressure for all localities in a region."""
    log.info("pressure.compute_field", n_localities=len(states))

    results = []
    for target in states:
        if target.lat is None or target.lon is None:
            continue
        pressure = compute_pressure(target, states)
        results.append(pressure)

    # Summary stats
    if results:
        pressures = [r.pressure_index for r in results]
        log.info(
            "pressure.field_done",
            mean=round(np.mean(pressures), 1),
            max=round(max(pressures), 1),
            critical=sum(1 for r in results if r.risk_level == "critical"),
            high=sum(1 for r in results if r.risk_level == "high"),
        )

    return results
