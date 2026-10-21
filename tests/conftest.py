"""
Shared pytest fixtures for FishIntel test suite.
=================================================
Provides common fixtures used across multiple test files:
  - event_loop: session-scoped async event loop
  - test_client: FastAPI TestClient for API route tests
  - sample_lice_data: realistic lice record data for unit tests

It also decides WHICH database the suite runs against: a throwaway copy of the
dev database in the temp dir (WS-24), so a test run cannot write the database
the app serves. See `_prepare_test_database` below.
"""
import asyncio
import os
import sqlite3
import tempfile
from pathlib import Path

# Disable the production rate limit for the test suite BEFORE core.api is
# first imported anywhere in the process. The suite makes hundreds of
# requests from a single TestClient IP; rate-limit enforcement is verified
# explicitly (with its own strict limiter) in tests/test_rate_limit.py.
os.environ.setdefault("FISHINTEL_RATE_LIMIT", "100000/minute")
# Same pattern for the tier daily quota: disabled suite-wide; enforcement
# is verified explicitly (monkeypatched quotas) in tests/test_tier_quota.py.
os.environ.setdefault("FISHINTEL_ENFORCE_QUOTAS", "0")


# ── WS-24: the suite never writes the dev database ──────────────────────────
# Before this, a full run wrote design_partners ("X", "Scorecard Co"), audit
# rows and price predictions into the database the app serves — the dev box held
# 850 design_partners rows by 2026-10-21, every one a test fixture — and the
# bootstrap's `alembic upgrade head` migrated the dev DB at collection (trap 17).
# The suite now points DATABASE_URL at a throwaway COPY of that database in the
# system temp dir (one stable path, replaced each run), deleted when the session
# ends. Tests keep the realistic row counts they were written against, and the
# dev DB's counts cannot move.
#   * The copy uses the SQLite backup API: a plain file copy misses the WAL
#     (trap 18).
#   * An explicit DATABASE_URL always wins (CI/PostgreSQL, and
#     tests/test_migrations.py overrides it per subprocess).
#   * With no dev DB (fresh clone, CI) no copy is made and the bootstrap below
#     builds and demo-seeds a fresh database — the behaviour CI already had.
def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _configured_database_url() -> str:
    """DATABASE_URL as the app would resolve it, WITHOUT importing config.settings.

    Order matches pydantic: an exported env var wins, then `.env`, then the
    canonical dev SQLite file (with the pre-rename `data/openclaw.db` fallback
    that `config/settings.py` documents). Importing `config.settings` here would
    instantiate the cached `settings` object before the override is in place,
    and `core.models` would then bind the engine to the dev DB — the exact bug
    this fixture exists to prevent.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    env_file = _repo_root() / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip("'\"")
    canonical = _repo_root() / "data" / "aquaintel.db"
    legacy = _repo_root() / "data" / "openclaw.db"
    chosen = canonical if (canonical.exists() or not legacy.exists()) else legacy
    return f"sqlite:///{chosen}"


def _prepare_test_database() -> str | None:
    """Point DATABASE_URL at a throwaway copy of the dev DB; return its path."""
    explicit = os.environ.get("DATABASE_URL", "").strip()
    if explicit:
        print(f"conftest: DATABASE_URL is set — tests use it as given ({explicit})")
        return None

    dev_url = _configured_database_url()
    if not dev_url.startswith("sqlite"):
        # A PostgreSQL DATABASE_URL in .env: never shadow it with a local copy.
        print(f"conftest: configured database is not SQLite — tests use {dev_url}")
        return None

    dev = Path(dev_url.split("sqlite:///", 1)[-1])
    if not dev.is_absolute():
        dev = (_repo_root() / dev).resolve()  # .env uses "./data/openclaw.db"
    dev = dev if dev.exists() else None

    _sweep_stale_copies()
    # One stable path in the temp dir, replaced at the start of every run: a
    # crashed run can leave at most ONE copy behind (nothing accumulates), an
    # aiosqlite handle left open by the previous run cannot block this one, and
    # the dev DB is never the target.
    target = Path(tempfile.gettempdir()) / "_test_suite.db"
    try:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{target}{suffix}").unlink(missing_ok=True)
    except OSError:
        # Something still holds it (a suite running concurrently — already a
        # documented no-no); use a pid-unique name rather than corrupt it.
        target = Path(tempfile.gettempdir()) / f"aquaintel_test_{os.getpid()}.db"
        for suffix in ("", "-wal", "-shm"):
            Path(f"{target}{suffix}").unlink(missing_ok=True)
    if dev is not None:
        src = sqlite3.connect(str(dev))
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)  # WAL-aware; a file copy would be stale (trap 18)
        finally:
            dst.close()
            src.close()
        size_mb = target.stat().st_size / 1_048_576
        print(f"conftest: tests run on a throwaway copy of {dev.name} "
              f"({size_mb:.0f} MB) at {target}")
    else:
        print("conftest: no dev database — tests build and demo-seed a fresh one")
    os.environ["DATABASE_URL"] = f"sqlite:///{target}"
    # Importing settings is safe now (the override is in place) and proves the
    # engine `core.models` builds will bind to the copy, not to the dev file.
    from config.settings import settings as _settings

    if str(_settings.database_url) != os.environ["DATABASE_URL"]:
        print(
            "conftest: WARNING settings.database_url="
            f"{_settings.database_url} ignored the WS-24 override "
            f"{os.environ['DATABASE_URL']} — something imported config.settings "
            "before conftest ran; the dev DB is NOT protected"
        )
    # Record where the real dev DB is, for the few tests that check its contents,
    # and where the copy came from, so tests/test_ws24_test_isolation.py can pin
    # that the fixture above really produced a copy rather than a fresh seed.
    os.environ["FISHINTEL_DEV_DB"] = str(dev) if dev is not None else ""
    os.environ["FISHINTEL_TEST_DB_COPIED_FROM"] = str(dev) if dev is not None else ""
    return str(target)


def _sweep_stale_copies() -> None:
    """Remove copies left by the earlier pid-named layout (superseded, never re-added).

    Cheap and harmless: only files matching the old `aquaintel_test_<pid>.db`
    pattern, which this version no longer creates.
    """
    for stale in Path(tempfile.gettempdir()).glob("aquaintel_test_*.db*"):
        try:
            stale.unlink(missing_ok=True)
        except OSError:
            pass


def _remove_throwaway_database() -> None:
    """Delete the throwaway DB and its WAL sidecars (idempotent, never raises).

    Windows can hold a handle (aiosqlite's worker thread), so a failed unlink is
    harmless: the next run replaces this same stable path instead of adding a
    second copy, so at most one throwaway database exists on disk.
    """
    if not _TEST_DB_PATH:
        return
    try:
        from core.models import engine

        engine.dispose()
    except Exception:
        pass
    for suffix in ("", "-wal", "-shm"):
        try:
            Path(f"{_TEST_DB_PATH}{suffix}").unlink(missing_ok=True)
        except OSError:
            pass


_TEST_DB_PATH = _prepare_test_database()

import pytest
from fastapi.testclient import TestClient


# ── Test-database bootstrap (CI runners & fresh clones) ─────────────────────
# TestClient(app) does NOT run the FastAPI lifespan, so on a machine without
# a populated data/aquaintel.db (CI!) the schema was never created and every
# DB-touching test failed with "no such table" / "unable to open database
# file". Build the schema explicitly and seed the deterministic demo dataset
# when the lice table is empty. This runs against the throwaway copy (WS-24), or
# against a fresh file when the box has no dev DB; the dev DB itself is never
# migrated, reconciled or seeded by a test run any more.
def _reconcile_sqlite_schema() -> None:
    """Add ORM columns that an existing SQLite DB is missing (idempotent).

    AGENTS.md documents the gap: "Local dev SQLite may lag the ORM (create_all vs
    Alembic) -> reconcile with PRAGMA table_info + ALTER TABLE". This automates
    exactly that, so a stale dev DB cannot make the suite fail with
    "no such column" — which is what the money-path tests hit on
    `subscriptions.stripe_customer_id` (the column IS in migration 002, but this
    box's DB predates the reconciliation).

    Column additions are safe on SQLite. Non-nullable columns without a default
    are skipped with a warning (they need a real migration, not a patch).
    """
    try:
        from sqlalchemy import inspect, text

        from core.models import Base, engine

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        added: list[str] = []
        with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                if table.name not in tables:
                    continue
                have = {c["name"] for c in inspector.get_columns(table.name)}
                for column in table.columns:
                    if column.name in have:
                        continue
                    if (
                        not column.nullable
                        and column.default is None
                        and column.server_default is None
                    ):
                        print(
                            f"conftest: {table.name}.{column.name} missing and NOT "
                            "NULL without default — add a migration"
                        )
                        continue
                    ddl = column.type.compile(engine.dialect)
                    # Carry a constant server default (and NOT NULL) so the reconciled
                    # column matches the ORM contract instead of leaving NULLs. WS-1's
                    # lice_records.source relies on it: NULL classifies as unverified
                    # (honest), but the DDL would diverge from migration 019.
                    server_default = getattr(column.server_default, "arg", None)
                    if isinstance(server_default, str):
                        ddl += " DEFAULT '" + server_default.replace("'", "''") + "'"
                        if not column.nullable:
                            ddl += " NOT NULL"
                    conn.execute(
                        text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl}')
                    )
                    added.append(f"{table.name}.{column.name}")
        if added:
            print(f"conftest: reconciled {len(added)} missing column(s): {added[:8]}")
    except Exception as exc:  # never block collection on reconciliation issues
        print(f"conftest: schema reconciliation skipped: {exc}")


def _stamp_alembic_if_unstamped() -> None:
    """Stamp the DB at head when it was built by ``create_all`` (dev/test).

    Found by ``scripts/verify_production_truth.py``: this box's ``alembic_version``
    table existed but was EMPTY, so the production-truth check reported
    "DB at None, code head 017" — a genuine drift signal. ``create_all`` had built
    the schema (plus the column reconciliation above), so stamping head is the
    honest reconciliation for a dev/test database. A real production DB is left
    alone: if it is unstamped or behind, the verifier must keep failing.
    """
    from sqlalchemy import text

    from core.models import engine

    try:
        with engine.connect() as conn:
            stamped = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if stamped:
            return
    except Exception:
        return  # no alembic_version table: create_all-only DB, nothing to stamp
    try:
        from alembic import command as _alembic_cmd
        from alembic.config import Config as _AlembicConfig

        _cfg = _AlembicConfig("alembic.ini")
        _cfg.set_main_option("script_location", "alembic")
        _alembic_cmd.stamp(_cfg, "head")
        print("conftest: stamped alembic_version at head (create_all-built test DB)")
    except Exception as exc:  # never block collection
        print(f"conftest: alembic stamp skipped: {exc}")


def _bootstrap_test_database() -> None:
    try:
        from core.models import engine, init_db

        init_db()
        try:
            from alembic import command as _alembic_cmd
            from alembic.config import Config as _AlembicConfig

            _cfg = _AlembicConfig("alembic.ini")
            _cfg.set_main_option("script_location", "alembic")
            _alembic_cmd.upgrade(_cfg, "head")
        except Exception:
            pass  # ORM create_all already provided the schema

        _reconcile_sqlite_schema()
        _stamp_alembic_if_unstamped()

        from sqlalchemy import text

        with engine.connect() as conn:
            empty = conn.execute(text("SELECT COUNT(*) FROM lice_records")).scalar() == 0
        if empty:
            from core.demo_seed import seed_demo_data

            stats = seed_demo_data()
            print(f"conftest: seeded demo dataset for tests: {stats}")
    except Exception as exc:  # never block collection on bootstrap issues
        print(f"conftest: test-db bootstrap skipped: {exc}")


_bootstrap_test_database()


@pytest.fixture(scope="session", autouse=True)
def _discard_throwaway_database():
    """Delete the throwaway DB when the session ends (WS-24).

    The dev DB was never opened for writing, so there is nothing to restore.
    On Windows an aiosqlite handle can still hold the file, so the unlink is
    best-effort — the next run replaces this same path instead of adding another
    copy, which keeps at most one throwaway database on disk.
    """
    yield
    _remove_throwaway_database()


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def test_client():
    """FastAPI TestClient wired to the real app — no external APIs needed."""
    from core.api import app
    return TestClient(app)


@pytest.fixture()
def sample_lice_data():
    """
    Returns a realistic lice record dict matching BarentsWatch schema.
    Suitable for unit tests that need plausible farm-level data.
    """
    return {
        "locality_no": 10362,
        "locality_name": "KORSNES",
        "owner_company": "MOWI ASA",
        "municipality": "NÆRØYSUND",
        "county": "TRØNDELAG",
        "production_area": 7,
        "year": 2026,
        "week": 14,
        "avg_adult_female_lice": 0.18,
        "avg_mobile_lice": 0.42,
        "avg_stationary_lice": 0.07,
        "sea_temp_c": 7.2,
        "has_cleaner_fish": True,
        "is_fallow": False,
        "lat": 64.85,
        "lon": 11.25,
    }
