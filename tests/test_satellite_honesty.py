"""WS-32 — the satellite surface may not invent a reading.

The engine used to fabricate per-farm Sentinel-2 readings with a seeded RNG whenever
CDSE was unconfigured (and whenever a farm's query returned nothing), while
``is_live`` merely echoed whether credentials existed and the UI rendered
"Action required". These tests pin the replacement contract:

* no scene -> no reading, and the snapshot says why;
* ``is_live`` follows verified scenes with dates, never the configuration;
* an NDVI anomaly is a *surface scum / vegetation* signal, never a bloom confirmation;
* the product catalogue does not sell capabilities that are not implemented;
* every satellite route carries provenance, and none of them claims live without a scene.
"""
from __future__ import annotations

import datetime as dt

import pytest

from core.market import satellite_engine as sat_module
from core.market.satellite_engine import SatelliteEngine, SatelliteSnapshot

FARM = {"locality_no": 10029, "name": "Testfjord", "lat": 60.1, "lon": 5.2}
SCENE_DATE = "2026-10-15"


def _snapshot(**overrides) -> SatelliteSnapshot:
    fields = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "date_range": "",
        "n_farms_queried": 1,
        "n_readings": 0,
        "n_anomalies": 0,
        "cloud_free_pct": 0.0,
    }
    fields.update(overrides)
    return SatelliteSnapshot(**fields)


@pytest.fixture
def engine(monkeypatch):
    instance = SatelliteEngine()

    async def farms(limit=50):
        return [FARM]

    monkeypatch.setattr(instance, "_get_farm_locations", farms)
    return instance


def test_the_seeded_rng_simulator_is_gone():
    assert not hasattr(SatelliteEngine, "_simulate_reading")
    source = (sat_module.__file__ and open(sat_module.__file__, encoding="utf-8").read()) or ""
    assert "default_rng" not in source
    assert "possible_bloom" not in source


@pytest.mark.asyncio
async def test_unconfigured_scan_returns_nothing_and_says_why(engine, monkeypatch):
    monkeypatch.setattr(sat_module, "SH_CONFIGURED", False)
    snapshot = await engine.scan_farms(n_farms=1)
    assert snapshot.n_readings == 0
    assert snapshot.readings == []
    assert snapshot.anomalies == []
    assert snapshot.n_readings_verified == 0
    assert snapshot.summary["is_live"] is False
    assert snapshot.summary["data_quality"] == "unavailable"
    assert snapshot.missing_reason and "credentials are not configured" in snapshot.missing_reason


@pytest.mark.asyncio
async def test_configured_but_no_scene_still_yields_nothing(engine, monkeypatch):
    """A farm whose query fails must not fall back to invented values."""

    async def no_scene(self, lat, lon):
        return None

    monkeypatch.setattr(sat_module, "SH_CONFIGURED", True)
    monkeypatch.setattr(SatelliteEngine, "query_farm", no_scene)
    snapshot = await engine.scan_farms(n_farms=1)
    assert snapshot.n_readings == 0
    assert snapshot.n_readings_unverified == 1
    assert snapshot.summary["is_live"] is False
    assert "no farm returned" in (snapshot.missing_reason or "")


@pytest.mark.asyncio
async def test_a_verified_scene_is_reported_with_its_date_and_not_as_a_bloom(engine, monkeypatch):
    async def scene(self, lat, lon):
        return {
            "date": SCENE_DATE,
            "ndwi": 0.31,
            "ndvi": 0.12,  # above the surface-scum threshold
            "turbidity": 0.4,
            "cloud_pct": 5.0,
            "nir_reflectance": 0.06,
        }

    monkeypatch.setattr(sat_module, "SH_CONFIGURED", True)
    monkeypatch.setattr(SatelliteEngine, "query_farm", scene)
    snapshot = await engine.scan_farms(n_farms=1)
    assert snapshot.n_readings == 1
    assert snapshot.n_readings_verified == 1
    assert snapshot.scene_dates == [SCENE_DATE]
    assert snapshot.summary["is_live"] is True
    assert snapshot.summary["confidence"] == pytest.approx(0.6)
    anomaly = snapshot.anomalies[0]
    assert anomaly["anomaly_type"] == "surface_scum_or_vegetation"
    assert "not a chlorophyll" in anomaly["anomaly_detail"]


def test_the_catalogue_does_not_sell_unimplemented_capabilities():
    products = SatelliteEngine().get_products()
    ids = {p["id"] for p in products}
    assert "cage_census" not in ids, "no object detection is implemented"
    assert "hab_confirmation" not in ids, "Sentinel-2 cannot confirm a HAB"
    for product in products:
        assert product["validated"] is False
        assert "bloom confirmation" not in product["description"].lower()


def test_status_is_live_only_with_a_verified_scene():
    instance = SatelliteEngine()
    instance._cache = None
    status = instance.get_status()
    assert status["is_live"] is False
    assert status["missing_reason"] == "no scan has run yet"

    instance._cache = _snapshot(
        n_readings=1, n_readings_verified=1, scene_dates=[SCENE_DATE], missing_reason=None
    )
    status = instance.get_status()
    assert status["is_live"] is True
    assert status["cached_readings_verified"] == 1
    assert status["scene_dates"] == [SCENE_DATE]

    instance._cache = _snapshot(n_readings=0, missing_reason="no scene")
    assert instance.get_status()["is_live"] is False


# ── Route payloads ──────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from core.api import app

    return TestClient(app)


def test_every_satellite_route_carries_provenance(client, monkeypatch):
    monkeypatch.setattr(sat_module, "SH_CONFIGURED", False)
    sat_module.satellite_engine._cache = None

    for path in ("/api/satellite/status", "/api/satellite/products", "/api/satellite/anomalies"):
        body = client.get(path).json()
        assert "data_provenance" in body, path
        assert body["data_provenance"]["is_live"] is False, path
        assert body["data_provenance"]["fallback_reason"], path

    scan = client.post("/api/satellite/scan", params={"n_farms": 1})
    assert scan.status_code == 200
    payload = scan.json()
    assert payload["n_readings"] == 0
    assert payload["data_provenance"]["is_live"] is False
    assert "credentials" in payload["data_provenance"]["fallback_reason"]


def test_the_scan_route_reports_verified_scenes(client, monkeypatch):
    async def farms(self, limit=50):
        return [FARM]

    async def scene(self, lat, lon):
        return {
            "date": SCENE_DATE,
            "ndwi": 0.3,
            "ndvi": -0.1,
            "turbidity": 0.4,
            "cloud_pct": 2.0,
            "nir_reflectance": 0.05,
        }

    monkeypatch.setattr(sat_module, "SH_CONFIGURED", True)
    monkeypatch.setattr(SatelliteEngine, "_get_farm_locations", farms)
    monkeypatch.setattr(SatelliteEngine, "query_farm", scene)
    sat_module.satellite_engine._cache = None

    payload = client.post("/api/satellite/scan", params={"n_farms": 1}).json()
    assert payload["n_readings_verified"] == 1
    assert payload["data_provenance"]["is_live"] is True
    assert payload["data_provenance"]["freshness"].startswith(SCENE_DATE)
    sat_module.satellite_engine._cache = None
