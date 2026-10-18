"""WS-33 — the bloom surface must not claim a currency or a certainty it has not got.

The audit found six defects: the page crashed on the response envelope, six-month-old
chlorophyll wore a live badge, ``chl_a_trend`` was computed against the row the agent
had just written (0.0 on all 123 045 rows), 842 alerts said "sent" with no channel
configured, the bio-risk disease count called a method that does not exist, and the
brief reported 5 108 sites from every row ever stored. These tests pin the fixes.
"""
from __future__ import annotations

import datetime as dt
import inspect

import pytest

from core.bloom.risk_model import compute_bloom_risk


# ── 1. The risk model: a band, not a toxicity probability ───────────────


def test_the_result_says_it_is_not_a_toxicity_measurement():
    result = compute_bloom_risk(6.0, sst=12.0, chl_a_trend=0.5)
    assert result.is_toxicity_measurement is False
    assert "not toxicity" in result.measurement


def test_a_missing_trend_earns_no_bonus_and_says_so():
    unknown = compute_bloom_risk(6.0, sst=12.0, chl_a_trend=None)
    rising = compute_bloom_risk(6.0, sst=12.0, chl_a_trend=1.5)
    assert unknown.chl_a_trend is None
    assert any("trend unavailable" in factor for factor in unknown.contributing_factors)
    assert rising.risk_score > unknown.risk_score
    assert any("Rapid chl-a increase" in factor for factor in rising.contributing_factors)


def test_zero_trend_is_a_measurement_not_a_default():
    flat = compute_bloom_risk(6.0, sst=12.0, chl_a_trend=0.0)
    assert flat.chl_a_trend == 0.0
    assert any("trend unavailable" in f for f in flat.contributing_factors) is False


# ── 2. Freshness: live only from the newest observation ────────────────


