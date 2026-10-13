"""
China demand honesty tests (R10)
=================================
Pins the rule that curated estimates are never presented as live data:
- `_china_provenance` (routes) liveness logic,
- engine `_format_snapshot` / `_build_supplier_breakdown` nested claims,
- an end-to-end route check with a failing SSB series.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.market.china_demand import ChinaDemandSnapshot, china_demand_engine
from core.routers.country_routes import _china_provenance


@pytest.fixture(scope="module")
def client():
    from core.api import app
    return TestClient(app)


class TestChinaProvenanceHelper:
    def test_live_when_monthly_series_present(self):
        p = _china_provenance({"monthly_series": [{"month": "2026-01", "tonnes": 1200}]})
        assert p.is_live is True
        assert p.confidence == 0.75

    def test_tonnes_without_records_is_degraded(self):
        # Repinned (review M1): a rounded tonnes_12m alone must NOT flip
        # the payload to LIVE — liveness is keyed on records actually
        # returned (monthly_series), never on a rounded tonnage that can
        # legitimately be 0.
        p = _china_provenance({"norway_exports_to_china": {"tonnes_12m": 21000}})
        assert p.is_live is False
        assert p.confidence == 0.5
        assert p.fallback_reason

    def test_degraded_when_series_missing(self):
        p = _china_provenance(
            {"norway_exports_to_china": {"tonnes_12m": 0}, "source": "estimates"}
        )
        assert p.is_live is False
        assert p.confidence == 0.5
        assert p.fallback_reason
        assert "estimates" in p.source


class TestEngineNestedClaims:
    def test_format_snapshot_degrades_when_series_empty(self):
        snap = ChinaDemandSnapshot(norway_monthly_series=[])
        d = china_demand_engine._format_snapshot(snap)
        assert "LIVE" not in d["source"]
        assert d["norway_exports_to_china"]["data_source"].startswith("Unavailable")

    def test_format_snapshot_live_when_series_present(self):
        snap = ChinaDemandSnapshot(
            norway_monthly_series=[{"month": "2026-01", "tonnes": 1200, "value_mnok": 90.0}]
        )
        d = china_demand_engine._format_snapshot(snap)
        assert "LIVE" in d["source"]
        assert d["norway_exports_to_china"]["data_source"].startswith("LIVE")

    def test_norway_is_live_field_keyed_on_records(self):
        # Structured liveness flag (review M3, additive under schema 1.1):
        # mirrors the records-based invariant, not the data_source text.
        live = china_demand_engine._format_snapshot(
            ChinaDemandSnapshot(
                norway_monthly_series=[{"month": "2026-01", "tonnes": 1200, "value_mnok": 90.0}]
            )
        )
        assert live["norway_exports_to_china"]["is_live"] is True
        degraded = china_demand_engine._format_snapshot(
            ChinaDemandSnapshot(norway_monthly_series=[])
        )
        assert degraded["norway_exports_to_china"]["is_live"] is False

    def test_supplier_breakdown_downgrades_norway(self):
        suppliers = china_demand_engine._build_supplier_breakdown(
            norway_tonnes=0, est_year=2025, total_imports=95000, norway_live=False
        )
        norway = next(s for s in suppliers if s["origin"] == "Norway")
        assert norway["is_live"] is False
        assert "Estimate" in norway["data_source"]


class TestChinaRouteHonesty:
    def test_route_returns_degraded_when_ssb_fails(self, client, monkeypatch):
        async def fake_snapshot() -> dict:
            return {
                "source": "GACC/Comtrade estimates (SSB table 08799 unavailable)",
                "norway_exports_to_china": {
                    "tonnes_12m": 0,
                    "data_source": "Unavailable — SSB 08799 returned no records",
                },
                "monthly_series": [],
            }

        monkeypatch.setattr(china_demand_engine, "get_snapshot", fake_snapshot)
        r = client.get("/api/china/demand")
        assert r.status_code == 200
        prov = r.json()["data_provenance"]
        assert prov["is_live"] is False
        assert prov["confidence"] == 0.5
        assert prov["fallback_reason"]

    def test_route_returns_live_when_series_present(self, client, monkeypatch):
        async def fake_snapshot() -> dict:
            return {
                "source": "SSB table 08799 (Norway LIVE) + GACC/Comtrade estimates",
                "norway_exports_to_china": {"tonnes_12m": 21000},
                "monthly_series": [{"month": "2026-01", "tonnes": 1200}],
            }

        monkeypatch.setattr(china_demand_engine, "get_snapshot", fake_snapshot)
        r = client.get("/api/china/demand")
        assert r.status_code == 200
        assert r.json()["data_provenance"]["is_live"] is True
