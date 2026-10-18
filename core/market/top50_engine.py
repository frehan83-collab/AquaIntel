"""
Top 100 Salmon Leaders — Real-Data Compilation & Scoring Engine
=================================================================
Discovers companies directly from the database (owner_company field
on Locality table, populated from Fiskeridirektoratet Akvakulturregisteret).

NO hardcoded company lists. All 123+ companies with lice data are
ranked using real 6-year weekly performance records.

For each company:
  1. Count localities and aggregate production capacity
  2. Compute composite Performance Score (0-100) from REAL lice data
  3. Generate 12-week outlook from historical seasonal patterns
  4. Build 8-week sparkline + 4-week prediction from actual data
  5. Identify risk factors from real lice levels
  6. Detect subsidiary relationships (Lerøy = 3 entities, etc.)
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import structlog
from sqlalchemy import select, func, distinct

from core.models import Locality, LiceRecord

from core.market.company_facts import volume_basis, volume_or_none

log = structlog.get_logger(__name__)

# ── Known parent groups (for subsidiary badges) ──────────────────
PARENT_GROUPS: dict[str, list[str]] = {
    "Lerøy Seafood Group": [
        "LERØY MIDT AS", "LERØY VEST AS", "LERØY AURORA AS",
        "LERØY SJØTROLL AS", "SJØTROLL HAVBRUK AS",
    ],
    "Grieg Seafood ASA": [
        "GRIEG SEAFOOD FINNMARK AS", "GRIEG SEAFOOD ROGALAND AS",
        "GRIEG SEAFOOD SHETLAND AS",
    ],
    "SalMar ASA": [
        "SALMAR FARMING AS", "SALMAR NORD AS",
        "NRS FARMING AS",
    ],
    "Mowi ASA": ["MOWI ASA"],
    "Cermaq": ["CERMAQ NORWAY AS"],
    "NTS ASA": ["MIDT NORSK HAVBRUK AS", "NTS FARMING AS"],
}

# Public tickers
PUBLIC_TICKERS: dict[str, str] = {
    "MOWI ASA": "MOWI",
    "SALMAR FARMING AS": "SALM",
    "LERØY MIDT AS": "LSG", "LERØY VEST AS": "LSG", "LERØY AURORA AS": "LSG",
    "GRIEG SEAFOOD FINNMARK AS": "GSF", "GRIEG SEAFOOD ROGALAND AS": "GSF",
    "CERMAQ NORWAY AS": None,  # owned by Mitsubishi, not listed on Oslo Børs
    "NRS FARMING AS": "SALM",  # merged into SalMar
}


@dataclass
class CompanyProfile:
    """Full profile for a salmon producer — all data from real DB records."""
    rank: int = 0
    name: str = ""
    ticker: Optional[str] = None
    is_public: bool = False
    parent_group: str = ""

    # Production. `production_volume_tonnes` is a *reported* harvest (WS-35): it is
    # None when no figure is registered for the company, because a locality count is not
    # a volume. `volume_basis` says which year, scope and source the number comes from.
    n_localities: int = 0
    production_areas: list[int] = field(default_factory=list)
    capacity_tonnes: float = 0.0
    production_volume_tonnes: float | None = None
    volume_basis: dict = field(default_factory=dict)

    # Composite Performance Score (0-100) — ALL from real data
    performance_score: float = 0.0
    score_components: dict = field(default_factory=dict)

    # 12-week outlook
    outlook_index: float = 50.0
    outlook_direction: str = "neutral"

    # Price impact
    price_impact_pct: float = 0.0
    price_impact_direction: str = "neutral"

    # Risk
    risk_level: str = "LOW"
    risk_factors: list[str] = field(default_factory=list)

    # Lice metrics — REAL data
    avg_lice: float = 0.0
    max_lice: float = 0.0
    pct_above_threshold: float = 0.0
    lice_trend: str = "stable"
    n_lice_records: int = 0

    # Peer comparison
    peer_percentile: float = 50.0

    # Sparkline + prediction — REAL data
    lice_sparkline: list[float] = field(default_factory=list)
    lice_prediction: list[float] = field(default_factory=list)


class Top50Engine:
    """
    Discovers and scores the top 100 Norwegian salmon producers
    entirely from real database records. No hardcoded company lists.
    """

    def __init__(self) -> None:
        self._cache: list[CompanyProfile] = []
        self._cache_time: Optional[dt.datetime] = None
        self._cache_ttl = dt.timedelta(minutes=30)

    async def compile_top50(self, force_refresh: bool = False) -> list[CompanyProfile]:
        """Compile top 100 salmon producers from real DB data."""
        now = dt.datetime.now(dt.UTC)
        if (
            not force_refresh
            and self._cache
            and self._cache_time
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._cache

        log.info("top100.compile_start")

        # 1. Discover all companies from DB
        companies = await self._discover_companies()
        log.info("top100.discovered", n_companies=len(companies))

        # 2. Get latest data week
        from core.async_db import get_async_session
        async with get_async_session() as s:
            latest = (await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )).first()

        if not latest:
            return []

        # 3. Compute all metrics in batch
        await self._compute_all_metrics(companies, latest[0], latest[1])

        # 4. Sort by production volume, take top 100
        # Unknown volumes sort last rather than tying with a real zero.
        companies.sort(
            key=lambda c: (
                c.production_volume_tonnes is not None,
                c.production_volume_tonnes or 0.0,
            ),
            reverse=True,
        )
        companies = companies[:100]

        # 5. Assign ranks and peer percentiles
        for i, co in enumerate(companies):
            co.rank = i + 1

        self._compute_peer_percentiles(companies)

        self._cache = companies
        self._cache_time = now
        log.info("top100.compile_done", n_companies=len(companies))
        return companies

    async def get_company_detail(self, company_name: str) -> Optional[CompanyProfile]:
        companies = await self.compile_top50()
        for co in companies:
            if co.name.lower() == company_name.lower():
                return co
        return None

    async def get_pa_leaderboard(self) -> list[dict]:
        """Production Area leaderboard — which PA has the best operators?"""
        companies = await self.compile_top50()
        pa_data: dict[int, list[CompanyProfile]] = defaultdict(list)

        for co in companies:
            for pa in co.production_areas:
                pa_data[pa].append(co)

        leaderboard = []
        for pa in sorted(pa_data.keys()):
            cos = pa_data[pa]
            avg_score = np.mean([c.performance_score for c in cos])
            avg_lice = np.mean([c.avg_lice for c in cos if c.avg_lice > 0])
            best = min(cos, key=lambda c: c.avg_lice) if cos else None
            worst = max(cos, key=lambda c: c.avg_lice) if cos else None

            leaderboard.append({
                "pa": pa,
                "n_companies": len(cos),
                "avg_score": round(float(avg_score), 1),
                "avg_lice": round(float(avg_lice), 3) if not np.isnan(avg_lice) else 0,
                "best_company": best.name if best else "",
                "best_lice": round(best.avg_lice, 3) if best else 0,
                "worst_company": worst.name if worst else "",
                "worst_lice": round(worst.avg_lice, 3) if worst else 0,
            })

        return leaderboard

    # ── Discovery ──────────────────────────────────────────────

    async def _discover_companies(self) -> list[CompanyProfile]:
        """Discover companies from Locality.owner_company + lice data."""
        from core.async_db import get_async_session
        async with get_async_session() as s:
            # Get all companies that have lice records
            result = await s.execute(
                select(
                    Locality.owner_company,
                    func.count(distinct(Locality.locality_no)),
                    func.count(distinct(LiceRecord.id)),
                )
                .join(LiceRecord, LiceRecord.locality_no == Locality.locality_no)
                .where(
                    Locality.owner_company.isnot(None),
                    Locality.owner_company != "",
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )
                .group_by(Locality.owner_company)
                .having(func.count(distinct(LiceRecord.id)) >= 10)  # minimum 10 records
                .order_by(func.count(distinct(Locality.locality_no)).desc())
            )
            company_stats = result.all()

        profiles = []
        for name, n_locs, n_records in company_stats:
            # Detect parent group
            parent = ""
            for group, subs in PARENT_GROUPS.items():
                if name.upper() in [s.upper() for s in subs]:
                    parent = group
                    break

            # Detect if public
            ticker = PUBLIC_TICKERS.get(name.upper())
            is_public = ticker is not None

            profiles.append(CompanyProfile(
                name=name,
                ticker=ticker,
                is_public=is_public,
                parent_group=parent,
                n_localities=n_locs,
                n_lice_records=n_records,
                # WS-35: a reported harvest, not `n_locs * 800`. The multiplier
                # understated the largest producers several-fold (Mowi read 113 600 t
                # against ~332 000 t harvested in Norway in 2025) and is retired.
                production_volume_tonnes=volume_or_none(name),
                volume_basis=volume_basis(name),
            ))

        return profiles

    # ── Batch metrics computation ──────────────────────────────

    async def _compute_all_metrics(
        self, companies: list[CompanyProfile], year: int, week: int
    ) -> None:
        """Compute all metrics for all companies in efficient batched queries."""
        from core.async_db import get_async_session

        async with get_async_session() as s:
            for co in companies:
                # Get this company's locality numbers
                loc_data = (await s.execute(
                    select(
                        Locality.locality_no,
                        Locality.production_area,
                    )
                    .where(Locality.owner_company == co.name)
                )).all()

                locality_nos = [r[0] for r in loc_data]
                co.production_areas = sorted(set(
                    r[1] for r in loc_data if r[1] is not None
                ))

                if not locality_nos:
                    continue

                # ── Current lice stats (find most recent data, up to 12 weeks back) ──
                # Always use the latest available data even if weeks old
                lice_vals = []
                for w_offset in range(12):
                    w_check = week - w_offset
                    y_check = year
                    while w_check < 1:
                        w_check += 52
                        y_check -= 1
                    vals = (await s.execute(
                        select(LiceRecord.avg_adult_female_lice)
                        .where(
                            LiceRecord.locality_no.in_(locality_nos),
                            LiceRecord.year == y_check,
                            LiceRecord.week == w_check,
                            LiceRecord.avg_adult_female_lice.isnot(None),
                        )
                    )).scalars().all()
                    if vals:
                        lice_vals.extend(vals)
                        break  # use most recent week with data

                if lice_vals:
                    arr = np.array(lice_vals)
                    co.avg_lice = round(float(np.mean(arr)), 4)
                    co.max_lice = round(float(np.max(arr)), 4)
                    co.pct_above_threshold = round(float(np.mean(arr > 0.5)), 3)

                # ── 8-week sparkline ───────────────────────────
                sparkline = []
                for offset in range(8, 0, -1):
                    w = week - offset
                    y = year
                    if w < 1:
                        w += 52
                        y -= 1
                    avg = (await s.execute(
                        select(func.avg(LiceRecord.avg_adult_female_lice))
                        .where(
                            LiceRecord.locality_no.in_(locality_nos),
                            LiceRecord.year == y,
                            LiceRecord.week == w,
                            LiceRecord.avg_adult_female_lice.isnot(None),
                        )
                    )).scalar()
                    sparkline.append(round(float(avg or 0), 4))
                co.lice_sparkline = sparkline

                # ── Trend detection ────────────────────────────
                if len(sparkline) >= 4:
                    recent = np.mean(sparkline[-2:])
                    earlier = np.mean(sparkline[:2])
                    if recent > earlier * 1.2:
                        co.lice_trend = "increasing"
                    elif recent < earlier * 0.8:
                        co.lice_trend = "decreasing"

                # ── 4-week prediction (historical seasonal) ────
                predictions = []
                for step in range(1, 5):
                    target_week = week + step
                    if target_week > 52:
                        target_week -= 52

                    hist_avgs = []
                    for hist_year in range(2020, year):
                        hist_avg = (await s.execute(
                            select(func.avg(LiceRecord.avg_adult_female_lice))
                            .where(
                                LiceRecord.locality_no.in_(locality_nos),
                                LiceRecord.year == hist_year,
                                LiceRecord.week == target_week,
                                LiceRecord.avg_adult_female_lice.isnot(None),
                            )
                        )).scalar()
                        if hist_avg is not None:
                            hist_avgs.append(float(hist_avg))

                    if len(hist_avgs) >= 3:
                        seasonal = float(np.median(hist_avgs))
                        if co.avg_lice > 0:
                            blend = 0.6 * seasonal + 0.4 * co.avg_lice
                        else:
                            blend = seasonal
                        predictions.append(round(max(0, blend), 4))
                    else:
                        break

                if len(predictions) >= 2:
                    co.lice_prediction = predictions

                # ── Performance Score (0-100) ──────────────────
                self._score_company(co)

                # ── Outlook index ──────────────────────────────
                self._compute_outlook(co)

                # ── Risk factors ───────────────────────────────
                self._compute_risks(co, s)

    def _score_company(self, co: CompanyProfile) -> None:
        """Composite score from REAL lice data."""
        # Lice control (lower = better)
        if co.avg_lice <= 0.05:
            lice_score = 100
        elif co.avg_lice >= 0.5:
            lice_score = 10
        else:
            lice_score = max(10, 100 - (co.avg_lice / 0.5) * 90)

        # Scale (more sites = more data confidence)
        scale_score = min(100, co.n_localities * 5)

        # Treatment avoidance
        treatment_score = max(0, 100 - co.pct_above_threshold * 200)

        # Trend stability
        if len(co.lice_sparkline) > 2:
            variance = float(np.var(co.lice_sparkline))
            stability_score = max(0, 100 - variance * 10000)
        else:
            stability_score = 50

        # Data richness (more records = more reliable)
        data_score = min(100, co.n_lice_records / 50)

        co.performance_score = round(
            0.35 * lice_score +
            0.10 * scale_score +
            0.20 * treatment_score +
            0.15 * stability_score +
            0.20 * data_score,
            1,
        )
        co.score_components = {
            "lice_control": round(lice_score, 1),
            "scale": round(scale_score, 1),
            "treatment_avoidance": round(treatment_score, 1),
            "trend_stability": round(stability_score, 1),
            "data_richness": round(data_score, 1),
        }

    def _compute_outlook(self, co: CompanyProfile) -> None:
        """12-week outlook from lice trajectory."""
        lice_impact = max(-30, min(30, (0.15 - co.avg_lice) * 100))
        treatment_impact = -co.pct_above_threshold * 40
        trend_impact = -15 if co.lice_trend == "increasing" else 10 if co.lice_trend == "decreasing" else 0

        raw = 50 + lice_impact + treatment_impact + trend_impact
        co.outlook_index = round(max(0, min(100, raw)), 1)
        co.outlook_direction = (
            "positive" if co.outlook_index >= 65
            else "negative" if co.outlook_index <= 35
            else "neutral"
        )

        # Price impact
        if co.pct_above_threshold > 0.2:
            co.price_impact_pct = round(2.5 + co.pct_above_threshold * 5, 1)
            co.price_impact_direction = "bullish"
        elif co.avg_lice < 0.1:
            co.price_impact_pct = round(-0.5, 1)
            co.price_impact_direction = "neutral"
        else:
            co.price_impact_pct = round(co.avg_lice * 3, 1)
            co.price_impact_direction = "bearish" if co.avg_lice > 0.3 else "neutral"

    def _compute_risks(self, co: CompanyProfile, s) -> None:
        """Identify real risk factors."""
        risks = []
        if co.avg_lice > 0.3:
            risks.append("Elevated lice levels")
        if co.pct_above_threshold > 0.15:
            risks.append(f"{co.pct_above_threshold:.0%} farms above regulatory limit")
        if co.max_lice > 1.0:
            risks.append(f"Peak lice {co.max_lice:.2f} — forced treatment likely")
        if co.lice_trend == "increasing":
            risks.append("Worsening lice trend")
        if co.n_localities < 3:
            risks.append("Low site diversification")

        co.risk_factors = risks
        if len(risks) >= 3 or any("forced treatment" in r for r in risks):
            co.risk_level = "CRITICAL"
        elif len(risks) >= 2:
            co.risk_level = "HIGH"
        elif len(risks) >= 1:
            co.risk_level = "MEDIUM"
        else:
            co.risk_level = "LOW"

    def _compute_peer_percentiles(self, companies: list[CompanyProfile]) -> None:
        if not companies:
            return
        scores = [c.performance_score for c in companies]
        for co in companies:
            better = sum(1 for s in scores if s < co.performance_score)
            co.peer_percentile = round(better / len(scores) * 100, 1)

    # ── Serialization ──────────────────────────────────────────

    def to_api_response(self, companies: list[CompanyProfile]) -> list[dict]:
        return [
            {
                "rank": co.rank,
                "name": co.name,
                "ticker": co.ticker,
                "is_public": co.is_public,
                "parent_group": co.parent_group,
                "n_localities": co.n_localities,
                "production_areas": co.production_areas,
                "production_volume_tonnes": (
                    round(co.production_volume_tonnes)
                    if co.production_volume_tonnes is not None
                    else None
                ),
                "volume_basis": co.volume_basis,
                "performance_score": co.performance_score,
                "score_components": co.score_components,
                "outlook_index": co.outlook_index,
                "outlook_direction": co.outlook_direction,
                "price_impact_pct": co.price_impact_pct,
                "price_impact_direction": co.price_impact_direction,
                "risk_level": co.risk_level,
                "risk_factors": co.risk_factors,
                "avg_lice": co.avg_lice,
                "max_lice": co.max_lice,
                "pct_above_threshold": co.pct_above_threshold,
                "lice_trend": co.lice_trend,
                "n_lice_records": co.n_lice_records,
                "lice_sparkline": co.lice_sparkline,
                "lice_prediction": co.lice_prediction,
                "peer_percentile": co.peer_percentile,
            }
            for co in companies
        ]


# Singleton
top50_engine = Top50Engine()
