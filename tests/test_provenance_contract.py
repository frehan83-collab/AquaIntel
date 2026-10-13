"""
Provenance contract tests (review L4)
=====================================
Regression net for the R10 bug class: a payload whose provenance says
`is_live: false` must not claim "LIVE" anywhere — including nested
engine-level fields (Norway `data_source`, supplier rows) that the
original bug left asserting LIVE while the route said degraded.

Also pins the shared records-based helper
(`core.market.data_provenance.from_records`) that the china routes use.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.api import app
from core.market.china_demand import ChinaDemandSnapshot, china_demand_engine
from core.market.data_provenance import from_records
from core.routers.country_routes import _china_provenance


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def iter_strings(node, path: str = "payload"):
    """Yield (path, string) for every string anywhere in the payload."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from iter_strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from iter_strings(value, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def live_claim_offenders(payload) -> list[tuple[str, str]]:
    """Every string containing "LIVE" (the claim token) with its path."""
    return [(p, s) for p, s in iter_strings(payload) if "LIVE" in s]


class TestFromRecordsHelper:
    def test_live_when_records_returned(self):
        p = from_records(
            [{"month": "2026-01", "tonnes": 1200}],
            live_source="src",
            degraded_source="deg",
            reason="r",
        )
        assert p.is_live is True

    def test_degraded_when_records_empty(self):
        p = from_records(
            [],
            live_source="src",
            degraded_source="deg",
            reason="r",
            degraded_confidence=0.5,
        )
        assert p.is_live is False
        assert p.confidence == 0.5
        assert p.fallback_reason == "r"

    def test_none_records_degrade(self):
        # None (upstream never answered) must degrade, not crash
        p = from_records(
            None, live_source="src", degraded_source="deg", reason="r"
        )
        assert p.is_live is False


class TestDegradedPayloadsContainNoLiveClaims:
    """The contract: is_live=false  =>  no "LIVE" string anywhere."""

    def test_engine_degraded_snapshot_has_no_live_claims(self):
        d = china_demand_engine._format_snapshot(
            ChinaDemandSnapshot(norway_monthly_series=[])
        )
        offenders = live_claim_offenders(d)
        assert not offenders, f"degraded engine snapshot claims LIVE: {offenders}"

    def test_engine_degraded_supplier_breakdown_has_no_live_claims(self):
        suppliers = china_demand_engine._build_supplier_breakdown(
            norway_tonnes=0, est_year=2025, total_imports=95000,
            norway_live=False,
        )
        offenders = live_claim_offenders(suppliers)
        assert not offenders, f"degraded supplier rows claim LIVE: {offenders}"

    def test_degraded_route_payloads_have_no_live_claims(self, client, monkeypatch):
        degraded_snapshot = {
            "source": "GACC/Comtrade estimates (SSB table 08799 unavailable)",
            "norway_exports_to_china": {
                "tonnes_12m": 0,
                "is_live": False,
                "data_source": "Unavailable — SSB 08799 returned no records",
            },
            "monthly_series": [],
            "suppliers": china_demand_engine._build_supplier_breakdown(
                norway_tonnes=0, est_year=2025, total_imports=95000,
                norway_live=False,
            ),
        }

        async def fake_snapshot() -> dict:
            return degraded_snapshot

        async def fake_signals() -> dict:
            return {"signal_score": 0.0, "signal_label": "Neutral"}

        async def fake_impact() -> dict:
            return {"impact_label": "Neutral"}

        monkeypatch.setattr(china_demand_engine, "get_snapshot", fake_snapshot)
        monkeypatch.setattr(china_demand_engine, "get_demand_signals", fake_signals)
        monkeypatch.setattr(china_demand_engine, "get_supply_impact", fake_impact)

        for path in (
            "/api/china/demand",
            "/api/china/demand-signals",
            "/api/china/demand-impact",
        ):
            r = client.get(path)
            assert r.status_code == 200, path
            payload = r.json()
            assert payload["data_provenance"]["is_live"] is False, path
            offenders = live_claim_offenders(payload)
            assert not offenders, f"{path} degraded but claims LIVE: {offenders}"

    def test_helper_degrades_tonnes_only_payload(self):
        # Rounded tonnes alone (no records) must yield degraded provenance
        # and therefore forbid LIVE claims downstream.
        p = _china_provenance({"norway_exports_to_china": {"tonnes_12m": 21000}})
        assert p.is_live is False