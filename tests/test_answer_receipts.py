"""WS-49 — the answer receipt: prove what the model saw, without storing the question.

A customer who says "your assistant told me X" can only be answered if the facts, their `as_of`,
the mode and the claim-check verdict were retained. A receipt does that while storing *less* than
a transcript: the question is hashed, the answer text is not stored, and the facts carry the dates
they had at the time.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from core.auth import create_token
from core.llm import receipts


def test_a_question_is_hashed_not_stored():
    digest = receipts.question_hash("What is the margin on my farm?")
    assert len(digest) == 32
    assert "margin" not in digest
    assert digest == receipts.question_hash("  what is the margin on my farm?  ")


def test_retention_is_stored_not_promised():
    now = dt.datetime(2026, 10, 18, tzinfo=dt.UTC)
    assert receipts.retained_until(now).year == 2028


@pytest.mark.asyncio
async def test_a_model_answer_gets_a_receipt_and_a_refusal_does_not():
    answer = {
        "mode": "grounded",
        "model": "test-model",
        "sources": [{"key": "price.spot", "as_of": "2026-W41", "provenance": "live"}],
        "verification": {"checked": 3, "unverified": [], "clean": True},
        "usage": {"cost_usd": 0.0082},
        "latency_ms": 120.0,
        "question": "What is the margin?",
    }
    receipt_id = await receipts.record("user:receipt-test", answer)
    assert receipt_id

    refused = dict(answer, mode="refusal")
    assert await receipts.record("user:receipt-test", refused) is None

    withheld = dict(answer, mode="withheld")
    assert await receipts.record("user:receipt-test", withheld) is None


@pytest.mark.asyncio
async def test_the_receipt_carries_the_dates_the_customer_saw():
    answer = {
        "mode": "grounded_fallback",
        "model": "",
        "sources": [{"key": "bloom.chlorophyll", "as_of": "2026-04-05", "age_days": 196}],
        "verification": {"checked": 0, "unverified": [], "clean": True},
        "usage": {"cost_usd": 0.0},
        "latency_ms": 10.0,
        "question": "How old is the chlorophyll?",
    }
    await receipts.record("user:receipt-dates", answer)
    rows = await receipts.list_for("user:receipt-dates")
    row = next(r for r in rows if r["sources"])
    assert row["sources"][0]["as_of"] == "2026-04-05"
    assert row["sources"][0]["age_days"] == 196
    assert row["question_hash"]


@pytest.mark.asyncio
async def test_a_receipt_belongs_to_one_account():
    answer = {
        "mode": "grounded",
        "model": "m",
        "sources": [],
        "verification": {},
        "usage": {"cost_usd": 0.0},
        "latency_ms": 1.0,
        "question": "q",
    }
    await receipts.record("user:owner", answer)
    rows = await receipts.list_for("user:someone-else")
    assert all(row["question_hash"] != receipts.question_hash("q") for row in rows)


def test_the_receipts_endpoint_needs_an_account_and_explains_retention():
    from core.api import app

    client = TestClient(app)
    assert client.get("/api/chat/receipts").status_code == 401

    response = client.get(
        "/api/chat/receipts",
        headers={"Authorization": f"Bearer {create_token(7, 'a@b.no', 'operator')}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["retention_months"] == 24
    assert "stored as a hash" in body["note"]
