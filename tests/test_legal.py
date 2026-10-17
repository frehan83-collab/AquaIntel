"""Legal-foundation tests (hardening §7).

The register must be complete for what we publish, must refuse uncleared uses, must
not claim legal clearance it has not obtained, and the performance fee must stay
deferred and unadvertised.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.api import app
from core.legal import data_licenses as dl
from core.legal import performance_fee
from core.market import indices as ix


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestRegisterCompleteness:
    def test_every_published_index_source_is_registered(self):
        """An index component's source must be traceable to a licence entry.

        The declared sources (methodology) are checked whatever the environment; the
        sources a computation actually used are added when it could run (WS-19: the
        lice-quota tracker is no longer an index source, so it is no longer allowed).
        """
        method = ix.methodology()["indices"]
        published_sources: set[str] = set()
        for code in ix.PUBLISHED_INDICES:
            published_sources.update(method[code]["sources"])
            result = __import__("asyncio").run(ix.compute(code))
            published_sources.update(result["sources"])
        assert published_sources, "indices must report their sources"
        known = {s.upstream for s in dl.SOURCES} | {"Fiskeridir biomass (SSB)"}
        assert published_sources <= known, published_sources - known

    def test_register_has_no_duplicate_keys_and_a_label(self):
        keys = [s.key for s in dl.SOURCES]
        assert len(keys) == len(set(keys))
        for source in dl.SOURCES:
            assert source.label and source.upstream and source.redistribution_notes

    def test_every_use_in_the_vocabulary_is_known(self):
        for source in dl.SOURCES:
            for use in source.allowed_uses:
                assert use in dl.USES, (source.key, use)


class TestHonestClearance:
    def test_nothing_is_cleared_without_a_reviewer(self):
        for source in dl.SOURCES:
            if source.classification_status == dl.CLEARED:
                assert source.reviewed_by and source.reviewed_at, source.key

    def test_summary_reports_uncleared_sources(self):
        summary = dl.compliance_summary()
        assert summary["cleared"] == 0
        assert summary["pending_legal_review"]
        assert "legal advice" in summary["statement"]

    def test_licence_permitted_but_uncleared_is_not_allowed(self):
        assert dl.check_use("ssb_prices", "resale_as_data_product")[
            "permitted_by_licence"
        ] is False
        public = dl.check_use("ssb_prices", "public_display")
        assert public["permitted_by_licence"] is True
        assert public["allowed"] is False, "uncleared sources cannot be relied on"
        assert public["requires_legal_signoff"] is True

    def test_unknown_source_is_refused(self):
        result = dl.check_use("not_registered", "public_display")
        assert result["allowed"] is False
        assert "not registered" in result["reason"]

    def test_unknown_use_raises(self):
        with pytest.raises(ValueError):
            dl.check_use("ssb_prices", "sell_to_martians")

    def test_resale_conflicts_are_visible(self):
        summary = dl.compliance_summary()
        assert "fish_pool_futures" in summary["resale_not_allowed"]
        assert summary["blocking_for_data_product"]


class TestPerformanceFeeDeferred:
    def test_default_is_deferred_and_off(self, monkeypatch):
        monkeypatch.delenv("FISHINTEL_PERFORMANCE_FEE_ENABLED", raising=False)
        assert performance_fee.is_enabled() is False
        report = performance_fee.status()
        assert report["status"] == "deferred"
        assert report["conditions_to_enable"]
        assert report["prohibited_while_deferred"]

    def test_flag_can_be_enabled_explicitly(self, monkeypatch):
        monkeypatch.setenv("FISHINTEL_PERFORMANCE_FEE_ENABLED", "1")
        assert performance_fee.is_enabled() is True
        assert performance_fee.status()["status"] == "enabled"

    def test_no_plan_advertises_a_performance_fee(self):
        from core.entitlements import PLANS

        for plan in PLANS.values():
            joined = " ".join(plan.features).lower()
            assert "performance fee" not in joined, plan.key


class TestLegalEndpoints:
    def test_data_licenses_endpoint(self, client):
        body = client.get("/api/legal/data-licenses").json()
        assert body["summary"]["registered_sources"] == len(dl.SOURCES)
        assert "fish_pool_futures" in {s["key"] for s in body["sources"]}
        assert body["uses_vocabulary"]

    def test_single_licence_and_404(self, client):
        assert client.get("/api/legal/data-licenses/ssb_prices").status_code == 200
        assert client.get("/api/legal/data-licenses/nope").status_code == 404

    def test_use_check_endpoint_refuses_uncleared(self, client):
        body = client.get(
            "/api/legal/use-check",
            params={"source": "copernicus_marine", "use": "resale_as_data_product"},
        ).json()
        assert body["permitted_by_licence"] is False
        assert body["allowed"] is False
        bad_use = client.get(
            "/api/legal/use-check",
            params={"source": "ssb_prices", "use": "martian_sales"},
        )
        assert bad_use.status_code == 422

    def test_advice_boundary_states_what_we_are_not(self, client):
        body = client.get("/api/legal/advice-boundary").json()
        assert body["what_we_are_not"]
        assert "not investment advice" in body["required_disclosure"]
        assert body["classification_status"] == "pending_legal_review"

    def test_ai_act_transparency_notes(self, client):
        body = client.get("/api/legal/ai-act").json()
        assert body["uses_ai"] is True
        assert body["systems"]
        assert body["prohibited_practices_not_used"]
        for system in body["systems"]:
            assert system["transparency"] and system["human_oversight"]

    def test_performance_fee_endpoint(self, client):
        body = client.get("/api/legal/performance-fee").json()
        assert body["status"] in {"deferred", "enabled"}
        assert body["switch"] == "FISHINTEL_PERFORMANCE_FEE_ENABLED"
