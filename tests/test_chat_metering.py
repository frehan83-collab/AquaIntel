"""WS-38 — chat is metered, gated by plan, and convertible into a running alert.

Two commercial defects motivated this: the chat was free to any Desk plan while the
farmer plan paying more (Operator, NOK 4,900) had no chat at all, and a single power user
could consume the platform's whole USD 100/month model budget because nothing counted
tokens per user.

These tests pin the allowance arithmetic, the 402 payloads, the metering write, and the
save-as-alert conversion (including its refusal to invent a metric or a threshold).
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from core.auth import create_token
from core.llm import usage as chat_usage
from core.llm.chat_service import ChatAnswer

NOW = dt.datetime(2026, 10, 18, 12, 0, tzinfo=dt.UTC)


def _token(tier: str, user_id: int = 7) -> str:
    return create_token(user_id, f"user{user_id}@example.com", tier)


@pytest.fixture()
def client():
    from core.api import app

    return TestClient(app)


# ── 1. The allowance arithmetic ────────────────────────────────────────


def test_each_plan_states_its_allowance():
    assert chat_usage.allowance_for("free") == 0
    assert chat_usage.allowance_for("operator") == 100
    assert chat_usage.allowance_for("professional") == 300
    assert chat_usage.allowance_for("enterprise") == 1000
    assert chat_usage.allowance_for("intelligence") == -1
    assert chat_usage.allowance_for("nonsense-plan") == 0


def test_the_farmer_plan_now_includes_chat():
    """Operator pays 4,900 and Desk 2,990; the farmer must not lack the feature."""
    from core.entitlements import get_plan, route_allowed

    assert get_plan("operator").chat_questions_per_month > 0
    assert route_allowed("operator", "/api/chat") is True


def test_exhaustion_and_inclusion_rules():
    assert chat_usage.not_included({"allowance": 0}) is True
    assert chat_usage.not_included({"allowance": 100}) is False
    assert chat_usage.exhausted({"allowance": 100, "used": 99, "unlimited": False}) is False
    assert chat_usage.exhausted({"allowance": 100, "used": 100, "unlimited": False}) is True
    assert chat_usage.exhausted({"allowance": -1, "used": 9999, "unlimited": True}) is False


def test_the_month_key_is_stable():
    assert chat_usage.month_key(NOW) == "2026-10"


@pytest.mark.asyncio
async def test_status_reports_remaining_and_the_reset(monkeypatch):
    async def fake_used(user_key, *, now=None):
        return {"month": "2026-10", "questions": 40, "input_tokens": 1, "output_tokens": 1,
                "cost_usd": 0.8}

    monkeypatch.setattr(chat_usage, "used_this_month", fake_used)
    status = await chat_usage.status("user:7", "operator", now=NOW)
    assert status["allowance"] == 100
    assert status["used"] == 40
    assert status["remaining"] == 60
    assert status["included"] is True
    assert status["meter_available"] is True
    assert status["resets_on"] == "2026-11-01"


@pytest.mark.asyncio
async def test_an_unreadable_meter_is_reported_not_assumed(monkeypatch):
    async def broken(user_key, *, now=None):
        return None

    monkeypatch.setattr(chat_usage, "used_this_month", broken)
    status = await chat_usage.status("user:7", "operator", now=NOW)
    assert status["meter_available"] is False
    assert status["used"] is None
    assert status["remaining"] is None


# ── 2. The route ───────────────────────────────────────────────────────


def test_anonymous_callers_get_a_structured_402(client):
    response = client.post("/api/chat", json={"message": "What is the margin?"})
    assert response.status_code == 402
    body = response.json()
    assert body["error"] == "chat_not_available"
    assert "Operator" in body["message"]
    assert body["allowance"] == 0
    assert body["chat"]["plan"] == "free"


def test_an_exhausted_allowance_names_the_reset(client, monkeypatch):
    async def fake_status(user_key, plan_key, *, now=None):
        return {"plan": plan_key, "month": "2026-10", "allowance": 100, "included": True,
                "unlimited": False, "used": 100, "remaining": 0, "meter_available": True,
                "resets_on": "2026-11-01 (next month)"}

    monkeypatch.setattr(chat_usage, "status", fake_status)
    response = client.post(
        "/api/chat",
        json={"message": "What is the margin?"},
        headers={"Authorization": f"Bearer {_token('operator')}"},
    )
    assert response.status_code == 402
    body = response.json()
    assert "100 grounded questions" in body["message"]
    assert body["remaining"] == 0


def test_a_grounded_answer_is_served_and_metered(client, monkeypatch):
    recorded = {}

    async def fake_status(user_key, plan_key, *, now=None):
        return {"plan": plan_key, "month": "2026-10", "allowance": 100, "included": True,
                "unlimited": False, "used": 3, "remaining": 97, "meter_available": True,
                "resets_on": "2026-11-01 (next month)"}

    async def fake_ask(question, *, user_id="anonymous", history=None, site=None):
        return ChatAnswer(
            answer="The margin is -1.69 NOK/kg.",
            sources=[{"key": "margin.bridge", "provenance": "degraded", "as_of": "2026-07"}],
            followups=["What moved it?"],
            usage={"input_tokens": 4000, "output_tokens": 120, "cost_usd": 0.014},
            model="test-model",
            mode="grounded",
            degraded=True,
        )

    async def fake_record(user_key, usage, *, now=None):
        recorded["user_key"] = user_key
        recorded["usage"] = usage

    monkeypatch.setattr(chat_usage, "status", fake_status)
    monkeypatch.setattr(chat_usage, "record", fake_record)
    monkeypatch.setattr("core.routers.chat_routes.chat_service", type("S", (), {"ask": staticmethod(fake_ask)})())

    response = client.post(
        "/api/chat",
        json={"message": "What is the margin?"},
        headers={"Authorization": f"Bearer {_token('operator')}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "grounded"
    assert body["sources"][0]["key"] == "margin.bridge"
    assert body["chat"]["remaining"] == 97
    assert recorded["usage"]["cost_usd"] == pytest.approx(0.014)
    assert recorded["user_key"] == "user:7"


def test_a_fallback_answer_does_not_consume_the_allowance(client, monkeypatch):
    recorded = {"called": False}

    async def fake_status(user_key, plan_key, *, now=None):
        return {"plan": plan_key, "month": "2026-10", "allowance": 100, "included": True,
                "unlimited": False, "used": 3, "remaining": 97, "meter_available": True,
                "resets_on": "2026-11-01 (next month)"}

    async def fake_ask(question, *, user_id="anonymous", history=None, site=None):
        return ChatAnswer(answer="numbers", mode="grounded_fallback", usage={"cost_usd": 0.0})

    async def fake_record(*args, **kwargs):
        recorded["called"] = True

    monkeypatch.setattr(chat_usage, "status", fake_status)
    monkeypatch.setattr(chat_usage, "record", fake_record)
    monkeypatch.setattr("core.routers.chat_routes.chat_service", type("S", (), {"ask": staticmethod(fake_ask)})())

    response = client.post(
        "/api/chat",
        json={"message": "What is the margin?"},
        headers={"Authorization": f"Bearer {_token('operator')}"},
    )
    assert response.status_code == 200
    assert recorded["called"] is False


def test_the_usage_endpoint_serves_the_meter(client, monkeypatch):
    async def fake_status(user_key, plan_key, *, now=None):
        return {"plan": plan_key, "month": "2026-10", "allowance": 300, "included": True,
                "unlimited": False, "used": 12, "remaining": 288, "meter_available": True,
                "resets_on": "2026-11-01 (next month)"}

    monkeypatch.setattr(chat_usage, "status", fake_status)
    response = client.get(
        "/api/chat/usage", headers={"Authorization": f"Bearer {_token('professional')}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["allowance"] == 300
    assert body["plan_name"] == "Desk"


# ── 3. Save as alert ───────────────────────────────────────────────────


def test_a_question_without_a_metric_is_refused_with_the_metric_list(client):
    response = client.post(
        "/api/chat/save-alert",
        json={"question": "What do you think about the market?"},
        headers={"Authorization": f"Bearer {_token('operator')}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["saved"] is False
    assert "lice_avg" in body["available_metrics"]
    assert "Ask about lice" in body["message"]


def test_a_question_with_an_explicit_threshold_becomes_a_running_rule(client, monkeypatch):
    created = {}

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, *args, **kwargs):
            class _Result:
                def scalar_one_or_none(self):
                    return None

            return _Result()

        def add(self, obj):
            created["obj"] = obj

        async def commit(self):
            created["obj"].id = 42

    monkeypatch.setattr("core.routers.chat_routes.get_async_session", lambda: _Session())

    response = client.post(
        "/api/chat/save-alert",
        json={"question": "Tell me when lice in PA 3 goes above 0.4"},
        headers={"Authorization": f"Bearer {_token('operator')}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["saved"] is True
    assert body["alert_id"] == 42
    assert body["metric"] == "lice_avg"
    assert body["operator"] == ">"
    assert body["threshold"] == pytest.approx(0.4)
    assert body["production_area"] == 3
    assert body["is_active"] is True
    rule = created["obj"]
    assert rule.metric == "lice_avg"
    assert rule.is_active is True
    assert rule.user_id == 7


def test_a_duplicate_watch_is_not_created_twice(client, monkeypatch):
    class _Existing:
        id = 11
        name = "Tell me when lice in PA 3 goes above 0.4"
        metric = "lice_avg"
        operator = ">"
        threshold = 0.4
        production_area = 3

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, *args, **kwargs):
            class _Result:
                def scalar_one_or_none(self):
                    return _Existing()

            return _Result()

        def add(self, obj):  # pragma: no cover - must not be called
            raise AssertionError("a duplicate must not be inserted")

    monkeypatch.setattr("core.routers.chat_routes.get_async_session", lambda: _Session())
    response = client.post(
        "/api/chat/save-alert",
        json={"question": "Tell me when lice in PA 3 goes above 0.4"},
        headers={"Authorization": f"Bearer {_token('operator')}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["saved"] is False
    assert body["duplicate"] is True
    assert body["alert_id"] == 11


def test_the_operator_and_metric_inference():
    from core.routers.chat_routes import (
        _explicit_threshold,
        _infer_area,
        _infer_metric,
        _infer_operator,
    )

    assert _infer_metric("how is the lice pressure") == "lice_avg"
    assert _infer_metric("what is the spot price") == "spot_price"
    assert _infer_metric("chlorophyll trend") == "bloom_risk"
    assert _infer_metric("disease outbreaks") == "disease_count"
    assert _infer_metric("hello there") is None
    assert _infer_operator("when lice drops below 0.2") == "<"
    assert _infer_operator("when lice exceeds 0.5") == ">"
    assert _infer_area("lice in PA 3") == 3
    assert _infer_area("lice in production area 12") == 12
    assert _infer_area("lice in PA 99") is None
    assert _explicit_threshold("lice above 0,45") == pytest.approx(0.45)
    assert _explicit_threshold("lice is high") is None
