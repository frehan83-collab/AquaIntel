"""
Tests for causal inference endpoints (/api/causal/summary and /api/causal/granger).
Verifies stateless execution on cold workers without cross-request state dependencies.
"""
from unittest import mock
from starlette.testclient import TestClient
from types import SimpleNamespace

from core.api import app


def test_causal_summary_stateless():
    """Verify /api/causal/summary returns causal structure and Granger lags."""
    from core.market.causal_engine import causal_engine

    causal_engine._lice = None
    causal_engine._prices = None

    client = TestClient(app, raise_server_exceptions=False)
    fake_ssb = SimpleNamespace(prices=[SimpleNamespace(price_nok_kg=75.0 + (i % 5) * 3.0) for i in range(100)])

    with mock.patch("core.market.ssb_price_client.ssb_price_client.fetch_prices", new_callable=mock.AsyncMock, return_value=fake_ssb):
        r = client.get("/api/causal/summary?max_lag=4")
        assert r.status_code == 200
        data = r.json()
        assert "granger_results" in data or "dominant_lag_weeks" in data


def test_causal_granger_direct_call_stateless():
    """Verify /api/causal/granger auto-initializes without requiring /api/causal/summary first."""
    from core.market.causal_engine import causal_engine

    causal_engine._lice = None
    causal_engine._prices = None

    client = TestClient(app, raise_server_exceptions=False)
    fake_ssb = SimpleNamespace(prices=[SimpleNamespace(price_nok_kg=80.0 + (i % 7) * 2.0) for i in range(100)])

    with mock.patch("core.market.ssb_price_client.ssb_price_client.fetch_prices", new_callable=mock.AsyncMock, return_value=fake_ssb):
        r = client.get("/api/causal/granger?max_lag=4")
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "dominant_lag" in data

    """Verify /api/causal/granger auto-initializes without requiring /api/causal/summary first."""
    from core.market.causal_engine import causal_engine

    # Ensure engine starts cleared
    causal_engine._lice = None
    causal_engine._prices = None

    client = TestClient(app, raise_server_exceptions=False)

    fake_ssb = SimpleNamespace(prices=[SimpleNamespace(price_nok_kg=80.0 + (i % 7) * 2.0) for i in range(100)])

    with mock.patch("core.market.ssb_price_client.ssb_price_client.fetch_prices", new_callable=mock.AsyncMock, return_value=fake_ssb):
        r = client.get("/api/causal/granger?max_lag=4")
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "dominant_lag" in data
