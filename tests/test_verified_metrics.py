"""WS-48 — a watch that cannot fire honestly is not a watch.

The council's rank 5: the alert evaluator was the last consumer that skipped the lineage work the
rest of the platform enforces. It compared a seven-month-old (or demo-seeded) lice row and
reported "OK"; `disease_count` returned `0.0` on failure, so a dead feed evaluated as "no
outbreaks"; and chat-to-alert seeded thresholds from a question with no plausibility check and no
§ 8 cross-check — "lice in PA 3 above 0.4" is twice the legal limit in the southern spring window
and *below* it in October.

These tests pin the one definition of "current", the refusal to evaluate against a stale value,
the § 8 cross-check and the plausibility band.
"""
from __future__ import annotations


import pytest

from core.market import verified_metrics
from core.market.verified_metrics import LIVE, STALE, UNAVAILABLE, plausibility, verified_current


@pytest.fixture()
def client():
    from core.api import app

    return TestClient(app)


from fastapi.testclient import TestClient  # noqa: E402  (kept below the fixture for readability)


def test_plausibility_rejects_a_threshold_that_can_never_fire():
    ok, why = plausibility("lice_avg", 40.0)
    assert ok is False
    assert "never fire" in why
    assert plausibility("lice_avg", 0.6)[0] is True
    assert plausibility("spot_price", 72.55)[0] is True
    assert plausibility("spot_price", 2.0)[0] is False


@pytest.mark.asyncio
async def test_a_stale_lice_row_is_reported_stale_not_current(monkeypatch):
    async def fake_lice(production_area, now):
        return verified_metrics.VerifiedMetric(
            metric="lice_avg",
            value=0.31,
            as_of="2026-W15",
            age_days=210,
            source="BarentsWatch",
            provenance=STALE,
            note="the newest verified lice report is 2026-W15 (210 days old)",
        )

    monkeypatch.setattr(verified_metrics, "_lice", fake_lice)
    state = await verified_current("lice_avg")
    assert state.provenance == STALE
    assert state.current is False
    assert state.age_days == 210


@pytest.mark.asyncio
async def test_an_unreadable_disease_feed_is_unavailable_not_zero(monkeypatch):
    from core.market import mattilsynet_client as matt

    async def broken(*args, **kwargs):
        raise RuntimeError("feed down")

    monkeypatch.setattr(matt.mattilsynet_client, "fetch_disease_cases", broken)
    state = await verified_current("disease_count")
    assert state.provenance == UNAVAILABLE
    assert state.value is None, "a dead feed must not evaluate as 'no outbreaks'"


@pytest.mark.asyncio
async def test_the_spot_price_is_current_with_its_week_and_age():
    state = await verified_current("spot_price")
    assert state.provenance in (LIVE, STALE)
    assert state.value and state.value > 10
    assert state.as_of and state.as_of.startswith("20")
    assert state.age_days is not None


def test_a_rule_below_the_legal_limit_is_refused(client, monkeypatch):
    async def no_state(metric, question, area):
        return {"metric": metric, "value": 0.31, "current": True, "provenance": "live",
                "as_of": "2026-W41", "age_days": 13}

    monkeypatch.setattr("core.routers.chat_routes._current_value", no_state)
    response = client.post(
        "/api/chat/save-alert",
        json={"question": "Tell me when lice in PA 3 goes above 0.4"},
        headers={"Authorization": f"Bearer {__import__('core.auth', fromlist=['create_token']).create_token(7, 'a@b.no', 'operator')}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["saved"] is False
    assert body["reason"] == "below_legal_limit"
    assert "§ 8" in body["message"]


def test_an_implausible_threshold_is_refused(client, monkeypatch):
    async def no_state(metric, question, area):
        return {"metric": metric, "value": 0.31, "current": True, "provenance": "live"}

    monkeypatch.setattr("core.routers.chat_routes._current_value", no_state)
    response = client.post(
        "/api/chat/save-alert",
        json={"question": "Tell me when lice goes above 40"},
        headers={"Authorization": f"Bearer {__import__('core.auth', fromlist=['create_token']).create_token(7, 'a@b.no', 'operator')}"},
    )
    body = response.json()
    assert body["saved"] is False
    assert body["reason"] == "implausible_threshold"


def test_a_stale_metric_cannot_seed_a_threshold(client, monkeypatch):
    async def stale(metric, question, area):
        return {"metric": metric, "value": 0.31, "current": False, "provenance": "stale",
                "age_days": 210, "note": "the newest verified lice report is 2026-W15",
                "as_of": "2026-W15"}

    monkeypatch.setattr("core.routers.chat_routes._current_value", stale)
    response = client.post(
        "/api/chat/save-alert",
        json={"question": "Tell me when lice exceeds the level"},
        headers={"Authorization": f"Bearer {__import__('core.auth', fromlist=['create_token']).create_token(7, 'a@b.no', 'operator')}"},
    )
    body = response.json()
    assert body["saved"] is False
    assert body["reason"] == "no verified current value to seed the threshold"
    assert "2026-W15" in body["message"]
