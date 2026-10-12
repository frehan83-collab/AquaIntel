"""
CMEMS wave client tests.

Covers:
- pure risk-band mapping
- deterministic simulated fallback (no credentials) with honest flags
- PA validation
- HTTP surface via /api/ocean/waves/*
"""
import pytest
from starlette.testclient import TestClient

from core.api import app
from core.market.wave_client import CMEMSWaveClient, wave_risk_band


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestRiskBands:
    def test_bands_map_monotonically(self):
        assert wave_risk_band(0.1)["level"] == "low"
        assert wave_risk_band(0.5)["level"] == "moderate"
        assert wave_risk_band(1.5)["level"] == "high"
        assert wave_risk_band(3.0)["level"] == "severe"
        assert wave_risk_band(12.0)["level"] == "severe"

    def test_band_notes_present(self):
        for hs in (0.1, 1.0, 2.0, 5.0):
            band = wave_risk_band(hs)
            assert band["note"], "operational note required for every band"


class TestSimulatedFallback:
    def test_no_credentials_falls_back_marked(self, monkeypatch):
        from config.settings import settings as _settings
        victim = CMEMSWaveClient()
        # Force the no-credentials path without touching real settings
        monkeypatch.setattr(_settings, "cmems_username", "")
        monkeypatch.setattr(_settings, "cmems_password", "")
        ok = victim._fetch_sync()
        assert ok is False
        result = victim.get_pa_wave(4)
        assert result["is_live"] is False
        assert result["source"].startswith("simulated")
        assert "fallback_reason" in result
        assert result["risk"] in ("low", "moderate", "high", "severe")

    def test_simulated_is_deterministic_per_pa(self):
        a = CMEMSWaveClient().get_pa_wave(7)
        b = CMEMSWaveClient().get_pa_wave(7)
        assert a["hs_m"] == b["hs_m"]

    def test_invalid_pa_rejected(self):
        result = CMEMSWaveClient().get_pa_wave(99)
        assert "error" in result


class TestWaveForecast:
    def test_forecast_simulated_deterministic(self, monkeypatch):
        from config.settings import settings as _settings
        monkeypatch.setattr(_settings, "cmems_username", "")
        monkeypatch.setattr(_settings, "cmems_password", "")
        victim = CMEMSWaveClient()
        assert victim._fetch_forecast_sync() is False
        a = victim.get_pa_wave_forecast(4)
        b = victim.get_pa_wave_forecast(4)
        assert a["is_live"] is False
        assert a["source"].startswith("simulated")
        assert [d["hs_m"] for d in a["days"]] == [d["hs_m"] for d in b["days"]]
        assert len(a["days"]) == 5

    def test_forecast_days_sliced_and_dates_ordered(self, monkeypatch):
        from config.settings import settings as _settings
        monkeypatch.setattr(_settings, "cmems_username", "")
        monkeypatch.setattr(_settings, "cmems_password", "")
        victim = CMEMSWaveClient()
        result = victim.get_pa_wave_forecast(7, days=3)
        days = result["days"]
        assert len(days) == 3
        assert days == sorted(days, key=lambda d: d["date"])
        for d in days:
            assert d["risk"] in ("low", "moderate", "high", "severe")
            assert d["operational_note"]
            assert d["hs_m"] >= 0

    def test_forecast_invalid_pa(self):
        assert "error" in CMEMSWaveClient().get_pa_wave_forecast(99)

    def test_forecast_endpoint_shape(self, client):
        r = client.get("/api/ocean/waves/pa/4/forecast?days=3")
        assert r.status_code == 200
        data = r.json()
        assert data["production_area"] == 4
        assert len(data["days"]) == 3
        assert data["data_provenance"]["source"]

    def test_forecast_endpoint_bounds(self, client):
        assert client.get("/api/ocean/waves/pa/0/forecast").status_code == 400
        assert client.get("/api/ocean/waves/pa/14/forecast").status_code == 400


class TestWaveEndpoints:
    def test_status_endpoint(self, client):
        r = client.get("/api/ocean/waves/status")
        assert r.status_code == 200
        data = r.json()
        assert "product" in data and "dataset" in data

    def test_pa_endpoint_shape(self, client):
        r = client.get("/api/ocean/waves/pa/4")
        assert r.status_code == 200
        data = r.json()
        for key in ("production_area", "hs_m", "risk", "is_live", "data_provenance"):
            assert key in data, f"missing {key}"
        assert data["data_provenance"]["source"]

    def test_pa_endpoint_bounds(self, client):
        assert client.get("/api/ocean/waves/pa/0").status_code == 400
        assert client.get("/api/ocean/waves/pa/14").status_code == 400
