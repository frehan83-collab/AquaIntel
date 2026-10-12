"""
OpenClaw Intelligence Agent
============================
Background polling agent that drives all 6 intelligence modules:

  1. AIS Vessel Tracker       — every 5 minutes
  2. Sentiment Engine         — every 15 minutes (feed cycle)
  3. Farm Network Graph       — every 30 minutes (rebuild)
  4. Regulatory Regime        — every 60 minutes
  5. Chile Monitor            — every 60 minutes
  6. Pairs Engine             — every 10 minutes (price updates)

Runs concurrently in the main OpenClaw agent loop. Each sub-task
runs on its own cadence via internal scheduling.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

import structlog

from agents.base import BaseAgent

log = structlog.get_logger(__name__)


class IntelligenceAgent(BaseAgent):
    """
    Master intelligence polling agent.

    Runs all 6 market intelligence modules on staggered schedules
    to avoid API rate limits and spread I/O load.
    """

    name = "intelligence_agent"
    interval_seconds = 60  # master tick every 60s; each sub-module has its own cadence

    # Sub-module poll intervals (seconds)
    AIS_INTERVAL = 300           # 5 min
    SENTIMENT_INTERVAL = 900     # 15 min
    FARM_GRAPH_INTERVAL = 1800   # 30 min
    REGIME_INTERVAL = 3600       # 60 min
    CHILE_INTERVAL = 3600        # 60 min
    PAIRS_INTERVAL = 600         # 10 min
    CAUSAL_INTERVAL = 21600      # 6 hours (heavy computation)

    def __init__(self) -> None:
        super().__init__()
        self._last: dict[str, dt.datetime | None] = {
            "ais": None,
            "sentiment": None,
            "farm_graph": None,
            "regime": None,
            "chile": None,
            "pairs": None,
            "causal": None,
        }
        # Lazily imported singletons
        self._modules_loaded = False

    def _load_modules(self) -> None:
        """Import intelligence singletons lazily to avoid circular imports."""
        if self._modules_loaded:
            return
        try:
            from core.market.ais_tracker import ais_tracker
            from core.market.sentiment_engine import sentiment_engine
            from core.market.farm_graph import farm_graph
            from core.market.regime_detector import regime_detector
            from core.market.chile_monitor import chile_monitor
            from core.market.pairs_engine import pairs_engine
            from core.market.causal_engine import causal_engine
            self._ais = ais_tracker
            self._sentiment = sentiment_engine
            self._farm_graph = farm_graph
            self._regime = regime_detector
            self._chile = chile_monitor
            self._pairs = pairs_engine
            self._causal = causal_engine
            self._modules_loaded = True
            self.log.info("intelligence.modules_loaded")
        except Exception as exc:
            self.log.error("intelligence.module_load_failed", error=str(exc))

    def _due(self, key: str, interval: int) -> bool:
        """Check if a sub-module is due for a poll."""
        last = self._last.get(key)
        if last is None:
            return True
        return (dt.datetime.now(dt.UTC) - last).total_seconds() >= interval

    async def tick(self) -> None:
        """One master tick — run due sub-modules."""
        self._load_modules()
        if not self._modules_loaded:
            return

        tasks = []

        if self._due("ais", self.AIS_INTERVAL):
            tasks.append(self._run_ais())

        if self._due("sentiment", self.SENTIMENT_INTERVAL):
            tasks.append(self._run_sentiment())

        if self._due("farm_graph", self.FARM_GRAPH_INTERVAL):
            tasks.append(self._run_farm_graph())

        if self._due("regime", self.REGIME_INTERVAL):
            tasks.append(self._run_regime())

        if self._due("chile", self.CHILE_INTERVAL):
            tasks.append(self._run_chile())

        if self._due("pairs", self.PAIRS_INTERVAL):
            tasks.append(self._run_pairs())

        if self._due("causal", self.CAUSAL_INTERVAL):
            tasks.append(self._run_causal())

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    self.log.error("intelligence.subtask_error", error=str(r))

    # ── Sub-module runners ────────────────────────────────────────────────

    async def _run_ais(self) -> None:
        try:
            tracks = await self._ais.poll_ais_positions()
            self._last["ais"] = dt.datetime.now(dt.UTC)
            self.log.info("intelligence.ais_polled", tracks=len(tracks))
        except Exception as exc:
            self.log.warning("intelligence.ais_failed", error=str(exc)[:120])

    async def _run_sentiment(self) -> None:
        try:
            articles = await self._sentiment.poll_feeds()
            self._last["sentiment"] = dt.datetime.now(dt.UTC)
            self.log.info("intelligence.sentiment_polled", articles=len(articles))
        except Exception as exc:
            self.log.warning("intelligence.sentiment_failed", error=str(exc)[:120])

    async def _run_farm_graph(self) -> None:
        try:
            # Farm graph builds from DB — no external HTTP.
            # build_graph()/get_graph_summary() are async — must be awaited
            # (they silently returned coroutines before2026-10, so the farm
            # graph never actually built).
            summary = await self._farm_graph.get_graph_summary()
            if summary.get("n_farms", 0) == 0:
                # build_graph() reads directly from DB — no args needed
                await self._farm_graph.build_graph()
                summary = await self._farm_graph.get_graph_summary()
            self._last["farm_graph"] = dt.datetime.now(dt.UTC)
            self.log.info(
                "intelligence.farm_graph_updated",
                nodes=summary.get("n_farms", 0),
                clusters=summary.get("n_clusters", 0),
            )
        except Exception as exc:
            self.log.warning("intelligence.farm_graph_failed", error=str(exc)[:120])

    async def _run_regime(self) -> None:
        try:
            # Try to pull lice averages from DB to update pressure scores
            from core.models import LiceRecord
            from core.async_db import get_async_session
            from sqlalchemy import select
            import datetime as dt
            import collections

            lice_by_pa: dict[str, list[float]] = collections.defaultdict(list)
            async with get_async_session() as session:
                cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=90)
                result = await session.execute(
                    select(LiceRecord).where(LiceRecord.fetched_at >= cutoff)
                )
                rows = result.scalars().all()
                for r in rows:
                    pa = getattr(r, "production_area", None)
                    val = r.avg_adult_female_lice
                    if pa and val is not None:
                        lice_by_pa[str(pa)].append(float(val))

            if lice_by_pa:
                self._regime.update_lice_data(lice_by_pa)

            self._last["regime"] = dt.datetime.now(dt.UTC)
            self.log.info(
                "intelligence.regime_updated",
                pas_with_data=len(lice_by_pa),
            )
        except Exception as exc:
            self.log.warning("intelligence.regime_failed", error=str(exc)[:120])

    async def _run_chile(self) -> None:
        try:
            snapshot = await self._chile.fetch_chile_data()
            self._last["chile"] = dt.datetime.now(dt.UTC)
            self.log.info(
                "intelligence.chile_polled",
                disruption=snapshot.supply_disruption_score,
            )
        except Exception as exc:
            self.log.warning("intelligence.chile_failed", error=str(exc)[:120])

    async def _run_pairs(self) -> None:
        """
        Update pairs engine with latest salmon price data.
        Tries Fish Pool / SSB price client before falling back to DB.
        Also propagates the latest causal lag (if discovered) to the pairs engine.
        """
        try:
            from core.market.salmon_price import get_latest_prices
            prices = await get_latest_prices()
            if prices:
                # Inject causal lag before computing signals so rationale is fresh
                self._propagate_causal_lag()
                await self._pairs.update_prices(prices)
                self._last["pairs"] = dt.datetime.now(dt.UTC)
                self.log.info(
                    "intelligence.pairs_updated",
                    tickers=list(prices.keys()),
                    causal_lag=self._pairs._causal_lag_weeks,
                )
        except Exception as exc:
            self.log.warning("intelligence.pairs_failed", error=str(exc)[:120])

    def _propagate_causal_lag(self) -> None:
        """
        Read the dominant causal lag from the causal engine (if data has been
        loaded) and push it to the pairs engine so signal horizons are
        data-driven rather than hardcoded.
        """
        try:
            summary = self._causal.get_causal_summary()
            if summary and summary.get("dominant_lag_weeks"):
                lag = int(summary["dominant_lag_weeks"])
                conf = summary.get("confidence", "medium")
                self._pairs.set_causal_lag(lag, conf)
        except Exception as exc:
            self.log.debug("intelligence.causal_lag_propagate_skip", reason=str(exc)[:80])

    async def _run_causal(self) -> None:
        """
        Run the full causal inference analysis (Granger + Transfer Entropy).
        This is the heaviest computation — runs every 6 hours.
        Results are cached inside CausalEngine and served by /api/causal/*.
        After completion, the dominant lag is propagated to the pairs engine.
        """
        try:
            # Pull lice series and price series from DB / SSB
            from core.models import LiceRecord
            from core.async_db import get_async_session
            from sqlalchemy import select
            from core.market.ssb_price_client import ssb_price_client
            import collections, numpy as np

            # --- Lice series (national weekly mean) ---
            lice_by_week: dict[tuple[int, int], list[float]] = collections.defaultdict(list)
            async with get_async_session() as session:
                result = await session.execute(
                    select(LiceRecord)
                    .where(LiceRecord.avg_adult_female_lice.isnot(None))
                    .order_by(LiceRecord.year, LiceRecord.week)
                )
                rows = result.scalars().all()
                for r in rows:
                    if r.avg_adult_female_lice is not None:
                        lice_by_week[(r.year, r.week)].append(float(r.avg_adult_female_lice))

            if len(lice_by_week) < 20:
                self.log.info("intelligence.causal_skip", reason="insufficient_lice_data")
                self._last["causal"] = dt.datetime.now(dt.UTC)  # backoff — don't retry every tick
                return

            sorted_weeks = sorted(lice_by_week.keys())
            lice_series = [float(np.mean(lice_by_week[wk])) for wk in sorted_weeks]

            # --- Price series (SSB export prices) ---
            try:
                ssb_data = await ssb_price_client.get_price_history(n_weeks=len(lice_series) + 20)
                price_series = [float(p["price_nok"]) for p in ssb_data if p.get("price_nok")]
            except Exception:
                price_series = []

            if len(price_series) < 20:
                self.log.info("intelligence.causal_skip", reason="insufficient_price_data")
                self._last["causal"] = dt.datetime.now(dt.UTC)  # backoff — don't retry every tick
                return

            # Align lengths
            n = min(len(lice_series), len(price_series))
            lice_series = lice_series[-n:]
            price_series = price_series[-n:]

            # --- Load and run ---
            self._causal.load_data(lice_series, price_series)
            self._causal.run_granger(max_lag=16)
            self._causal.run_transfer_entropy(max_lag=16)
            self._last["causal"] = dt.datetime.now(dt.UTC)

            summary = self._causal.get_causal_summary()
            lag = summary.get("dominant_lag_weeks")
            conf = summary.get("confidence", "medium")
            self.log.info(
                "intelligence.causal_complete",
                dominant_lag_weeks=lag,
                confidence=conf,
            )

            # Push to pairs engine immediately
            if lag:
                self._pairs.set_causal_lag(int(lag), conf)

        except Exception as exc:
            self.log.warning("intelligence.causal_failed", error=str(exc)[:200])

    # ── Health ────────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        base = super().health()
        base["module_last_poll"] = {
            k: v.isoformat() if v else None for k, v in self._last.items()
        }
        # Include causal calibration status if available
        if self._modules_loaded:
            try:
                base["causal_lag_weeks"] = self._pairs._causal_lag_weeks
                base["causal_confidence"] = self._pairs._causal_confidence
            except Exception:
                pass
        return base
