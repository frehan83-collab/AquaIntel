"""Resilience regression tests: SSB/MET retry + serve-stale + bulk-history fix.

Covers the 2026-10 production-hardening pass:
- SSB fetch_bulk_history silently returned 14 weeks (broken ``fromTo`` SSB
  filter) instead of ~350 — TFT trained on 25x too little data without any
  error surfacing. The fixed path uses ``filter:all`` + client-side filtering.
- SSB/MET had no retry/backoff (BarentsWatch tenacity pattern added).
- Serve-stale semantics on total fetch failure.
"""
import asyncio
from unittest import mock

import pytest
import tenacity

from core.market.ssb_price_client import SalmonPriceWeek, SSBPriceClient, SSBPriceData


def _fresh_client() -> SSBPriceClient:
    import datetime as dt

    c = SSBPriceClient.__new__(SSBPriceClient)  # skip httpx client in __init__
    c._cache = None
    c._cache_time = None
    c._cache_requested = 0
    c._cache_ttl = dt.timedelta(hours=6)
    c._bulk_cache = None
    c._bulk_cache_time = None
    return c


class TestRetryWiring:
    def test_ssb_fetch_remote_has_retry(self):
        assert hasattr(SSBPriceClient._fetch_remote, "retry")

    def test_ssb_fetch_all_history_has_retry(self):
        assert hasattr(SSBPriceClient._fetch_all_history, "retry")

    def test_met_helpers_have_retry(self):
        from core.market.met_ocean import METOceanClient

        assert hasattr(METOceanClient._frost_request, "retry")
        assert hasattr(METOceanClient._ocean_forecast_request, "retry")


class TestSSBBulkHistory:
    def test_fetch_all_history_uses_filter_all(self, monkeypatch):
        """Regression for the silent 14-week bulk history (fromTo bug)."""
        c = _fresh_client()
        seen = {}

        class FakeResp:
            status_code = 200

            def json(self):
                return {"fake": "json-stat2"}

        async def fake_post(url, json=None, headers=None):
            seen["query"] = json
            return FakeResp()

        c._client = mock.Mock(post=fake_post)
        fake_prices = [
            SalmonPriceWeek(2019, 52, 60.0),
            SalmonPriceWeek(2020, 1, 70.0),
            SalmonPriceWeek(2020, 2, 71.0),
        ]
        monkeypatch.setattr(c, "_parse_response", lambda data: fake_prices)

        result = asyncio.run(c._fetch_all_history(start_year=2020))

        tid = seen["query"]["query"][2]["selection"]
        assert tid["filter"] == "all"  # NOT fromTo — the starved-data bug
        assert result == fake_prices[1:]  # client-side start_year filter

    def test_fetch_all_history_raises_on_http_error(self):
        c = _fresh_client()

        class FakeResp:
            status_code = 500

        async def fake_post(url, json=None, headers=None):
            return FakeResp()

        c._client = mock.Mock(post=fake_post)
        retry = SSBPriceClient._fetch_all_history.retry
        old_stop = retry.stop
        retry.stop = tenacity.stop_after_attempt(1)  # no slow backoff in tests
        try:
            with pytest.raises(RuntimeError, match="ssb_http_500"):
                asyncio.run(c._fetch_all_history(start_year=2020))
        finally:
            retry.stop = old_stop

    def test_bulk_history_sorts_and_sets_latest(self, monkeypatch):
        c = _fresh_client()

        async def fake_fetch(start_year):
            return [
                SalmonPriceWeek(2026, 2, 71.0),
                SalmonPriceWeek(2026, 1, 70.0),
            ]

        monkeypatch.setattr(c, "_fetch_all_history", fake_fetch)
        result = asyncio.run(c.fetch_bulk_history(start_year=2020))

        assert [(p.year, p.week) for p in result.prices] == [(2026, 1), (2026, 2)]
        assert result.latest_price == 71.0
        assert result.n_weeks == 2

    def test_bulk_history_serves_stale_on_failure(self, monkeypatch):
        import datetime as dt

        c = _fresh_client()
        c._bulk_cache = SSBPriceData(
            prices=[SalmonPriceWeek(2026, 39, 72.0)], latest_price=72.0, n_weeks=1
        )
        c._bulk_cache_time = dt.datetime.now(dt.UTC) - dt.timedelta(hours=48)

        async def boom(start_year):
            raise RuntimeError("down")

        monkeypatch.setattr(c, "_fetch_all_history", boom)
        result = asyncio.run(c.fetch_bulk_history(start_year=2020))
        assert result.latest_price == 72.0  # stale, not empty


