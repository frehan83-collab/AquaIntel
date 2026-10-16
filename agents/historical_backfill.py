"""
Historical Backfill Agent
==========================
Downloads historical lice data from BarentsWatch for model training.
Uses the download/preview endpoint and weekly lice reports.
Backfills from 2012 to present.

Runs once on startup, then weekly to fill gaps.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select, func

from agents.base import BaseAgent
from agents.data_ingest import DataIngestAgent
from core.barentswatch import BarentsWatchClient
from core.models import LiceRecord, AuditLog
from core.async_db import get_async_session
from core.source_lineage import REAL_LICE_SOURCES

import structlog

log = structlog.get_logger(__name__)


class HistoricalBackfillAgent(BaseAgent):
    name = "historical_backfill"
    interval_seconds = 86400  # daily check for gaps

    def __init__(self, start_year: int = 2017) -> None:
        super().__init__()
        self.bw = BarentsWatchClient()
        self.start_year = start_year
        self._initial_done = False

    async def tick(self) -> None:
        if self._initial_done:
            # Just fill gaps after initial run
            await self._fill_gaps()
            return

        self.log.info("backfill.start", from_year=self.start_year)
        await self._backfill_range(self.start_year)
        self._initial_done = True

    async def _backfill_range(self, from_year: int) -> None:
        """Backfill all weeks from from_year to present."""
        now = dt.datetime.now(dt.UTC)
        current_year, current_week, _ = now.isocalendar()

        total_inserted = 0

        for year in range(from_year, current_year + 1):
            max_week = current_week if year == current_year else 52

            for week in range(1, max_week + 1):
                # Check if we already have data for this week
                count = await self._week_count(year, week)
                if count >= 100:  # already have substantial data
                    continue

                try:
                    data = await self.bw.get_locality_reports_v2(year, week)
                    inserted = await DataIngestAgent._upsert_lice_v2(data, year, week)
                    total_inserted += inserted

                    if inserted > 0:
                        self.log.debug(
                            "backfill.week",
                            year=year, week=week,
                            records=inserted,
                        )
                except Exception as exc:
                    # Some historical weeks may not be available
                    self.log.debug(
                        "backfill.week_skip",
                        year=year, week=week,
                        error=str(exc)[:80],
                    )

            self.log.info("backfill.year_done", year=year, total=total_inserted)

        await self._audit(f"Backfill complete: {total_inserted} records from {from_year}")
        self.log.info("backfill.done", total=total_inserted)

    async def _fill_gaps(self) -> None:
        """Find and fill gaps in recent data."""
        now = dt.datetime.now(dt.UTC)
        year, week, _ = now.isocalendar()

        gaps_filled = 0
        # Check last 8 weeks
        for w_offset in range(1, 9):
            check_week = week - w_offset
            check_year = year
            if check_week < 1:
                check_week += 52
                check_year -= 1

            count = await self._week_count(check_year, check_week)
            if count < 50:  # probably missing data
                try:
                    data = await self.bw.get_locality_reports_v2(check_year, check_week)
                    inserted = await DataIngestAgent._upsert_lice_v2(data, check_year, check_week)
                    gaps_filled += inserted
                except Exception:
                    pass

        if gaps_filled:
            self.log.info("backfill.gaps_filled", records=gaps_filled)

    @staticmethod
    async def _week_count(year: int, week: int) -> int:
        """Rows for the week whose lineage is VERIFIED (source in REAL_LICE_SOURCES).

        WS-1: pre-migration rows carry source='unverified'. Counting them here made
        the backfill skip every bulk-loaded week forever, so its lineage could never
        become verifiable. Re-ingesting such a week flips its rows to 'barentswatch'
        through the upsert's update branch — the only honest way to earn the label.
        """
        async with get_async_session() as s:
            result = await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.year == year,
                    LiceRecord.week == week,
                    LiceRecord.source.in_(sorted(REAL_LICE_SOURCES)),
                )
            )
            return result.scalar() or 0

    @staticmethod
    async def _audit(detail: str) -> None:
        async with get_async_session() as s:
            s.add(AuditLog(event_type="historical_backfill", detail=detail))

    async def shutdown(self) -> None:
        await self.bw.close()
