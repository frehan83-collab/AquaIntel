"""
China demand engine caching tests (review M5)
=============================================
Pins the two fixes in `ChinaDemandEngine.get_snapshot`:

- Degraded snapshots (SSB returned no records) use a SHORT negative-cache
  TTL (10 min) instead of the full 2h data TTL, so recovery after an SSB
  outage takes minutes, not hours.
- A per-event-loop single-flight lock prevents concurrent cold calls from
  double-fetching the upstream.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from core.market.china_demand import ChinaDemandEngine


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _live_ssb() -> dict:
    return {
        "tonnes_12m": 21_000,
        "nok_millions_12m": 1_500,
        "avg_price_nok_kg": 71.5,
        "trend_pct": 5.2,
        "monthly_series": [
            {"month": "2026-08", "tonnes": 3_500, "value_mnok": 250.0}
        ],
    }


def _degraded_ssb() -> dict:
    return {"tonnes_12m": 0, "monthly_series": []}


class _CountingFetcher:
    def __init__(self, payload: dict, delay: float = 0.0):
        self.calls = 0
        self.payload = payload
        self.delay = delay

    async def __call__(self) -> dict:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.payload


def _fresh_engine(monkeypatch, payload: dict, delay: float = 0.0):
    engine = ChinaDemandEngine()
    fetcher = _CountingFetcher(payload, delay)
    monkeypatch.setattr(engine, "_ensure_ssb_data", fetcher)
    return engine, fetcher


class TestDegradedNegativeCache:
    def test_degraded_snapshot_uses_short_ttl_then_recovers(self, monkeypatch):
        engine, fetcher = _fresh_engine(monkeypatch, _degraded_ssb())
        run_async(engine.get_snapshot())
        assert fetcher.calls == 1

        # Within the short TTL -> served from cache
        snap = run_async(engine.get_snapshot())
        assert fetcher.calls == 1
        assert snap["norway_exports_to_china"]["is_live"] is False

        # Aged past the 10-minute negative TTL -> refetch (not 2 hours)
        engine._last_fetch = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=11)
        run_async(engine.get_snapshot())
        assert fetcher.calls == 2

        # SSB recovers -> once the short negative TTL expires the very
        # next call is LIVE (never blocked for the 2h data TTL)
        fetcher.payload = _live_ssb()
        engine._last_fetch = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=11)
        snap = run_async(engine.get_snapshot())
        assert fetcher.calls == 3
        assert snap["norway_exports_to_china"]["is_live"] is True

    def test_live_snapshot_keeps_full_data_ttl(self, monkeypatch):
        engine, fetcher = _fresh_engine(monkeypatch, _live_ssb())
        run_async(engine.get_snapshot())
        assert fetcher.calls == 1

        # 11 minutes old: still cached for LIVE snapshots (2h TTL)
        engine._last_fetch = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=11)
        run_async(engine.get_snapshot())
        assert fetcher.calls == 1

        # Past the full TTL -> refetch
        engine._last_fetch = dt.datetime.now(dt.UTC) - dt.timedelta(hours=3)
        run_async(engine.get_snapshot())
        assert fetcher.calls == 2

    def test_degraded_ttl_is_bounded(self):
        engine = ChinaDemandEngine()
        assert engine._degraded_cache_ttl < engine._cache_ttl
        assert engine._degraded_cache_ttl == dt.timedelta(minutes=10)


class TestSingleFlight:
    def test_concurrent_cold_calls_fetch_once(self, monkeypatch):
        engine, fetcher = _fresh_engine(monkeypatch, _live_ssb(), delay=0.05)

        async def _gather():
            return await asyncio.gather(
                engine.get_snapshot(),
                engine.get_snapshot(),
                engine.get_snapshot(),
            )

        snaps = run_async(_gather())
        assert fetcher.calls == 1
        assert len(snaps) == 3
        assert all(s["norway_exports_to_china"]["is_live"] for s in snaps)

    def test_single_flight_also_covers_degraded_fetches(self, monkeypatch):
        engine, fetcher = _fresh_engine(monkeypatch, _degraded_ssb(), delay=0.05)

        async def _gather():
            return await asyncio.gather(
                engine.get_snapshot(), engine.get_snapshot()
            )

        snaps = run_async(_gather())
        assert fetcher.calls == 1
        assert all(s["norway_exports_to_china"]["is_live"] is False for s in snaps)