class TestSSBServeStale:
    def test_fetch_prices_serves_stale_on_failure(self, monkeypatch):
        import datetime as dt

        c = _fresh_client()
        c._cache = SSBPriceData(
            prices=[SalmonPriceWeek(2026, 40, 73.8)], latest_price=73.8, n_weeks=1
        )
        c._cache_time = dt.datetime.now(dt.UTC) - dt.timedelta(hours=10)  # expired
        c._cache_requested = 260  # stale cache covers the (default) request

        async def boom(n_weeks):
            raise RuntimeError("down")

        monkeypatch.setattr(c, "_fetch_remote", boom)
        result = asyncio.run(c.fetch_prices())
        assert result.latest_price == 73.8  # stale cache, not empty

    def test_fetch_prices_empty_without_cache(self, monkeypatch):
        c = _fresh_client()

        async def boom(n_weeks):
            raise RuntimeError("down")

        monkeypatch.setattr(c, "_fetch_remote", boom)
        result = asyncio.run(c.fetch_prices())
        assert result.n_weeks == 0


class TestSSBCacheWindow:
    """Regression: the week-count-agnostic cache starved wider requests.

    A small cached window (e.g. an 8-week startup fetch) answered every later
    request for the whole 6h TTL — including price_feed_hub's 260-week request,
    whose <52 rows silently collapsed /api/futures/forward-curve to an empty
    curve (cached 600s by that route's ``@cached`` decorator and fed on by the
    hub's own 1h cache). Both the fresh-cache path and the serve-stale path
    are gated on the cached request window covering the incoming request.
    """

    def test_small_cache_does_not_satisfy_larger_request(self, monkeypatch):
        import datetime as dt

        c = _fresh_client()
        c._cache = SSBPriceData(
            prices=[SalmonPriceWeek(2026, 40, 73.8)], latest_price=73.8, n_weeks=1
        )
        c._cache_time = dt.datetime.now(dt.UTC)  # fresh, within TTL
        c._cache_requested = 8
        calls = []

        async def fake_fetch(n_weeks):
            calls.append(n_weeks)
            return [SalmonPriceWeek(2026, w, 70.0) for w in range(1, 261)]

        monkeypatch.setattr(c, "_fetch_remote", fake_fetch)
        result = asyncio.run(c.fetch_prices(n_weeks=260))
        assert calls == [260]  # smaller cache bypassed, wider window fetched
        assert result.n_weeks == 260
        assert c._cache_requested == 260  # cache replaced by the wider window

    def test_large_cache_serves_smaller_request(self, monkeypatch):
        import datetime as dt

        c = _fresh_client()
        c._cache = SSBPriceData(
            prices=[SalmonPriceWeek(2026, 40, 73.8)], latest_price=73.8, n_weeks=260
        )
        c._cache_time = dt.datetime.now(dt.UTC)
        c._cache_requested = 260

        async def boom(n_weeks):
            raise AssertionError("cache should have been reused")

        monkeypatch.setattr(c, "_fetch_remote", boom)
        result = asyncio.run(c.fetch_prices(n_weeks=52))
        assert result is c._cache  # superset cache satisfies the request

    def test_stale_small_cache_not_served_for_larger_request(self, monkeypatch):
        import datetime as dt

        c = _fresh_client()
        c._cache = SSBPriceData(
            prices=[SalmonPriceWeek(2026, 40, 73.8)], latest_price=73.8, n_weeks=1
        )
        c._cache_time = dt.datetime.now(dt.UTC) - dt.timedelta(hours=10)  # expired
        c._cache_requested = 8  # does NOT cover the request below

        async def boom(n_weeks):
            raise RuntimeError("down")

        monkeypatch.setattr(c, "_fetch_remote", boom)
        result = asyncio.run(c.fetch_prices(n_weeks=260))
        assert result.n_weeks == 0  # empty beats an inadequate stale window


class TestMETRequests:
    def test_frost_412_is_not_an_error(self):
        from core.market.met_ocean import METOceanClient

        c = METOceanClient.__new__(METOceanClient)
        c._frost_id = "test-id"

        class FakeResp:
            status_code = 412

        async def fake_get(*args, **kwargs):
            return FakeResp()

        c._client = mock.Mock(get=fake_get)
        assert asyncio.run(c._frost_request(["SN1"], "ref", "now")) == []

    def test_frost_http_error_raises_after_retries(self):
        from core.market.met_ocean import METOceanClient

        c = METOceanClient.__new__(METOceanClient)
        c._frost_id = "test-id"

        class FakeResp:
            status_code = 503

        async def fake_get(*args, **kwargs):
            return FakeResp()

        c._client = mock.Mock(get=fake_get)
        retry = METOceanClient._frost_request.retry
        old_stop = retry.stop
        retry.stop = tenacity.stop_after_attempt(1)
        try:
            with pytest.raises(RuntimeError, match="frost_http_503"):
                asyncio.run(c._frost_request(["SN1"], "ref", "now"))
        finally:
            retry.stop = old_stop


class TestAgentsServiceWiring:
    def test_main_offers_agents_only_mode(self):
        """The production agents service runs `python main.py --agents-only`."""
        import main as main_mod

        params = {p.name for p in main_mod.main.params}
        assert "agents_only" in params

    def test_run_agents_handles_shutdown_signals(self):
        """run_agents must install SIGTERM/SIGINT handlers (graceful shutdown)."""
        import inspect

        import main as main_mod

        src = inspect.getsource(main_mod.run_agents)
        assert "SIGTERM" in src and "SIGINT" in src
        assert "orchestrator.stopped" in src  # cleanup path runs on signal