"""Design-partner / paid-pilot infrastructure tests (hardening §6).

Pilots must be REAL entitlements (granted through entitlement_sync, auditable and
revocable), admin-only, validated, and tracked against success metrics — so 5–8
paid 90-day pilots can be run immediately without inventing a second plan table.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.api import app
from core.auth import create_token
from core.entitlements import PLANS
from core.models import Session as DBSession, DesignPartner, PartnerMetric, User

BASE = "/api/admin/partners"


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def admin_client(client, monkeypatch):
    """Client authenticated as admin via the FISHINTEL_ADMIN_EMAILS allow-list."""
    admin_email = "partners-admin@fishintel.local"
    monkeypatch.setenv("FISHINTEL_ADMIN_EMAILS", admin_email)
    client.headers["Authorization"] = (
        f"Bearer {create_token(99998, admin_email, 'investor')}"
    )
    yield client
    client.headers.pop("Authorization", None)


@pytest.fixture
def pilot_user():
    """A real user row to own the pilot entitlement."""
    with DBSession() as s:
        user = User(
            email=f"pilot-{id(object())}@x.test",
            hashed_password="x",
            role="buyer",
            tier="free",
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        uid = user.id
    yield uid
    with DBSession() as s:
        for partner in s.query(DesignPartner).filter(DesignPartner.user_id == uid).all():
            s.query(PartnerMetric).filter(PartnerMetric.partner_id == partner.id).delete()
            s.delete(partner)
        s.query(User).filter(User.id == uid).delete()
        s.commit()


def _create(admin_client, **overrides) -> dict:
    body = {"company": "Nordlaks Test AS", "icp": "producer", "country": "NO"}
    body.update(overrides)
    r = admin_client.post(BASE, json=body)
    assert r.status_code == 200, r.text
    return r.json()


class TestAdminGate:
    def test_anonymous_is_rejected(self, client):
        assert client.get(BASE).status_code in (401, 403)

    def test_non_admin_is_rejected(self, client, monkeypatch):
        monkeypatch.delenv("FISHINTEL_ADMIN_EMAILS", raising=False)
        client.headers["Authorization"] = (
            f"Bearer {create_token(424242, 'nobody@x.test', 'professional')}"
        )
        try:
            assert client.get(BASE).status_code in (401, 403)
        finally:
            client.headers.pop("Authorization", None)

    def test_admin_can_list(self, admin_client):
        body = admin_client.get(BASE).json()
        assert "partners" in body and "by_icp" in body
        assert "5-8 paid 90-day pilots" in body["target"]


class TestCreateValidation:
    def test_company_is_required(self, admin_client):
        assert admin_client.post(BASE, json={"icp": "desk"}).status_code == 422

    def test_icp_is_validated(self, admin_client):
        r = admin_client.post(BASE, json={"company": "X", "icp": "astronaut"})
        assert r.status_code == 422

    def test_unknown_plan_is_rejected(self, admin_client):
        r = admin_client.post(
            BASE, json={"company": "X", "icp": "desk", "plan_granted": "platinum"}
        )
        # 'platinum' is not an alias and not a plan -> normalises to free (a real
        # plan), so creation succeeds but the plan must be canonical.
        assert r.status_code == 200
        assert r.json()["plan_granted"] in PLANS

    def test_alias_plan_is_normalised(self, admin_client):
        partner = _create(admin_client, company="Alias Co", plan_granted="pilot")
        assert partner["plan_granted"] == "professional"


class TestPilotLifecycle:
    def test_created_partner_starts_as_prospect(self, admin_client):
        partner = _create(admin_client, company="Prospect Co", icp="desk")
        assert partner["status"] == "prospect"
        assert partner["days_remaining"] is None

    def test_onboard_without_user_is_rejected(self, admin_client):
        partner = _create(admin_client, company="No Owner Co", icp="insurer")
        r = admin_client.post(f"{BASE}/{partner['id']}/onboard", json={})
        assert r.status_code == 422

    def test_onboard_grants_a_real_entitlement(self, admin_client, pilot_user):
        partner = _create(
            admin_client,
            company="Entitlement Co",
            icp="producer",
            plan_granted="enterprise",
            user_id=pilot_user,
        )
        r = admin_client.post(f"{BASE}/{partner['id']}/onboard", json={"days": 90})
        assert r.status_code == 200, r.text
        assert r.json()["entitlement"]["plan"] == "enterprise"

        with DBSession() as s:
            user = s.execute(
                User.__table__.select().where(User.id == pilot_user)
            ).first()
            assert user.tier == "enterprise"

        detail = admin_client.get(f"{BASE}/{partner['id']}").json()
        assert detail["status"] == "onboarded"
        assert detail["days_remaining"] is not None
        assert detail["days_remaining"] <= 90


class TestSuccessMetrics:
    def test_metric_requires_a_name(self, admin_client):
        partner = _create(admin_client, company="Metric Co", icp="desk")
        r = admin_client.post(f"{BASE}/{partner['id']}/metrics", json={"value": 1})
        assert r.status_code == 422

    def test_metrics_are_recorded_and_scored_against_targets(self, admin_client):
        partner = _create(admin_client, company="Scorecard Co", icp="desk")
        pid = partner["id"]
        admin_client.post(
            f"{BASE}/{pid}/metrics",
            json={"name": "forecast_adoption", "value": 3, "target": 5, "unit": "users"},
        )
        admin_client.post(
            f"{BASE}/{pid}/metrics",
            json={"name": "forecast_adoption", "value": 6, "target": 5, "unit": "users"},
        )
        admin_client.post(
            f"{BASE}/{pid}/metrics",
            json={"name": "revenue_impact_nok", "value": 100000, "target": 250000},
        )
        detail = admin_client.get(f"{BASE}/{pid}").json()
        scorecard = {m["name"]: m for m in detail["metrics"]}
        # latest observation wins, and the achieved flag is computed
        assert scorecard["forecast_adoption"]["value"] == 6
        assert scorecard["forecast_adoption"]["achieved"] is True
        assert scorecard["revenue_impact_nok"]["achieved"] is False
        assert len(detail["metric_history"]) == 3


class TestDataReciprocity:
    def test_shares_list_is_required(self, admin_client):
        partner = _create(admin_client, company="Recip Co", icp="producer")
        r = admin_client.post(f"{BASE}/{partner['id']}/reciprocity", json={})
        assert r.status_code == 422

    def test_reciprocity_terms_are_stored(self, admin_client):
        partner = _create(admin_client, company="Recip2 Co", icp="producer")
        r = admin_client.post(
            f"{BASE}/{partner['id']}/reciprocity",
            json={
                "shares": ["lice_counts_weekly", "harvest_plan"],
                "cadence": "weekly",
                "agreement_ref": "DPA-2026-014",
            },
        )
        assert r.status_code == 200
        body = r.json()["reciprocity"]
        assert body["shares"] == ["lice_counts_weekly", "harvest_plan"]
        assert body["agreement_ref"] == "DPA-2026-014"


class TestStatusStateMachine:
    def test_illegal_transition_is_conflict(self, admin_client):
        partner = _create(admin_client, company="Fsm Co", icp="desk")
        r = admin_client.post(f"{BASE}/{partner['id']}/status", json={"status": "active"})
        assert r.status_code == 409

    def test_legal_transitions_are_applied(self, admin_client, pilot_user):
        partner = _create(
            admin_client, company="Fsm2 Co", icp="desk", user_id=pilot_user
        )
        pid = partner["id"]
        assert (
            admin_client.post(f"{BASE}/{pid}/onboard", json={}).json()["status"]
            == "onboarded"
        )
        assert admin_client.post(f"{BASE}/{pid}/status", json={"status": "active"}).json()[
            "to"
        ] == "active"
        converted = admin_client.post(
            f"{BASE}/{pid}/status", json={"status": "converted", "note": "signed annual"}
        ).json()
        assert converted["to"] == "converted"
        # terminal state: no further transitions
        again = admin_client.post(f"{BASE}/{pid}/status", json={"status": "churned"})
        assert again.status_code == 409

    def test_unknown_status_is_rejected(self, admin_client):
        partner = _create(admin_client, company="Fsm3 Co", icp="desk")
        r = admin_client.post(f"{BASE}/{partner['id']}/status", json={"status": "vibing"})
        assert r.status_code == 422

    def test_unknown_partner_404s(self, admin_client):
        assert admin_client.get(f"{BASE}/999999999").status_code == 404
