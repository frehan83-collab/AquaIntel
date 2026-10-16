"""Named indices (AI-STI / AI-LPI) + Bio→Price Weekly tests (hardening §3).

These lock the *contract* that makes the indices sellable: a published method
version, published weights, component-level traceability, and loud degradation
when a source is unavailable (never a silent substitution).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.api import app
from core.market import indices as ix

PUBLISHED = (ix.AI_STI, ix.AI_LPI)


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


def _throwaway_observation_store(tmp_path, monkeypatch, create_table=True):
    """Bind the observation store to a throwaway SQLite file.

    WS-2: the agent owns the real published history, so no test may write into
    it — before this helper every run stored the current week into the dev DB,
    and this box still carries two such rows written before the lineage guard.
    `save_observation` / `history` / `index_publication.status()` import
    `core.models.Session` at call time, so rebinding it here is enough.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base, IndexObservation

    engine = create_engine(f"sqlite:///{tmp_path / 'observation_store.db'}")
    if create_table:
        Base.metadata.create_all(engine, tables=[IndexObservation.__table__])
    monkeypatch.setattr("core.models.Session", sessionmaker(bind=engine))
    return engine


@pytest.fixture
def observation_store(tmp_path, monkeypatch):
    engine = _throwaway_observation_store(tmp_path, monkeypatch)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def missing_observation_store(tmp_path, monkeypatch):
    """The store bound to a database that has no index_observations table."""
    engine = _throwaway_observation_store(tmp_path, monkeypatch, create_table=False)
    try:
        yield engine
    finally:
        engine.dispose()


class TestMethodology:
    def test_version_is_published_and_matches_results(self):
        method = ix.methodology()
        assert method["version"] == ix.INDEX_METHOD_VERSION
        assert set(method["indices"]) == set(PUBLISHED)

    def test_weights_are_published_and_sum_to_one(self):
        method = ix.methodology()
        for code in PUBLISHED:
            weights = method["indices"][code]["components"]
            assert weights, code
            assert abs(sum(c["weight"] for c in weights.values()) - 1.0) < 1e-6, code
            for entry in weights.values():
                assert entry["scoring"], "every component publishes its scoring"

    def test_bands_are_ordered_and_complete(self):
        bands = [b["band"] for b in ix.methodology()["bands"]]
        # published ascending by minimum (documented order in docs/INDICES.md)
        assert bands == ["minimal", "low", "moderate", "elevated", "severe"]

    def test_limitations_and_planned_components_are_declared(self):
        method = ix.methodology()
        assert method["limitations"]
        assert "v1.1" in method["planned_components"]
        assert method["revision_policy"]


class TestComputation:
    @pytest.mark.parametrize("code", PUBLISHED)
    def test_result_shape_and_ranges(self, code, anyio_backend=None):
        import asyncio

        result = asyncio.run(ix.compute(code))
        assert result["index"] == code
        assert result["version"] == ix.INDEX_METHOD_VERSION
        if result["value"] is not None:
            assert 0.0 <= result["value"] <= 100.0
            assert result["band"] in {"minimal", "low", "moderate", "elevated", "severe"}
        assert result["permalink"] == f"/indices/{code.lower()}"
        assert result["api"] == f"/api/indices/{code.lower()}"
        assert result["methodology_url"] == "/api/indices/methodology"
        assert result["week"].count("-W") == 1
        for component in result["components"]:
            assert {"name", "weight", "score", "raw", "source", "used"} <= set(component)

    def test_band_thresholds(self):
        assert ix._band(85) == "severe"
        assert ix._band(65) == "elevated"
        assert ix._band(45) == "moderate"
        assert ix._band(25) == "low"
        assert ix._band(5) == "minimal"

    def test_unknown_index_is_rejected(self):
        import asyncio

        with pytest.raises(ValueError):
            asyncio.run(ix.compute("AI-NOPE"))