class _Result:
    def __init__(self, *, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar(self):
        return self._scalar

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self


class _Session:
    def __init__(self, results):
        self._results = list(results)
        self._index = 0

    async def execute(self, *_args, **_kwargs):
        result = self._results[self._index]
        self._index += 1
        return result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _patch_session(monkeypatch, results):
    """Patch the session factory where the router *bound* it at import time."""
    from core.routers import bloom_routes

    monkeypatch.setattr(
        bloom_routes, "get_async_session", lambda: _Session(results), raising=False
    )


@pytest.mark.asyncio
async def test_an_old_observation_degrades_with_its_age(monkeypatch):
    from core.routers import bloom_routes

    old = dt.datetime.now(dt.UTC) - dt.timedelta(days=196)
    _patch_session(monkeypatch, [_Result(scalar=old), _Result(rows=[])])
    freshness = await bloom_routes._bloom_freshness()
    assert freshness["age_days"] == 196
    provenance = bloom_routes._bloom_provenance(freshness)
    assert provenance["is_live"] is False
    assert "196 days old" in provenance["fallback_reason"]
    assert provenance["freshness"].startswith(old.date().isoformat())


@pytest.mark.asyncio
async def test_a_current_observation_is_live(monkeypatch):
    from core.routers import bloom_routes

    fresh = dt.datetime.now(dt.UTC) - dt.timedelta(days=1)
    _patch_session(monkeypatch, [_Result(scalar=fresh), _Result(rows=[])])
    freshness = await bloom_routes._bloom_freshness()
    assert bloom_routes._bloom_provenance(freshness)["is_live"] is True


@pytest.mark.asyncio
async def test_an_empty_store_is_never_live(monkeypatch):
    from core.routers import bloom_routes

    _patch_session(monkeypatch, [_Result(scalar=None), _Result(rows=[]), _Result(scalar=None)])
    freshness = await bloom_routes._bloom_freshness()
    assert freshness["observed_at"] is None
    assert bloom_routes._bloom_provenance(freshness)["is_live"] is False


@pytest.mark.asyncio
async def test_a_mixed_dataset_store_is_named(monkeypatch):
    """The model's default id (1 km L3) is not the client's product (4 km L4)."""
    from core.routers import bloom_routes

    fresh = dt.datetime.now(dt.UTC) - dt.timedelta(days=1)
    _patch_session(
        monkeypatch,
        [
            _Result(scalar=fresh),
            _Result(rows=[("cmems_obs-oc_atl_bgc-plankton_nrt_l3-multi-1km_P1D", 10)]),
        ],
    )
    freshness = await bloom_routes._bloom_freshness()
    assert freshness["dataset_note"]
    assert "not interchangeable" in freshness["dataset_note"]


def test_the_routes_carry_the_freshness_fields():
    from core.routers import bloom_routes

    source = inspect.getsource(bloom_routes)
    assert source.count("_bloom_provenance(freshness)") >= 3
    assert '"age_days": freshness["age_days"]' in source
    # The unconditional live stamp is gone from every route.
    assert 'DataProvenance.live("Copernicus CMEMS chlorophyll-a"' not in source


# ── 3. Alerts: delivery truth ──────────────────────────────────────────


def test_the_message_calls_itself_a_chlorophyll_watch():
    from core.bloom.notifications import _format_message

    message = _format_message("Testfjord", 10029, "HIGH", 60, 6.1)
    assert "CHLOROPHYLL WATCH" in message
    assert "not a toxicity measurement" in message
    assert "not a harmful-algal-bloom confirmation" in message
    assert "recommended actions" not in message.lower()


@pytest.mark.asyncio
async def test_an_unconfigured_channel_records_not_configured(monkeypatch):
    from core.bloom import notifications

    stored = []

    class _WriteSession(_Session):
        def add_all(self, objs):
            stored.extend(objs)

    monkeypatch.setattr(
        notifications, "get_async_session", lambda: _WriteSession([_Result(rows=[])])
    )
    monkeypatch.setattr(notifications, "_sms_configured", lambda: False)
    monkeypatch.setattr(notifications, "_email_configured", lambda: False)

    alerts = await notifications.send_bloom_alert(
        locality_no=10029,
        locality_name="Testfjord",
        risk_level="CRITICAL",
        risk_score=80,
        chl_a=9.0,
    )
    statuses = {alert.channel: alert.delivery_status for alert in alerts}
    assert statuses == {"sms": "not_configured", "email": "not_configured"}, statuses
    assert all(alert.delivered_at is None for alert in alerts)


@pytest.mark.asyncio
async def test_a_configured_channel_marks_sent_only_after_dispatch(monkeypatch):
    from core.bloom import notifications

    sent = []

    class _WriteSession(_Session):
        def add_all(self, objs):
            pass

    async def fake_send(message):
        sent.append(message)

    async def fake_email(name, level, body):
        sent.append(body)

    monkeypatch.setattr(
        notifications, "get_async_session", lambda: _WriteSession([_Result(rows=[])])
    )
    monkeypatch.setattr(notifications, "_sms_configured", lambda: True)
    monkeypatch.setattr(notifications, "_email_configured", lambda: True)
    monkeypatch.setattr(notifications, "_send_sms", fake_send)
    monkeypatch.setattr(notifications, "_send_email", fake_email)

    alerts = await notifications.send_bloom_alert(
        locality_no=10029, locality_name="Testfjord", risk_level="CRITICAL",
        risk_score=80, chl_a=9.0,
    )
    assert len(sent) == 2
    assert {alert.delivery_status for alert in alerts} == {"sent"}
    assert all(alert.delivered_at is not None for alert in alerts)


# ── 4. Trend and brief source rules ────────────────────────────────────


def test_the_trend_excludes_the_row_just_written():
    from agents.bloom_agent import BloomAgent

    source = inspect.getsource(BloomAgent._compute_trend)
    assert "ChlorophyllReading.date < current_dt" in source
    assert "return None" in source


def test_the_brief_counts_current_sites_not_all_history():
    from core.market import morning_brief

    source = inspect.getsource(morning_brief)
    assert "func.distinct(BloomRiskAssessment.locality_no)" in source
    assert "BloomRiskAssessment.assessed_at >= week_start" in source


def test_the_bio_risk_disease_count_calls_the_real_client_api():
    from core.routers import bloom_routes

    source = inspect.getsource(bloom_routes)
    # The comment is allowed to explain the old bug; the call must be gone.
    assert "norway = mattilsynet_client.get_active_outbreaks()" not in source
    assert "fetch_disease_cases" in source
    assert '"status": "unavailable"' in source


# ── 5. The page contract ───────────────────────────────────────────────


def test_the_frontend_no_longer_claims_live_monitoring():
    from pathlib import Path

    page = Path("frontend/src/app/bloom/page.tsx").read_text(encoding="utf-8")
    assert "Live monitoring" not in page
    assert "riskBody.items" in page, "the envelope must be unwrapped (this was the crash)"
    assert "What it cannot show" in page
    assert "chlorophyll band, not a toxicity measurement" in page

    map_component = Path("frontend/src/components/BloomMap.tsx").read_text(encoding="utf-8")
    assert "chl_a_trend: number | null" in map_component


# ── 6. Dated context (WS-34) ───────────────────────────────────────────


def test_the_context_events_are_sourced_and_not_a_forecast():
    from core.bloom.context import LIMITATIONS, REGIONAL_EVENTS, context

    assert len(REGIONAL_EVENTS) >= 3
    for event in REGIONAL_EVENTS:
        assert event["source"] and event["source_url"].startswith("https://")
        assert event["species"] and event["areas"]
    block = context()
    assert block["imr_algeinfo"]["api"] is None
    assert "no machine-readable interface" in block["imr_algeinfo"]["api_note"].lower()
    text = " ".join(block["limitations"]).lower()
    assert "not toxicity" in text
    assert "pycnocline" in text
    assert len(LIMITATIONS) == 5
    assert "probability" in block["note"]


def test_the_context_route_never_claims_live():
    from fastapi.testclient import TestClient

    from core.api import app

    body = TestClient(app).get("/api/bloom/context").json()
    assert body["data_provenance"]["is_live"] is False
    assert "dated link, not a live feed" in body["data_provenance"]["fallback_reason"]
    assert body["imr_algeinfo"]["api"] is None
