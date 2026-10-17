"""WS-14 — lice lineage propagation to the last consumers.

The WS-1 rule is that a lice-derived value may claim live only through the
lineage of the rows it was computed from. WS-14 extends that rule from the
lice routes to every consumer (decision, welfare, treatment, ESG, supply
chain, compliance, reporting) and pins two behaviours that used to drift:

* ``freshness`` is the **observation** time (the ISO week's Monday 00:00 UTC),
  never the request time — otherwise a months-old week looks current.
* a payload whose lineage is empty/unknown degrades with a note instead of
  keeping a blanket ``DataProvenance.live`` stamp.

These tests are deterministic: they inject ``now`` / synthetic rows for the
pure helpers and monkeypatch the engines for the route wiring, so they neither
depend on the local database's vintage nor on network access.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from core.api import app
from core.source_lineage import provenance_for, summarise_rows

# 2026-W14 is the week the dev/CI demo seed reports; using ``fromisocalendar``
# keeps the expectation derived from the week instead of hardcoding a date.
MONDAY = dt.date.fromisocalendar(2026, 14, 1)
NOW = dt.datetime.combine(MONDAY, dt.time(6, 0), tzinfo=dt.UTC)
FETCHED = dt.datetime.combine(MONDAY, dt.time(3, 0), tzinfo=dt.UTC)


def _row(source="barentswatch", year=2026, week=14, fetched_at=FETCHED) -> dict:
    return {
        "source": source,
        "year": year,
        "week": week,
        "fetched_at": (
            fetched_at.isoformat() if isinstance(fetched_at, dt.datetime) else fetched_at
        ),
    }


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestSummariseRowsContract:
    """The primitives every WS-14 consumer relies on."""

    def test_verified_fresh_rows_are_live(self):
        lineage = summarise_rows([_row()], now=NOW)
        assert lineage["is_live"] is True
        assert lineage["note"] is None
        assert lineage["rows_used"] == 1
        assert lineage["latest_week"] == "2026-W14"

    def test_empty_row_list_degrades(self):
        lineage = summarise_rows([])
        assert lineage["rows_used"] == 0
        assert lineage["is_live"] is False
        assert "no lice rows" in lineage["note"]

    def test_empty_mapping_degrades(self):
        # A consumer that passes ``{}`` (or rows without a source) must never
        # inherit liveness from its caller.
        lineage = summarise_rows([{}])
        assert lineage["is_live"] is False
        assert lineage["by_class"]["unverified"] == 1
        assert "unverifiable" in lineage["note"]

    def test_synthetic_rows_are_never_live(self):
        lineage = summarise_rows([_row(source="demo_seed")], now=NOW)
        assert lineage["is_live"] is False
        assert lineage["by_class"]["synthetic"] == 1
        assert "synthetic" in lineage["note"]

    def test_null_source_is_unverified(self):
        lineage = summarise_rows([_row(source=None)], now=NOW)
        assert lineage["is_live"] is False
        assert lineage["by_class"]["unverified"] == 1

    def test_provenance_for_empty_lineage_degrades(self):
        prov = provenance_for({}, "some lice-derived score", 0.8)
        assert prov["is_live"] is False
        assert prov["fallback_reason"]
        assert prov["confidence"] <= 0.40

    def test_provenance_for_none_lineage_degrades(self):
        prov = provenance_for(None, "some lice-derived score", 0.8)
        assert prov["is_live"] is False



class TestFreshnessIsObservationTime:
    """WS-14 widened rule: freshness = newest observation, not request time."""

    def test_freshness_is_iso_week_monday(self):
        lineage = summarise_rows([_row()], now=NOW)
        prov = provenance_for(lineage, "label", 0.8)
        expected = f"{MONDAY.isoformat()}T00:00:00+00:00"
        assert prov["freshness"] == expected
        assert prov["is_live"] is True

    def test_degraded_payload_also_reports_observation_time(self):
        lineage = summarise_rows([_row(source="demo_seed")], now=NOW)
        prov = provenance_for(lineage, "label", 0.8)
        assert prov["is_live"] is False
        assert prov["freshness"] == f"{MONDAY.isoformat()}T00:00:00+00:00"
        assert prov["fallback_reason"] == lineage["note"]

    def test_stale_week_degrades(self):
        # 2026-W14 observed ~6 months after NOW's week: weekly reports cannot be
        # live this late, whatever the fetch time says.
        late = NOW + dt.timedelta(days=180)
        lineage = summarise_rows([_row()], now=late)
        assert lineage["is_live"] is False
        assert "weeks old" in lineage["note"]



class TestTrafficLightFreshness:
    """The widened rule on the one visible route that is calendar-, not lice-driven."""

    def test_freshness_is_the_decision_date(self, client, monkeypatch):
        from core.market.traffic_light_simulator import traffic_light_simulator

        async def fake_colors() -> dict:
            return {
                "total_pas": 13,
                "production_areas": [],
                "decision": {
                    "decided_on": "2026-06-19",
                    "regulation": "FOR-2026-08-20-1764",
                },
            }

        monkeypatch.setattr(traffic_light_simulator, "get_current_colors", fake_colors)
        r = client.get("/api/regulatory/traffic-light/current")
        assert r.status_code == 200
        prov = r.json()["data_provenance"]
        assert prov["is_live"] is True
        # Freshness is the observation (decision date), never the request time.
        assert prov["freshness"].startswith("2026-06-19")
        assert "2026-06-19" in prov["source"]

    def test_undated_decision_degrades(self, client, monkeypatch):
        from core.market.traffic_light_simulator import traffic_light_simulator

        async def fake_colors() -> dict:
            return {"total_pas": 13, "production_areas": [], "decision": {}}

        monkeypatch.setattr(traffic_light_simulator, "get_current_colors", fake_colors)
        r = client.get("/api/regulatory/traffic-light/current")
        assert r.status_code == 200
        prov = r.json()["data_provenance"]
        assert prov["is_live"] is False
        assert prov["fallback_reason"]


class TestConsumerRoutesCarryLineage:
    """Route wiring: consumers expose lineage and never blanket-claim live."""

    def test_esg_summary_carries_lineage(self, client, monkeypatch):
        from core.market.esg_scorer import esg_scorer

        async def fake_summary() -> dict:
            return {"n_companies": 0}

        monkeypatch.setattr(esg_scorer, "get_summary", fake_summary)
        r = client.get("/api/esg/summary")
        assert r.status_code == 200
        payload = r.json()
        assert "lineage" in payload
        prov = payload["data_provenance"]
        # Whatever the local DB holds, provenance must agree with its lineage.
        assert prov["is_live"] == (payload["lineage"]["note"] is None)

    def test_esg_scores_rows_carry_lineage(self, client, monkeypatch):
        from core.market.esg_scorer import esg_scorer

        async def fake_all() -> list[dict]:
            return [{"rank": 1, "company_name": "Fake AS", "total": 50.0}]

        monkeypatch.setattr(esg_scorer, "get_all", fake_all)
        r = client.get("/api/esg/scores")
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and rows
        assert "lineage" in rows[0]
        assert "data_provenance" in rows[0]

    def test_treatment_optimize_attaches_lineage(self, client, monkeypatch):
        from core.market.treatment_optimizer import treatment_optimizer

        # Async on purpose: the engine methods are coroutines, so a route that
        # forgets ``await`` returns a coroutine and fails here (regression guard
        # for the missing-await bug these endpoints shipped with).
        async def fake_optimize(locality_no: int, budget_nok=None) -> dict:
            return {"locality_no": locality_no, "recommendation": "wait"}

        monkeypatch.setattr(treatment_optimizer, "optimize_timing", fake_optimize)
        r = client.get("/api/treatment/optimize/12071")
        assert r.status_code == 200
        payload = r.json()
        assert payload["locality_no"] == 12071
        assert "lineage" in payload
        assert payload["data_provenance"]["is_live"] == (
            payload["lineage"]["note"] is None
        )

    def test_treatment_compare_attaches_lineage(self, client, monkeypatch):
        from core.market.treatment_optimizer import treatment_optimizer

        async def fake_compare(locality_no: int) -> dict:
            return {"locality_no": locality_no, "treatments": []}

        monkeypatch.setattr(treatment_optimizer, "compare_treatments", fake_compare)
        r = client.get("/api/treatment/compare/12071")
        assert r.status_code == 200
        payload = r.json()
        assert "lineage" in payload
        assert payload["data_provenance"]["is_live"] == (
            payload["lineage"]["note"] is None
        )

    def test_treatment_network_schedule_attaches_lineage(self, client, monkeypatch):
        from core.market.treatment_optimizer import treatment_optimizer

        async def fake_schedule(pa: int) -> dict:
            return {"pa": pa, "schedule": []}

        monkeypatch.setattr(treatment_optimizer, "network_schedule", fake_schedule)
        r = client.get("/api/treatment/network-schedule/3")
        assert r.status_code == 200
        payload = r.json()
        assert "lineage" in payload
        assert "data_provenance" in payload

    def test_treatment_cost_benefit_attaches_lineage(self, client, monkeypatch):
        from core.market.treatment_optimizer import treatment_optimizer

        async def fake_cost_benefit(locality_no: int, treatment_type: str) -> dict:
            return {"locality_no": locality_no, "treatment_type": treatment_type}

        monkeypatch.setattr(
            treatment_optimizer, "cost_benefit_analysis", fake_cost_benefit
        )
        r = client.get("/api/treatment/cost-benefit/12071?treatment_type=mechanical")
        assert r.status_code == 200
        payload = r.json()
        assert "lineage" in payload
        assert "data_provenance" in payload

    def test_welfare_score_degrades_on_empty_lineage(self, client, monkeypatch):
        from core.market.welfare_scorer import WelfareScore, welfare_scorer

        async def fake_score(locality_no: int) -> WelfareScore:
            # No lice row found: the engine leaves lice_lineage empty, and the
            # route must degrade instead of stamping live.
            return WelfareScore(
                total_score=80.0,
                grade="B",
                components={"lice": 1.0},
                predicted_mortality_7d=0.2,
                alert_reason="no lice row",
                locality_no=locality_no,
                scored_at=dt.datetime.now(dt.UTC).isoformat(),
            )

        monkeypatch.setattr(welfare_scorer, "score_farm", fake_score)
        r = client.get("/api/welfare/score/12071")
        assert r.status_code == 200
        payload = r.json()
        assert payload["lice_lineage"] == {}
        prov = payload["data_provenance"]
        assert prov["is_live"] is False
        assert prov["fallback_reason"]

    def test_welfare_pa_summary_carries_lineage(self, client, monkeypatch):
        from core.market.welfare_scorer import WelfareScore, welfare_scorer

        async def fake_score(locality_no: int) -> WelfareScore:
            return WelfareScore(
                total_score=70.0,
                grade="C",
                components={},
                predicted_mortality_7d=0.4,
                alert_reason="ok",
                locality_no=locality_no,
            )

        monkeypatch.setattr(welfare_scorer, "score_farm", fake_score)
        r = client.get("/api/welfare/pa/3")
        assert r.status_code == 200
        payload = r.json()
        assert "lineage" in payload
        assert payload["data_provenance"]["is_live"] == (
            payload["lineage"]["note"] is None
        )


class TestDegradedSideWins:
    """A payload is live only when *every* contributing claim is live.

    WS-14 regression guards: a clean lineage must not launder a fallback model
    result, and a route must never overwrite the lineage an engine recorded for
    the rows it actually used.
    """

    def test_attach_lineage_uses_the_engine_lineage(self):
        from core.routers.decision_routes import _attach_lineage

        live = summarise_rows([_row()], now=NOW)
        engine = summarise_rows([_row(source="demo_seed")], now=NOW)
        payload = _attach_lineage(
            {"locality_no": 1, "lineage": engine}, live, "engine label", 0.65
        )
        # The route's newest-week lineage must not replace the engine's.
        assert payload["lineage"] is engine
        assert payload["data_provenance"]["is_live"] is False
        assert payload["data_provenance"]["fallback_reason"] == engine["note"]

    def test_gnn_predict_keeps_model_fallback_reason(self, client, monkeypatch):
        import core.source_lineage as lineage_mod
        from core.market.lice_gnn import lice_gnn_trainer

        async def fake_lineage_for(session, *predicates, year=None) -> dict:
            return summarise_rows([_row()], now=NOW)

        def fake_predict(farm_id: int) -> dict:
            # Honest engine contract: fallback output is tagged as such.
            return {"farm_id": farm_id, "model": "seasonal-naive-fallback", "predictions": []}

        monkeypatch.setattr(lineage_mod, "lineage_for", fake_lineage_for)
        monkeypatch.setattr(lice_gnn_trainer, "is_available", lambda: True)
        monkeypatch.setattr(lice_gnn_trainer, "predict", fake_predict)
        r = client.get("/api/gnn/predict/12071")
        assert r.status_code == 200
        prov = r.json()["data_provenance"]
        # Clean rows + fallback model = still degraded, and the model reason survives.
        assert prov["is_live"] is False
        assert "fallback" in prov["fallback_reason"]

    def test_welfare_pa_rollup_degrades_when_a_farm_fails(self, client, monkeypatch):
        from core.market.welfare_scorer import welfare_scorer

        async def failing_score(locality_no: int):
            raise RuntimeError("lice query failed")

        monkeypatch.setattr(welfare_scorer, "score_farm", failing_score)
        r = client.get("/api/welfare/pa/3")
        assert r.status_code == 200
        payload = r.json()
        prov = payload["data_provenance"]
        assert prov["is_live"] is False
        # A failed farm is recorded as a failed fetch, never silently dropped.
        assert "fetch failed" in prov["fallback_reason"]

