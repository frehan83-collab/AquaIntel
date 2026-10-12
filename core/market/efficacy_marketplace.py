"""
Efficacy Marketplace Engine
============================
Crowdsourced treatment efficacy database with anonymization and
multi-dimensional aggregation. Transforms farmer-reported outcomes
into an industry-wide efficacy knowledge base.

Privacy: Never exposes individual locality outcomes. All data is
anonymized to Production Area level with a minimum of 3 data points
per aggregation cell.

Singleton: efficacy_marketplace = EfficacyMarketplace()
"""
from __future__ import annotations

import datetime as dt
import random
from typing import Optional

import structlog
from sqlalchemy import text

from core.market.data_provenance import DataProvenance

log = structlog.get_logger()

# Minimum data points per aggregation cell for privacy
MIN_CELL_SIZE = 3

# Season mapping
MONTH_TO_SEASON = {
    1: "winter", 2: "winter", 3: "spring", 4: "spring",
    5: "spring", 6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn", 12: "winter",
}

# Temperature buckets
TEMP_BUCKETS = [
    (0, 6, "cold (0-6C)"),
    (6, 10, "cool (6-10C)"),
    (10, 14, "moderate (10-14C)"),
    (14, 20, "warm (14-20C)"),
]


def _temp_bucket(temp: Optional[float]) -> str:
    """Classify temperature into bucket."""
    if temp is None:
        return "unknown"
    for lo, hi, label in TEMP_BUCKETS:
        if lo <= temp < hi:
            return label
    return "extreme (20C+)" if temp >= 20 else "cold (0-6C)"


def _season_from_month(month: int) -> str:
    return MONTH_TO_SEASON.get(month, "unknown")


