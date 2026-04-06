"""
Demo Data Seed for Offline Expo Mode
======================================
Populates the database with realistic Norwegian salmon farming data
so the platform can run without external API dependencies.

Designed for Seafood Expo Global 2026 Barcelona (April 21-23).

Triggered by: FISHINTEL_DEMO_MODE=true environment variable at startup.

Idempotent: safe to run multiple times — checks for existing data before inserting.

Data includes:
  - 20 localities across PA 1-7 (Hitra, Froya, Austevoll, Senja, etc.)
  - 52 weeks of lice data with realistic seasonal pattern
  - Sea temperatures (4-16C seasonal curve)
  - 5 companies (Mowi, SalMar, Leroy, Grieg, Cermaq)
  - Treatment history (mechanical + freshwater + medicinal mix)
  - Price history (NOK 60-120 range with seasonal pattern)
"""
from __future__ import annotations

import datetime as dt
import math
import random

import structlog

log = structlog.get_logger(__name__)


# ── Demo companies ───────────────────────────────────────────────────
DEMO_COMPANIES = [
    {"ticker": "MOWI", "name": "Mowi ASA"},
    {"ticker": "SALM", "name": "SalMar ASA"},
    {"ticker": "LSG", "name": "Leroy Seafood Group ASA"},
    {"ticker": "GSF", "name": "Grieg Seafood ASA"},
    {"ticker": "CMQ", "name": "Cermaq Norway AS"},
]

# ── Demo localities — real Norwegian farm names and municipalities ────
DEMO_LOCALITIES = [
    # PA 1 — Rogaland → Hordaland
    {"locality_no": 10001, "name": "Borkanes",     "municipality": "Stord",       "county": "Vestland",   "lat": 59.76, "lon": 5.51, "pa": 1, "company": "MOWI"},
    {"locality_no": 10002, "name": "Varaldsoy",    "municipality": "Kvinnherad",  "county": "Vestland",   "lat": 59.89, "lon": 5.82, "pa": 1, "company": "LSG"},
    {"locality_no": 10003, "name": "Hjellestad",   "municipality": "Bergen",      "county": "Vestland",   "lat": 60.26, "lon": 5.21, "pa": 1, "company": "GSF"},
    # PA 2 — Austevoll / Sotra
    {"locality_no": 10004, "name": "Austevoll Nord","municipality": "Austevoll",   "county": "Vestland",   "lat": 60.09, "lon": 5.22, "pa": 2, "company": "LSG"},
    {"locality_no": 10005, "name": "Austevoll Sor", "municipality": "Austevoll",   "county": "Vestland",   "lat": 60.05, "lon": 5.19, "pa": 2, "company": "LSG"},
    {"locality_no": 10006, "name": "Sotra Vest",   "municipality": "Oygarden",    "county": "Vestland",   "lat": 60.40, "lon": 4.90, "pa": 2, "company": "MOWI"},
    # PA 3 — Sunnmoere → Nordmoere
    {"locality_no": 10007, "name": "Midsund",      "municipality": "Molde",       "county": "More og Romsdal", "lat": 62.67, "lon": 6.65, "pa": 3, "company": "SALM"},
    {"locality_no": 10008, "name": "Aukra",         "municipality": "Aukra",       "county": "More og Romsdal", "lat": 62.87, "lon": 6.58, "pa": 3, "company": "CMQ"},
    # PA 4 — Trondelag
    {"locality_no": 10009, "name": "Hitra Sor",     "municipality": "Hitra",       "county": "Trondelag",  "lat": 63.54, "lon": 8.74, "pa": 4, "company": "SALM"},
    {"locality_no": 10010, "name": "Hitra Nord",    "municipality": "Hitra",       "county": "Trondelag",  "lat": 63.62, "lon": 8.82, "pa": 4, "company": "SALM"},
    {"locality_no": 10011, "name": "Froya Vest",    "municipality": "Froya",       "county": "Trondelag",  "lat": 63.72, "lon": 8.55, "pa": 4, "company": "MOWI"},
    {"locality_no": 10012, "name": "Froya Ost",     "municipality": "Froya",       "county": "Trondelag",  "lat": 63.70, "lon": 8.70, "pa": 4, "company": "SALM"},
    # PA 5 — Helgeland
    {"locality_no": 10013, "name": "Vega",          "municipality": "Vega",        "county": "Nordland",   "lat": 65.66, "lon": 11.90, "pa": 5, "company": "MOWI"},
    {"locality_no": 10014, "name": "Bronnoysund",   "municipality": "Bronnoy",     "county": "Nordland",   "lat": 65.47, "lon": 12.21, "pa": 5, "company": "CMQ"},
    {"locality_no": 10015, "name": "Sandnessjoen",  "municipality": "Alstahaug",   "county": "Nordland",   "lat": 66.02, "lon": 12.63, "pa": 5, "company": "GSF"},
    # PA 6 — Salten → Lofoten
    {"locality_no": 10016, "name": "Bodo Havn",     "municipality": "Bodo",        "county": "Nordland",   "lat": 67.28, "lon": 14.40, "pa": 6, "company": "CMQ"},
    {"locality_no": 10017, "name": "Lofoten Sor",   "municipality": "Vestvagoy",   "county": "Nordland",   "lat": 68.18, "lon": 13.76, "pa": 6, "company": "GSF"},
    # PA 7 — Troms
    {"locality_no": 10018, "name": "Senja Nord",    "municipality": "Senja",       "county": "Troms",      "lat": 69.14, "lon": 17.03, "pa": 7, "company": "SALM"},
    {"locality_no": 10019, "name": "Senja Sor",     "municipality": "Senja",       "county": "Troms",      "lat": 69.00, "lon": 16.80, "pa": 7, "company": "MOWI"},
    {"locality_no": 10020, "name": "Kvaloya",       "municipality": "Tromso",      "county": "Troms",      "lat": 69.70, "lon": 18.88, "pa": 7, "company": "CMQ"},
    # ── Offshore farms (Session 28) ────────────────────────────────
    # Reference: SalMar Ocean Farm 1 (Frohavet, operational 2017), Ocean Farm 2 (planned)
    {"locality_no": 10021, "name": "Ocean Farm 1",  "municipality": "Froya",       "county": "Trondelag",  "lat": 63.80, "lon": 8.40, "pa": 4, "company": "SALM",
     "farm_type": "offshore", "max_depth_m": 64.0, "current_speed_avg_ms": 0.8, "wave_exposure_class": "ocean",
     "cage_volume_m3": 250000, "distance_to_shore_km": 8.0},
    {"locality_no": 10022, "name": "Ocean Farm 2",  "municipality": "Froya",       "county": "Trondelag",  "lat": 63.85, "lon": 8.35, "pa": 4, "company": "SALM",
     "farm_type": "offshore", "max_depth_m": 72.0, "current_speed_avg_ms": 1.0, "wave_exposure_class": "ocean",
     "cage_volume_m3": 385000, "distance_to_shore_km": 10.0},
]


