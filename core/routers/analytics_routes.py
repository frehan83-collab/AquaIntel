"""
Analytics, benchmarking, leaders, production, anomaly, and morning brief routes.
Extracted from core/api.py (Session 10 — Router Wave 4).
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func

from core.async_db import get_async_session
from core.models import LiceRecord, Locality, AuditLog
from core.cache import cached
from core.schemas import MorningBriefResponse

router = APIRouter(tags=["analytics"])


# ── Year-over-Year Analytics ─────────────────────────────────────────

@router.get("/api/analytics/yoy-comparison")
@cached(ttl=600, key_prefix="yoy")
async def yoy_comparison(metric: str = "lice", production_area: int = 0):
    """Year-over-year comparison for lice, price, or disease metrics."""
    today = dt.date.today()
    cur_year = today.year
    prev_year = cur_year - 1
    two_yr = cur_year - 2

    if metric == "lice":
        async with get_async_session() as s:
            async def _lice_by_year(yr: int, pa: int):
                q = (
                    select(
                        LiceRecord.week,
                        func.avg(LiceRecord.avg_adult_female_lice).label("value"),
                    )
                    .where(
                        LiceRecord.year == yr,
                        LiceRecord.avg_adult_female_lice.isnot(None),
                    )
                )
                if pa > 0:
                    q = q.join(Locality, Locality.locality_no == LiceRecord.locality_no).where(
                        Locality.production_area == pa
                    )
                q = q.group_by(LiceRecord.week).order_by(LiceRecord.week)
                rows = (await s.execute(q)).all()
                return [{"week": r.week, "value": round(float(r.value), 4)} for r in rows]

            return {
                "metric": "lice",
                "production_area": production_area,
                "current_year": await _lice_by_year(cur_year, production_area),
                "previous_year": await _lice_by_year(prev_year, production_area),
                "two_years_ago": await _lice_by_year(two_yr, production_area),
                "years": [cur_year, prev_year, two_yr],
            }

    elif metric == "price":
        from core.models import SSBWeeklyPrice
        async with get_async_session() as s:
            async def _price_by_year(yr: int):
                rows = (await s.execute(
                    select(SSBWeeklyPrice.week, SSBWeeklyPrice.price_nok_kg)
                    .where(SSBWeeklyPrice.year == yr)
                    .order_by(SSBWeeklyPrice.week)
                )).all()
                return [{"week": r.week, "value": round(float(r.price_nok_kg), 2)} for r in rows]

            return {
                "metric": "price",
                "production_area": 0,
                "current_year": await _price_by_year(cur_year),
                "previous_year": await _price_by_year(prev_year),
                "two_years_ago": await _price_by_year(two_yr),
                "years": [cur_year, prev_year, two_yr],
            }

    elif metric == "disease":
        from core.market.mattilsynet_client import mattilsynet_client
        try:
            cases = await mattilsynet_client.fetch_disease_cases(limit=500)
        except Exception:
            cases = []

        from collections import Counter
        def _count_by_month(yr: int):
            month_counts: Counter = Counter()
            for c in cases:
                d = getattr(c, "detected_date", None) or getattr(c, "date", None)
                if d and hasattr(d, "year") and d.year == yr:
                    month_counts[d.month] += 1
            return [{"week": m, "value": month_counts.get(m, 0)} for m in range(1, 13)]

        return {
            "metric": "disease",
            "production_area": 0,
            "current_year": _count_by_month(cur_year),
            "previous_year": _count_by_month(prev_year),
            "two_years_ago": _count_by_month(two_yr),
            "years": [cur_year, prev_year, two_yr],
        }

    elif metric == "sst":
        async with get_async_session() as s:
            async def _sst_by_year(yr: int, pa: int):
                q = (
                    select(
                        LiceRecord.week,
                        func.avg(LiceRecord.sea_temp_c).label("value"),
                    )
                    .where(
                        LiceRecord.year == yr,
                        LiceRecord.sea_temp_c.isnot(None),
                    )
                )
                if pa > 0:
                    q = q.join(Locality, Locality.locality_no == LiceRecord.locality_no).where(
                        Locality.production_area == pa
                    )
                q = q.group_by(LiceRecord.week).order_by(LiceRecord.week)
                rows = (await s.execute(q)).all()
                return [{"week": r.week, "value": round(float(r.value), 2)} for r in rows]

            return {
                "metric": "sst",
                "production_area": production_area,
                "current_year": await _sst_by_year(cur_year, production_area),
                "previous_year": await _sst_by_year(prev_year, production_area),
                "two_years_ago": await _sst_by_year(two_yr, production_area),
                "years": [cur_year, prev_year, two_yr],
            }

    else:
        raise HTTPException(400, f"Unknown metric: {metric}. Use lice, price, disease, or sst.")


# ── Peer Benchmarking ────────────────────────────────────────────────

@router.get("/api/benchmark/leaderboard")
async def benchmark_leaderboard(limit: int = Query(20, ge=1, le=1000)):
    """Top performers by overall peer percentile."""
    from core.market.benchmarking import benchmarking_engine
    from core.market.data_provenance import DataProvenance
    return {
        "data": await benchmarking_engine.get_leaderboard(min(limit, 100)),
        "data_provenance": DataProvenance.live(
            "Derived analytics (lice + production + ESG)", confidence=0.75
        ).to_dict(),
    }


@router.get("/api/benchmark/company/{company_name}")
async def benchmark_company(company_name: str):
    """Full peer benchmark report for a specific company."""
    import urllib.parse
    from core.market.benchmarking import benchmarking_engine
    decoded = urllib.parse.unquote(company_name)
    result = await benchmarking_engine.get_company(decoded)
    if not result:
        raise HTTPException(404, f"Company not found: {decoded}")
    return result


@router.get("/api/benchmark/pa/{pa}")
async def benchmark_pa(pa: int):
    """Peer rankings within a specific production area."""
    from core.market.benchmarking import benchmarking_engine
    return await benchmarking_engine.get_pa_leaderboard(pa)


@router.get("/api/benchmark/summary")
async def benchmark_summary():
    """Industry-wide benchmark statistics."""
    from core.market.benchmarking import benchmarking_engine
    return await benchmarking_engine.get_summary()


# ── Federated Benchmarking (Privacy-Preserving) ─────────────────────

@router.get("/api/federated/company/{company_name}")
async def federated_company(company_name: str):
    from core.market.federated_benchmark import federated_benchmark_engine
    return await federated_benchmark_engine.get_company_report(company_name)


@router.get("/api/federated/cohorts")
async def federated_cohorts():
    from core.market.federated_benchmark import federated_benchmark_engine
    return await federated_benchmark_engine.get_cohorts()


@router.get("/api/federated/cohort/{cohort_id}/summary")
async def federated_cohort_summary(cohort_id: str):
    from core.market.federated_benchmark import federated_benchmark_engine
    return await federated_benchmark_engine.get_cohort_summary(cohort_id)


@router.get("/api/federated/privacy-info")
async def federated_privacy_info():
    from core.market.federated_benchmark import federated_benchmark_engine
    return federated_benchmark_engine.get_privacy_info()


# ── Top 100 Leaders ──────────────────────────────────────────────────

@router.get("/api/leaders/top100")
@router.get("/api/leaders/top30")
async def leaders_top30():
    """Top 30 Norwegian salmon producers with performance scores."""
    from core.market.top50_engine import top50_engine
    from core.market.data_provenance import DataProvenance
    companies = await top50_engine.compile_top50()
    return {
        "data": top50_engine.to_api_response(companies),
        "data_provenance": DataProvenance.live(
            "BarentsWatch + company registry", confidence=0.85
        ).to_dict(),
    }


@router.get("/api/leaders/company/{company_name}")
async def leader_detail(company_name: str):
    """Detailed profile for a single company."""
    from core.market.top50_engine import top50_engine
    import urllib.parse
    decoded = urllib.parse.unquote(company_name)
    co = await top50_engine.get_company_detail(decoded)
    if not co:
        raise HTTPException(404, f"Company not found: {decoded}")
    return top50_engine.to_api_response([co])[0]


@router.get("/api/leaders/pa-leaderboard")
async def pa_leaderboard():
    """Production Area leaderboard."""
    from core.market.top50_engine import top50_engine
    return await top50_engine.get_pa_leaderboard()


# ── Production Data ──────────────────────────────────────────────────

@router.get("/api/production/summary")
async def production_summary():
    """Latest annual production summary from official Fiskeridirektoratet data."""
    from core.market.data_provenance import from_records
    from core.market.fiskeridir_data import fiskeridir_data
    summary = fiskeridir_data.get_latest_summary()
    if isinstance(summary, dict):
        summary.setdefault(
            "data_provenance",
            from_records(
                [summary] if summary else [],
                live_source="Fiskeridirektoratet production statistics (open data)",
                degraded_source="Fiskeridirektoratet production statistics",
                reason="Fiskeridirektoratet dataset not loaded — summary is empty",
            ).to_dict(),
        )
    return summary


@router.get("/api/production/annual")
async def production_annual():
    """Annual production time series (2005-2024) from official data."""
    from core.market.fiskeridir_data import fiskeridir_data
    return fiskeridir_data.get_annual()


@router.get("/api/production/monthly")
async def production_monthly(year: int | None = None):
    """Monthly production data (biomass, harvest, feed, mortality, smolt)."""
    from core.market.fiskeridir_data import fiskeridir_data
    return fiskeridir_data.get_monthly(year)


@router.get("/api/production/by-county")
async def production_by_county():
    """Latest year production data by county."""
    from core.market.fiskeridir_data import fiskeridir_data
    return fiskeridir_data.get_by_county()


# ── Anomaly Detection ────────────────────────────────────────────────

@router.get("/api/anomaly/scores")
async def anomaly_scores():
    """Multi-modal anomaly detection — composite risk score 0-100."""
    from core.market.anomaly_engine import anomaly_engine
    from core.market.data_provenance import DataProvenance
    report = await anomaly_engine.compute()
    result = anomaly_engine.to_dict(report)
    result["data_provenance"] = DataProvenance.live(
        "BarentsWatch lice + PyOD anomaly detection",
        confidence=0.75,
    ).to_dict()
    return result


@router.get("/api/anomaly/alerts")
async def anomaly_alerts():
    """High-severity anomaly alerts only."""
    from core.market.anomaly_engine import anomaly_engine
    from core.market.data_provenance import DataProvenance
    await anomaly_engine.compute()
    alerts = anomaly_engine.get_alerts()
    return {
        "alerts": alerts,
        "data_provenance": DataProvenance.degraded(
            "BarentsWatch lice + PyOD anomaly detection",
            reason=(
                "detector output — derived from the current lice series, not a "
                "reported regulatory finding"
            ),
            confidence=0.5,
        ).to_dict(),
    }


# ── Morning Brief ────────────────────────────────────────────────────

@router.get("/api/brief", response_model=MorningBriefResponse)
async def morning_brief():
    """Daily market intelligence digest."""
    from core.market.morning_brief import morning_brief_engine
    from core.market.data_provenance import DataProvenance
    brief = await morning_brief_engine.generate()
    result = morning_brief_engine.to_dict(brief)
    result["data_provenance"] = DataProvenance.live(
        "BarentsWatch + SSB + FRED + Mattilsynet + RSS",
        confidence=0.85,
    ).to_dict()
    return result


# ── Self-Improvement ─────────────────────────────────────────────────

@router.get("/api/self-improvement/proposals")
async def self_improvement_proposals():
    """Self-Improvement Agent proposals and accuracy metrics."""
    from core.market.data_provenance import DataProvenance
    async with get_async_session() as s:
        logs = (await s.execute(
            select(AuditLog)
            .where(AuditLog.action == "self_evolve")
            .order_by(AuditLog.timestamp.desc())
            .limit(10)
        )).scalars().all()

    return {
        "audits": [
            {
                "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                "detail": l.details,
            }
            for l in logs
        ],
        "data_provenance": DataProvenance.degraded(
            "Internal self-improvement audit log",
            reason=(
                "proposals are derived from the platform's own audit trail — "
                "internal model suggestions, not external findings"
            ),
            confidence=0.4,
        ).to_dict(),
    }


# ── Lice Emission Quota Tracker ─────────────────────────────────────

@router.get("/api/analytics/lice-emission/{locality_no}")
@cached(ttl=1800, key_prefix="lice_emission")
async def lice_emission_estimate(locality_no: int):
    """Estimate lice emission from a single farm based on lice counts, biomass, and water flow.

    PROJECTED: Regulation not yet finalized (targeted 2026-2028).
    """
    from core.market.lice_quota_tracker import lice_quota_tracker
    return await lice_quota_tracker.estimate_emission(locality_no)


@router.get("/api/analytics/lice-quota/pa/{pa}")
@cached(ttl=1800, key_prefix="lice_quota_pa")
async def lice_quota_pa_status(pa: int):
    """Current estimated emission vs hypothetical quota for a production area.

    PROJECTED: Regulation not yet finalized (targeted 2026-2028).
    """
    from core.market.lice_quota_tracker import lice_quota_tracker
    result = await lice_quota_tracker.pa_quota_status(pa)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/api/analytics/lice-quota/national")
@cached(ttl=1800, key_prefix="lice_quota_national")
async def lice_quota_national():
    """National emission overview — all 13 PAs with emission estimates and utilization.

    PROJECTED: Regulation not yet finalized (targeted 2026-2028).
    """
    from core.market.lice_quota_tracker import lice_quota_tracker
    return await lice_quota_tracker.national_emission_overview()