class TestHonestDegradation:
    def test_lineage_note_decides_the_live_claim(self):
        """WS-1: AI-LPI is live iff every lice row the tracker used has a verified
        source (and nothing is missing); otherwise the note names why, unconditionally.

        The zero-arg `_lice_lineage_note()` reflects the tracker's LAST computation,
        so compute first. CI (demo-seeded) and a bulk-loaded dev box (unverified
        rows) both land on the degraded branch today; the live branch is locked
        deterministically by test_ai_lpi_is_live_follows_the_lice_lineage.
        """
        import asyncio

        result = asyncio.run(ix.compute(ix.AI_LPI))
        note = ix._lice_lineage_note()
        if result["provenance"]["is_live"]:
            assert note is None, note
            assert result["lineage_notes"] == [] and result["components_missing"] == []
        else:
            assert result["components_missing"] or note is not None, result
            if note is not None:
                assert note in result["lineage_notes"], result["lineage_notes"]
                assert note in result["provenance"]["fallback_reason"]
                # the value is still produced — honest, not hidden
                assert result["components_used"] >= 1

    def test_lpi_lineage_mirrors_the_trackers_rows(self):
        """The index reads the quota tracker's OWN lineage (rows it aggregated),
        never a separate query that could disagree with the value."""
        import asyncio

        from core.market.lice_quota_tracker import lice_quota_tracker as tracker

        result = asyncio.run(ix.compute(ix.AI_LPI))
        lineage = tracker.last_lineage
        if lineage is None:
            assert result["components_missing"], "no lineage only when the tracker failed"
            return
        assert lineage["rows_used"] == sum(lineage["by_class"].values())
        assert tracker.last_is_live == lineage["is_live"]
        assert tracker.last_source == lineage["source"]
        assert lineage["is_live"] == (lineage["note"] is None)
        # the index output is built FROM this lineage, not from a separate query
        assert result["provenance"]["is_live"] == lineage["is_live"]
        assert result["lineage_notes"] == ([lineage["note"]] if lineage["note"] else [])

    def test_component_source_reflects_the_trackers_own_lineage(self):
        """Not a hardcoded label: the index reports what the tracker actually did.

        `biomass_tracker` sets `last_source`/`last_is_live` during the fetch (filters
        synthetic records, else falls back to a historical-pattern estimate), so the
        component source must equal whatever the tracker recorded — not the fixed
        upstream string this code used to assume.
        """
        import asyncio

        from core.market.biomass_tracker import biomass_tracker

        result = asyncio.run(ix.compute(ix.AI_STI))
        component = next(
            (c for c in result["components"] if c["name"] == "biomass_momentum"), None
        )
        if component is None or not component["used"]:
            pytest.skip("biomass component unavailable in this environment")
        assert component["source"] == biomass_tracker.last_source
        if biomass_tracker.last_is_live is False:
            assert any(
                "fallback" in note for note in result["lineage_notes"]
            ), result["lineage_notes"]
            assert result["provenance"]["is_live"] is False


    def test_missing_source_is_named_and_not_reported_as_live(self, monkeypatch):
        import asyncio

        async def _boom(attribute: str):
            raise RuntimeError("source offline")

        monkeypatch.setattr(ix, "_totals_by_month", _boom)
        result = asyncio.run(ix.compute(ix.AI_STI))
        assert "biomass_momentum" in result["components_missing"]
        assert "harvest_pressure" in result["components_missing"]
        assert result["provenance"]["is_live"] is False
        assert result["provenance"]["fallback_reason"]
        # the quota component still works, so a value is still produced
        assert result["components_used"] >= 1
        assert result["value"] is not None

    def test_all_sources_dead_yields_no_value(self, monkeypatch):
        import asyncio

        async def _boom(*_args, **_kwargs):
            raise RuntimeError("everything offline")

        monkeypatch.setattr(ix, "_totals_by_month", _boom)
        monkeypatch.setattr(ix, "_national_emission", _boom)
        result = asyncio.run(ix.compute(ix.AI_STI))
        assert result["value"] is None
        assert result["band"] is None
        assert result["provenance"]["is_live"] is False
        assert "no index component" in (result["provenance"]["fallback_reason"] or "")


class TestHistory:
    def test_publish_then_history_round_trip(self, observation_store):
        import asyncio

        published = asyncio.run(ix.publish(ix.AI_LPI))
        assert published["storage"]["status"] in {"stored", "duplicate"}
        rows = asyncio.run(ix.history(ix.AI_LPI, limit=10))
        assert rows, "published observation must be readable back"
        assert rows[0]["week"] == published["week"]
        assert rows[0]["version"] == ix.INDEX_METHOD_VERSION
        assert rows[0]["provenance"], "history keeps the provenance it was published with"

    def test_publish_is_idempotent_per_week_and_version(self, observation_store):
        import asyncio

        first = asyncio.run(ix.publish(ix.AI_STI))
        second = asyncio.run(ix.publish(ix.AI_STI))
        assert second["storage"]["status"] == "duplicate"
        assert second["storage"]["id"] == first["storage"]["id"]


class TestIndexEndpoints:
    def test_list_indices(self, client):
        body = client.get("/api/indices").json()
        assert body["method_version"] == ix.INDEX_METHOD_VERSION
        assert set(body["indices"]) == set(PUBLISHED)

    @pytest.mark.parametrize("slug", ["ai-sti", "ai-lpi"])
    def test_permalinks_are_stable(self, client, slug):
        r = client.get(f"/api/indices/{slug}")
        assert r.status_code == 200
        assert r.json()["index"] == slug.upper()

    def test_methodology_endpoint(self, client):
        assert client.get("/api/indices/methodology").json()["version"] == ix.INDEX_METHOD_VERSION

    def test_unknown_index_404s(self, client):
        assert client.get("/api/indices/ai-nope").status_code == 404

    def test_history_endpoint(self, client):
        body = client.get("/api/indices/AI-STI/history").json()
        assert body["index"] == ix.AI_STI
        assert isinstance(body["observations"], list)


class TestBioPriceWeekly:
    def test_digest_shape_and_honesty(self, client):
        body = client.get("/api/indices/bio-price-weekly").json()
        assert body["report"] == "Bio>Price Weekly"
        assert body["version"]
        assert body["week"].count("-W") == 1
        assert body["transmission"]["read"] in {"elevated", "balanced", "loose", "unknown"}
        assert "provenance" in body
        assert isinstance(body["caveats"], list)
        assert set(body["indices"]) == set(PUBLISHED)
        # Any caveat must be visible in the provenance, not hidden.
        if body["caveats"]:
            assert body["provenance"]["is_live"] is False
            assert body["provenance"]["fallback_reason"]

    def test_publish_week_stores_both_indices(self, observation_store):
        import asyncio

        from core.market.bio_price_weekly import publish_week

        digest = asyncio.run(publish_week())
        for code in PUBLISHED:
            status = digest["indices"][code]["storage"]["status"]
            assert status in {"stored", "duplicate"}


