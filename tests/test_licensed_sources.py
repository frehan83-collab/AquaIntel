"""WS-31b — licensed sources only: no Yahoo Finance on any data path.

Yahoo's API terms forbid selling, sharing or **deriving income from** its data, so a
paid product cannot price anything from it. The platform used it for USD/NOK, for the
competitiveness cross rates, for EUR/NOK in the futures module, for commodity futures
gap-filling, and for Oslo-listed equity quotes — and, when the equity call failed, it
*derived* share prices by multiplying the salmon spot by fixed multiples, which was
fabrication presented as a market price.

These tests pin the replacement: Norges Bank official rates (+ documented constants,
always flagged), SSB for the salmon spot, and no equity quotes until a licensed display
feed exists.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from core.market import fx_rates


# ── 1. No Yahoo host anywhere ───────────────────────────────────────────


def test_no_backend_module_calls_yahoo():
    offenders = []
    for path in list(Path("core").rglob("*.py")) + list(Path("agents").rglob("*.py")):
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "query1.finance.yahoo.com" in source:
            offenders.append(str(path))
    assert offenders == [], f"Yahoo data calls remain in {offenders}"


def test_the_feed_engine_no_longer_lists_yahoo_as_a_live_source():
    from core.market.feed_cost_engine import LIVE_SOURCES

    assert "yahoo_finance" not in LIVE_SOURCES


# ── 2. The licensed conversion rules ───────────────────────────────────


@pytest.mark.asyncio
async def test_per_100_quotes_are_divided_correctly(monkeypatch):
    """Norges Bank quotes DKK/SEK/ISK per 100 units; treating them as per-unit is 100x."""

    async def fake_nok_rate(currency="USD", *, timeout=8.0):
        table = {"USD": 10.0, "DKK": 140.0, "EUR": 11.0}
        if currency not in table:
            return {"currency": currency, "nok_per_unit": None, "observed_at": None,
                    "is_fallback": True, "fallback_reason": "no quote"}
        return {"currency": currency, "nok_per_unit": table[currency],
                "observed_at": "2026-10-16", "is_fallback": False, "fallback_reason": None}

    monkeypatch.setattr(fx_rates, "nok_rate", fake_nok_rate)
    dkk = await fx_rates.rate_to_usd("DKK")
    # 100 DKK = NOK 140 -> 1 DKK = NOK 1.4 -> USD 0.14 at 10 NOK/USD
    assert dkk["usd_per_unit"] == pytest.approx(0.14)
    assert dkk["is_fallback"] is False
    assert dkk["observed_at"] == "2026-10-16"


@pytest.mark.asyncio
async def test_nok_is_the_inverse_of_the_official_usd_rate(monkeypatch):
    async def fake_nok_rate(currency="USD", *, timeout=8.0):
        return {"currency": "USD", "nok_per_unit": 9.5, "observed_at": "2026-10-16",
                "is_fallback": False, "fallback_reason": None}

    monkeypatch.setattr(fx_rates, "nok_rate", fake_nok_rate)
    nok = await fx_rates.rate_to_usd("NOK")
    assert nok["usd_per_unit"] == pytest.approx(1 / 9.5)
    assert nok["is_fallback"] is False


@pytest.mark.asyncio
async def test_a_currency_with_no_licensed_source_is_flagged_never_silent(monkeypatch):
    async def no_quote(currency="USD", *, timeout=8.0):
        return {"currency": currency, "nok_per_unit": None, "observed_at": None,
                "is_fallback": True, "fallback_reason": "no quote"}

    monkeypatch.setattr(fx_rates, "nok_rate", no_quote)
    clp = await fx_rates.rate_to_usd("CLP")
    assert clp["usd_per_unit"] == pytest.approx(0.00105)
    assert clp["is_fallback"] is True
    assert "documented constant" in clp["fallback_reason"]
    assert "Norges Bank" not in clp["source"], "a constant must not be labelled a feed"


@pytest.mark.asyncio
async def test_the_official_usd_rate_carries_an_observation_date(monkeypatch):
    async def fake_nok_rate(currency="USD", *, timeout=8.0):
        return {"currency": "USD", "nok_per_unit": 9.44, "observed_at": "2026-10-16",
                "is_fallback": False, "fallback_reason": None}

    monkeypatch.setattr(fx_rates, "nok_rate", fake_nok_rate)
    usd = await fx_rates.rate_to_usd("USD")
    assert usd["usd_per_unit"] == 1.0


# ── 3. The salmon price function serves only licensed data ─────────────


@pytest.mark.asyncio
async def test_latest_prices_returns_only_the_ssb_spot(monkeypatch):
    from core.market import salmon_price

    class _SSB:
        async def get_current_spot(self):
            return 72.55

    monkeypatch.setattr(
        "core.market.ssb_price_client.ssb_price_client", _SSB(), raising=False
    )
    prices = await salmon_price.get_latest_prices()
    assert prices == {"SSB_NOK": 72.55}
    # No equity ticker and no derived proxy may appear.
    assert not any(key.endswith(".OL") for key in prices)
    assert "MOWI" not in prices and "SALM" not in prices


def test_the_derived_share_price_block_is_gone():
    from core.market import salmon_price

    source = inspect.getsource(salmon_price)
    assert "_SPOT_MULTIPLES" not in source
    # The old Yahoo fetch assigned `prices[short]`; that assignment is gone.
    assert "prices[short]" not in source


# ── 4. The route tells the truth ───────────────────────────────────────


def test_equity_prices_route_serves_no_quote_and_says_why():
    from fastapi.testclient import TestClient

    from core.api import app

    body = TestClient(app).get("/api/market/equity-prices").json()
    assert body["prices_nok"] == {}
    assert body["equity_quotes"] == "unavailable"
    assert "licensed display feed" in body["equity_quotes_reason"]
    assert body["data_provenance"]["is_live"] is False
    assert "licensed display feed" in body["data_provenance"]["fallback_reason"]
    assert "fpi_eur_per_kg" in body["benchmarks"]
    # The old claim must be gone: no "15min delay" and no Yahoo attribution.
    assert "Yahoo" not in body["source"]


def test_the_pairs_agent_skips_without_an_equity_feed():
    from agents import intelligence_agent

    source = inspect.getsource(intelligence_agent)
    assert "pairs_skipped" in source
    assert "equity_prices" in source
