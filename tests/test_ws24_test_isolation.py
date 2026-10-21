"""WS-24: a test run cannot write the dev database.

Before this, running the suite wrote `design_partners` ("X", "Scorecard Co"),
`audit_logs` and `price_predictions` rows into `data/openclaw.db` — the database
the app serves — and the collection-time bootstrap ran `alembic upgrade head`
against it (HANDOVER trap 17). The dev box accumulated 820 design_partners rows
that are all test fixtures, which is exactly the pollution a demo would show.

The fix lives in `tests/conftest.py`: before anything imports `config.settings`,
`DATABASE_URL` is pointed at a throwaway COPY of the dev DB in the temp dir
(SQLite backup API, so the WAL is included — trap 18). These tests pin that
wiring from the outside, so a future conftest edit that re-points the suite at
the dev DB fails here rather than quietly polluting it:

  * the suite runs on the copy, not on the dev file;
  * the copy is a copy of the dev DB, so tests keep the row counts they were
    written against (a fresh demo seed on CI is the other, allowed path);
  * writes through the app's own session factory move the copy's counts and
    leave the dev DB's counts untouched — the WS-24 acceptance;
  * an explicit `DATABASE_URL` (CI/PostgreSQL) is still honoured.
"""
from __future__ import annotations

import datetime as dt
import os
import sqlite3
import tempfile
import uuid
from pathlib import Path

import pytest

# The tables the WS-24 acceptance names.
WATCHED_TABLES = (
    "design_partners",
    "audit_logs",
    "price_predictions",
    "index_observations",
)


def _dev_db() -> Path | None:
    raw = os.environ.get("FISHINTEL_DEV_DB", "").strip()
    return Path(raw) if raw else None


def _suite_db() -> Path:
    from config.settings import settings

    assert settings.database_url.startswith("sqlite:///"), settings.database_url
    return Path(settings.database_url.split("sqlite:///", 1)[-1])


def _counts(path: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(path))
    try:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in WATCHED_TABLES
        }
    finally:
        conn.close()


def test_the_suite_runs_on_a_throwaway_database_not_the_dev_one():
    suite = _suite_db()
    assert suite.exists(), "the throwaway database was never created"
    assert suite.parent == Path(tempfile.gettempdir()), (
        f"the suite's database {suite} is not in the temp dir — it is a real file"
    )
    dev = _dev_db()
    if dev is not None:
        assert suite != dev
        # samefile() would raise if either file were missing; both exist here.
        assert not suite.samefile(dev), "the suite is writing the dev database"


def test_the_throwaway_database_is_a_copy_of_the_dev_one():
    """Guard against silently switching to an empty DB, which would weaken every
    test that reads data. On CI there is no dev DB and the fresh seed path runs."""
    from sqlalchemy import text

    from core.models import engine

    dev = _dev_db()
    with engine.connect() as conn:
        suite_lice = conn.execute(text("SELECT COUNT(*) FROM lice_records")).scalar()
    assert suite_lice > 0, "the suite's database is empty — its data tests are vacuous"
    if dev is None:
        pytest.skip("no dev database on this box (CI/fresh clone): fresh seed path")
    copied_from = os.environ.get("FISHINTEL_TEST_DB_COPIED_FROM", "").strip()
    assert Path(copied_from) == dev, (
        "the suite's database was not copied from the dev database — "
        f"FISHINTEL_TEST_DB_COPIED_FROM={copied_from!r}, dev={str(dev)!r}"
    )


def test_writes_land_in_the_copy_and_never_move_the_dev_row_counts():
    """The WS-24 acceptance: write one row into each watched table through the
    app's own session factory; the dev DB's counts stay exactly as they were."""
    dev = _dev_db()
    if dev is None:
        pytest.skip("no dev database on this box (CI/fresh clone): nothing to protect")

    from core.models import (
        AuditLog,
        DesignPartner,
        IndexObservation,
        PricePrediction,
        Session,
    )

    before_dev = _counts(dev)
    before_copy = _counts(_suite_db())

    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    # Unique per run: a leftover probe in the dev DB (or in a re-used copy) must
    # not make this test collide with the (index_code, week, version) constraint.
    probe = f"ws24-probe-{uuid.uuid4().hex[:8]}"
    with Session() as session:
        session.add(DesignPartner(company="WS-24 isolation probe", icp="other"))
        session.add(AuditLog(action="ws24_isolation_probe", resource="test:ws24"))
        session.add(PricePrediction(horizon_weeks=1, direction="flat"))
        session.add(
            IndexObservation(
                index_code="AI-STI",
                week="1999-W01",  # far outside the published weeks
                as_of=now,
                version=probe,
                value=100.0,
            )
        )
        session.commit()

    assert _counts(dev) == before_dev, (
        "a test write reached the dev database — WS-24 regressed: "
        f"{before_dev} -> {_counts(dev)}"
    )
    after_copy = _counts(_suite_db())
    for table in WATCHED_TABLES:
        assert after_copy[table] > before_copy[table], f"{table} did not take the probe row"


def test_an_explicit_database_url_is_honoured(monkeypatch):
    """CI and the migration tests set DATABASE_URL themselves; never override it."""
    from tests.conftest import _prepare_test_database

    monkeypatch.setenv("DATABASE_URL", "sqlite:///explicit-from-environment.db")
    assert _prepare_test_database() is None
    assert os.environ["DATABASE_URL"] == "sqlite:///explicit-from-environment.db"