def _seasonal_lice(week: int, pa: int, rng: random.Random) -> tuple[float, float, float]:
    """
    Generate realistic seasonal lice counts.
    Low in winter (weeks 1-12, 45-52), peak in late summer (weeks 28-38).
    Northern PAs (higher numbers) have somewhat lower lice.
    """
    # Base seasonal curve: sinusoidal with peak around week 32
    season_factor = 0.5 + 0.5 * math.sin(2 * math.pi * (week - 12) / 52)
    # Northern PAs have ~20% lower lice
    latitude_factor = 1.0 - 0.03 * max(0, pa - 3)

    base = season_factor * latitude_factor

    # Adult female lice (regulatory metric, threshold 0.5)
    adult_female = round(base * rng.uniform(0.05, 0.65), 2)
    # Mobile lice = adult female * 1.5-3x
    mobile = round(adult_female * rng.uniform(1.5, 3.0), 2)
    # Stationary lice = mobile * 0.3-0.8x
    stationary = round(mobile * rng.uniform(0.3, 0.8), 2)

    return adult_female, mobile, stationary


def _seasonal_temp(week: int, pa: int, rng: random.Random) -> float:
    """
    Realistic Norwegian sea temperature: 4-16C seasonal curve.
    Southern PAs warmer, northern PAs cooler.
    """
    # Base: sinusoidal with peak around week 32 (early August)
    base = 10.0 + 6.0 * math.sin(2 * math.pi * (week - 10) / 52)
    # Northern PAs ~1.5C cooler per PA above 3
    latitude_adj = -0.5 * max(0, pa - 3)
    noise = rng.uniform(-0.5, 0.5)
    temp = base + latitude_adj + noise
    return round(max(3.5, min(17.0, temp)), 1)


def _seasonal_price(week: int, rng: random.Random) -> float:
    """
    Realistic salmon spot price NOK/kg: 60-120 range.
    Prices higher in spring/summer (strong demand), lower in autumn after harvest peak.
    """
    # Seasonal pattern: peak around weeks 14-24 (spring), dip around weeks 36-44 (autumn)
    seasonal = 90.0 + 20.0 * math.sin(2 * math.pi * (week - 4) / 52)
    noise = rng.uniform(-5.0, 5.0)
    price = seasonal + noise
    return round(max(58.0, min(125.0, price)), 2)


