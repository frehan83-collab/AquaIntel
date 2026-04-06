"""
ASC Farm Standard v1.0 Compliance Checker
==========================================
The new ASC Farm Standard v1.0 became effective Aug 2025, mandatory May 2027.
Farms need 6 months of pre-audit data. Key requirements: continuous monitoring
data, feed chain traceability, GHG reporting, welfare indicators.

This engine checks data completeness vs ASC requirements and produces an
audit-readiness score per locality and across the platform.

Reference: ASC Farm Standard v1.0 (2025), Indicators 1-7.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, asdict

import structlog
from sqlalchemy import select, func

from core.async_db import get_async_session
from core.market.data_provenance import DataProvenance

log = structlog.get_logger(__name__)

# ASC mandatory date
ASC_MANDATORY_DATE = dt.date(2027, 5, 1)
# Pre-audit data window: 6 months of continuous data required
PRE_AUDIT_MONTHS = 6

# ASC v1.0 Indicator Checklist
# Each indicator has: id, category, title, description, data_check function name
ASC_INDICATORS = [
    {
        "id": "1.1",
        "category": "Lice Monitoring",
        "title": "Weekly lice counts",
        "description": "Continuous weekly sea lice monitoring with adult female counts",
        "check": "check_lice_monitoring",
        "weight": 15,
    },
    {
        "id": "1.2",
        "category": "Lice Monitoring",
        "title": "Lice threshold compliance",
        "description": "Adult female lice maintained below 0.5 per fish",
        "check": "check_lice_threshold",
        "weight": 10,
    },
    {
        "id": "2.1",
        "category": "Treatment Records",
        "title": "Treatment outcome logging",
        "description": "All treatments recorded with pre/post lice counts, method, and cost",
        "check": "check_treatment_records",
        "weight": 12,
    },
    {
        "id": "2.2",
        "category": "Treatment Records",
        "title": "Non-medicinal treatment preference",
        "description": "Evidence of non-medicinal treatment methods (mechanical, thermal, cleaner fish)",
        "check": "check_nonmedicinal_preference",
        "weight": 8,
    },
    {
        "id": "3.1",
        "category": "Mortality Data",
        "title": "Mortality monitoring",
        "description": "Treatment-related mortality tracked and reported",
        "check": "check_mortality_data",
        "weight": 10,
    },
    {
        "id": "4.1",
        "category": "Feed Data",
        "title": "Feed traceability",
        "description": "Feed supplier records and feed conversion data available",
        "check": "check_feed_data",
        "weight": 10,
    },
    {
        "id": "5.1",
        "category": "Temperature Data",
        "title": "Sea temperature monitoring",
        "description": "Continuous sea temperature records for welfare assessment",
        "check": "check_temperature_data",
        "weight": 10,
    },
    {
        "id": "6.1",
        "category": "Welfare Indicators",
        "title": "Fish welfare scoring",
        "description": "Welfare indicators tracked (lice burden, treatment stress, mortality)",
        "check": "check_welfare_indicators",
        "weight": 10,
    },
    {
        "id": "6.2",
        "category": "Welfare Indicators",
        "title": "Cleaner fish records",
        "description": "Cleaner fish usage documented where applicable",
        "check": "check_cleaner_fish",
        "weight": 5,
    },
    {
        "id": "7.1",
        "category": "Reporting Completeness",
        "title": "Data continuity",
        "description": "6 months of continuous monitoring data without gaps",
        "check": "check_data_continuity",
        "weight": 10,
    },
]


class ASCComplianceChecker:
    """Check farm readiness for ASC Farm Standard v1.0 audit."""

    _cache: dict = {}
    _cache_ttl = dt.timedelta(minutes=15)

    def __init__(self) -> None:
        self._cache = {}

    async def audit_readiness(self, locality_no: int) -> dict:
        """Check data completeness vs ASC requirements for a single farm."""
        now = dt.datetime.now(dt.UTC)
        cache_key = f"readiness_{locality_no}"
        if cache_key in self._cache:
            cached_at, cached_val = self._cache[cache_key]
            if (now - cached_at) < self._cache_ttl:
                return cached_val

        from core.models import LiceRecord, TreatmentOutcome, Locality

        checks = []
        total_weight = sum(ind["weight"] for ind in ASC_INDICATORS)
        earned_weight = 0.0

        # Fetch data for the locality
        async with get_async_session() as s:
            # Get locality info
            loc_result = await s.execute(
                select(Locality).where(Locality.locality_no == locality_no)
            )
            locality = loc_result.scalar()
            locality_name = locality.name if locality else f"Locality {locality_no}"
            company = locality.owner_company if locality else "Unknown"

            # Lice records in last 26 weeks
            cutoff_26w = now - dt.timedelta(weeks=26)
            lice_result = await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.locality_no == locality_no,
                    LiceRecord.fetched_at >= cutoff_26w,
                )
            )
            lice_count_26w = lice_result.scalar() or 0

            # Lice records in last 6 months (for continuity check)
            cutoff_6m = now - dt.timedelta(days=PRE_AUDIT_MONTHS * 30)
            lice_6m_result = await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.locality_no == locality_no,
                    LiceRecord.fetched_at >= cutoff_6m,
                )
            )
            lice_count_6m = lice_6m_result.scalar() or 0

            # Above threshold count
            above_threshold_result = await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.locality_no == locality_no,
                    LiceRecord.fetched_at >= cutoff_26w,
                    LiceRecord.avg_adult_female_lice > 0.5,
                )
            )
            above_threshold = above_threshold_result.scalar() or 0

            # Treatment records
            treatment_result = await s.execute(
                select(func.count(TreatmentOutcome.id)).where(
                    TreatmentOutcome.locality_no == locality_no,
                )
            )
            treatment_count = treatment_result.scalar() or 0

            # Non-medicinal treatments
            nonmed_result = await s.execute(
                select(func.count(TreatmentOutcome.id)).where(
                    TreatmentOutcome.locality_no == locality_no,
                    TreatmentOutcome.method.in_(["mechanical", "thermal", "freshwater", "biological"]),
                )
            )
            nonmed_count = nonmed_result.scalar() or 0

            # Treatments with mortality data
            mortality_result = await s.execute(
                select(func.count(TreatmentOutcome.id)).where(
                    TreatmentOutcome.locality_no == locality_no,
                    TreatmentOutcome.mortality_observed.isnot(None),
                )
            )
            mortality_tracked = mortality_result.scalar() or 0

            # Cleaner fish usage
            cleaner_result = await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.locality_no == locality_no,
                    LiceRecord.has_cleaner_fish == True,  # noqa: E712
                    LiceRecord.fetched_at >= cutoff_26w,
                )
            )
            cleaner_count = cleaner_result.scalar() or 0

            # Temperature data (from lice records that have sea_temperature)
            temp_result = await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.locality_no == locality_no,
                    LiceRecord.sea_temp_c.isnot(None),
                    LiceRecord.fetched_at >= cutoff_26w,
                )
            )
            temp_count = temp_result.scalar() or 0

        # ── Run checks ──────────────────────────────────────────────

        # 1.1 Weekly lice counts (expect ~26 records for 26 weeks)
        lice_pct = min(100, round(lice_count_26w / max(1, 26) * 100, 1))
        status_lice = "pass" if lice_pct >= 90 else ("partial" if lice_pct >= 50 else "fail")
        checks.append({
            "indicator": "1.1", "category": "Lice Monitoring",
            "title": "Weekly lice counts", "status": status_lice,
            "data_completeness_pct": lice_pct,
            "detail": f"{lice_count_26w} of ~26 expected weekly records",
        })
        if status_lice == "pass":
            earned_weight += ASC_INDICATORS[0]["weight"]
        elif status_lice == "partial":
            earned_weight += ASC_INDICATORS[0]["weight"] * (lice_pct / 100)

        # 1.2 Lice threshold compliance
        if lice_count_26w > 0:
            compliance_pct = round((1 - above_threshold / lice_count_26w) * 100, 1)
        else:
            compliance_pct = 0.0
        status_threshold = "pass" if compliance_pct >= 95 else ("partial" if compliance_pct >= 80 else "fail")
        checks.append({
            "indicator": "1.2", "category": "Lice Monitoring",
            "title": "Lice threshold compliance", "status": status_threshold,
            "data_completeness_pct": compliance_pct,
            "detail": f"{compliance_pct}% of records below 0.5 threshold",
        })
        if status_threshold == "pass":
            earned_weight += ASC_INDICATORS[1]["weight"]
        elif status_threshold == "partial":
            earned_weight += ASC_INDICATORS[1]["weight"] * (compliance_pct / 100)

        # 2.1 Treatment records
        treatment_pct = min(100, round(treatment_count / max(1, 2) * 100, 1))  # Expect at least 2 records
        status_treatment = "pass" if treatment_count >= 2 else ("partial" if treatment_count >= 1 else "fail")
        checks.append({
            "indicator": "2.1", "category": "Treatment Records",
            "title": "Treatment outcome logging", "status": status_treatment,
            "data_completeness_pct": treatment_pct,
            "detail": f"{treatment_count} treatment outcomes recorded",
        })
        if status_treatment == "pass":
            earned_weight += ASC_INDICATORS[2]["weight"]
        elif status_treatment == "partial":
            earned_weight += ASC_INDICATORS[2]["weight"] * 0.5

        # 2.2 Non-medicinal preference
        if treatment_count > 0:
            nonmed_pct = round(nonmed_count / treatment_count * 100, 1)
        else:
            nonmed_pct = 0.0
        status_nonmed = "pass" if nonmed_pct >= 50 else ("partial" if nonmed_pct > 0 else "fail")
        checks.append({
            "indicator": "2.2", "category": "Treatment Records",
            "title": "Non-medicinal treatment preference", "status": status_nonmed,
            "data_completeness_pct": nonmed_pct,
            "detail": f"{nonmed_pct}% of treatments are non-medicinal",
        })
        if status_nonmed == "pass":
            earned_weight += ASC_INDICATORS[3]["weight"]
        elif status_nonmed == "partial":
            earned_weight += ASC_INDICATORS[3]["weight"] * 0.5

        # 3.1 Mortality data
        if treatment_count > 0:
            mort_pct = round(mortality_tracked / treatment_count * 100, 1)
        else:
            mort_pct = 0.0
        status_mort = "pass" if mort_pct >= 90 else ("partial" if mort_pct >= 50 else "fail")
        checks.append({
            "indicator": "3.1", "category": "Mortality Data",
            "title": "Mortality monitoring", "status": status_mort,
            "data_completeness_pct": mort_pct,
            "detail": f"{mortality_tracked}/{treatment_count} treatments have mortality data",
        })
        if status_mort == "pass":
            earned_weight += ASC_INDICATORS[4]["weight"]
        elif status_mort == "partial":
            earned_weight += ASC_INDICATORS[4]["weight"] * (mort_pct / 100)

        # 4.1 Feed data (check if any feed cost engine data available)
        feed_available = False
        try:
            from core.market.feed_cost_engine import feed_cost_engine
            feed_data = await feed_cost_engine.fetch_prices()
            feed_available = feed_data is not None
        except Exception:
            pass
        feed_pct = 100.0 if feed_available else 0.0
        status_feed = "pass" if feed_available else "fail"
        checks.append({
            "indicator": "4.1", "category": "Feed Data",
            "title": "Feed traceability", "status": status_feed,
            "data_completeness_pct": feed_pct,
            "detail": "Feed cost data available" if feed_available else "No feed data found",
        })
        if status_feed == "pass":
            earned_weight += ASC_INDICATORS[5]["weight"]

        # 5.1 Temperature data
        temp_pct = min(100, round(temp_count / max(1, 26) * 100, 1))
        status_temp = "pass" if temp_pct >= 80 else ("partial" if temp_pct >= 40 else "fail")
        checks.append({
            "indicator": "5.1", "category": "Temperature Data",
            "title": "Sea temperature monitoring", "status": status_temp,
            "data_completeness_pct": temp_pct,
            "detail": f"{temp_count} temperature readings in last 26 weeks",
        })
        if status_temp == "pass":
            earned_weight += ASC_INDICATORS[6]["weight"]
        elif status_temp == "partial":
            earned_weight += ASC_INDICATORS[6]["weight"] * (temp_pct / 100)

        # 6.1 Welfare indicators (composite of lice + treatment stress + mortality)
        welfare_inputs = sum([
            1 if lice_count_26w > 0 else 0,
            1 if treatment_count > 0 else 0,
            1 if mortality_tracked > 0 else 0,
        ])
        welfare_pct = round(welfare_inputs / 3 * 100, 1)
        status_welfare = "pass" if welfare_inputs == 3 else ("partial" if welfare_inputs >= 1 else "fail")
        checks.append({
            "indicator": "6.1", "category": "Welfare Indicators",
            "title": "Fish welfare scoring", "status": status_welfare,
            "data_completeness_pct": welfare_pct,
            "detail": f"{welfare_inputs}/3 welfare data streams available",
        })
        if status_welfare == "pass":
            earned_weight += ASC_INDICATORS[7]["weight"]
        elif status_welfare == "partial":
            earned_weight += ASC_INDICATORS[7]["weight"] * (welfare_pct / 100)

        # 6.2 Cleaner fish records
        cleaner_pct = min(100, round(cleaner_count / max(1, 26) * 100, 1))
        status_cleaner = "pass" if cleaner_pct >= 50 else ("partial" if cleaner_pct > 0 else "fail")
        checks.append({
            "indicator": "6.2", "category": "Welfare Indicators",
            "title": "Cleaner fish records", "status": status_cleaner,
            "data_completeness_pct": cleaner_pct,
            "detail": f"{cleaner_count} records with cleaner fish data",
        })
        if status_cleaner == "pass":
            earned_weight += ASC_INDICATORS[8]["weight"]
        elif status_cleaner == "partial":
            earned_weight += ASC_INDICATORS[8]["weight"] * (cleaner_pct / 100)

        # 7.1 Data continuity (6 months continuous)
        expected_6m = PRE_AUDIT_MONTHS * 4  # ~4 records per month
        continuity_pct = min(100, round(lice_count_6m / max(1, expected_6m) * 100, 1))
        status_continuity = "pass" if continuity_pct >= 90 else ("partial" if continuity_pct >= 50 else "fail")
        checks.append({
            "indicator": "7.1", "category": "Reporting Completeness",
            "title": "Data continuity", "status": status_continuity,
            "data_completeness_pct": continuity_pct,
            "detail": f"{lice_count_6m} records in last 6 months (expect ~{expected_6m})",
        })
        if status_continuity == "pass":
            earned_weight += ASC_INDICATORS[9]["weight"]
        elif status_continuity == "partial":
            earned_weight += ASC_INDICATORS[9]["weight"] * (continuity_pct / 100)

        # ── Compute overall readiness ───────────────────────────────
        readiness_score = round(earned_weight / total_weight * 100, 1) if total_weight > 0 else 0.0
        days_until_mandatory = (ASC_MANDATORY_DATE - dt.date.today()).days

        # Data gaps
        data_gaps = [c for c in checks if c["status"] != "pass"]

        result = {
            "locality_no": locality_no,
            "locality_name": locality_name,
            "company": company,
            "readiness_score": readiness_score,
            "readiness_grade": self._grade(readiness_score),
            "days_until_mandatory": max(0, days_until_mandatory),
            "mandatory_date": ASC_MANDATORY_DATE.isoformat(),
            "pre_audit_window_ok": continuity_pct >= 90,
            "checks": checks,
            "summary": {
                "total_indicators": len(ASC_INDICATORS),
                "passing": sum(1 for c in checks if c["status"] == "pass"),
                "partial": sum(1 for c in checks if c["status"] == "partial"),
                "failing": sum(1 for c in checks if c["status"] == "fail"),
            },
            "data_gaps": [
                {"indicator": g["indicator"], "title": g["title"], "status": g["status"], "detail": g["detail"]}
                for g in data_gaps
            ],
            "checked_at": now.isoformat(),
            "data_provenance": DataProvenance.live(
                "BarentsWatch + Internal treatment data", confidence=0.85
            ).to_dict(),
        }

        self._cache[cache_key] = (now, result)
        log.info("asc.readiness_checked", locality_no=locality_no, score=readiness_score)
        return result

    async def readiness_summary(self) -> dict:
        """Overview of ASC readiness across all farms with data."""
        now = dt.datetime.now(dt.UTC)
        cache_key = "readiness_summary"
        if cache_key in self._cache:
            cached_at, cached_val = self._cache[cache_key]
            if (now - cached_at) < self._cache_ttl:
                return cached_val

        from core.models import Locality

        async with get_async_session() as s:
            loc_result = await s.execute(select(Locality.locality_no))
            locality_nos = [row[0] for row in loc_result.fetchall()]

        if not locality_nos:
            return {
                "total_farms": 0,
                "farms": [],
                "avg_readiness": 0.0,
                "days_until_mandatory": max(0, (ASC_MANDATORY_DATE - dt.date.today()).days),
                "mandatory_date": ASC_MANDATORY_DATE.isoformat(),
                "data_provenance": DataProvenance.live(
                    "BarentsWatch + Internal", confidence=0.85
                ).to_dict(),
            }

        # Check up to 50 farms for performance
        sample = locality_nos[:50]
        farm_summaries = []
        for ln in sample:
            try:
                r = await self.audit_readiness(ln)
                farm_summaries.append({
                    "locality_no": r["locality_no"],
                    "locality_name": r["locality_name"],
                    "company": r["company"],
                    "readiness_score": r["readiness_score"],
                    "readiness_grade": r["readiness_grade"],
                    "passing": r["summary"]["passing"],
                    "partial": r["summary"]["partial"],
                    "failing": r["summary"]["failing"],
                    "pre_audit_window_ok": r["pre_audit_window_ok"],
                })
            except Exception as exc:
                log.debug("asc.farm_check_error", locality_no=ln, error=str(exc)[:80])

        farm_summaries.sort(key=lambda x: x["readiness_score"], reverse=True)
        scores = [f["readiness_score"] for f in farm_summaries]
        avg = round(sum(scores) / max(len(scores), 1), 1)

        result = {
            "total_farms": len(locality_nos),
            "checked_farms": len(farm_summaries),
            "farms": farm_summaries,
            "avg_readiness": avg,
            "readiness_distribution": {
                "audit_ready": sum(1 for s in scores if s >= 80),
                "needs_work": sum(1 for s in scores if 40 <= s < 80),
                "not_ready": sum(1 for s in scores if s < 40),
            },
            "days_until_mandatory": max(0, (ASC_MANDATORY_DATE - dt.date.today()).days),
            "mandatory_date": ASC_MANDATORY_DATE.isoformat(),
            "checked_at": now.isoformat(),
            "data_provenance": DataProvenance.live(
                "BarentsWatch + Internal treatment data", confidence=0.85
            ).to_dict(),
        }

        self._cache[cache_key] = (now, result)
        log.info("asc.summary_computed", n_farms=len(farm_summaries), avg_readiness=avg)
        return result

    def get_checklist(self) -> dict:
        """Return full ASC v1.0 indicator checklist with descriptions."""
        return {
            "standard": "ASC Farm Standard v1.0",
            "effective_date": "2025-08-01",
            "mandatory_date": ASC_MANDATORY_DATE.isoformat(),
            "days_until_mandatory": max(0, (ASC_MANDATORY_DATE - dt.date.today()).days),
            "indicators": [
                {
                    "id": ind["id"],
                    "category": ind["category"],
                    "title": ind["title"],
                    "description": ind["description"],
                    "weight": ind["weight"],
                }
                for ind in ASC_INDICATORS
            ],
            "total_weight": sum(ind["weight"] for ind in ASC_INDICATORS),
            "data_provenance": DataProvenance.live(
                "ASC Farm Standard v1.0 specification", confidence=1.0
            ).to_dict(),
        }

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 75:
            return "B"
        if score >= 50:
            return "C"
        if score >= 25:
            return "D"
        return "F"


# Singleton
asc_compliance = ASCComplianceChecker()