class TestWeeklyPublication:
    """WS-2: the weekly publication is a scheduled agent, not a test side-effect.

    Every test that writes observations takes the `observation_store` fixture (a
    throwaway SQLite file), so the real history is never touched; the agent's
    clock is injected at fixed instants so a week boundary is crossed
    deterministically whatever the wall clock says.
    """

    import datetime as _dt

    WED_NOON = _dt.datetime(2026, 10, 7, 12, tzinfo=_dt.UTC)  # 2026-W41, Wednesday noon
    MON_0100 = _dt.datetime(2026, 10, 5, 1, tzinfo=_dt.UTC)  # 2026-W41, 1 h into the week
    THU_0100 = _dt.datetime(2026, 10, 8, 1, tzinfo=_dt.UTC)  # 2026-W41, 73 h into the week

    @staticmethod
    def _fake_result(code, as_of, value=42.0, live=True):
        return {
            "index": code,
            "week": as_of.strftime("%G-W%V"),
            "as_of": as_of.isoformat(),
            "version": ix.INDEX_METHOD_VERSION,
            "value": value,
            "band": "moderate",
            "components": [],
            "components_missing": [],
            "provenance": {
                "is_live": live,
                "fallback_reason": None if live else "test: source offline",
            },
        }

    @classmethod
    def _fake_digest(cls, as_of, value=42.0, live=True, per_index=None):
        results = {}
        for code in PUBLISHED:
            override = (per_index or {}).get(code, {})
            results[code] = cls._fake_result(
                code, as_of, override.get("value", value), override.get("live", live)
            )
        return {
            "week": as_of.strftime("%G-W%V"),
            "as_of": as_of.isoformat(),
            "transmission": {"read": "balanced"},
            "caveats": [],
            "indices": results,
        }

    def _agent(self, monkeypatch, build_fn):
        from agents import index_publisher_agent as mod

        monkeypatch.setattr(mod, "build", build_fn)
        agent = mod.IndexPublisherAgent()
        audits: list = []

        async def record(detail: str) -> None:
            audits.append(detail)

        monkeypatch.setattr(agent, "_audit", record)
        return mod, agent, audits

    # ── contracts ──────────────────────────────────────────────────────────

    def test_week_label_and_cadence_contracts(self):
        import datetime as dt

        from core.market import index_publication as pub

        stamp = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)  # ISO week 2026-W01 (Thursday)
        assert pub.current_week_label(stamp) == stamp.strftime("%G-W%V") == "2026-W01"
        assert pub.week_tuple("2026-W42") == (2026, 42)
        assert pub.week_tuple("garbage") is None
        assert pub.week_tuple(None) is None
        assert pub.week_start(self.WED_NOON) == dt.datetime(2026, 10, 5, tzinfo=dt.UTC)
        assert pub.hours_into_week(self.MON_0100) == 1.0
        # an aware non-UTC instant is normalised: Sunday 23:00 UTC is still W40
        oslo = dt.datetime(2026, 10, 5, 1, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        assert pub.current_week_label(oslo) == "2026-W40"
        assert pub.hours_into_week(oslo) >= 0
        # the freshness cadence includes the readiness grace — one definition
        assert pub.FRESHNESS_CADENCE_HOURS == (
            pub.PUBLICATION_CADENCE_HOURS + pub.READINESS_GRACE_HOURS + pub.PUBLISH_TICK_HOURS
        )
        from core.market import freshness_monitor as fm

        spec = next(s for s in fm.SOURCES if s.key == "index_observations")
        assert spec.expected_cadence_hours == pub.FRESHNESS_CADENCE_HOURS
        assert spec.refresh_hint == pub.PUBLISHER

    def test_status_is_honest_when_the_table_is_missing(self, missing_observation_store):
        import asyncio

        from core.market import index_publication as pub

        st = asyncio.run(pub.status())
        assert st["current_week_published"] is False
        assert set(st["missing"]) == set(PUBLISHED)
        assert "missing" in (st["reason"] or "")
        assert st["interval_ok"] is None  # not measurable, never "ok"

    def test_status_never_publishes_raw_driver_errors(self, observation_store, monkeypatch):
        """status() is served on the public GET /api/indices: a driver message that
        could name a host, a user or the SQL must not reach the reason field."""
        import asyncio

        from core.market import index_publication as pub

        def exploding(version, week):
            raise RuntimeError('connection to server at "db.internal" failed: password for user "svc"')

        monkeypatch.setattr(pub, "_read_latest", exploding)
        st = asyncio.run(pub.status(now=self.WED_NOON))
        assert st["reason"] == "index_observations unreadable: RuntimeError"
        assert "db.internal" not in str(st) and "svc" not in str(st)
        assert st["current_week_published"] is False and st["interval_ok"] is None

    def test_status_detects_a_missing_then_published_week(self, observation_store):
        import asyncio

        from core.market import index_publication as pub

        now = self.WED_NOON
        st = asyncio.run(pub.status(now=now))
        assert st["current_week_published"] is False
        assert set(st["missing"]) == set(PUBLISHED)
        assert st["week"] == "2026-W41"
        assert st["version"] == ix.INDEX_METHOD_VERSION
        assert st["within_grace"] is True  # Wednesday noon is 60 h in; the grace is 72 h
        assert asyncio.run(pub.status(now=self.THU_0100))["within_grace"] is False

        # an observation under an OLD method version does not count
        old = self._fake_result(ix.AI_STI, now)
        old["version"] = "0.9.0"
        asyncio.run(ix.save_observation(old))
        assert ix.AI_STI in asyncio.run(pub.status(now=now))["missing"]

        for code in PUBLISHED:
            asyncio.run(ix.save_observation(self._fake_result(code, now, live=code == ix.AI_STI)))
        st = asyncio.run(pub.status(now=now))
        assert st["current_week_published"] is True
        assert st["missing"] == []
        assert st["degraded_current"] == [ix.AI_LPI]  # stored provenance is visible
        for code in PUBLISHED:
            entry = st["indices"][code]
            assert entry["latest_week"] == "2026-W41"
            assert entry["latest_value"] == 42.0
            assert entry["weeks_behind"] == 0
            assert entry["week_steps"] == [] and entry["gaps_days"] == []
            assert entry["interval_ok"] is None  # one observation: no interval yet
        assert st["indices"][ix.AI_STI]["latest_is_live"] is True
        assert st["indices"][ix.AI_LPI]["latest_is_live"] is False
        assert st["interval_ok"] is None

    def test_interval_is_measured_in_iso_weeks_not_wall_clock(self, observation_store):
        """An hourly tick's phase drifts: 7 days + 30 min between two consecutive
        weekly observations is NOT a skipped week; 2 weeks apart is."""
        import asyncio
        import datetime as dt

        from core.market import index_publication as pub

        week1 = self.WED_NOON  # 2026-W41
        week2 = week1 + dt.timedelta(days=7, minutes=30)  # 2026-W42, tick phase drifted
        for stamp in (week1, week2):
            for code in PUBLISHED:
                asyncio.run(ix.save_observation(self._fake_result(code, stamp)))
        st = asyncio.run(pub.status(now=week2))
        assert st["interval_ok"] is True and st["skipped_weeks"] == []
        for code in PUBLISHED:
            assert st["indices"][code]["week_steps"] == [1]
            assert st["indices"][code]["gaps_days"] == [7.02]  # informational only

        week4 = week1 + dt.timedelta(days=21)  # 2026-W44: W43 never published
        before = asyncio.run(pub.status(now=week4))
        assert before["current_week_published"] is False
        assert all(v["weeks_behind"] == 2 for v in before["indices"].values())
        for code in PUBLISHED:
            asyncio.run(ix.save_observation(self._fake_result(code, week4)))
        st = asyncio.run(pub.status(now=week4))
        assert st["current_week_published"] is True
        assert st["interval_ok"] is False
        assert st["max_week_step"] == 2
        assert any("2026-W42→2026-W44" in s for s in st["skipped_weeks"]), st["skipped_weeks"]

    def test_status_flags_a_store_ahead_of_the_clock(self, observation_store):
        import asyncio
        import datetime as dt

        from core.market import index_publication as pub

        for code in PUBLISHED:
            asyncio.run(ix.save_observation(self._fake_result(code, self.WED_NOON)))
            asyncio.run(
                ix.save_observation(self._fake_result(code, self.WED_NOON + dt.timedelta(days=7)))
            )
        st = asyncio.run(pub.status(now=self.WED_NOON))
        assert st["current_week_published"] is True  # looked up directly, not via the window
        for entry in st["indices"].values():
            assert entry["weeks_behind"] == -1 and entry["store_ahead_of_clock"] is True

    def test_readiness_is_per_index_and_uses_the_unrounded_hour(self):
        import datetime as dt

        from core.market import index_publication as pub

        mixed = self._fake_digest(self.WED_NOON, per_index={ix.AI_LPI: {"value": None}})
        ready = pub.readiness(mixed, now=self.WED_NOON)
        assert ready["store"] == [ix.AI_STI]
        assert "no value" in ready["withheld"][ix.AI_LPI]
        assert ready["ready"] is True and ready["degraded"] == []

        degraded = self._fake_digest(self.MON_0100, live=False)
        early = pub.readiness(degraded, now=self.MON_0100)
        assert early["store"] == [] and set(early["withheld"]) == set(PUBLISHED)
        assert early["within_grace"] is True and "waiting" in early["reason"]

        edge = pub.week_start(self.MON_0100) + dt.timedelta(hours=72, seconds=-10)
        assert pub.readiness(degraded, now=edge)["store"] == []  # 71.997 h: still in grace
        at_grace = pub.week_start(self.MON_0100) + dt.timedelta(hours=72)
        late = pub.readiness(degraded, now=at_grace)
        assert late["store"] == list(PUBLISHED) and late["degraded"] == list(PUBLISHED)
        assert late["within_grace"] is False

    # ── the agent ──────────────────────────────────────────────────────────

    def test_agent_publishes_once_per_week_across_a_week_boundary(self, observation_store, monkeypatch):
        import asyncio
        import datetime as dt

        from core.market import index_publication as pub

        calls: list = []

        async def fake_build(as_of=None):
            calls.append(as_of)
            return self._fake_digest(as_of)

        mod, agent, audits = self._agent(monkeypatch, fake_build)
        week1 = self.WED_NOON
        asyncio.run(agent.tick(now=week1))
        # a second tick in the same ISO week must NOT publish again
        asyncio.run(agent.tick(now=week1 + dt.timedelta(hours=1)))
        assert len(calls) == 1, calls
        assert agent.last_published_week == "2026-W41"

        week2 = week1 + dt.timedelta(days=7, minutes=30)
        asyncio.run(agent.tick(now=week2))
        assert len(calls) == 2, calls
        assert agent.last_published_week == "2026-W42"

        st = asyncio.run(pub.status(now=week2))
        assert st["current_week_published"] is True
        assert st["interval_ok"] is True
        assert agent.last_failure is None and agent.waiting is None
        assert any("published" in note.lower() for note in audits), audits
        assert agent.health()["last_published_week"] == "2026-W42"

    def test_tick_without_arguments_uses_the_wall_clock(self, observation_store, monkeypatch):
        """BaseAgent.start() calls tick() bare — that form must keep working."""
        import asyncio

        from core.market import index_publication as pub

        calls: list = []

        async def fake_build(as_of=None):
            calls.append(as_of)
            return self._fake_digest(as_of)

        _mod, agent, _audits = self._agent(monkeypatch, fake_build)
        asyncio.run(agent.tick())
        assert len(calls) == 1 and calls[0] is not None
        assert agent.last_published_week == pub.current_week_label()

    def test_agent_waits_then_stores_a_disclosed_degraded_value(self, observation_store, monkeypatch):
        """Readiness: within the grace only a live value is stored; after it a
        degraded value is stored with its provenance saying why."""
        import asyncio

        from core.market import index_publication as pub

        async def degraded_build(as_of=None):
            return self._fake_digest(as_of, live=False)

        _mod, agent, audits = self._agent(monkeypatch, degraded_build)
        asyncio.run(agent.tick(now=self.MON_0100))
        assert agent.waiting is not None
        assert "waiting" in agent.waiting["reason"] and "source offline" in agent.waiting["reason"]
        assert asyncio.run(pub.status(now=self.MON_0100))["current_week_published"] is False
        assert agent.last_failure is None
        assert agent.health()["waiting"] == agent.waiting

        asyncio.run(agent.tick(now=self.THU_0100))  # past the 72 h grace
        st = asyncio.run(pub.status(now=self.THU_0100))
        assert st["current_week_published"] is True
        assert set(st["degraded_current"]) == set(PUBLISHED)
        assert agent.waiting is None
        assert any("degraded this week" in note for note in audits), audits

    def test_agent_stores_the_ready_index_and_withholds_the_other(self, observation_store, monkeypatch):
        import asyncio
        import datetime as dt

        from core.market import bio_price_weekly as bpw
        from core.market import index_publication as pub

        shape = {ix.AI_LPI: {"value": None}}
        builds: list = []

        async def mixed_build(as_of=None):
            builds.append(as_of)
            return self._fake_digest(as_of, per_index=shape)

        mod, agent, audits = self._agent(monkeypatch, mixed_build)
        stored_codes: list = []
        real_store = bpw.store_digest

        async def spying_store(digest, codes=None):
            stored_codes.append(list(codes) if codes is not None else None)
            return await real_store(digest, codes=codes)

        monkeypatch.setattr(mod, "store_digest", spying_store)

        asyncio.run(agent.tick(now=self.WED_NOON))  # must not raise
        st = asyncio.run(pub.status(now=self.WED_NOON))
        assert st["indices"][ix.AI_STI]["current_week_published"] is True
        assert st["missing"] == [ix.AI_LPI]
        assert stored_codes == [[ix.AI_STI]]
        assert agent.last_failure is None
        assert agent.last_published_week == "2026-W41"
        assert ix.AI_LPI in agent.waiting["reason"]
        assert any("withheld" in note for note in audits), audits

        # next tick, AI-LPI ready: ONLY the still-missing index is stored
        shape[ix.AI_LPI] = {"value": 7.0}
        asyncio.run(agent.tick(now=self.WED_NOON + dt.timedelta(hours=1)))
        assert stored_codes == [[ix.AI_STI], [ix.AI_LPI]], stored_codes
        st = asyncio.run(pub.status(now=self.WED_NOON))
        assert st["missing"] == [] and agent.waiting is None
        assert agent.last_published_week == "2026-W41"

        # a third tick in the same week neither builds nor stores
        asyncio.run(agent.tick(now=self.WED_NOON + dt.timedelta(hours=2)))
        assert len(builds) == 2 and len(stored_codes) == 2

    def test_agent_never_stores_a_null_value(self, observation_store, monkeypatch):
        import asyncio

        from core.market import index_publication as pub

        async def empty_build(as_of=None):
            return self._fake_digest(as_of, value=None, live=False)

        _mod, agent, _audits = self._agent(monkeypatch, empty_build)
        asyncio.run(agent.tick(now=self.THU_0100))  # even past the grace
        assert agent.waiting is not None and "no value" in agent.waiting["reason"]
        assert asyncio.run(pub.status(now=self.THU_0100))["current_week_published"] is False

    def test_agent_records_a_store_failure_and_raises(self, observation_store, monkeypatch):
        """A failed store is a named failure (log + audit + health) and the tick
        raises so the orchestrator counts it — never silence."""
        import asyncio

        import pytest

        async def fake_build(as_of=None):
            return self._fake_digest(as_of)

        mod, agent, audits = self._agent(monkeypatch, fake_build)

        async def broken_store(digest, codes=None):
            raise RuntimeError("simulated store outage")

        monkeypatch.setattr(mod, "store_digest", broken_store)
        with pytest.raises(RuntimeError):
            asyncio.run(agent.tick(now=self.WED_NOON))
        assert agent.last_failure["week"] == "2026-W41"
        assert agent.last_failure["stage"] == "store"
        assert "simulated" in agent.last_failure["reason"]
        assert agent.health()["last_failure"] == agent.last_failure
        assert any("FAILED" in note for note in audits), audits

    def test_build_failure_is_recorded_too(self, observation_store, monkeypatch):
        import asyncio

        import pytest

        async def broken_build(as_of=None):
            raise RuntimeError("simulated compute failure")

        _mod, agent, audits = self._agent(monkeypatch, broken_build)
        with pytest.raises(RuntimeError):
            asyncio.run(agent.tick(now=self.WED_NOON))
        assert agent.last_failure["stage"] == "build"
        assert any("FAILED" in note and "build" in note for note in audits), audits

    def test_losing_the_insert_race_is_not_a_failure(self, observation_store, monkeypatch):
        import asyncio

        from core.market.bio_price_weekly import store_digest as real_store

        async def fake_build(as_of=None):
            return self._fake_digest(as_of)

        mod, agent, audits = self._agent(monkeypatch, fake_build)

        async def racing_store(digest, codes=None):
            await real_store(digest, codes=codes)  # the other writer wins first …
            raise RuntimeError("UNIQUE constraint failed: index_observations")

        monkeypatch.setattr(mod, "store_digest", racing_store)
        asyncio.run(agent.tick(now=self.WED_NOON))  # must not raise
        assert agent.last_failure is None
        assert agent.last_published_week == "2026-W41"
        assert any("another writer" in note for note in audits), audits

    def test_store_unreadable_after_publish_is_not_reported_as_missing(self, observation_store, monkeypatch):
        import asyncio

        from core.market import index_publication as pub

        async def fake_build(as_of=None):
            return self._fake_digest(as_of)

        mod, agent, audits = self._agent(monkeypatch, fake_build)
        real_status = pub.status
        seen = {"n": 0}

        async def flaky_status(now=None):
            seen["n"] += 1
            if seen["n"] == 2:  # the re-read right after the successful write
                return {
                    "week": pub.current_week_label(now), "current_week_published": False,
                    "missing": list(PUBLISHED),
                    "reason": "index_observations unreadable: simulated lock",
                }
            return await real_status(now=now)

        monkeypatch.setattr(mod, "publication_status", flaky_status)
        asyncio.run(agent.tick(now=self.WED_NOON))  # must not raise
        assert agent.last_failure is None
        assert agent.last_published_week == "2026-W41"
        assert any("unreadable" in note for note in audits), audits
        assert asyncio.run(real_status(now=self.WED_NOON))["current_week_published"] is True

    def test_incomplete_store_is_a_named_failure(self, observation_store, monkeypatch):
        import asyncio

        import pytest

        async def fake_build(as_of=None):
            return self._fake_digest(as_of)

        mod, agent, audits = self._agent(monkeypatch, fake_build)

        async def partial_store(digest, codes=None):
            storage = await ix.save_observation(digest["indices"][ix.AI_STI])
            return {ix.AI_STI: storage["status"], ix.AI_LPI: "error"}

        monkeypatch.setattr(mod, "store_digest", partial_store)
        with pytest.raises(RuntimeError):
            asyncio.run(agent.tick(now=self.WED_NOON))
        assert agent.last_failure["stage"] == "verify"
        assert ix.AI_LPI in agent.last_failure["reason"]
        assert any("FAILED" in note for note in audits), audits

    # ── the store ──────────────────────────────────────────────────────────

    def test_store_digest_with_an_empty_code_list_stores_nothing(self, observation_store):
        import asyncio

        from core.market import bio_price_weekly as bpw
        from core.market import index_publication as pub

        digest = self._fake_digest(self.WED_NOON)
        assert asyncio.run(bpw.store_digest(digest, codes=[])) == {}
        assert asyncio.run(pub.status(now=self.WED_NOON))["current_week_published"] is False
        assert set(asyncio.run(bpw.store_digest(digest))) == set(PUBLISHED)  # None = both

    def test_week_labels_agree_for_a_non_utc_instant(self, observation_store, monkeypatch):
        """build()/the store, readiness() and status() must stamp and judge the SAME
        UTC week for an aware non-UTC instant (one normaliser)."""
        import asyncio
        import datetime as dt

        from core.market import bio_price_weekly as bpw
        from core.market import index_publication as pub

        oslo_monday_0100 = dt.datetime(2026, 10, 5, 1, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        # = Sunday 2026-10-04 23:00 UTC, still 2026-W40
        assert pub.current_week_label(oslo_monday_0100) == "2026-W40"
        result = asyncio.run(ix.compute(ix.AI_LPI, as_of=oslo_monday_0100))
        assert result["week"] == "2026-W40"

        async def live_build(as_of=None):
            return self._fake_digest(as_of)

        _mod, agent, _audits = self._agent(monkeypatch, live_build)
        asyncio.run(agent.tick(now=oslo_monday_0100))  # must not raise a false verify error
        assert agent.last_failure is None
        assert agent.last_published_week == "2026-W40"
        monkeypatch.setattr(bpw, "build", live_build)
        st = asyncio.run(pub.status(now=oslo_monday_0100))
        assert st["week"] == "2026-W40" and st["current_week_published"] is True

    def test_save_observation_refuses_a_null_value(self, observation_store):
        import asyncio

        import pytest

        from sqlalchemy import select
        from sqlalchemy.orm import sessionmaker

        from core.models import IndexObservation

        with pytest.raises(ValueError):
            asyncio.run(ix.save_observation(self._fake_result(ix.AI_STI, self.WED_NOON, value=None)))
        with sessionmaker(bind=observation_store)() as s:
            assert s.execute(select(IndexObservation)).scalars().all() == []

    def test_save_observation_treats_a_real_lost_insert_race_as_duplicate(self, tmp_path, monkeypatch):
        """Two writers inside save_observation: the loser's flush raises the REAL
        unique IntegrityError and gets 'duplicate' with the winner's id."""
        import asyncio
        import datetime as dt

        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import Session as OrmSession, sessionmaker

        from core.models import Base, IndexObservation

        engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}")
        Base.metadata.create_all(engine, tables=[IndexObservation.__table__])
        fake = self._fake_result(ix.AI_STI, self.WED_NOON)

        class RacingSession(OrmSession):
            raced = False

            def commit(self):
                if not RacingSession.raced:
                    RacingSession.raced = True
                    with sessionmaker(bind=engine)() as other:  # the other writer wins …
                        other.add(
                            IndexObservation(
                                index_code=fake["index"], week=fake["week"],
                                as_of=dt.datetime.fromisoformat(fake["as_of"]),
                                version=fake["version"], value=1.0, band="x",
                                components_json="[]", provenance_json="{}",
                            )
                        )
                        other.commit()
                return super().commit()  # … and OUR flush hits the real unique constraint

        monkeypatch.setattr("core.models.Session", sessionmaker(bind=engine, class_=RacingSession))
        try:
            result = asyncio.run(ix.save_observation(fake))
            assert result["status"] == "duplicate" and result["id"] is not None, result
            with sessionmaker(bind=engine)() as s:
                rows = s.execute(select(IndexObservation)).scalars().all()
            assert len(rows) == 1 and rows[0].id == result["id"] and rows[0].value == 1.0
        finally:
            engine.dispose()

    def test_save_observation_reraises_a_non_unique_integrity_error(self, observation_store):
        import asyncio

        import pytest
        from sqlalchemy import select
        from sqlalchemy.exc import IntegrityError
        from sqlalchemy.orm import sessionmaker

        from core.models import IndexObservation

        broken = self._fake_result(ix.AI_STI, self.WED_NOON)
        broken["index"] = None  # NOT NULL violation, not the unique race
        with pytest.raises(IntegrityError):
            asyncio.run(ix.save_observation(broken))
        with sessionmaker(bind=observation_store)() as s:
            assert s.execute(select(IndexObservation)).scalars().all() == []

    # ── the admin path shares the gate ─────────────────────────────────────

    def test_publish_week_obeys_the_gate_and_force_is_explicit(self, observation_store, monkeypatch):
        import asyncio

        import pytest

        from core.market import bio_price_weekly as bpw
        from core.market import index_publication as pub

        async def degraded_build(as_of=None):
            return self._fake_digest(as_of, live=False)

        monkeypatch.setattr(bpw, "build", degraded_build)
        digest = asyncio.run(bpw.publish_week(as_of=self.MON_0100))
        assert set(digest["readiness"]["withheld"]) == set(PUBLISHED)
        assert all(digest["indices"][c]["storage"]["status"] == "withheld" for c in PUBLISHED)
        assert asyncio.run(pub.status(now=self.MON_0100))["current_week_published"] is False
        assert digest["forced"] is False

        forced = asyncio.run(bpw.publish_week(as_of=self.MON_0100, force=True))
        assert forced["forced"] is True
        assert all(forced["indices"][c]["storage"]["status"] == "stored" for c in PUBLISHED)
        assert asyncio.run(pub.status(now=self.MON_0100))["degraded_current"] == list(PUBLISHED)

        # forcing again in the same week writes nothing: duplicate, and NOT "forced"
        again = asyncio.run(bpw.publish_week(as_of=self.MON_0100, force=True))
        assert again["forced"] is False
        assert all(again["indices"][c]["storage"]["status"] == "duplicate" for c in PUBLISHED)

        async def empty_build(as_of=None):
            return self._fake_digest(as_of, value=None, live=False)

        monkeypatch.setattr(bpw, "build", empty_build)
        later = self.THU_0100
        for force in (False, True):  # force never stores a null value — it is withheld
            out = asyncio.run(bpw.publish_week(as_of=later, force=force))
            assert all(out["indices"][c]["storage"]["status"] == "withheld" for c in PUBLISHED)
            assert out["forced"] is False
        with pytest.raises(ValueError):  # and the store itself refuses one
            asyncio.run(ix.save_observation(self._fake_result(ix.AI_STI, later, value=None)))

    def test_admin_publish_endpoint_is_gated(self, observation_store, monkeypatch):
        from contextlib import asynccontextmanager

        from core import async_db
        from core.auth import require_admin
        from core.market import bio_price_weekly as bpw
        from core.market import index_publication as pub

        import datetime as dt

        shape = {"live": False, "value": 42.0}

        async def stub_build(as_of=None):  # the route passes as_of=None
            return self._fake_digest(as_of or dt.datetime.now(dt.UTC), **shape)

        monkeypatch.setattr(bpw, "build", stub_build)
        monkeypatch.setattr(pub, "READINESS_GRACE_HOURS", 10**6)  # always within the grace
        audits: list = []

        class FakeSession:
            def add(self, row):
                audits.append(row)

        @asynccontextmanager
        async def fake_session():
            yield FakeSession()

        monkeypatch.setattr(async_db, "get_async_session", fake_session)  # no real audit rows
        app.dependency_overrides[require_admin] = lambda: None
        try:
            client = TestClient(app, raise_server_exceptions=False)
            refused = client.post("/api/indices/publish")
            assert refused.status_code == 409, refused.text
            assert set(refused.json()["detail"]["withheld"]) == set(PUBLISHED)

            assert client.post("/api/indices/publish?force=true").status_code == 422

            forced = client.post("/api/indices/publish?force=true&reason=ops+decision")
            assert forced.status_code == 200, forced.text
            body = forced.json()
            assert body["forced"] is True and body["audited_intent"] is True
            assert all(body["storage"][c]["status"] == "stored" for c in PUBLISHED)
            # the readiness block reports what force did, not only the prior verdict
            assert set(body["readiness"]["overridden"]) == set(PUBLISHED)
            assert body["readiness"]["withheld"] == {}
            assert audits and audits[0].action == "index_publication_forced"
            assert "ops decision" in audits[0].details and "intent" in audits[0].details

            # the audit row precedes the store: no audit log, no forced publication
            class BrokenSession:
                def add(self, row):
                    raise RuntimeError("audit db locked")

            @asynccontextmanager
            async def broken_session():
                yield BrokenSession()

            monkeypatch.setattr(async_db, "get_async_session", broken_session)
            builds_before = len(audits)
            refused = client.post("/api/indices/publish?force=true&reason=again")
            assert refused.status_code == 503, refused.text
            assert "nothing was stored" in refused.json()["detail"]["hint"]
            assert len(audits) == builds_before
            monkeypatch.setattr(async_db, "get_async_session", fake_session)

            # a null value cannot be forced: nothing storable is a 409, not a fake success
            shape["value"] = None
            nothing = client.post("/api/indices/publish?force=true&reason=ops+decision")
            assert nothing.status_code == 409, nothing.text
            assert "no value" in str(nothing.json()["detail"]["withheld"])
            assert "force=true" not in nothing.json()["detail"]["hint"]  # the caller already forced
        finally:
            app.dependency_overrides.pop(require_admin, None)

    # ── orchestration ──────────────────────────────────────────────────────

    def test_base_agent_recovers_its_status_after_a_failed_tick(self):
        """health() must not report 'error' forever once a later tick succeeded."""
        import asyncio

        from agents.base import AgentStatus, BaseAgent

        class Flaky(BaseAgent):
            name = "flaky_test_agent"
            interval_seconds = 0.01

            def __init__(self):
                super().__init__()
                self.n = 0

            async def tick(self):
                self.n += 1
                if self.n == 1:
                    raise RuntimeError("first tick fails")

        async def run():
            agent = Flaky()
            task = asyncio.create_task(agent.start())
            for _ in range(300):
                await asyncio.sleep(0.01)
                if agent.run_count >= 1:
                    break
            assert agent.error_count == 1 and agent.run_count >= 1
            assert agent.status == AgentStatus.RUNNING
            agent.stop()
            await asyncio.wait_for(task, 5)
            assert agent.status == AgentStatus.STOPPED

        asyncio.run(run())

    def test_list_indices_exposes_publication_status(self, client):
        body = client.get("/api/indices").json()
        pub = body["publication"]
        assert {
            "week", "version", "current_week_published", "missing", "indices",
            "interval_ok", "skipped_weeks", "degraded_current", "within_grace",
        } <= set(pub)
        assert set(pub["indices"]) == set(PUBLISHED)

    def test_orchestrator_runs_the_publisher(self):
        """`python main.py --agents-only` (the production `agents` service) must start it."""
        import re
        from pathlib import Path

        source = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
        assert re.search(r"^from agents\.index_publisher_agent import IndexPublisherAgent$", source, re.M)
        assert re.search(r"^\s*publisher = IndexPublisherAgent\(\)", source, re.M)
        start = source.index("agents = [")
        block = source[start : source.index("]", start)]
        live_lines = [line.strip() for line in block.splitlines() if not line.strip().startswith("#")]
        assert any(re.search(r"\bpublisher\b", line) for line in live_lines), block
        assert "asyncio.run(run_agents())" in source
