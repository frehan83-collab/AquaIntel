"""Regression guards from the route-liveness audit (Sprints 0–1).

`scripts/probe_liveness.py` measured every parameterless GET route and found
(a) routes that crashed outright, and (b) routes whose numbers were synthetic
(or randomly generated) yet advertised as live government data. These tests pin
both classes without needing network access.

The full audit table lives in docs/REPORT_LIVENESS.md.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.api import app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("path", [
    "/api/self-improvement/proposals",  # AuditLog.event_type / l.detail -> action / details
    "/api/parametric/risk-profile",     # async engine was never awaited
])
def test_audited_routes_no_longer_crash(client, path):
    assert client.get(path).status_code == 200


def test_audit_trail_is_admin_only(client):
    """The audit trail carries user-scoped metadata (who did what, webhook and
    API-key names), so it is operational data under AGENTS.md rule 2. It used to
    500 (nothing leaked); repairing it made it readable — it must stay admin-only
    (401 anonymous, never 200). The limit bound is still declared on the route,
    but auth is resolved first, so an oversized limit also yields 401."""
    assert client.get("/api/audit").status_code == 401
    assert client.get("/api/audit?limit=999999").status_code == 401


@pytest.mark.parametrize("path", [
    "/api/billing/subscription-status",
    "/api/billing/invoice-history",
])
def test_billing_routes_require_auth_not_crash(client, path):
    """billing_routes called ``get_current_user(creds)`` while the signature is
    ``(request, credentials)``, so ``credentials`` stayed a ``Depends`` object
    and every billing endpoint raised AttributeError instead of returning 401."""
    assert client.get(path).status_code == 401


def test_biomass_market_route_never_claims_live(client):
    """The supply model's metrics come from hardcoded seasonal profiles, so even
    with a live biomass base the route must never report live. Asserted at the
    source too, so a hardcoded provenance value cannot satisfy this test."""
    route_src = (ROOT / "core/routers/market_routes.py").read_text(encoding="utf-8")
    assert "biomass_tracker.provenance()" in route_src, (
        "route must derive provenance from the tracker, not a hardcoded value"
    )
    prov = client.get("/api/market/biomass").json()["data_provenance"]
    assert prov["is_live"] is False
    assert prov["source"] == "simulated" or prov["fallback_reason"]


def test_biomass_tracker_provenance_degrades_with_live_base():
    """Even when the biomass BASE is live, harvestable / weekly-harvest /
    days-of-supply / outlook are model estimates, so provenance must degrade and
    never claim live."""
    from core.market.biomass_tracker import BiomassTracker

    tracker = BiomassTracker()
    tracker.last_source = "Fiskeridirektoratet Biomass Status (ArcGIS)"
    tracker.last_is_live = True
    prov = tracker.provenance()
    assert prov.is_live is False
    assert prov.fallback_reason


def test_biomass_fallback_records_are_flagged_synthetic():
    """random.uniform() placeholders must never be reported as live government
    data. They were: the fallback set report_year, so ``is_live`` was True and
    get_national_summary() returned DataProvenance.live(confidence=0.95)."""
    from core.market.fiskeridir_biomass import FiskeridirBiomassClient

    records = FiskeridirBiomassClient()._generate_fallback()
    assert records and all(r.is_synthetic for r in records)
    prov = FiskeridirBiomassClient._provenance(records)
    assert prov["is_live"] is False
    assert prov["source"] == "simulated"
    assert prov["confidence"] == 0.0


def test_lice_quota_uses_existing_locality_columns():
    """lice_quota_tracker queried ``Locality.company``, which does not exist (the
    column is ``owner_company``), so every production area silently returned [].
    Source-level, so reintroducing the bug fails this test."""
    src = (ROOT / "core/market/lice_quota_tracker.py").read_text(encoding="utf-8")
    assert "owner_company" in src
    assert "Locality.company" not in src
    assert "loc.company" not in src


@pytest.mark.parametrize("path", [
    "/api/efficacy/benchmarks",
    "/api/efficacy/by-region",
    "/api/efficacy/learned-profiles",
])
def test_efficacy_routes_work_on_sqlite(client, path):
    """These queries used PostgreSQL-only ``EXTRACT(MONTH FROM ...)`` raw SQL, so
    they raised OperationalError on SQLite (dev + CI) even though the full suite
    was green — no test covered them. Now dialect-aware."""
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", [
    "/api/market/price-forecast",
    "/api/market/seasonal",
    "/api/market/exports",
    "/api/market/price-outlook/multi",
    "/api/market/futures-curve",
    "/api/market/ssb-price-history",
    "/api/market/ssb-seasonal",
    "/api/market/export-destinations",
    "/api/market/spot-price",
    "/api/market/forward-curve",
])
def test_market_routes_carry_provenance(client, path):
    """Rule 3: every number surfaced to users must be traceable. These market
    routes returned payloads with no provenance envelope at all (found by the
    liveness audit). Their upstreams are network-bound, so only a 200 response
    is asserted — an unavailable upstream is skipped, not failed."""
    r = client.get(path)
    if r.status_code != 200:
        pytest.skip(f"{path} -> {r.status_code} (upstream unavailable)")
    body = r.json()
    assert isinstance(body, dict), f"{path} should return an object"
    assert "data_provenance" in body, f"{path} returned data with no provenance"


def test_frontend_api_client_sends_the_stored_jwt():
    """The client previously sent NO Authorization header and nothing ever read
    the token stored at login, so user-scoped routes (billing, API keys,
    webhooks) and the per-user tier quota were unreachable from the UI."""
    src = (ROOT / "frontend/src/lib/api.ts").read_text(encoding="utf-8")
    assert "Authorization" in src and "Bearer" in src
    assert "AUTH_TOKEN_KEY" in src
    login = (ROOT / "frontend/src/app/login/page.tsx").read_text(encoding="utf-8")
    assert "AUTH_TOKEN_KEY" in login, "login must use the shared key constant"