class EfficacyMarketplace:
    """Crowdsourced treatment efficacy with anonymization and multi-dimensional aggregation."""

    async def aggregate_by_dimensions(
        self,
        method: Optional[str] = None,
        production_area: Optional[int] = None,
        temp_range: Optional[tuple] = None,
        season: Optional[str] = None,
    ) -> dict:
        """Multi-dimensional efficacy aggregation with filters."""
        try:
            from core.async_db import get_async_session
            async with get_async_session() as s:
                result = await s.execute(text("""
                    SELECT
                        t.method,
                        l.production_area,
                        EXTRACT(MONTH FROM t.treatment_date) as month,
                        lr.sea_temp_c,
                        t.pre_lice_count,
                        t.post_lice_count,
                        t.mortality_observed,
                        t.cost_nok,
                        t.treatment_date
                    FROM treatment_outcomes t
                    JOIN localities l ON t.locality_no = l.locality_no
                    LEFT JOIN lice_records lr ON t.locality_no = lr.locality_no
                        AND lr.year = EXTRACT(YEAR FROM t.treatment_date)
                        AND lr.week = EXTRACT(WEEK FROM t.treatment_date)
                    WHERE t.method IS NOT NULL
                      AND t.pre_lice_count IS NOT NULL
                      AND t.pre_lice_count > 0
                """))
                rows = result.fetchall()

            if not rows:
                return self._empty_explore_response(method, production_area, season)

            # Build records with derived dimensions
            records = []
            for r in rows:
                rec_method = r[0]
                pa = r[1]
                month = int(r[2]) if r[2] else None
                temp = r[3]
                pre = r[4]
                post = r[5]
                mort = r[6] or 0
                cost = r[7]
                tdate = r[8]

                rec_season = _season_from_month(month) if month else "unknown"
                rec_temp_bucket = _temp_bucket(temp)
                reduction_pct = ((pre - (post or 0)) / pre * 100) if pre > 0 else 0

                # Apply filters
                if method and rec_method != method:
                    continue
                if production_area and pa != production_area:
                    continue
                if season and rec_season != season:
                    continue
                if temp_range:
                    if temp is None:
                        continue
                    if temp < temp_range[0] or temp > temp_range[1]:
                        continue

                records.append({
                    "method": rec_method,
                    "production_area": pa,
                    "season": rec_season,
                    "temp_bucket": rec_temp_bucket,
                    "reduction_pct": reduction_pct,
                    "mortality": mort,
                    "cost_nok": cost,
                    "date": str(tdate) if tdate else None,
                })

            # Group by (method, PA, temp_bucket, season)
            groups: dict[tuple, list] = {}
            for rec in records:
                key = (rec["method"], rec["production_area"], rec["temp_bucket"], rec["season"])
                groups.setdefault(key, []).append(rec)

            # Build benchmarks, enforcing min cell size
            benchmarks = []
            for (m, pa, tb, sn), items in groups.items():
                if len(items) < MIN_CELL_SIZE:
                    continue
                reductions = [i["reduction_pct"] for i in items]
                costs = [i["cost_nok"] for i in items if i["cost_nok"] is not None]
                morts = [i["mortality"] for i in items]

                benchmarks.append({
                    "method": m,
                    "production_area": pa,
                    "temp_bucket": tb,
                    "season": sn,
                    "n": len(items),
                    "avg_reduction_pct": round(sum(reductions) / len(reductions), 1),
                    "avg_cost_nok": round(sum(costs) / len(costs)) if costs else None,
                    "avg_mortality": round(sum(morts) / len(morts), 1),
                })

            benchmarks.sort(key=lambda b: b["avg_reduction_pct"], reverse=True)

            return {
                "dimensions": {
                    "method": method,
                    "production_area": production_area,
                    "temp_range": list(temp_range) if temp_range else None,
                    "season": season,
                },
                "benchmarks": benchmarks,
                "total_records": len(records),
                "cells_suppressed": sum(1 for items in groups.values() if len(items) < MIN_CELL_SIZE),
                "privacy_note": f"Cells with fewer than {MIN_CELL_SIZE} outcomes are suppressed for anonymity.",
                "generated_at": dt.datetime.now(dt.UTC).isoformat(),
                "data_provenance": DataProvenance.live(
                    "Crowdsourced treatment outcomes (anonymized to PA level)",
                    confidence=min(0.9, 0.3 + 0.05 * len(records)),
                ).to_dict(),
            }

        except Exception as e:
            log.error("efficacy_marketplace.aggregate_by_dimensions.error", error=str(e))
            return self._empty_explore_response(method, production_area, season, error=str(e))

    async def get_method_benchmarks(self) -> dict:
        """Industry-wide benchmarks per treatment method."""
        try:
            from core.async_db import get_async_session
            async with get_async_session() as s:
                result = await s.execute(text("""
                    SELECT
                        method,
                        COUNT(*) as n,
                        AVG(CASE WHEN pre_lice_count > 0
                            THEN (pre_lice_count - post_lice_count) / pre_lice_count * 100
                            ELSE 0 END) as avg_reduction,
                        AVG(cost_nok) as avg_cost,
                        AVG(mortality_observed) as avg_mortality,
                        MIN(treatment_date) as first_outcome,
                        MAX(treatment_date) as last_outcome
                    FROM treatment_outcomes
                    WHERE method IS NOT NULL
                      AND pre_lice_count IS NOT NULL
                      AND pre_lice_count > 0
                    GROUP BY method
                    HAVING COUNT(*) >= :min_n
                    ORDER BY avg_reduction DESC
                """), {"min_n": MIN_CELL_SIZE})
                rows = result.fetchall()

            # Also get percentiles per method with separate queries
            methods = []
            for r in rows:
                method_name = r[0]
                n = r[1]

                # Calculate percentiles from the aggregation
                avg_red = round(r[2] or 0, 1)

                # Import TREATMENT_PROFILES for baseline comparison
                from core.market.decision_engine import TREATMENT_PROFILES
                baseline = TREATMENT_PROFILES.get(method_name, {})
                baseline_success = baseline.get("base_success", 0) * 100

                methods.append({
                    "method": method_name,
                    "label": baseline.get("label", method_name.title()),
                    "sample_size": n,
                    "avg_reduction_pct": avg_red,
                    "avg_cost_nok": round(r[3] or 0),
                    "avg_mortality": round(r[4] or 0, 1),
                    "baseline_success_pct": round(baseline_success, 1),
                    "vs_baseline_delta": round(avg_red - baseline_success, 1),
                    "first_outcome": str(r[5]) if r[5] else None,
                    "last_outcome": str(r[6]) if r[6] else None,
                    "resistance_risk": baseline.get("resistance_risk", "unknown"),
                })

            total = sum(m["sample_size"] for m in methods)

            return {
                "methods": methods,
                "total_outcomes": total,
                "contributing_methods": len(methods),
                "privacy_note": f"Only methods with {MIN_CELL_SIZE}+ outcomes shown.",
                "generated_at": dt.datetime.now(dt.UTC).isoformat(),
                "data_provenance": DataProvenance.live(
                    "Crowdsourced treatment outcomes (anonymized)",
                    confidence=min(0.9, 0.3 + 0.03 * total),
                ).to_dict(),
            }

        except Exception as e:
            log.error("efficacy_marketplace.get_method_benchmarks.error", error=str(e))
            return {
                "methods": [],
                "total_outcomes": 0,
                "contributing_methods": 0,
                "note": "No outcome data yet. Contribute by logging treatments on the Daily Check page.",
                "generated_at": dt.datetime.now(dt.UTC).isoformat(),
                "data_provenance": DataProvenance.simulated("No treatment outcome data available").to_dict(),
            }

    async def get_regional_efficacy(self) -> dict:
        """Efficacy broken down by production area. Returns PA x method matrix."""
        try:
            from core.async_db import get_async_session
            async with get_async_session() as s:
                result = await s.execute(text("""
                    SELECT
                        l.production_area,
                        t.method,
                        COUNT(*) as n,
                        AVG(CASE WHEN t.pre_lice_count > 0
                            THEN (t.pre_lice_count - t.post_lice_count) / t.pre_lice_count * 100
                            ELSE 0 END) as avg_reduction,
                        AVG(t.cost_nok) as avg_cost,
                        AVG(t.mortality_observed) as avg_mortality
                    FROM treatment_outcomes t
                    JOIN localities l ON t.locality_no = l.locality_no
                    WHERE t.method IS NOT NULL
                      AND t.pre_lice_count IS NOT NULL
                      AND t.pre_lice_count > 0
                    GROUP BY l.production_area, t.method
                    ORDER BY l.production_area, t.method
                """))
                rows = result.fetchall()

            # Build PA x Method matrix, enforcing min cell size
            matrix = []
            total_outcomes = 0
            suppressed = 0

            for r in rows:
                pa = r[0]
                method = r[1]
                n = r[2]

                if n < MIN_CELL_SIZE:
                    suppressed += 1
                    continue

                total_outcomes += n
                matrix.append({
                    "production_area": pa,
                    "method": method,
                    "n": n,
                    "avg_reduction_pct": round(r[3] or 0, 1),
                    "avg_cost_nok": round(r[4] or 0),
                    "avg_mortality": round(r[5] or 0, 1),
                })

            # Build summary per PA
            pa_summary = {}
            for cell in matrix:
                pa = cell["production_area"]
                if pa not in pa_summary:
                    pa_summary[pa] = {"production_area": pa, "methods": [], "total_n": 0}
                pa_summary[pa]["methods"].append(cell)
                pa_summary[pa]["total_n"] += cell["n"]

            return {
                "regions": list(pa_summary.values()),
                "matrix": matrix,
                "total_outcomes": total_outcomes,
                "cells_suppressed": suppressed,
                "privacy_note": f"Cells with fewer than {MIN_CELL_SIZE} outcomes are suppressed.",
                "generated_at": dt.datetime.now(dt.UTC).isoformat(),
                "data_provenance": DataProvenance.live(
                    "Crowdsourced outcomes, anonymized to PA level",
                    confidence=min(0.9, 0.3 + 0.03 * total_outcomes),
                ).to_dict(),
            }

        except Exception as e:
            log.error("efficacy_marketplace.get_regional_efficacy.error", error=str(e))
            return {
                "regions": [],
                "matrix": [],
                "total_outcomes": 0,
                "note": "No regional data yet. Contribute by logging treatments.",
                "generated_at": dt.datetime.now(dt.UTC).isoformat(),
                "data_provenance": DataProvenance.simulated("No treatment outcome data available").to_dict(),
            }

    async def get_seasonal_patterns(self) -> dict:
        """How efficacy varies by month and season. Returns month x method matrix."""
        try:
            from core.async_db import get_async_session
            async with get_async_session() as s:
                result = await s.execute(text("""
                    SELECT
                        EXTRACT(MONTH FROM t.treatment_date) as month,
                        t.method,
                        COUNT(*) as n,
                        AVG(CASE WHEN t.pre_lice_count > 0
                            THEN (t.pre_lice_count - t.post_lice_count) / t.pre_lice_count * 100
                            ELSE 0 END) as avg_reduction,
                        AVG(t.cost_nok) as avg_cost,
                        AVG(t.mortality_observed) as avg_mortality
                    FROM treatment_outcomes t
                    WHERE t.method IS NOT NULL
                      AND t.pre_lice_count IS NOT NULL
                      AND t.pre_lice_count > 0
                    GROUP BY EXTRACT(MONTH FROM t.treatment_date), t.method
                    ORDER BY month, t.method
                """))
                rows = result.fetchall()

            matrix = []
            total_outcomes = 0
            suppressed = 0

            for r in rows:
                month = int(r[0]) if r[0] else None
                method = r[1]
                n = r[2]

                if n < MIN_CELL_SIZE:
                    suppressed += 1
                    continue

                total_outcomes += n
                season = _season_from_month(month) if month else "unknown"
                month_names = [
                    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
                ]

                matrix.append({
                    "month": month,
                    "month_name": month_names[month] if month and 1 <= month <= 12 else "?",
                    "season": season,
                    "method": method,
                    "n": n,
                    "avg_reduction_pct": round(r[3] or 0, 1),
                    "avg_cost_nok": round(r[4] or 0),
                    "avg_mortality": round(r[5] or 0, 1),
                })

            # Build per-month summary
            monthly = {}
            for cell in matrix:
                m = cell["month"]
                if m not in monthly:
                    monthly[m] = {
                        "month": m,
                        "month_name": cell["month_name"],
                        "season": cell["season"],
                        "methods": [],
                        "total_n": 0,
                    }
                monthly[m]["methods"].append(cell)
                monthly[m]["total_n"] += cell["n"]

            return {
                "monthly": sorted(monthly.values(), key=lambda x: x["month"] or 0),
                "matrix": matrix,
                "total_outcomes": total_outcomes,
                "cells_suppressed": suppressed,
                "privacy_note": f"Cells with fewer than {MIN_CELL_SIZE} outcomes are suppressed.",
                "generated_at": dt.datetime.now(dt.UTC).isoformat(),
                "data_provenance": DataProvenance.live(
                    "Crowdsourced outcomes, seasonal analysis",
                    confidence=min(0.9, 0.3 + 0.03 * total_outcomes),
                ).to_dict(),
            }

        except Exception as e:
            log.error("efficacy_marketplace.get_seasonal_patterns.error", error=str(e))
            return {
                "monthly": [],
                "matrix": [],
                "total_outcomes": 0,
                "note": "No seasonal data yet. Contribute by logging treatments.",
                "generated_at": dt.datetime.now(dt.UTC).isoformat(),
                "data_provenance": DataProvenance.simulated("No treatment outcome data available").to_dict(),
            }

    # ── Learned profiles for Decision Engine feedback loop ─────────
    # Cache: (timestamp, data)
    _learned_profiles_cache: tuple[float, dict] = (0.0, {})
    _LEARNED_CACHE_TTL = 3600  # 1 hour

    async def get_learned_profiles(self) -> dict:
        """
        Query treatment outcomes grouped by (method, production_area).
        For cells with >= 5 outcomes, return learned efficacy rates that
        the Decision Engine can use instead of static literature profiles.

        Returns:
            dict keyed by (method, pa) with reduction_pct, sample_size,
            cost_nok, and mortality_rate for each cell.
        """
        import time

        now = time.time()
        cache_ts, cache_data = EfficacyMarketplace._learned_profiles_cache
        if cache_data and (now - cache_ts) < self._LEARNED_CACHE_TTL:
            return cache_data

        min_n = 5  # statistical significance threshold

        try:
            from core.async_db import get_async_session
            async with get_async_session() as s:
                result = await s.execute(text("""
                    SELECT
                        t.method,
                        l.production_area,
                        COUNT(*) as n,
                        AVG(CASE WHEN t.pre_lice_count > 0
                            THEN (t.pre_lice_count - t.post_lice_count) / t.pre_lice_count
                            ELSE 0 END) as avg_reduction,
                        AVG(t.cost_nok) as avg_cost,
                        AVG(t.mortality_observed) as avg_mortality
                    FROM treatment_outcomes t
                    JOIN localities l ON t.locality_no = l.locality_no
                    WHERE t.method IS NOT NULL
                      AND t.pre_lice_count IS NOT NULL
                      AND t.pre_lice_count > 0
                    GROUP BY t.method, l.production_area
                    HAVING COUNT(*) >= :min_n
                    ORDER BY t.method, l.production_area
                """), {"min_n": min_n})
                rows = result.fetchall()

            profiles: dict[tuple[str, int], dict] = {}
            for r in rows:
                method = r[0]
                pa = r[1]
                if method is None or pa is None:
                    continue
                profiles[(method, pa)] = {
                    "reduction_pct": round((r[3] or 0) * 100, 1),
                    "sample_size": r[2],
                    "cost_nok": round(r[4] or 0, 1),
                    "mortality_rate": round(r[5] or 0, 1),
                }

            EfficacyMarketplace._learned_profiles_cache = (now, profiles)
            log.info(
                "efficacy_marketplace.learned_profiles_refreshed",
                cells=len(profiles),
                total_outcomes=sum(p["sample_size"] for p in profiles.values()),
            )
            return profiles

        except Exception as e:
            log.error("efficacy_marketplace.get_learned_profiles.error", error=str(e))
            return {}

    def _anonymize(self, data: list[dict]) -> list[dict]:
        """Remove locality-specific identifiers, keep only PA-level granularity."""
        anonymized = []
        for item in data:
            clean = {k: v for k, v in item.items() if k != "locality_no"}
            anonymized.append(clean)
        return anonymized

    async def log_outcome(self, data) -> dict:
        """
        Insert a validated treatment outcome into the database.

        Args:
            data: TreatmentOutcomeRequest (Pydantic model, already validated).

        Returns:
            dict with created record ID, reduction_pct, and status.
        """
        from core.async_db import get_async_session

        treatment_date = (
            dt.datetime.fromisoformat(data.treatment_date)
            if data.treatment_date
            else dt.datetime.now(dt.UTC)
        )

        reduction_pct = round(
            (data.pre_lice_count - data.post_lice_count) / data.pre_lice_count * 100, 1
        )

        async with get_async_session() as s:
            result = await s.execute(text("""
                INSERT INTO treatment_outcomes
                    (locality_no, treatment_date, method, pre_lice_count, post_lice_count,
                     mortality_observed, cost_nok, notes, resistance_observed, reported_at)
                VALUES
                    (:loc, :tdate, :method, :pre, :post, :mort, :cost, :notes, :resist, :now)
                RETURNING id
            """), {
                "loc": data.locality_no,
                "tdate": treatment_date,
                "method": data.method,
                "pre": data.pre_lice_count,
                "post": data.post_lice_count,
                "mort": data.mortality_observed,
                "cost": data.cost_nok,
                "notes": data.notes,
                "resist": data.resistance_observed,
                "now": dt.datetime.now(dt.UTC),
            })
            row = result.fetchone()
            record_id = row[0] if row else None

        log.info(
            "efficacy_marketplace.log_outcome",
            locality_no=data.locality_no,
            method=data.method,
            reduction_pct=reduction_pct,
            record_id=record_id,
        )

        return {
            "id": record_id,
            "status": "recorded",
            "reduction_pct": reduction_pct,
            "method": data.method,
            "locality_no": data.locality_no,
        }

    def _empty_explore_response(
        self,
        method: Optional[str] = None,
        production_area: Optional[int] = None,
        season: Optional[str] = None,
        error: Optional[str] = None,
    ) -> dict:
        resp = {
            "dimensions": {
                "method": method,
                "production_area": production_area,
                "season": season,
            },
            "benchmarks": [],
            "total_records": 0,
            "cells_suppressed": 0,
            "note": "No matching outcome data yet. Be the first to contribute!",
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "data_provenance": DataProvenance.simulated("No treatment outcome data available").to_dict(),
        }
        if error:
            resp["error"] = error
        return resp


