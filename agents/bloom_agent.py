"""
Algal Bloom Monitor Agent.

Hourly agent that fetches Copernicus satellite chlorophyll-a data,
scores bloom risk per farm locality, dispatches alerts to farmers,
and injects bearish trading signals when CRITICAL bloom risk is detected.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select, desc, func, and_

from agents.base import BaseAgent
from config.settings import settings
from core.models import Locality, LiceRecord, Signal
from core.async_db import get_async_session
from core.bloom.copernicus import CopernicusClient, ChlGridPoint
from core.bloom.models import ChlorophyllReading, BloomRiskAssessment
from core.bloom.risk_model import compute_bloom_risk
from core.bloom.notifications import send_bloom_alert


class BloomAgent(BaseAgent):
    """Monitors algal bloom risk using satellite chlorophyll-a data."""

    name = "bloom_monitor"
    interval_seconds = 3600  # 1 hour

    def __init__(self) -> None:
        super().__init__()
        self.cmems = CopernicusClient(
            username=settings.cmems_username,
            password=settings.cmems_password,
        )

    async def tick(self) -> None:
        """One monitoring cycle: fetch → score → alert → signal."""

        # 1. Fetch satellite chlorophyll data
        grid_points = await self.cmems.fetch_chlorophyll()
        if not grid_points:
            self.log.info("bloom.no_data", reason="CMEMS returned no points")
            return

        # 2. Store raw chlorophyll readings
        await self._store_chlorophyll(grid_points)

        # 3. Load all farm localities with coordinates
        async with get_async_session() as session:
            result = await session.execute(
                select(Locality).where(
                    Locality.latitude.isnot(None),
                    Locality.longitude.isnot(None),
                )
            )
            localities = result.scalars().all()

        self.log.info("bloom.assessing", localities=len(localities), grid_points=len(grid_points))

        # 4. Score each locality
        assessments: list[BloomRiskAssessment] = []
        critical_tickers: set[str] = set()

        for loc in localities:
            nearest = self.cmems.find_nearest_grid_cell(
                loc.latitude, loc.longitude, grid_points
            )
            if nearest is None:
                continue

            # Get trend: compare with previous day's reading for this cell
            chl_trend = await self._compute_trend(nearest.grid_cell_id, nearest.chl_a_mg_m3)

            # Get latest sea temperature from lice records
            sst = await self._get_latest_sst(loc.locality_no)

            # Score risk
            result = compute_bloom_risk(
                chl_a=nearest.chl_a_mg_m3,
                sst=sst,
                chl_a_trend=chl_trend,
                chl_elevated=settings.bloom_chl_elevated,
                chl_high=settings.bloom_chl_high,
                chl_critical=settings.bloom_chl_critical,
            )

            assessment = BloomRiskAssessment(
                locality_no=loc.locality_no,
                assessed_at=dt.datetime.now(dt.UTC),
                chl_a_value=result.chl_a_value,
                sst_value=result.sst_value,
                chl_a_trend=result.chl_a_trend,
                risk_level=result.risk_level,
                risk_score=result.risk_score,
                nearest_grid_cell_id=nearest.grid_cell_id,
                contributing_factors=result.factors_json(),
            )
            assessments.append(assessment)

            # 5. Alert if HIGH or CRITICAL
            if result.risk_level in ("HIGH", "CRITICAL"):
                await send_bloom_alert(
                    locality_no=loc.locality_no,
                    locality_name=loc.name,
                    risk_level=result.risk_level,
                    risk_score=result.risk_score,
                    chl_a=result.chl_a_value,
                    cooldown_hours=settings.bloom_alert_cooldown_hours,
                )

            # 6. Track CRITICAL tickers for trading signals
            if result.risk_level == "CRITICAL" and loc.owner_company:
                critical_tickers.add(loc.owner_company)

        # Count risk levels before committing (objects detach after commit)
        risk_counts: dict[str, int] = {}
        for a in assessments:
            risk_counts[a.risk_level] = risk_counts.get(a.risk_level, 0) + 1

        # Store all assessments
        async with get_async_session() as session:
            session.add_all(assessments)

        self.log.info("bloom.cycle_complete", assessments=len(assessments), risks=risk_counts)

        # 7. Inject bearish signals for CRITICAL bloom events
        if critical_tickers:
            await self._inject_bloom_signals(critical_tickers)

    async def _store_chlorophyll(self, points: list[ChlGridPoint]) -> None:
        """Upsert chlorophyll readings into DB."""
        async with get_async_session() as session:
            for pt in points:
                result = await session.execute(
                    select(ChlorophyllReading).where(
                        and_(
                            ChlorophyllReading.date == dt.datetime.combine(pt.date, dt.time()),
                            ChlorophyllReading.grid_cell_id == pt.grid_cell_id,
                        )
                    )
                )
                existing = result.scalars().first()

                if existing:
                    existing.chl_a_mg_m3 = pt.chl_a_mg_m3
                    existing.fetched_at = dt.datetime.now(dt.UTC)
                else:
                    session.add(ChlorophyllReading(
                        date=dt.datetime.combine(pt.date, dt.time()),
                        latitude=pt.latitude,
                        longitude=pt.longitude,
                        grid_cell_id=pt.grid_cell_id,
                        chl_a_mg_m3=pt.chl_a_mg_m3,
                    ))

    async def _compute_trend(self, grid_cell_id: str, current_value: float) -> float:
        """Compute chl-a trend as mg/m3 per day vs previous reading."""
        async with get_async_session() as session:
            result = await session.execute(
                select(ChlorophyllReading)
                .where(ChlorophyllReading.grid_cell_id == grid_cell_id)
                .order_by(desc(ChlorophyllReading.date))
                .limit(1)
            )
            prev = result.scalars().first()

        if prev is None:
            return 0.0

        days_diff = max(
            (dt.datetime.now(dt.UTC).replace(tzinfo=None) - prev.date).total_seconds() / 86400, 0.1
        )
        return (current_value - prev.chl_a_mg_m3) / days_diff

    async def _get_latest_sst(self, locality_no: int) -> float | None:
        """Get most recent sea surface temperature from lice records."""
        async with get_async_session() as session:
            result = await session.execute(
                select(LiceRecord.sea_temp_c)
                .where(
                    LiceRecord.locality_no == locality_no,
                    LiceRecord.sea_temp_c.isnot(None),
                )
                .order_by(desc(LiceRecord.fetched_at))
                .limit(1)
            )
            return result.scalars().first()

    async def _inject_bloom_signals(self, tickers: set[str]) -> None:
        """Create bearish trading signals for companies hit by CRITICAL bloom."""
        async with get_async_session() as session:
            for ticker in tickers:
                # Don't duplicate if a bloom signal already pending
                result = await session.execute(
                    select(Signal).where(
                        and_(
                            Signal.ticker == ticker,
                            Signal.status == "pending",
                            Signal.rationale.like("%algal bloom%"),
                        )
                    )
                )
                existing = result.scalars().first()

                if existing:
                    continue

                signal = Signal(
                    created_at=dt.datetime.now(dt.UTC),
                    ticker=ticker,
                    direction="SHORT",
                    strength=0.85,
                    lice_score=0.0,
                    exposure_score=0.0,
                    rationale=(
                        f"CRITICAL algal bloom risk detected at {ticker} farm localities. "
                        f"Historical precedent: 2019 Chrysochromulina event caused 8M+ fish deaths "
                        f"and significant stock decline. Recommend defensive positioning."
                    ),
                    status="pending",
                    confirmed_by_user=False,
                )
                session.add(signal)
                self.log.warning(
                    "bloom.bearish_signal",
                    ticker=ticker,
                    direction="SHORT",
                )
