"""
Correlation Engine Agent
========================
Computes weighted impact scores per company by:
  1. Aggregating lice levels across owned localities
  2. Checking against regulatory thresholds (0.5 adult female lice)
  3. Estimating harvest-reduction risk
  4. Correlating with historical price movements

Output: ImpactScore objects stored in memory / DB for the signal generator.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import select, func

from agents.base import BaseAgent
from core.models import LiceRecord, CompanyExposure, AuditLog
from core.async_db import get_async_session

# ── Regulatory thresholds ────────────────────────────────────────────
LICE_THRESHOLD_ADULT_FEMALE = 0.5   # Norwegian regulatory limit
LICE_WARNING_LEVEL = 0.2            # internal early-warning
HARVEST_REDUCTION_FACTOR = 0.15     # est. % harvest loss per 0.1 lice above threshold


@dataclass
class ImpactScore:
    ticker: str
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    avg_lice: float = 0.0
    max_lice: float = 0.0
    pct_above_threshold: float = 0.0
    weighted_lice_index: float = 0.0
    estimated_harvest_reduction_pct: float = 0.0
    composite_score: float = 0.0  # 0-1 final signal strength
    n_localities: int = 0
    details: str = ""


class CorrelationEngineAgent(BaseAgent):
    name = "correlation_engine"
    interval_seconds = 900  # runs after data ingest

    def __init__(self) -> None:
        super().__init__()
        self.latest_scores: dict[str, ImpactScore] = {}

    async def tick(self) -> None:
        self.log.info("correlation.tick_start")

        tickers = ["MOWI", "SALM", "LSG", "GSF"]
        for ticker in tickers:
            score = await self._compute_score(ticker)
            self.latest_scores[ticker] = score
            self.log.info(
                "correlation.score",
                ticker=ticker,
                composite=round(score.composite_score, 4),
                avg_lice=round(score.avg_lice, 3),
                harvest_reduction=round(score.estimated_harvest_reduction_pct, 2),
            )

        await self._audit()

    @staticmethod
    async def _compute_score(ticker: str) -> ImpactScore:
        """Aggregate lice data for a company and produce an impact score."""
        async with get_async_session() as s:
            # Get company's localities
            result = await s.execute(
                select(CompanyExposure).where(CompanyExposure.ticker == ticker)
            )
            exposures = result.scalars().all()

            if not exposures:
                return ImpactScore(ticker=ticker, details="No locality mapping")

            locality_nos = [e.locality_no for e in exposures]
            weights = {e.locality_no: e.weight for e in exposures}

            # Get most recent lice records (last 4 weeks)
            now = dt.datetime.now(dt.UTC)
            year, week, _ = now.isocalendar()
            recent_weeks = [(year, max(1, week - i)) for i in range(4)]

            result = await s.execute(
                select(LiceRecord).where(
                    LiceRecord.locality_no.in_(locality_nos),
                    LiceRecord.year == year,
                    LiceRecord.week >= max(1, week - 3),
                )
            )
            records = result.scalars().all()

        if not records:
            return ImpactScore(
                ticker=ticker,
                n_localities=len(locality_nos),
                details="No recent lice data",
            )

        # Weighted lice values
        lice_values = []
        weighted_values = []
        above_threshold = 0

        for rec in records:
            val = rec.avg_adult_female_lice or 0.0
            w = weights.get(rec.locality_no, 1.0)
            lice_values.append(val)
            weighted_values.append(val * w)
            if val > LICE_THRESHOLD_ADULT_FEMALE:
                above_threshold += 1

        arr = np.array(lice_values)
        warr = np.array(weighted_values)

        avg_lice = float(np.mean(arr))
        max_lice = float(np.max(arr))
        pct_above = above_threshold / len(records) if records else 0.0
        weighted_index = float(np.mean(warr))

        # Estimated harvest reduction
        excess = max(0.0, avg_lice - LICE_THRESHOLD_ADULT_FEMALE)
        harvest_reduction = min(excess / 0.1 * HARVEST_REDUCTION_FACTOR, 0.5)

        # Composite score (0-1): higher = more bearish signal
        # Components: lice severity, breadth, trend
        severity = min(avg_lice / 1.0, 1.0)  # normalize to [0,1]
        breadth = pct_above
        trend = min(max_lice / 2.0, 1.0)

        composite = 0.4 * severity + 0.3 * breadth + 0.3 * trend
        composite = min(max(composite, 0.0), 1.0)

        return ImpactScore(
            ticker=ticker,
            avg_lice=avg_lice,
            max_lice=max_lice,
            pct_above_threshold=pct_above,
            weighted_lice_index=weighted_index,
            estimated_harvest_reduction_pct=harvest_reduction * 100,
            composite_score=composite,
            n_localities=len(set(r.locality_no for r in records)),
            details=f"{len(records)} records from {len(set(r.locality_no for r in records))} sites",
        )

    async def _audit(self) -> None:
        async with get_async_session() as s:
            for ticker, sc in self.latest_scores.items():
                s.add(AuditLog(
                    event_type="correlation_score",
                    detail=f"{ticker}: composite={sc.composite_score:.4f} "
                           f"avg_lice={sc.avg_lice:.3f} "
                           f"harvest_reduction={sc.estimated_harvest_reduction_pct:.1f}%",
                ))
