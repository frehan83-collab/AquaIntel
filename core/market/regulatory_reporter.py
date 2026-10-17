"""
Regulatory Reporting Engine
=============================
Automates compliance report generation for Norwegian aquaculture farms.
- Weekly lice reports (Mattilsynet format)
- Monthly treatment summaries
- Quarterly biomass/production reports
- Compliance calendar with deadlines

Reference: Akvakulturforskriften (Norwegian Aquaculture Regulation)
Mattilsynet weekly lice reporting: mandatory for all active marine localities.
Treatment summaries: required monthly for farms with chemical/mechanical treatments.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, asdict
from typing import Optional

import structlog
from sqlalchemy import select, func

from core.async_db import get_async_session
from core.source_lineage import lineage_for, provenance_for

from core.regulatory_facts import (
    LICE_LIMIT_DEFAULT,
    LICE_LIMIT_SPRING,
    LICE_REPORT_DUE_WEEKDAY,
    LiceLimit,
    breaches_limit,
    lice_limit,
)

log = structlog.get_logger(__name__)

# ── Regulatory constants ────────────────────────────────────────────
# Weekly lice count reported no later than Tuesday of the following week
# (lakselusforskriften § 10; see core/regulatory_facts.py)
LICE_REPORT_DUE_DAY = LICE_REPORT_DUE_WEEKDAY  # Tuesday (0=Monday)
# Monthly treatment summary: due by 10th of following month
TREATMENT_SUMMARY_DUE_DAY = 10
# Legal adult-female lice limits (lakselusforskriften § 8): 0.5, and 0.2 in the
# spring window (weeks 16-21 in Nord-Trøndelag and southwards, weeks 21-26 in
# Nordland, Troms and Finnmark). One definition: core/regulatory_facts.py.
LICE_THRESHOLD_ADULT_FEMALE = LICE_LIMIT_DEFAULT
LICE_THRESHOLD_SPRING = LICE_LIMIT_SPRING


def applicable_lice_limit(
    pa: Optional[int], week: Optional[int],
    municipality: Optional[str] = None, county: Optional[str] = None,
) -> LiceLimit:
    """The legal limit for a site in an ISO week (the facts module decides)."""
    return lice_limit(pa, week, municipality=municipality, county=county)


def assess_lice_count(
    avg_adult_female: float, pa: Optional[int], week: Optional[int],
    municipality: Optional[str] = None, county: Optional[str] = None,
) -> dict:
    """Judge one weekly count against § 8.

    `exceeds` is None when the site's region is unknown inside a spring window
    and the count lies between 0.2 and 0.5: the legal answer then depends on the
    county, and a regulatory report must not assert a breach it cannot establish.
    """
    limit = applicable_lice_limit(pa, week, municipality, county)
    warnings: list[str] = []
    if limit.in_spring_window:
        warnings.append(f"Spring period: limit {limit.limit} applies ({limit.rule}, W{week})")
    if limit.established:
        exceeds: Optional[bool] = breaches_limit(avg_adult_female, limit.limit)
    elif breaches_limit(avg_adult_female, LICE_LIMIT_DEFAULT):
        exceeds = True          # a breach under either window
    elif breaches_limit(avg_adult_female, limit.limit):
        exceeds = None          # depends on the county
        warnings.append(
            f"Adult female lice {avg_adult_female:.2f}: breach only if the site is in the "
            f"northern/southern window that applies this week; region unknown"
        )
    else:
        exceeds = False
    return {
        "threshold": limit.limit,
        "threshold_established": limit.established,
        "threshold_rule": limit.rule,
        "threshold_source": limit.source_url,
        "exceeds_threshold": exceeds,
        "warnings": warnings,
    }


@dataclass
class RegulatoryDeadline:
    """A single regulatory reporting deadline."""
    report_type: str  # weekly_lice | monthly_treatment | quarterly_biomass
    due_date: str  # ISO date string
    locality_no: Optional[int] = None  # None = all localities
    status: str = "pending"  # pending | submitted | overdue
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RegulatoryReport:
    """A generated regulatory report ready for submission."""
    report_type: str  # weekly_lice | monthly_treatment | quarterly_biomass
    locality_no: int
    period: str  # e.g. "2026-W15" or "2026-03"
    generated_at: str  # ISO datetime
    data: dict = field(default_factory=dict)
    format: str = "json"  # csv | json
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class RegulatoryReporter:
    """
    Automates generation and validation of Norwegian aquaculture compliance reports.

    Pulls data from core.models (LiceRecord, Locality, TreatmentOutcome) via core.async_db.
    """

    async def get_upcoming_deadlines(
        self, locality_no: int | None = None, days_ahead: int = 30
    ) -> list[RegulatoryDeadline]:
        """
        Returns next 30 days of regulatory deadlines.

        Generates weekly lice deadlines (every Tuesday, § 10) and monthly treatment
        summary deadlines (10th of each month) for the requested period.
        """
        today = dt.date.today()
        end_date = today + dt.timedelta(days=days_ahead)
        deadlines: list[RegulatoryDeadline] = []

        # ── Weekly lice report deadlines (every Tuesday, § 10) ──────
        current = today
        while current <= end_date:
            if current.weekday() == LICE_REPORT_DUE_DAY:
                # This Tuesday is the deadline for the previous week's data
                report_week = current - dt.timedelta(days=current.weekday() + 7)
                iso_cal = report_week.isocalendar()
                status = "overdue" if current < today else "pending"
                deadlines.append(RegulatoryDeadline(
                    report_type="weekly_lice",
                    due_date=current.isoformat(),
                    locality_no=locality_no,
                    status=status,
                    description=f"Weekly lice report for W{iso_cal.week:02d}/{iso_cal.year} (Mattilsynet)",
                ))
            current += dt.timedelta(days=1)

        # ── Monthly treatment summary deadlines (10th of month) ─────
        month_start = today.replace(day=1)
        for i in range(3):  # check next 3 months
            year = month_start.year + (month_start.month + i - 1) // 12
            month = (month_start.month + i - 1) % 12 + 1
            due = dt.date(year, month, min(TREATMENT_SUMMARY_DUE_DAY, 28))
            if today <= due <= end_date:
                # Report for previous month
                prev_month = month - 1 if month > 1 else 12
                prev_year = year if month > 1 else year - 1
                deadlines.append(RegulatoryDeadline(
                    report_type="monthly_treatment",
                    due_date=due.isoformat(),
                    locality_no=locality_no,
                    status="pending",
                    description=f"Monthly treatment summary for {prev_year}-{prev_month:02d}",
                ))

        # ── Quarterly biomass reporting (Jan, Apr, Jul, Oct) ────────
        quarter_months = [1, 4, 7, 10]
        for qm in quarter_months:
            due = dt.date(today.year, qm, 15)
            if due < today:
                due = due.replace(year=today.year + 1) if qm < today.month else due
            if today <= due <= end_date:
                q_num = (qm - 1) // 3 + 1
                deadlines.append(RegulatoryDeadline(
                    report_type="quarterly_biomass",
                    due_date=due.isoformat(),
                    locality_no=locality_no,
                    status="pending",
                    description=f"Quarterly biomass report Q{q_num} {due.year}",
                ))

        deadlines.sort(key=lambda d: d.due_date)
        return deadlines

    async def generate_weekly_lice_report(
        self, locality_no: int, week: int, year: int
    ) -> RegulatoryReport:
        """
        Generate weekly lice report in Mattilsynet format.

        Pulls from LiceRecord table for the specified locality/week/year.
        Validates thresholds and flags warnings.
        """
        from core.models import LiceRecord, Locality

        warnings: list[str] = []
        data: dict = {}

        async with get_async_session() as s:
            # Get locality info
            loc_result = (await s.execute(
                select(Locality).where(Locality.locality_no == locality_no)
            )).scalars().first()

            locality_name = loc_result.name if loc_result else f"Locality {locality_no}"
            pa = loc_result.production_area if loc_result else None

            # Get lice record for specified week
            record = (await s.execute(
                select(LiceRecord).where(
                    LiceRecord.locality_no == locality_no,
                    LiceRecord.year == year,
                    LiceRecord.week == week,
                )
            )).scalars().first()

            if not record:
                warnings.append(f"No lice data found for locality {locality_no}, week {week}/{year}")
                data = {
                    "locality_no": locality_no,
                    "locality_name": locality_name,
                    "production_area": pa,
                    "year": year,
                    "week": week,
                    "status": "missing_data",
                }
            else:
                avg_af = float(record.avg_adult_female_lice or 0)
                avg_mobile = float(record.avg_mobile_lice or 0)
                avg_stationary = float(record.avg_stationary_lice or 0)

                # Judge the count against § 8 (equal to the limit is a breach)
                verdict = assess_lice_count(
                    avg_af, pa, week,
                    getattr(loc_result, "municipality", None),
                    getattr(loc_result, "county", None),
                )
                threshold = verdict["threshold"]
                exceeds = verdict["exceeds_threshold"]
                warnings.extend(verdict["warnings"])

                if exceeds:
                    warnings.append(
                        f"Adult female lice {avg_af:.2f} EXCEEDS threshold {threshold}"
                    )

                data = {
                    "locality_no": locality_no,
                    "locality_name": locality_name,
                    "production_area": pa,
                    "year": year,
                    "week": week,
                    "avg_adult_female_lice": round(avg_af, 4),
                    "avg_mobile_lice": round(avg_mobile, 4),
                    "avg_stationary_lice": round(avg_stationary, 4),
                    "sea_temperature_c": float(record.sea_temp_c) if record.sea_temp_c else None,
                    "has_cleaner_fish": record.has_cleaner_fish,
                    "threshold": threshold,
                    "threshold_established": verdict["threshold_established"],
                    "threshold_rule": verdict["threshold_rule"],
                    "threshold_source": verdict["threshold_source"],
                    "exceeds_threshold": exceeds,
                    "status": "complete",
                }

        report = RegulatoryReport(
            report_type="weekly_lice",
            locality_no=locality_no,
            period=f"{year}-W{week:02d}",
            generated_at=dt.datetime.now(dt.UTC).isoformat(),
            data=data,
            warnings=warnings,
        )

        log.info(
            "regulatory.weekly_lice_report",
            locality_no=locality_no,
            week=week,
            year=year,
            warnings_count=len(warnings),
        )
        return report

    async def generate_monthly_treatment_summary(
        self, locality_no: int, year: int, month: int
    ) -> RegulatoryReport:
        """
        Generate monthly treatment summary report.

        Pulls from TreatmentOutcome table for the specified locality/month/year.
        Aggregates by treatment method with efficacy statistics.
        """
        from core.models import TreatmentOutcome, Locality

        warnings: list[str] = []

        async with get_async_session() as s:
            # Get locality info
            loc_result = (await s.execute(
                select(Locality).where(Locality.locality_no == locality_no)
            )).scalars().first()
            locality_name = loc_result.name if loc_result else f"Locality {locality_no}"

            # Date range for the month
            month_start = dt.datetime(year, month, 1, tzinfo=dt.UTC)
            if month == 12:
                month_end = dt.datetime(year + 1, 1, 1, tzinfo=dt.UTC)
            else:
                month_end = dt.datetime(year, month + 1, 1, tzinfo=dt.UTC)

            # Fetch treatment outcomes for this month
            outcomes = (await s.execute(
                select(TreatmentOutcome).where(
                    TreatmentOutcome.locality_no == locality_no,
                    TreatmentOutcome.treatment_date >= month_start,
                    TreatmentOutcome.treatment_date < month_end,
                )
            )).scalars().all()

        if not outcomes:
            warnings.append(f"No treatment records for locality {locality_no} in {year}-{month:02d}")

        # Aggregate by method
        method_summary: dict[str, dict] = {}
        total_cost = 0.0
        for o in outcomes:
            m = o.method or "unknown"
            if m not in method_summary:
                method_summary[m] = {
                    "count": 0,
                    "avg_pre_lice": 0.0,
                    "avg_post_lice": 0.0,
                    "total_cost_nok": 0.0,
                    "avg_reduction_pct": 0.0,
                }
            ms = method_summary[m]
            ms["count"] += 1
            pre = float(o.pre_lice_count or 0)
            post = float(o.post_lice_count or 0)
            ms["avg_pre_lice"] += pre
            ms["avg_post_lice"] += post
            cost = float(o.cost_nok or 0)
            ms["total_cost_nok"] += cost
            total_cost += cost
            if pre > 0:
                ms["avg_reduction_pct"] += (1 - post / pre) * 100

        # Compute averages
        for m, ms in method_summary.items():
            n = ms["count"]
            if n > 0:
                ms["avg_pre_lice"] = round(ms["avg_pre_lice"] / n, 3)
                ms["avg_post_lice"] = round(ms["avg_post_lice"] / n, 3)
                ms["avg_reduction_pct"] = round(ms["avg_reduction_pct"] / n, 1)
                ms["total_cost_nok"] = round(ms["total_cost_nok"], 0)

        data = {
            "locality_no": locality_no,
            "locality_name": locality_name,
            "year": year,
            "month": month,
            "period": f"{year}-{month:02d}",
            "total_treatments": len(outcomes),
            "total_cost_nok": round(total_cost, 0),
            "methods": method_summary,
            "status": "complete" if outcomes else "no_data",
        }

        report = RegulatoryReport(
            report_type="monthly_treatment",
            locality_no=locality_no,
            period=f"{year}-{month:02d}",
            generated_at=dt.datetime.now(dt.UTC).isoformat(),
            data=data,
            warnings=warnings,
        )

        log.info(
            "regulatory.monthly_treatment_summary",
            locality_no=locality_no,
            year=year,
            month=month,
            treatments=len(outcomes),
        )
        return report

    async def generate_compliance_score(self, locality_no: int) -> dict:
        """
        Compute a compliance health score for a farm.

        Checks:
        - On-time reporting rate (weekly lice data completeness for last 12 weeks)
        - Data completeness (all required fields populated)
        - Discrepancy count (out-of-range values or missing records)
        - Treatment documentation rate
        """
        from core.models import LiceRecord, TreatmentOutcome

        today = dt.date.today()
        iso = today.isocalendar()
        current_week = iso.week
        current_year = iso.year

        async with get_async_session() as s:
            # ── Lice reporting completeness (last 12 weeks) ─────────
            weeks_with_data = (await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.locality_no == locality_no,
                    LiceRecord.year == current_year,
                    LiceRecord.week >= max(1, current_week - 12),
                )
            )).scalar() or 0

            expected_weeks = min(12, current_week)
            on_time_rate = round(weeks_with_data / max(expected_weeks, 1) * 100, 1)

            # ── Data completeness (check for null fields in recent records) ──
            total_records = (await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.locality_no == locality_no,
                    LiceRecord.year >= current_year - 1,
                )
            )).scalar() or 0

            null_fields = (await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.locality_no == locality_no,
                    LiceRecord.year >= current_year - 1,
                    LiceRecord.avg_adult_female_lice.is_(None),
                )
            )).scalar() or 0

            data_completeness = round(
                (1 - null_fields / max(total_records, 1)) * 100, 1
            )

            # ── Discrepancies (out-of-range values) ─────────────────
            discrepancies = (await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.locality_no == locality_no,
                    LiceRecord.year >= current_year - 1,
                    LiceRecord.avg_adult_female_lice > 10.0,  # suspiciously high
                )
            )).scalar() or 0

            # ── Treatment documentation rate ────────────────────────
            treatment_count = (await s.execute(
                select(func.count(TreatmentOutcome.id)).where(
                    TreatmentOutcome.locality_no == locality_no,
                )
            )).scalar() or 0

            # WS-14: lineage of the two-year lice window the score is computed from.
            lineage = await lineage_for(
                s,
                LiceRecord.locality_no == locality_no,
                LiceRecord.year >= current_year - 1,
            )

        # Composite score (weighted average)
        composite = round(
            on_time_rate * 0.40
            + data_completeness * 0.30
            + max(0, 100 - discrepancies * 10) * 0.15
            + min(100, treatment_count * 10) * 0.15,
            1,
        )

        # Grade
        if composite >= 90:
            grade = "A"
            status = "excellent"
        elif composite >= 75:
            grade = "B"
            status = "good"
        elif composite >= 60:
            grade = "C"
            status = "needs_improvement"
        else:
            grade = "D"
            status = "at_risk"

        return {
            "locality_no": locality_no,
            "compliance_score": composite,
            "grade": grade,
            "status": status,
            "on_time_rate": on_time_rate,
            "data_completeness": data_completeness,
            "discrepancy_count": discrepancies,
            "treatment_documentation_count": treatment_count,
            "weeks_with_data": weeks_with_data,
            "expected_weeks": expected_weeks,
            "lineage": lineage,
            "data_provenance": provenance_for(
                lineage, "Internal compliance database + BarentsWatch", 0.90
            ),
        }

    async def validate_report(self, report: RegulatoryReport) -> list[str]:
        """
        Validate a generated report for completeness and data quality.

        Checks:
        - Required fields present
        - Values within expected ranges
        - Period format valid
        """
        errors: list[str] = []

        if not report.data:
            errors.append("Report data is empty")
            return errors

        if report.report_type == "weekly_lice":
            required = ["locality_no", "year", "week"]
            for f in required:
                if f not in report.data:
                    errors.append(f"Missing required field: {f}")

            af = report.data.get("avg_adult_female_lice")
            if af is not None and (af < 0 or af > 50):
                errors.append(f"Adult female lice count {af} is out of expected range [0, 50]")

            temp = report.data.get("sea_temperature_c")
            if temp is not None and (temp < -2 or temp > 30):
                errors.append(f"Sea temperature {temp} is out of expected range [-2, 30]")

        elif report.report_type == "monthly_treatment":
            required = ["locality_no", "year", "month"]
            for f in required:
                if f not in report.data:
                    errors.append(f"Missing required field: {f}")

            cost = report.data.get("total_cost_nok")
            if cost is not None and cost < 0:
                errors.append(f"Total cost {cost} cannot be negative")

        return errors


# ── Singleton ───────────────────────────────────────────────────────
regulatory_reporter = RegulatoryReporter()