async def seed_demo_outcomes() -> int:
    """
    Generate 80 realistic treatment outcomes for demo mode.

    Distributes outcomes across 5 methods, 13 PAs, and 12 months with
    literature-consistent efficacy, cost, and mortality ranges.

    Returns:
        Number of records inserted.
    """
    # Ranges per method: (reduction_lo, reduction_hi, cost_lo, cost_hi, mort_lo, mort_hi)
    METHOD_RANGES = {
        "mechanical":  (70, 95, 15, 25, 0.0, 3.0),
        "freshwater":  (50, 80,  8, 15, 0.0, 3.0),
        "medicinal":   (60, 85, 20, 35, 0.0, 5.0),
        "thermal":     (75, 92, 18, 28, 0.0, 3.0),
        "biological":  (40, 70,  5, 12, 0.0, 1.0),
    }

    # Pick a spread of Norwegian locality_nos (well-known demo farms)
    # Use locality_no values that are likely to exist in demo DB
    sample_localities_by_pa = {
        1: [10735, 10736],
        2: [11049, 11050],
        3: [12115, 12116],
        4: [13302, 13303],
        5: [14401, 14402],
        6: [15501, 15502],
        7: [16601, 16602],
        8: [17701, 17702],
        9: [18801, 18802],
        10: [19901, 19902],
        11: [20001, 20002],
        12: [21001, 21002],
        13: [22001, 22002],
    }

    rng = random.Random(42)  # Deterministic for reproducibility
    methods = list(METHOD_RANGES.keys())
    records = []

    for _ in range(80):
        method = rng.choice(methods)
        red_lo, red_hi, cost_lo, cost_hi, mort_lo, mort_hi = METHOD_RANGES[method]

        pa = rng.randint(1, 13)
        loc = rng.choice(sample_localities_by_pa[pa])
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        year = rng.choice([2025, 2025, 2025, 2026])
        tdate = dt.datetime(year, month, day)

        pre_lice = round(rng.uniform(0.3, 2.5), 2)
        reduction = rng.uniform(red_lo, red_hi) / 100.0
        post_lice = round(pre_lice * (1 - reduction), 3)
        post_lice = max(0.0, post_lice)

        cost = round(rng.uniform(cost_lo, cost_hi), 1)
        mort = round(rng.uniform(mort_lo, mort_hi), 1)

        # Higher resistance chance for medicinal
        resist = rng.random() < (0.20 if method == "medicinal" else 0.03)

        records.append({
            "locality_no": loc,
            "treatment_date": tdate,
            "method": method,
            "pre_lice_count": pre_lice,
            "post_lice_count": post_lice,
            "mortality_observed": mort,
            "cost_nok": cost,
            "notes": f"Demo seed — {method} in PA {pa}",
            "resistance_observed": resist,
            "reported_at": dt.datetime.now(dt.UTC),
        })

    try:
        from core.async_db import get_async_session
        async with get_async_session() as s:
            # Check if demo data already seeded
            existing = (await s.execute(text(
                "SELECT COUNT(*) FROM treatment_outcomes WHERE notes LIKE 'Demo seed%'"
            ))).scalar()
            if existing and existing >= 40:
                log.info("seed_demo_outcomes.skipped", existing=existing)
                return 0

            for rec in records:
                await s.execute(text("""
                    INSERT INTO treatment_outcomes
                        (locality_no, treatment_date, method, pre_lice_count,
                         post_lice_count, mortality_observed, cost_nok, notes,
                         resistance_observed, reported_at)
                    VALUES
                        (:locality_no, :treatment_date, :method, :pre_lice_count,
                         :post_lice_count, :mortality_observed, :cost_nok, :notes,
                         :resistance_observed, :reported_at)
                """), rec)
            log.info("seed_demo_outcomes.inserted", count=len(records))
            return len(records)
    except Exception as e:
        log.error("seed_demo_outcomes.error", error=str(e))
        return 0


# Singleton
efficacy_marketplace = EfficacyMarketplace()
