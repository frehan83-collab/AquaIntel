"""WS-50 tests: the allowance is a budget, not a paywall; the ladder upsells upward."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.auth import create_token
from core.entitlements import get_plan, plan_catalog
from core.llm import usage as chat_usage


@pytest.fixture()
def client():
    from core.api import app

    return TestClient(app)


def test_the_catalogue_sells_what_it_enforces():
    rows = {row["key"]: row for row in plan_catalog()}
    assert rows["free"]["chat_questions_per_month"] == 0
    assert rows["operator"]["chat_questions_per_month"] == 100
    assert rows["professional"]["chat_questions_per_month"] == 300


def test_operator_upsells_upward_not_down():
    assert get_plan("operator").upgrade_to == "enterprise"


def test_the_free_plan_still_gets_an_answer(client, monkeypatch):
    async def status(user_key, plan_key, *, now=None):
        return {"plan": plan_key, "month": "2026-10", "allowance": 0, "included": False,
                "unlimited": False, "used": 0, "remaining": 0, "meter_available": True,
                "resets_on": "2026-11-01"}

    monkeypatch.setattr(chat_usage, "status", status)
    response = client.post("/api/chat", json={"message": "What is the margin?"})

    assert response.status_code == 200, "the funnel must not be a 402"
    body = response.json()
    assert body["mode"] == "grounded_fallback"
    assert "does not include model-written answers" in body["allowance_note"]


def test_a_spent_allowance_degrades_instead_of_blocking(client, monkeypatch):
    async def status(user_key, plan_key, *, now=None):
        return {"plan": plan_key, "month": "2026-10", "allowance": 100, "included": True,
                "unlimited": False, "used": 100, "remaining": 0, "meter_available": True,
                "resets_on": "2026-11-01"}

    monkeypatch.setattr(chat_usage, "status", status)
    response = client.post(
        "/api/chat",
        json={"message": "What is the margin?"},
        headers={"Authorization": f"Bearer {create_token(7, 'a@b.no', 'operator')}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "grounded_fallback"
    assert "used up" in body["allowance_note"]
    assert "at no model cost" in body["allowance_note"]
