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

    def test_alembic_head_matches_the_newest_migration(self):
        assert pt._alembic_head() == "017"

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
