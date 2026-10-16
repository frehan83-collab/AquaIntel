"""Named indices (AI-STI / AI-LPI) + Bio→Price Weekly tests (hardening §3).

These lock the *contract* that makes the indices sellable: a published method
version, published weights, component-level traceability, and loud degradation
when a source is unavailable (never a silent substitution).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.api import app
from core.market import indices as ix

PUBLISHED = (ix.AI_STI, ix.AI_LPI)


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestMethodology:
    def test_version_is_published_and_matches_results(self):
        method = ix.methodology()
        assert method["version"] == ix.INDEX_METHOD_VERSION
        assert set(method["indices"]) == set(PUBLISHED)

    def test_weights_are_published_and_sum_to_one(self):
        method = ix.methodology()
        for code in PUBLISHED:
            weights = method["indices"][code]["components"]
            assert weights, code
            assert abs(sum(c["weight"] for c in weights.values()) - 1.0) < 1e-6, code
            for entry in weights.values():
                assert entry["scoring"], "every component publishes its scoring"

    def test_bands_are_ordered_and_complete(self):
        bands = [b["band"] for b in ix.methodology()["bands"]]
        # published ascending by minimum (documented order in docs/INDICES.md)
        assert bands == ["minimal", "low", "moderate", "elevated", "severe"]

    def test_limitations_and_planned_components_are_declared(self):
        method = ix.methodology()
        assert method["limitations"]
        assert "v1.1" in method["planned_components"]
        assert method["revision_policy"]


class TestComputation:
    @pytest.mark.parametrize("code", PUBLISHED)
    def test_result_shape_and_ranges(self, code, anyio_backend=None):
        import asyncio

        result = asyncio.run(ix.compute(code))
        assert result["index"] == code
        assert result["version"] == ix.INDEX_METHOD_VERSION
        if result["value"] is not None:
            assert 0.0 <= result["value"] <= 100.0
            assert result["band"] in {"minimal", "low", "moderate", "elevated", "severe"}
        assert result["permalink"] == f"/indices/{code.lower()}"
        assert result["api"] == f"/api/indices/{code.lower()}"
        assert result["methodology_url"] == "/api/indices/methodology"
        assert result["week"].count("-W") == 1
        for component in result["components"]:
            assert {"name", "weight", "score", "raw", "source", "used"} <= set(component)

    def test_band_thresholds(self):
        assert ix._band(85) == "severe"
        assert ix._band(65) == "elevated"
        assert ix._band(45) == "moderate"
        assert ix._band(25) == "low"
        assert ix._band(5) == "minimal"

    def test_unknown_index_is_rejected(self):
        import asyncio

        with pytest.raises(ValueError):
            asyncio.run(ix.compute("AI-NOPE"))


class TestHonestDegradation:
    def test_lineage_notes_prevent_a_clean_live_claim(self):
        """lice_records has no source column, so AI-LPI cannot claim clean 'live'."""
        import asyncio

        result = asyncio.run(ix.compute(ix.AI_LPI))
        if ix._lice_lineage_note():
            assert result["lineage_notes"], result
            assert result["provenance"]["is_live"] is False
            assert "unverifiable" in result["provenance"]["fallback_reason"]
            # the value is still produced — honest, not hidden
            assert result["components_used"] >= 1

    def test_component_source_reflects_the_trackers_own_lineage(self):
        """Not a hardcoded label: the index reports what the tracker actually did.

        `biomass_tracker` sets `last_source`/`last_is_live` during the fetch (filters
        synthetic records, else falls back to a historical-pattern estimate), so the
        component source must equal whatever the tracker recorded — not the fixed
        upstream string this code used to assume.
        """
        import asyncio

        from core.market.biomass_tracker import biomass_tracker

        result = asyncio.run(ix.compute(ix.AI_STI))
        component = next(
            (c for c in result["components"] if c["name"] == "biomass_momentum"), None
        )
        if component is None or not component["used"]:
            pytest.skip("biomass component unavailable in this environment")
        assert component["source"] == biomass_tracker.last_source
        if biomass_tracker.last_is_live is False:
            assert any(
                "fallback" in note for note in result["lineage_notes"]
            ), result["lineage_notes"]
            assert result["provenance"]["is_live"] is False


    def test_missing_source_is_named_and_not_reported_as_live(self, monkeypatch):
        import asyncio

        async def _boom(attribute: str):
            raise RuntimeError("source offline")

        monkeypatch.setattr(ix, "_totals_by_month", _boom)
        result = asyncio.run(ix.compute(ix.AI_STI))
        assert "biomass_momentum" in result["components_missing"]
        assert "harvest_pressure" in result["components_missing"]
        assert result["provenance"]["is_live"] is False
        assert result["provenance"]["fallback_reason"]
        # the quota component still works, so a value is still produced
        assert result["components_used"] >= 1
        assert result["value"] is not None

    def test_all_sources_dead_yields_no_value(self, monkeypatch):
        import asyncio

        async def _boom(*_args, **_kwargs):
            raise RuntimeError("everything offline")

        monkeypatch.setattr(ix, "_totals_by_month", _boom)
        monkeypatch.setattr(ix, "_national_emission", _boom)
        result = asyncio.run(ix.compute(ix.AI_STI))
        assert result["value"] is None
        assert result["band"] is None
        assert result["provenance"]["is_live"] is False
        assert "no index component" in (result["provenance"]["fallback_reason"] or "")


class TestHistory:
    def test_publish_then_history_round_trip(self):
        import asyncio

        published = asyncio.run(ix.publish(ix.AI_LPI))
        assert published["storage"]["status"] in {"stored", "duplicate"}
        rows = asyncio.run(ix.history(ix.AI_LPI, limit=10))
        assert rows, "published observation must be readable back"
        assert rows[0]["week"] == published["week"]
        assert rows[0]["version"] == ix.INDEX_METHOD_VERSION
        assert rows[0]["provenance"], "history keeps the provenance it was published with"

    def test_publish_is_idempotent_per_week_and_version(self):
        import asyncio

        first = asyncio.run(ix.publish(ix.AI_STI))
        second = asyncio.run(ix.publish(ix.AI_STI))
        assert second["storage"]["status"] == "duplicate"
        assert second["storage"]["id"] == first["storage"]["id"]


class TestIndexEndpoints:
    def test_list_indices(self, client):
        body = client.get("/api/indices").json()
        assert body["method_version"] == ix.INDEX_METHOD_VERSION
        assert set(body["indices"]) == set(PUBLISHED)

    @pytest.mark.parametrize("slug", ["ai-sti", "ai-lpi"])
    def test_permalinks_are_stable(self, client, slug):
        r = client.get(f"/api/indices/{slug}")
        assert r.status_code == 200
        assert r.json()["index"] == slug.upper()

    def test_methodology_endpoint(self, client):
        assert client.get("/api/indices/methodology").json()["version"] == ix.INDEX_METHOD_VERSION

    def test_unknown_index_404s(self, client):
        assert client.get("/api/indices/ai-nope").status_code == 404

    def test_history_endpoint(self, client):
        body = client.get("/api/indices/AI-STI/history").json()
        assert body["index"] == ix.AI_STI
        assert isinstance(body["observations"], list)


class TestBioPriceWeekly:
    def test_digest_shape_and_honesty(self, client):
        body = client.get("/api/indices/bio-price-weekly").json()
        assert body["report"] == "Bio>Price Weekly"
        assert body["version"]
        assert body["week"].count("-W") == 1
        assert body["transmission"]["read"] in {"elevated", "balanced", "loose", "unknown"}
        assert "provenance" in body
        assert isinstance(body["caveats"], list)
        assert set(body["indices"]) == set(PUBLISHED)
        # Any caveat must be visible in the provenance, not hidden.
        if body["caveats"]:
            assert body["provenance"]["is_live"] is False
            assert body["provenance"]["fallback_reason"]

    def test_publish_week_stores_both_indices(self):
        import asyncio

        from core.market.bio_price_weekly import publish_week

        digest = asyncio.run(publish_week())
        for code in PUBLISHED:
            status = digest["indices"][code]["storage"]["status"]
            assert status in {"stored", "duplicate"}
