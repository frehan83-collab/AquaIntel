"""Provenance ratchet tests (hardening §8).

Rule 3 says every data route carries provenance. This gate guarantees a new data
route cannot ship without a *deliberate* decision: it must either carry provenance
or be added to the exempt register with a written reason.

The runtime *measurement* of provenance stays in `scripts/probe_liveness.py`; this
test is deterministic and offline.
"""
from __future__ import annotations

import pytest

from core import provenance_register as pr
from core.market.provenance_envelope import with_provenance


class TestExemptRegister:
    def test_every_exemption_has_a_category_and_a_reason(self):
        for prefix, entry in pr.EXEMPT.items():
            assert entry.get("category") in pr.CATEGORIES, prefix
            assert entry.get("reason", "").strip(), prefix
            assert prefix.startswith("/api"), prefix

    def test_exempt_matching_is_longest_prefix(self):
        match = pr.matching_exemption("/api/billing/catalog")
        assert match is not None and match["prefix"] == "/api/billing/"
        assert pr.matching_exemption("/api/lice/summary") is None

    def test_exempt_route_is_not_counted_as_data(self):
        data = pr.inventory()
        assert "/api/health" in data["exempt"]
        assert "/api/billing/catalog" in data["exempt"]


class TestBaselineCoversTheInventory:
    def test_no_unregistered_routes(self):
        data = pr.inventory()
        assert data["unregistered"] == [], (
            "New data route(s) without a provenance decision: "
            f"{data['unregistered']}. Add `@with_provenance(...)` "
            "(core.market.provenance_envelope) or an exemption in "
            "core/provenance_register.EXEMPT, then run "
            "`python scripts/provenance_ratchet.py --update`."
        )

    def test_baseline_is_readable_and_consistent(self):
        baseline = pr.load_baseline()
        assert baseline["version"] == "1.0"
        assert baseline["registered"], "baseline must not be empty"
        assert baseline["counts"]["total_routes"] >= baseline["counts"]["registered"]

    def test_baseline_exempt_prefixes_match_the_register(self):
        baseline = pr.load_baseline()
        assert sorted(pr.EXEMPT) == baseline["exempt_prefixes"]

    def test_frozen_counts_match_the_live_inventory(self):
        """A regression (routes added/removed) must be a conscious re-freeze."""
        baseline = pr.load_baseline()
        data = pr.inventory()
        assert len(data["exempt"]) == baseline["counts"]["exempt"]
        assert len(data["registered"]) == baseline["counts"]["registered"]
        assert data["total"] == baseline["counts"]["total_routes"]


class TestDetectionLogic:
    def test_a_new_route_is_detected_as_unregistered(self, monkeypatch):
        """The gate itself must fire for an unknown path."""
        monkeypatch.setattr(
            pr, "data_routes", lambda: ["/api/lice/summary", "/api/brand/new-metric"]
        )
        data = pr.inventory()
        assert "/api/brand/new-metric" in data["unregistered"]

    def test_a_new_exempt_route_is_allowed(self, monkeypatch):
        monkeypatch.setattr(pr, "data_routes", lambda: ["/api/health", "/api/auth/tiers"])
        assert pr.inventory()["unregistered"] == []


class TestProvenanceEnvelope:
    @pytest.mark.asyncio
    async def test_attaches_a_live_envelope(self):
        @with_provenance("test source", confidence=0.8)
        async def handler():
            return {"value": 1}

        result = await handler()
        assert result["value"] == 1
        assert result["data_provenance"]["source"] == "test source"
        assert result["data_provenance"]["is_live"] is True
        assert result["data_provenance"]["confidence"] == 0.8

    @pytest.mark.asyncio
    async def test_degraded_reason_forces_not_live(self):
        @with_provenance("model estimate", degraded_reason="not an observation")
        async def handler():
            return {"value": 2}

        provenance = (await handler())["data_provenance"]
        assert provenance["is_live"] is False
        assert provenance["fallback_reason"] == "not an observation"

    @pytest.mark.asyncio
    async def test_existing_envelope_is_preserved(self):
        """Nesting is safe: an engine that already set provenance wins."""

        @with_provenance("outer")
        async def handler():
            return {"value": 3, "data_provenance": {"source": "engine", "is_live": False}}

        assert (await handler())["data_provenance"]["source"] == "engine"

    @pytest.mark.asyncio
    async def test_non_dict_results_pass_through(self):
        @with_provenance("list source")
        async def handler():
            return [1, 2, 3]

        assert await handler() == [1, 2, 3]
