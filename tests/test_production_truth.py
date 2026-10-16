"""Production-truth checks (hardening §5) + per-source freshness monitor.

Regression nets for the operational gaps AGENTS.md documents: the agents never ran
in production, the DB was never verified against the migration head, and freshness
was unknowable. Each is now a check with a verdict.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from core import production_truth as pt
from core.api import app
from core.market import freshness_monitor as fm


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


def _status(checks: list[dict], name: str) -> dict:
    return next(c for c in checks if c["check"] == name)


class TestAgentsService:
    def test_production_compose_declares_agents_as_a_service(self):
        checks = pt.check_agents_service()
        assert _status(checks, "compose_service_agents")["status"] == "ok"
        assert _status(checks, "compose_service_db")["status"] == "ok"
        assert not [c for c in checks if c["status"] == "fail"], checks

    def test_agents_service_uses_the_agents_only_entrypoint(self):
        assert _status(pt.check_agents_service(), "agents_entrypoint")["status"] == "ok"

    def test_missing_compose_is_a_critical_failure(self, tmp_path):
        checks = pt.check_agents_service(tmp_path / "nope.yml")
        assert checks[0]["status"] == "fail"
        assert checks[0]["critical"] is True

    def test_api_only_topology_is_flagged(self, tmp_path):
        compose = tmp_path / "docker-compose.prod.yml"
        compose.write_text("services:\n  api:\n    build: .\n", encoding="utf-8")
        checks = pt.check_agents_service(compose)
        assert _status(checks, "compose_service_agents")["status"] == "fail"
        assert _status(checks, "compose_service_agents")["critical"] is True


class TestEnvironmentAndMigrations:
    def test_production_with_a_short_secret_is_a_critical_failure(self, monkeypatch):
        monkeypatch.setenv("FISHINTEL_ENV", "production")
        monkeypatch.setenv("FISHINTEL_JWT_SECRET", "short")
        check = _status(pt.check_environment(), "jwt_secret")
        assert check["status"] == "fail"
        assert check["critical"] is True

    def test_production_with_a_long_secret_passes(self, monkeypatch):
        monkeypatch.setenv("FISHINTEL_ENV", "production")
        monkeypatch.setenv("FISHINTEL_JWT_SECRET", "x" * 40)
        assert _status(pt.check_environment(), "jwt_secret")["status"] == "ok"

    def test_alembic_head_is_resolvable_and_matches_the_db(self):
        """Durable form: do not pin a revision number (018, 019, ... will come)."""
        head = pt._alembic_head()
        assert head is not None and head.isdigit(), head
        check = _status(pt.check_database(), "alembic_head")
        assert check["status"] == "ok", check["detail"]

    def test_database_check_reports_the_head_verdict(self):
        checks = pt.check_database()
        assert _status(checks, "database_reachable")["status"] == "ok"
        assert _status(checks, "alembic_head")["status"] in {"ok", "fail"}


class TestArtifactsAndRollup:
    def test_artifact_absence_is_declared_not_hidden(self, monkeypatch, tmp_path):
        monkeypatch.setattr(pt, "MODEL_DIR", tmp_path / "models")
        monkeypatch.setattr(pt, "ACCURACY_DIR", tmp_path / "accuracy")
        checks = pt.check_artifacts()
        for name in ("model_artifacts", "accuracy_artifacts"):
            check = _status(checks, name)
            assert check["status"] == "warn"
            assert "no " in check["detail"]

    def test_run_checks_returns_a_truth_gap_summary(self):
        import asyncio

        report = asyncio.run(pt.run_checks(include_freshness=False))
        assert report["checks"]
        assert isinstance(report["truth_gaps"], list)
        assert isinstance(report["critical_failures"], list)
        for check in report["checks"]:
            assert check["status"] in {"ok", "info", "warn", "fail"}


class TestFreshnessMonitor:
    def test_report_shape_and_allowed_statuses(self):
        import asyncio

        report = asyncio.run(fm.report())
        assert report["counts"]["total"] == len(fm.SOURCES)
        assert "never be presented as live" in report["note"]
        for source in report["sources"]:
            assert source["status"] in {"fresh", "stale", "dead", "unknown"}
            assert source["refresh_hint"]
            assert source["upstream"]

    def test_missing_table_is_unknown_not_fresh(self):
        import asyncio

        spec = fm.SourceSpec(
            key="does_not_exist",
            label="Absent source",
            table="definitely_not_a_table",
            upstream="nowhere",
            expected_cadence_hours=24,
            refresh_hint="create it",
        )
        source = asyncio.run(fm.report((spec,)))["sources"][0]
        assert source["status"] == "unknown"
        assert "table missing" in source["reason"]

    def test_synthetic_only_rows_are_flagged(self):
        import asyncio

        report = asyncio.run(fm.report())
        ssb = next((s for s in report["sources"] if s["key"] == "ssb_weekly_prices"), None)
        if ssb and ssb["rows"] and ssb["synthetic_rows"]:
            assert ssb["synthetic_only"] is True
            assert "synthetic" in (ssb.get("reason") or "")

    def test_status_thresholds(self):
        assert fm._status(None, 24) == "unknown"
        assert fm._status(1.0, 24) == "fresh"
        assert fm._status(48.0, 24) == "stale"
        assert fm._status(200.0, 24) == "dead"

    def test_timestamp_parsing_handles_sqlite_strings(self):
        # SQLite returns ISO strings; without coercion every source was "unknown".
        assert fm._parse_timestamp("2026-04-05 18:00:33.432829") is not None
        assert fm._parse_timestamp("2026-04-05T18:00:33Z") is not None
        assert fm._parse_timestamp(dt.datetime(2026, 1, 1, tzinfo=dt.UTC)) is not None
        assert fm._parse_timestamp(None) is None
        assert fm._parse_timestamp("not-a-date") is None


class TestFreshnessEndpoint:
    def test_endpoint_reports_counts_and_contract(self, client):
        body = client.get("/api/data-freshness").json()
        assert body["monitored"] == len(fm.SOURCES)
        assert "fresh" in body["contract"]
        assert set(body["counts"]) == {"total", "fresh", "stale", "dead", "unknown"}

    def test_sources_endpoint_lists_the_registry(self, client):
        body = client.get("/api/data-freshness/sources").json()
        keys = {s["key"] for s in body["sources"]}
        assert "lice_records" in keys
        assert all(s["refresh_hint"] for s in body["sources"])


class TestLiceLineage:
    """WS-1: `lice_records.source` makes the lice lineage verifiable, never assumed.

    Deterministic cases use stubs and throwaway file databases; the live-DB
    cases assert invariants only, because CI (demo-seeded) and a bulk-loaded dev
    box (unverified rows) exercise opposite branches by design.
    """

    def test_vocabulary_is_closed(self):
        from core import source_lineage as sl

        assert sl.classify_lice_source("barentswatch") == sl.REAL
        assert sl.classify_lice_source("BarentsWatch") == sl.REAL
        assert sl.classify_lice_source("demo_seed") == sl.SYNTHETIC
        assert sl.classify_lice_source("barentswatch_fallback") == sl.SYNTHETIC
        for value in (None, "", "   ", "unverified", "fiskeridir", "legacy"):
            assert sl.classify_lice_source(value) == sl.UNVERIFIED, value
        # one definition of the synthetic markers, shared with the freshness monitor
        assert sl.SYNTHETIC_MARKERS == fm.DEMO_MARKERS

    def test_lineage_rules(self):
        from core import source_lineage as sl

        now = dt.datetime.now(dt.UTC)
        fresh = now - dt.timedelta(hours=1)
        this_week = tuple(now.isocalendar()[:2])
        pa_ok = [{"pa": 1, "rows_used": 10, "fetch_failed": False}]

        def summarise(counts, **kw):
            kw.setdefault("year", 2026)
            kw.setdefault("latest_fetched_at", fresh)
            kw.setdefault("latest_week", this_week)
            kw.setdefault("pas", pa_ok)
            return sl.summarise_lineage(counts, now=now, **kw)

        live = summarise({"barentswatch": 10})
        assert live["is_live"] is True and live["note"] is None, live
        assert live["by_class"] == {"real": 10, "synthetic": 0, "unverified": 0}
        assert live["latest_week"] == f"{this_week[0]}-W{this_week[1]:02d}"
        assert live["weeks_stale"] == 0

        demo = summarise({"barentswatch": 9, "demo_seed": 1})
        assert demo["is_live"] is False
        assert "synthetic" in demo["note"] and "1/10" in demo["note"], demo["note"]

        legacy = summarise(
            {"unverified": 5, None: 2}, pas=[{"pa": 1, "rows_used": 7, "fetch_failed": False}]
        )
        assert legacy["is_live"] is False
        assert "unverifiable" in legacy["note"] and "7/7" in legacy["note"], legacy["note"]
        assert legacy["by_class"]["unverified"] == 7

        empty = sl.summarise_lineage({}, year=None, pas=[])
        assert empty["is_live"] is False and "no lice rows" in empty["note"], empty

        failed = summarise(
            {"barentswatch": 10}, pas=pa_ok + [{"pa": 7, "rows_used": 0, "fetch_failed": True}]
        )
        assert failed["is_live"] is False
        assert "PA 7" in failed["note"] and "failed" in failed["note"], failed["note"]

        stale_fetch = summarise({"barentswatch": 10}, latest_fetched_at=now - dt.timedelta(days=30))
        assert stale_fetch["is_live"] is False and "fetched" in stale_fetch["note"], stale_fetch["note"]

        # fetched_at is a WRITE time: a re-ingested old week must not look current
        old_week = summarise({"barentswatch": 10}, latest_week=(2026, 15))
        assert old_week["is_live"] is False
        assert "2026-W15" in old_week["note"] and "weeks old" in old_week["note"], old_week["note"]
        assert old_week["weeks_stale"] > 1

        no_week = summarise({"barentswatch": 10}, latest_week=None)
        assert no_week["is_live"] is False and "observation week unknown" in no_week["note"]

        # merge: a stale production area degrades the national view even when the
        # newest area is fresh
        fresh_pa = {
            "pa": 1, "rows_used": 10, "fetch_failed": False,
            "latest_fetched_at": fresh.isoformat(), "latest_week": list(this_week),
        }
        stale_pa = {
            "pa": 13, "rows_used": 40, "fetch_failed": False,
            "latest_fetched_at": (now - dt.timedelta(days=30)).isoformat(),
            "latest_week": [2026, 15],
        }
        a = summarise({"barentswatch": 10}, pas=[fresh_pa])
        b = summarise(
            {"barentswatch": 40}, latest_fetched_at=now - dt.timedelta(days=30),
            latest_week=(2026, 15), pas=[stale_pa],
        )
        assert a["is_live"] is True and b["is_live"] is False
        merged = sl.merge_lineages([a, b], now=now)
        assert merged["rows_used"] == 50
        assert merged["is_live"] is False
        assert "PA 13" in merged["note"], merged["note"]
        assert merged["latest_week"] == a["latest_week"]

        both_fresh = sl.merge_lineages([a, a], now=now)
        assert both_fresh["is_live"] is True and both_fresh["rows_used"] == 20

        dropped = sl.merge_lineages([a, None], now=now)
        assert dropped["is_live"] is False and "failed" in dropped["note"], dropped["note"]

        mixed = sl.merge_lineages([live, demo], now=now)
        assert mixed["rows_used"] == 20
        assert mixed["by_class"]["synthetic"] == 1
        assert mixed["is_live"] is False
        assert len(mixed["pas"]) == 2

    # -- freshness monitor: deterministic counts on a throwaway FILE database --
    # (the monitor runs in a worker thread; an in-memory SQLite would be empty there)

    @staticmethod
    def _lice_table(tmp_path, rows, source_ddl="source VARCHAR(32)"):
        """A throwaway lice_records table. The default DDL is the shape a type-only
        reconciliation produced (nullable, so NULL sources are real rows, not an ORM
        default); pass the 019 shape to model a migrated table."""
        import sqlite3
        import uuid

        from sqlalchemy import create_engine

        db_file = tmp_path / f"freshness_{uuid.uuid4().hex[:8]}.db"
        conn = sqlite3.connect(db_file)
        try:
            conn.execute(
                "CREATE TABLE lice_records "
                f"(id INTEGER PRIMARY KEY, {source_ddl}, fetched_at DATETIME)"
            )
            conn.executemany(
                "INSERT INTO lice_records (source, fetched_at) VALUES (?, '2026-10-01 00:00:00')",
                [(value,) for value in rows],
            )
            conn.commit()
        finally:
            conn.close()
        return create_engine(f"sqlite:///{db_file}")

    @staticmethod
    def _lice_entry(monkeypatch, engine):
        import asyncio

        monkeypatch.setattr("core.models.engine", engine)
        spec = next(s for s in fm.SOURCES if s.key == "lice_records")
        try:
            report = asyncio.run(fm.report((spec,)))
        finally:
            engine.dispose()
        return report, report["sources"][0]

    def test_freshness_counts_demo_real_and_unverified_rows_deterministically(
        self, tmp_path, monkeypatch
    ):
        engine = self._lice_table(
            tmp_path,
            ["demo_seed"] * 3
            + ["barentswatch"] * 2
            + ["barentswatch_fallback"]  # the marker the old SQL omitted
            + [" barentswatch "]  # padded: TRIM keeps SQL and classifier in step
            + [None, "unverified"],
        )
        report, entry = self._lice_entry(monkeypatch, engine)
        assert entry["rows"] == 9
        assert entry["synthetic_rows"] == 4
        assert entry["verified_rows"] == 3
        assert entry["unverified_rows"] == 2
        assert entry["synthetic_only"] is False
        assert entry["no_verified_rows"] is False
        assert report["no_verified_rows"] == []

    def test_freshness_flags_tables_with_no_verified_rows(self, tmp_path, monkeypatch):
        engine = self._lice_table(tmp_path, ["unverified"] * 4 + [None])
        report, entry = self._lice_entry(monkeypatch, engine)
        assert entry["verified_rows"] == 0 and entry["unverified_rows"] == 5
        assert entry["no_verified_rows"] is True
        assert entry["synthetic_only"] is False
        assert "verified" in entry["reason"]
        assert report["no_verified_rows"] == ["lice_records"]

        engine = self._lice_table(tmp_path, ["demo_seed"] * 2)
        report, entry = self._lice_entry(monkeypatch, engine)
        assert entry["synthetic_only"] is True and entry["no_verified_rows"] is True
        assert "synthetic" in entry["reason"]
        assert report["synthetic_only"] == ["lice_records"]

    def test_live_db_reports_lice_source_counts(self):
        import asyncio

        report = asyncio.run(fm.report())
        lice = next(s for s in report["sources"] if s["key"] == "lice_records")
        if lice["status"] == "unknown" and not lice.get("rows"):
            pytest.skip("lice_records absent in this environment")
        for key in ("synthetic_rows", "verified_rows", "unverified_rows"):
            assert isinstance(lice[key], int), (key, lice)
        assert lice["synthetic_rows"] + lice["verified_rows"] + lice["unverified_rows"] == lice["rows"]
        assert lice["synthetic_only"] == (lice["rows"] > 0 and lice["synthetic_rows"] == lice["rows"])
        assert lice["no_verified_rows"] == (lice["rows"] > 0 and lice["verified_rows"] == 0)

    def test_endpoint_exposes_lice_source_counts(self, client):
        body = client.get("/api/data-freshness").json()
        lice = next(s for s in body["sources"] if s["key"] == "lice_records")
        assert "unverified_rows" in lice and "verified_rows" in lice
        assert "unverified_rows" in body["contract"]
        assert isinstance(body["no_verified_rows"], list)

    def test_verifier_exposes_the_lice_lineage_gaps(self):
        import asyncio

        report = asyncio.run(fm.report())
        verdict = _status(asyncio.run(pt.check_freshness()), "freshness_no_verified_rows")
        assert verdict["status"] == ("warn" if report["no_verified_rows"] else "ok"), verdict
        column = _status(pt.check_database(), "lice_source_column")
        assert column["status"] == "ok", column

    def test_verifier_fails_closed_on_a_missing_or_reconciled_source_column(self, tmp_path):
        """Weakening `_lice_source_column_verdict` to an unconditional ok must be
        caught: no column is a critical fail, a nullable/no-default column (the
        reconciliation shape 019 never repaired) is a warn naming the recovery."""
        import sqlite3

        from sqlalchemy import create_engine

        db = tmp_path / "verdict.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE lice_records (id INTEGER PRIMARY KEY, fetched_at DATETIME)")
        conn.commit()
        conn.close()
        engine = create_engine(f"sqlite:///{db}")
        try:
            verdict = pt._lice_source_column_verdict(engine)
            assert verdict["status"] == "fail" and verdict["critical"] is True, verdict
            assert "stamp 018" in verdict["detail"]

            conn = sqlite3.connect(db)
            conn.execute("ALTER TABLE lice_records ADD COLUMN source VARCHAR(32)")
            conn.commit()
            conn.close()
            verdict = pt._lice_source_column_verdict(engine)
            assert verdict["status"] == "warn", verdict
            assert "stamp 018" in verdict["detail"]
        finally:
            engine.dispose()

        migrated = self._lice_table(
            tmp_path, ["barentswatch"], source_ddl="source VARCHAR(32) DEFAULT 'unverified' NOT NULL"
        )
        try:
            assert pt._lice_source_column_verdict(migrated)["status"] == "ok"
        finally:
            migrated.dispose()

    def test_conftest_reconciliation_carries_the_server_default(self, tmp_path, monkeypatch):
        """A reconciled lice_records.source must match the ORM contract (NOT NULL
        DEFAULT 'unverified'), not a type-only nullable column full of NULLs that the
        conftest then stamps past 019 (review finding)."""
        import sqlite3

        from sqlalchemy import create_engine

        import tests.conftest as ct
        from core.models import Base, LiceRecord, Locality

        db = tmp_path / "reconcile.db"
        engine = create_engine(f"sqlite:///{db}")
        try:
            Base.metadata.create_all(engine, tables=[Locality.__table__, LiceRecord.__table__])
            conn = sqlite3.connect(db)
            conn.execute("ALTER TABLE lice_records DROP COLUMN source")
            conn.execute("INSERT INTO localities (locality_no, name) VALUES (1, 'x')")
            conn.execute("INSERT INTO lice_records (locality_no, year, week) VALUES (1, 2026, 1)")
            conn.commit()
            conn.close()

            monkeypatch.setattr("core.models.engine", engine)
            ct._reconcile_sqlite_schema()

            conn = sqlite3.connect(db)
            column = next(r for r in conn.execute("PRAGMA table_info(lice_records)") if r[1] == "source")
            rows = conn.execute("SELECT source FROM lice_records").fetchall()
            conn.close()
            assert column[3] == 1 and column[4] == "'unverified'", column
            assert rows == [("unverified",)]
            assert pt._lice_source_column_verdict(engine)["status"] == "ok"
        finally:
            engine.dispose()

    # -- AI-LPI: is_live follows the lineage of the rows the tracker used --

    def test_ai_lpi_is_live_follows_the_lice_lineage(self, tmp_path, monkeypatch):
        import asyncio

        from core import source_lineage as sl
        from core.market import indices as ix

        now = dt.datetime.now(dt.UTC)
        this_week = tuple(now.isocalendar()[:2])
        pas = [{"pa": pa, "rows_used": 10, "fetch_failed": False} for pa in range(1, 14)]
        # the column-presence check must not depend on whichever DB the suite runs on
        engine = self._lice_table(
            tmp_path, ["barentswatch"], source_ddl="source VARCHAR(32) DEFAULT 'unverified' NOT NULL"
        )
        monkeypatch.setattr("core.models.engine", engine)

        def compute(counts, *, latest=now, pas=pas, week=this_week):
            lineage = sl.summarise_lineage(
                counts, year=2026, latest_fetched_at=latest, latest_week=week, pas=pas, now=now
            )

            async def stub():
                return {"national_utilization_pct": 60.0, "pas_over_quota": 2, "lineage": lineage}

            monkeypatch.setattr(ix, "_national_emission", stub)
            return asyncio.run(ix.compute(ix.AI_LPI))

        live = compute({"barentswatch": 130})
        assert live["provenance"]["is_live"] is True, live["provenance"]
        assert live["lineage_notes"] == []
        assert live["components_used"] == 2

        demo = compute({"demo_seed": 130})
        assert demo["provenance"]["is_live"] is False
        assert "synthetic" in demo["provenance"]["fallback_reason"]

        legacy = compute({"unverified": 130})
        assert legacy["provenance"]["is_live"] is False
        assert "unverifiable" in legacy["provenance"]["fallback_reason"]

        mixed = compute({"barentswatch": 129, "demo_seed": 1})
        assert mixed["provenance"]["is_live"] is False

        failed = compute(
            {"barentswatch": 120},
            pas=pas[:-1] + [{"pa": 13, "rows_used": 0, "fetch_failed": True}],
        )
        assert failed["provenance"]["is_live"] is False
        assert "PA 13" in failed["provenance"]["fallback_reason"]

        stale = compute({"barentswatch": 130}, latest=now - dt.timedelta(days=30))
        assert stale["provenance"]["is_live"] is False
        assert "fetched" in stale["provenance"]["fallback_reason"]

        old_week = compute({"barentswatch": 130}, week=(2026, 15))
        assert old_week["provenance"]["is_live"] is False
        assert "2026-W15" in old_week["provenance"]["fallback_reason"]
        engine.dispose()

    # -- the ingest writes the real marker on BOTH branches of its upsert --

    def test_upsert_writes_barentswatch_on_insert_and_update(self, tmp_path, monkeypatch):
        import asyncio
        from contextlib import asynccontextmanager

        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        from agents import data_ingest
        from core.models import Base, LiceRecord, Locality

        async def run():
            engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ingest.db'}")
            async with engine.begin() as conn:
                await conn.run_sync(
                    lambda c: Base.metadata.create_all(
                        c, tables=[Locality.__table__, LiceRecord.__table__]
                    )
                )
            factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

            @asynccontextmanager
            async def session():
                async with factory() as s:
                    try:
                        yield s
                        await s.commit()
                    except Exception:
                        await s.rollback()
                        raise

            # bind the ingest to the throwaway DB — never write a fake verified row
            # into the real database
            monkeypatch.setattr(data_ingest, "get_async_session", session)
            async with session() as s:
                s.add(Locality(locality_no=999001, name="WS-1 test locality"))

            payload = [{
                "locality": {"no": 999001},
                "liceReport": {
                    "hasReported": True,
                    "adultFemaleLice": {"average": 0.2},
                    "mobileLice": {"average": 0.5},
                    "stationaryLice": {"average": 0.1},
                    "seaTemperature": 8.0,
                },
            }]
            inserted = await data_ingest.DataIngestAgent._upsert_lice_v2(payload, 1999, 1)
            assert inserted == 1
            async with session() as s:
                row = (await s.execute(select(LiceRecord))).scalar_one()
                assert row.source == "barentswatch", row.source
                row.source = "demo_seed"  # simulate a demo row at the same key

            payload[0]["liceReport"]["adultFemaleLice"]["average"] = 0.3
            inserted = await data_ingest.DataIngestAgent._upsert_lice_v2(payload, 1999, 1)
            assert inserted == 0  # update branch
            async with session() as s:
                row = (await s.execute(select(LiceRecord))).scalar_one()
                assert row.source == "barentswatch", "update branch must flip the source"
                assert row.avg_adult_female_lice == 0.3
            await engine.dispose()

        asyncio.run(run())

    # -- the backfill re-ingests weeks whose rows are not verified --

    def test_backfill_counts_only_verified_rows(self, tmp_path, monkeypatch):
        """WS-1: the backfill's "already have this week" check must ignore demo and
        unverified rows, or bulk-loaded weeks would never be re-ingested and could
        never earn a verified lineage."""
        import asyncio
        from contextlib import asynccontextmanager

        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        from agents import historical_backfill
        from core.models import Base, LiceRecord, Locality

        async def run():
            engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'backfill.db'}")
            async with engine.begin() as conn:
                await conn.run_sync(
                    lambda c: Base.metadata.create_all(
                        c, tables=[Locality.__table__, LiceRecord.__table__]
                    )
                )
            factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

            @asynccontextmanager
            async def session():
                async with factory() as s:
                    yield s
                    await s.commit()

            monkeypatch.setattr(historical_backfill, "get_async_session", session)
            sources = ["unverified"] * 3 + ["demo_seed"] * 2 + ["barentswatch"] * 4
            async with session() as s:
                for i, source in enumerate(sources):
                    s.add(Locality(locality_no=999100 + i, name=f"WS-1 locality {i}"))
                    s.add(LiceRecord(locality_no=999100 + i, year=1998, week=1, source=source))

            count = await historical_backfill.HistoricalBackfillAgent._week_count(1998, 1)
            assert count == 4, f"expected only the 4 verified rows, got {count}"
            await engine.dispose()

        asyncio.run(run())


class TestIndexPublicationCheck:
    """WS-2: the verifier asserts the weekly index publication actually ran."""

    def test_verifier_reports_whether_the_current_week_is_published(self, monkeypatch):
        import asyncio

        from core.market import index_publication as pub

        verdicts = asyncio.run(pt.check_index_publication())
        verdict = _status(verdicts, "index_publication_current_week")
        state = asyncio.run(pub.status())
        if state["current_week_published"]:
            expected = "ok"
        elif (
            state["within_grace"]
            and not state["reason"]
            and all(state["indices"][c]["weeks_behind"] == 1 for c in state["missing"])
        ):
            expected = "info"  # a designed wait inside the grace, last week stored
        else:
            expected = "warn"
        assert verdict["status"] == expected, (verdict, state)
        assert state["week"] in verdict["detail"]

        def stub(**overrides):
            base = {
                "week": "2026-W42", "version": "1.0.0", "current_week_published": False,
                "missing": ["AI-STI"], "indices": {}, "interval_ok": True,
                "skipped_weeks": [], "degraded_current": [], "reason": None,
                "within_grace": False, "hours_into_week": 100.0, "readiness_grace_hours": 72,
            }
            base.update(overrides)

            async def _status(now=None):
                return base

            return _status

        # negative path, with the store's own reason surfaced
        monkeypatch.setattr(pub, "status", stub(reason="index_observations unreadable: simulated"))
        verdict = _status(asyncio.run(pt.check_index_publication()), "index_publication_current_week")
        assert verdict["status"] == "warn", verdict
        assert "2026-W42" in verdict["detail"] and "AI-STI" in verdict["detail"]
        assert "simulated" in verdict["detail"]

        # deterministic positive path, naming a degraded current week honestly
        monkeypatch.setattr(
            pub, "status", stub(current_week_published=True, missing=[], degraded_current=["AI-LPI"])
        )
        verdicts = asyncio.run(pt.check_index_publication())
        verdict = _status(verdicts, "index_publication_current_week")
        assert verdict["status"] == "ok", verdict
        assert "2026-W42" in verdict["detail"] and "AI-STI" in verdict["detail"]
        assert "1.0.0" in verdict["detail"] and "degraded" in verdict["detail"]
        assert _status(verdicts, "index_publication_interval")["status"] == "ok"

        # a skipped week is its own named warning
        monkeypatch.setattr(
            pub, "status",
            stub(current_week_published=True, missing=[], interval_ok=False,
                 skipped_weeks=["AI-STI 2026-W41→2026-W43"]),
        )
        interval = _status(asyncio.run(pt.check_index_publication()), "index_publication_interval")
        assert interval["status"] == "warn" and "2026-W43" in interval["detail"], interval

        # within the readiness grace with last week stored: a designed wait, not a fault
        monkeypatch.setattr(
            pub, "status",
            stub(within_grace=True, hours_into_week=5.0,
                 indices={"AI-STI": {"weeks_behind": 1}, "AI-LPI": {"weeks_behind": 1}}),
        )
        waiting = _status(asyncio.run(pt.check_index_publication()), "index_publication_current_week")
        assert waiting["status"] == "info" and "grace" in waiting["detail"], waiting

        # one index stored this week, the other withheld inside the grace: a designed
        # partial state — info naming the stored one, never "the agent has not run"
        monkeypatch.setattr(
            pub, "status",
            stub(within_grace=True, hours_into_week=5.0, missing=["AI-LPI"],
                 indices={"AI-STI": {"weeks_behind": 0, "current_week_published": True},
                          "AI-LPI": {"weeks_behind": 1, "current_week_published": False}}),
        )
        partial = _status(asyncio.run(pt.check_index_publication()), "index_publication_current_week")
        assert partial["status"] == "info", partial
        assert "AI-STI" in partial["detail"] and "has not run" not in partial["detail"]

        # past the grace with one index stored: the agent ran — say what is withheld
        monkeypatch.setattr(
            pub, "status",
            stub(within_grace=False, hours_into_week=100.0, missing=["AI-LPI"],
                 indices={"AI-STI": {"weeks_behind": 0, "current_week_published": True},
                          "AI-LPI": {"weeks_behind": 1, "current_week_published": False}}),
        )
        withheld = _status(asyncio.run(pt.check_index_publication()), "index_publication_current_week")
        assert withheld["status"] == "warn" and "has not run" not in withheld["detail"], withheld
        assert "AI-LPI" in withheld["detail"]

        # no history at this method version, inside the grace: the store cannot tell
        # a waiting publisher from a stopped one — and must not claim either
        monkeypatch.setattr(
            pub, "status",
            stub(within_grace=True, hours_into_week=5.0, version="1.1.0",
                 missing=["AI-STI", "AI-LPI"],
                 indices={"AI-STI": {"weeks_behind": None, "latest_week": None},
                          "AI-LPI": {"weeks_behind": None, "latest_week": None}}),
        )
        fresh = _status(asyncio.run(pt.check_index_publication()), "index_publication_current_week")
        assert fresh["status"] == "warn" and "cannot tell" in fresh["detail"], fresh
        assert "has not run" not in fresh["detail"] and "1.1.0" in fresh["detail"]

        # a future-dated row is a named anomaly, not a silent ok
        monkeypatch.setattr(
            pub, "status",
            stub(current_week_published=True, missing=[],
                 indices={"AI-STI": {"weeks_behind": -1, "store_ahead_of_clock": True},
                          "AI-LPI": {"weeks_behind": 0, "store_ahead_of_clock": False}}),
        )
        ahead = _status(asyncio.run(pt.check_index_publication()), "index_publication_store_ahead_of_clock")
        assert ahead["status"] == "warn" and "AI-STI" in ahead["detail"], ahead

        # fewer than two observations: the interval is not measurable, never "ok"
        monkeypatch.setattr(pub, "status", stub(current_week_published=True, missing=[], interval_ok=None))
        unmeasured = _status(asyncio.run(pt.check_index_publication()), "index_publication_interval")
        assert unmeasured["status"] == "info" and "not measurable" in unmeasured["detail"], unmeasured

    def test_run_checks_includes_the_publication_check(self):
        import asyncio

        report = asyncio.run(pt.run_checks(include_freshness=False))
        assert any(c["check"] == "index_publication_current_week" for c in report["checks"])
