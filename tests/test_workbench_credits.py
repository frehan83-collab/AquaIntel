"""WS-39/40 — credits, deep-analysis runs, and the numeric claim check.

Two claims are being tested here:

1. **A document is worth paying for, and a token is not.** A grounded chat answer costs
   USD 0.008; a dossier that synthesises three engines costs ~USD 0.35 and an hour less work.
   So credits buy runs, not tokens — and a run that could not be written by a model costs
   nothing.
2. **Citations do not enforce faithfulness.** The digits have to be checked, so every number
   in an answer is matched against the verified facts and an unsupported one is named.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.auth import create_token
from core.billing import credits_catalog
from core.llm import credits as ledger
from core.llm.claim_check import caveat, verify
from core.llm.workbench import RUN_KINDS, Workbench


# ── 1. The claim checker ───────────────────────────────────────────────


def test_a_number_that_appears_in_the_facts_is_verified():
    facts = [{"value": {"nok_per_kg": 72.55}}, {"value": {"rate_pct": 12.5}}]
    result = verify("Spot 72.55 NOK/kg, duty 12.5 %.", facts)
    assert [claim.token for claim in result.verified] == ["72.55", "12.5"]
    assert result.unverified == []
    assert result.clean is True


def test_an_invented_number_is_named_and_caveated():
    facts = [{"value": {"nok_per_kg": 72.55}}]
    result = verify("Spot 72.55 and the margin is 4.20 NOK/kg.", facts)
    assert [claim.token for claim in result.unverified] == ["4.20"]
    note = caveat(result)
    assert note and "4.20" in note and "could not be matched" in note


def test_a_rate_is_also_matched_as_a_percentage():
    result = verify("The tariff is 12.5 %.", [{"value": {"rate": 0.125}}])
    assert result.clean is True


def test_rounding_is_tolerated_but_drift_is_not():
    facts = [{"value": {"nok": 72.55}}]
    assert verify("about 72.6", facts).clean is True
    assert verify("about 74.0", facts).clean is False


def test_years_and_trivial_integers_are_not_claims():
    result = verify("In 2026 the limit was 0.5 and PA 3 reported it.", [{"value": 0.5}])
    tokens = [claim.token for claim in result.verified]
    assert "2026" not in tokens
    assert "3" not in tokens, "a production-area number is not a claim"
    assert "0.5" in tokens


def test_a_norwegian_decimal_comma_parses():
    result = verify("Marginen er -1,69 NOK/kg.", [{"value": {"margin": -1.69}}])
    assert result.clean is True


def test_nested_fact_values_are_searched():
    facts = [{"value": {"origins": [{"total_delivered_usd": 4.25}]}}]
    assert verify("delivered 4.25 USD/kg", facts).clean is True


# ── 2. Credit packs ───────────────────────────────────────────────────


def test_the_packs_are_priced_per_document_and_their_margin_is_stated():
    packs = credits_catalog.catalog()
    assert len(packs) == 3
    for item in packs:
        assert item["runs"] > 0
        assert 0 < item["per_run_nok"] < item["price_nok"]
        assert item["gross_margin_pct"] > 90, "a document must not be priced like a token"
    keys = [item["key"] for item in packs]
    assert credits_catalog.best_value_key() in keys


def test_an_unknown_pack_is_none():
    assert credits_catalog.pack("nope") is None
    assert credits_catalog.pack("desk").runs == 30


# ── 3. The run ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_run_without_a_model_returns_a_digest_and_spends_nothing():
    async def broken(**kwargs):
        raise RuntimeError("no provider")

    document = await Workbench(complete=broken).run("margin_dossier")
    assert document.mode == "digest"
    assert "verified" in document.document.lower()
    assert document.credits_spent == 0
    assert document.sources


@pytest.mark.asyncio
async def test_a_run_with_a_model_returns_a_document_and_its_cost():
    class _Response:
        content = "## What the numbers say\n- Spot 72.55 NOK/kg."
        model = "test"
        input_tokens = 18000
        output_tokens = 900
        cost_usd = 0.067
        error = None

    async def complete(**kwargs):
        return _Response()

    document = await Workbench(complete=complete).run("margin_dossier")
    assert document.mode == "model"
    assert document.usage["cost_usd"] == pytest.approx(0.067)
    assert document.document.startswith("##")


def test_every_run_kind_states_what_it_reads():
    for kind in RUN_KINDS.values():
        assert kind["name"] and kind["blurb"] and kind["reads"]
        assert kind["credits"] == 1


# ── 4. The routes ─────────────────────────────────────────────────────


@pytest.fixture()
def client():
    from core.api import app

    return TestClient(app)


def test_a_run_without_credits_is_a_structured_402(client, monkeypatch):
    async def zero(user_key):
        return 0

    monkeypatch.setattr(ledger, "balance", zero)
    response = client.post(
        "/api/workbench/run",
        json={"kind": "margin_dossier"},
        headers={"Authorization": f"Bearer {create_token(7, 'a@b.no', 'operator')}"},
    )
    assert response.status_code == 402
    body = response.json()
    assert body["error"] == "credits_required"
    assert body["packs"]
    assert "12 months" in body["validity_note"]


def test_an_unknown_run_kind_is_refused(client):
    response = client.post(
        "/api/workbench/run",
        json={"kind": "everything"},
        headers={"Authorization": f"Bearer {create_token(7, 'a@b.no', 'operator')}"},
    )
    assert response.status_code == 422
    assert "margin_dossier" in response.json()["available"]


def test_an_anonymous_run_is_refused(client):
    response = client.post("/api/workbench/run", json={"kind": "margin_dossier"})
    assert response.status_code == 402
    assert response.json()["error"] == "credits_required"


def test_a_digest_run_does_not_charge(client, monkeypatch):
    async def one_credit(user_key):
        return 1

    spent = {"called": False}

    async def fake_spend(*args, **kwargs):
        spent["called"] = True
        return 0

    async def fake_run(kind, *, user_id="anonymous"):
        from core.llm.workbench import WorkbenchDocument

        return WorkbenchDocument(
            kind=kind, title="Margin dossier", document="digest", mode="digest", sources=[]
        )

    monkeypatch.setattr(ledger, "balance", one_credit)
    monkeypatch.setattr(ledger, "spend", fake_spend)
    monkeypatch.setattr("core.routers.workbench_routes.workbench",
                        type("W", (), {"run": staticmethod(fake_run)})())

    response = client.post(
        "/api/workbench/run",
        json={"kind": "margin_dossier"},
        headers={"Authorization": f"Bearer {create_token(7, 'a@b.no', 'operator')}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["charged"] is False
    assert "no credit spent" in body["charge_note"]
    assert spent["called"] is False


def test_the_catalog_lists_runs_packs_and_balance(client, monkeypatch):
    async def three(user_key):
        return 3

    monkeypatch.setattr(ledger, "balance", three)
    response = client.get("/api/workbench/catalog")
    assert response.status_code == 200
    body = response.json()
    assert body["credits"] == 3
    assert len(body["runs"]) == 3
    assert body["packs"][0]["runs"] > 0


def test_credits_endpoint_serves_history(client, monkeypatch):
    async def three(user_key):
        return 3

    async def history(user_key, limit=20):
        return [{"id": 1, "delta": 3, "reason": "grant", "ref": None,
                 "created_at": "2026-10-18T12:00:00+00:00"}]

    monkeypatch.setattr(ledger, "balance", three)
    monkeypatch.setattr(ledger, "history", history)
    response = client.get(
        "/api/billing/credits",
        headers={"Authorization": f"Bearer {create_token(7, 'a@b.no', 'operator')}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["balance"] == 3
    assert body["history"][0]["reason"] == "grant"


def test_a_checkout_without_stripe_is_a_documented_mock(client):
    response = client.post(
        "/api/billing/credits/checkout",
        json={"pack": "review"},
        headers={"Authorization": f"Bearer {create_token(7, 'a@b.no', 'operator')}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["demo_mode"] is True
    assert "Stripe is not configured" in body["note"]
    assert body["runs"] == 10
