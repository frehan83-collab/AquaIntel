"""WS-43 — a document is verified before it is charged, or it is withheld.

The council's rank 1. The chat had a numeric checker; the NOK 149 credit run did not, so an
invented number returned `degraded: False`, was labelled a model run and spent a credit. And
the budget sentinel was returned as *content*, so an ops sentence could be written as the
document and billed.

These tests pin the four consequences: an unsupported number withholds the prose and costs
nothing, a verified document is charged, the budget sentinel never becomes content, and a
withdrawn run is refused without taking a credit.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.auth import create_token
from core.llm import credits as ledger
from core.llm.client import LLMClient
from core.llm.workbench import RUN_KINDS, Workbench

FACTS_DOC = "## What the numbers say\n- Spot 72.55 NOK/kg (2026-W41).\n"


class _Response:
    model = "test-model"
    input_tokens = 18000
    output_tokens = 900
    cost_usd = 0.067
    error = None

    def __init__(self, content: str) -> None:
        self.content = content


@pytest.fixture()
def client():
    from core.api import app

    return TestClient(app)


@pytest.mark.asyncio
async def test_a_document_with_an_unsupported_number_is_withheld_and_free():
    async def complete(**kwargs):
        return _Response(FACTS_DOC + "- Mortality ran at 30 % this year.\n")

    document = await Workbench(complete=complete).run("margin_dossier")

    assert document.mode == "withheld"
    assert document.credits_spent == 0
    assert document.usage["cost_usd"] == 0.0
    assert document.verification["clean"] is False
    assert any(claim["token"] == "30" for claim in document.verification["unverified"])
    # The verified data still reaches the customer.
    assert "as_of" in document.document.lower() or "verified facts" in document.document.lower()


@pytest.mark.asyncio
async def test_a_clean_document_is_a_model_run_and_is_charged_later_by_the_route():
    async def complete(**kwargs):
        return _Response(FACTS_DOC)

    document = await Workbench(complete=complete).run("margin_dossier")

    assert document.mode == "model"
    assert document.verification["clean"] is True
    assert document.usage["cost_usd"] == pytest.approx(0.067)


@pytest.mark.asyncio
async def test_the_budget_sentinel_is_an_error_not_a_document(monkeypatch):
    client_llm = LLMClient()

    def over_budget() -> bool:
        return False

    monkeypatch.setattr(client_llm.usage, "within_budget", over_budget)
    response = await client_llm.complete(prompt="q", system="s")

    assert response.content == ""
    assert response.error and "budget" in response.error
    assert response.ok is False


def test_a_withdrawn_run_is_refused_without_taking_a_credit(client, monkeypatch):
    """The 409 path: a run the catalogue has switched off takes no credit."""
    from core.llm.workbench import RUN_KINDS

    monkeypatch.setitem(
        RUN_KINDS,
        "margin_dossier",
        {**RUN_KINDS["margin_dossier"], "sellable": False,
         "withdrawn_reason": "test: withdrawn for this case"},
    )
    spent = {"called": False}

    async def five(user_key):
        return 5

    async def fake_spend(*args, **kwargs):  # pragma: no cover - must not run
        spent["called"] = True
        return 4

    monkeypatch.setattr(ledger, "balance", five)
    monkeypatch.setattr(ledger, "spend", fake_spend)

    response = client.post(
        "/api/workbench/run",
        json={"kind": "margin_dossier"},
        headers={"Authorization": f"Bearer {create_token(7, 'a@b.no', 'operator')}"},
    )
    assert response.status_code == 409
    assert response.json()["error"] == "run_withdrawn"
    assert spent["called"] is False


def test_the_lice_review_is_sellable_again_after_the_feed_was_restored():
    """WS-56: it was withdrawn for a dead feed; WS-53 restored the feed, so it is sold again."""
    kind = RUN_KINDS["lice_pressure_review"]
    assert kind["sellable"] is True
    assert "backfilled" in kind["reinstated_reason"]
    assert "Withdrawn" not in kind["blurb"]


def test_the_origin_payload_carries_the_engine_provenance():
    from core.llm.workbench import _competitiveness_payload

    text = _competitiveness_payload(
        {
            "us_spot_usd_kg": 8.5,
            "tariff_basis": "assessed on transaction value",
            "fx_rates": {"NOK": 0.106},
            "data_quality": "partial_fallback",
            "fx_fallbacks": ["CLP"],
            "fallback_reason": "US spot fell back to the undated constant",
            "origins": [],
        }
    )
    assert "partial_fallback" in text
    assert "CLP" in text
    assert "undated constant" in text

def test_a_document_gets_a_receipt_so_it_can_be_traced(client, monkeypatch):
    """WS-54: a forwarded PDF must be traceable to the facts and verdict it was built from."""
    from core.llm import credits as ledger
    from core.llm import receipts as receipts_module
    from core.llm.workbench import WorkbenchDocument

    recorded = {}

    async def one_credit(user_key):
        return 5

    async def fake_spend(*args, **kwargs):
        return 4

    async def fake_run(kind, *, user_id="anonymous"):
        return WorkbenchDocument(
            kind=kind,
            title="Origin landed cost",
            document="## What the numbers say",
            mode="model",
            sources=[{"key": "tariff.us_norway", "as_of": "2026-07-24"}],
            verification={"checked": 4, "unverified": [], "clean": True},
            usage={"input_tokens": 1200, "output_tokens": 400, "cost_usd": 0.02},
        )

    async def fake_record(user_key, answer, *, kind="chat"):
        recorded["kind"] = kind
        recorded["sources"] = answer.get("sources")
        return 99

    monkeypatch.setattr(ledger, "balance", one_credit)
    monkeypatch.setattr(ledger, "spend", fake_spend)
    monkeypatch.setattr(receipts_module, "record", fake_record)
    monkeypatch.setattr(
        "core.routers.workbench_routes.workbench",
        type("W", (), {"run": staticmethod(fake_run)})(),
    )

    response = client.post(
        "/api/workbench/run",
        json={"kind": "origin_landed_cost"},
        headers={"Authorization": f"Bearer {create_token(7, 'a@b.no', 'operator')}"},
    )
    assert response.status_code == 200
    assert response.json()["receipt_id"] == 99
    assert recorded["kind"] == "document"
    assert recorded["sources"][0]["key"] == "tariff.us_norway"
