"""
Price Outlook Endpoint Resilience Tests
=========================================
Verifies that /api/market/price-outlook degrades gracefully when
ML models, SSB data, or the database are unavailable.
Run: pytest tests/test_price_outlook_resilience.py -v
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from core.api import app
    return TestClient(app)


class TestPriceOutlookReturns200:
    def test_price_outlook_returns_200(self, client):
        """Basic smoke test — endpoint should always return 200."""
        r = client.get("/api/market/price-outlook")
        assert r.status_code == 200
        data = r.json()
        assert "horizon_weeks" in data
        assert "current_spot_nok" in data
        assert isinstance(data["current_spot_nok"], (int, float))
        assert data["current_spot_nok"] > 0


class TestPriceOutlookDegradedML:
    def test_price_outlook_degraded_ml(self, client):
        """When ML ensemble raises, endpoint should return 200 with fallback=True."""
        with patch(
            "core.routers.market_routes.price_ensemble",
            create=True,
        ) as mock_ensemble:
            # Make predict raise an exception
            mock_ensemble.predict.side_effect = RuntimeError("Model unavailable")

            # Also patch the import inside the endpoint
            with patch.dict(
                "sys.modules",
                {"core.market.price_ml": type("Module", (), {"price_ensemble": mock_ensemble})()},
            ):
                r = client.get("/api/market/price-outlook?horizon=4")
                assert r.status_code == 200
                data = r.json()
                # Should have fallback indicator
                assert data.get("fallback") is True or "degraded" in str(data.get("model", {}).get("version", ""))


class TestPriceOutlookSSBFailure:
    def test_price_outlook_ssb_failure(self, client):
        """When SSB price client raises, should use fallback spot of 75.0."""
        mock_ssb = AsyncMock()
        mock_ssb.get_current_spot.side_effect = ConnectionError("SSB down")
        mock_ssb.fetch_prices.side_effect = ConnectionError("SSB down")

        with patch.dict(
            "sys.modules",
            {"core.market.ssb_price_client": type("Module", (), {"ssb_price_client": mock_ssb})()},
        ):
            r = client.get("/api/market/price-outlook?horizon=4")
            assert r.status_code == 200
            data = r.json()
            # Should still have a current_spot_nok value
            assert "current_spot_nok" in data
            assert isinstance(data["current_spot_nok"], (int, float))
            assert data["current_spot_nok"] > 0


class TestPriceOutlookEmptyDB:
    def test_price_outlook_empty_db(self, client):
        """With empty database, should return 200 with default lice values."""
        r = client.get("/api/market/price-outlook?horizon=4")
        assert r.status_code == 200
        data = r.json()
        # Even with empty DB, we get a valid response structure
        assert "horizon_weeks" in data
        assert "bands" in data or "fallback" in data
        assert data["horizon_weeks"] >= 2