def seed_demo_data() -> dict:
    """
    Populate the database with realistic Norwegian salmon farming demo data.

    Idempotent: checks for existing demo localities before inserting.
    Returns a summary dict of inserted record counts.
    """
    from core.models import (
        Session, Locality, LiceRecord, CompanyExposure,
        SSBWeeklyPrice, TreatmentOutcome,
    )

    rng = random.Random(42)  # Deterministic for reproducibility
    session = Session()

    summary = {
        "localities": 0,
        "lice_records": 0,
        "company_exposures": 0,
        "price_records": 0,
        "treatment_outcomes": 0,
    }

    try:
        # ── Check idempotency ────────────────────────────────────────
        existing = session.query(Locality).filter(
            Locality.locality_no == DEMO_LOCALITIES[0]["locality_no"]
        ).first()
        if existing:
            log.info("demo_seed.already_seeded", first_locality=existing.name)
            return summary

        log.info("demo_seed.starting", localities=len(DEMO_LOCALITIES), companies=len(DEMO_COMPANIES))

        # ── 1. Localities ────────────────────────────────────────────
        for loc in DEMO_LOCALITIES:
            company = next(c for c in DEMO_COMPANIES if c["ticker"] == loc["company"])
            locality_kwargs = dict(
                locality_no=loc["locality_no"],
                name=loc["name"],
                municipality=loc["municipality"],
                county=loc["county"],
                latitude=loc["lat"],
                longitude=loc["lon"],
                owner_company=company["ticker"],
                production_area=loc["pa"],
                pa_color=rng.choice(["green", "green", "green", "yellow"]),
                updated_at=dt.datetime.now(dt.UTC),
                # Offshore fields (default to inshore if not specified)
                farm_type=loc.get("farm_type", "inshore"),
                max_depth_m=loc.get("max_depth_m"),
                current_speed_avg_ms=loc.get("current_speed_avg_ms"),
                wave_exposure_class=loc.get("wave_exposure_class"),
                cage_volume_m3=loc.get("cage_volume_m3"),
                distance_to_shore_km=loc.get("distance_to_shore_km"),
            )
            session.add(Locality(**locality_kwargs))
            summary["localities"] += 1

        # ── 2. Company exposures ─────────────────────────────────────
        for loc in DEMO_LOCALITIES:
            session.add(CompanyExposure(
                ticker=loc["company"],
                company_name=next(c["name"] for c in DEMO_COMPANIES if c["ticker"] == loc["company"]),
                locality_no=loc["locality_no"],
                estimated_biomass_tonnes=round(rng.uniform(800, 4500), 0),
                weight=round(rng.uniform(0.5, 2.0), 2),
            ))
            summary["company_exposures"] += 1

        # ── 3. Lice records — 52 weeks × 20 localities ──────────────
        year = 2025
        for loc in DEMO_LOCALITIES:
            for week in range(1, 53):
                adult_f, mobile, stationary = _seasonal_lice(week, loc["pa"], rng)
                temp = _seasonal_temp(week, loc["pa"], rng)
                session.add(LiceRecord(
                    locality_no=loc["locality_no"],
                    year=year,
                    week=week,
                    avg_adult_female_lice=adult_f,
                    avg_mobile_lice=mobile,
                    avg_stationary_lice=stationary,
                    has_cleaner_fish=rng.random() > 0.4,
                    sea_temp_c=temp,
                    fetched_at=dt.datetime.now(dt.UTC),
                ))
                summary["lice_records"] += 1

        # ── 4. Price history — 52 weeks ──────────────────────────────
        for week in range(1, 53):
            price = _seasonal_price(week, rng)
            volume = round(rng.uniform(12000, 22000), 0)
            session.add(SSBWeeklyPrice(
                year=year,
                week=week,
                price_nok_kg=price,
                volume_tonnes=volume,
                source="demo_seed",
                fetched_at=dt.datetime.now(dt.UTC),
            ))
            summary["price_records"] += 1

        # ── 5. Treatment outcomes ────────────────────────────────────
        METHODS = ["mechanical", "freshwater", "medicinal", "thermal", "biological"]
        METHOD_EFFICACY = {
            "mechanical":  (75, 95),
            "freshwater":  (50, 80),
            "medicinal":   (55, 85),
            "thermal":     (80, 95),
            "biological":  (30, 60),
        }
        METHOD_COST = {
            "mechanical":  (15, 30),
            "freshwater":  (8, 18),
            "medicinal":   (20, 40),
            "thermal":     (18, 30),
            "biological":  (5, 12),
        }

        for _ in range(60):
            method = rng.choice(METHODS)
            loc = rng.choice(DEMO_LOCALITIES)
            month = rng.randint(1, 12)
            day = rng.randint(1, 28)
            eff_lo, eff_hi = METHOD_EFFICACY[method]
            cost_lo, cost_hi = METHOD_COST[method]

            pre_lice = round(rng.uniform(0.3, 2.0), 2)
            reduction = rng.uniform(eff_lo, eff_hi) / 100.0
            post_lice = round(max(0.0, pre_lice * (1 - reduction)), 3)

            session.add(TreatmentOutcome(
                locality_no=loc["locality_no"],
                treatment_date=dt.datetime(year, month, day),
                method=method,
                pre_lice_count=pre_lice,
                post_lice_count=post_lice,
                mortality_observed=rng.randint(0, 50),
                cost_nok=round(rng.uniform(cost_lo, cost_hi) * 1000, 0),
                notes=f"Demo seed — {method} treatment at {loc['name']}",
                reported_at=dt.datetime.now(dt.UTC),
            ))
            summary["treatment_outcomes"] += 1

        session.commit()
        log.info("demo_seed.complete", **summary)
        return summary

    except Exception as exc:
        session.rollback()
        log.error("demo_seed.failed", error=str(exc))
        raise
    finally:
        session.close()
