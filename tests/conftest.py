"""
Shared pytest fixtures for FishIntel test suite.
=================================================
Provides common fixtures used across multiple test files:
  - event_loop: session-scoped async event loop
  - test_client: FastAPI TestClient for API route tests
  - sample_lice_data: realistic lice record data for unit tests
"""
import asyncio
import os

# Disable the production rate limit for the test suite BEFORE core.api is
# first imported anywhere in the process. The suite makes hundreds of
# requests from a single TestClient IP; rate-limit enforcement is verified
# explicitly (with its own strict limiter) in tests/test_rate_limit.py.
os.environ.setdefault("FISHINTEL_RATE_LIMIT", "100000/minute")
# Same pattern for the tier daily quota: disabled suite-wide; enforcement
# is verified explicitly (monkeypatched quotas) in tests/test_tier_quota.py.
os.environ.setdefault("FISHINTEL_ENFORCE_QUOTAS", "0")

import pytest
from fastapi.testclient import TestClient


# ── Test-database bootstrap (CI runners & fresh clones) ─────────────────────
# TestClient(app) does NOT run the FastAPI lifespan, so on a machine without
# a populated data/aquaintel.db (CI!) the schema was never created and every
# DB-touching test failed with "no such table" / "unable to open database
# file". Build the schema explicitly and seed the deterministic demo dataset
# when the lice table is empty. No-op on a populated dev DB (this box: 186k rows).
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
                    if not column.nullable and column.default is None:
                        print(
                            f"conftest: {table.name}.{column.name} missing and NOT "
                            "NULL without default — add a migration"
                        )
                        continue
                    ddl = column.type.compile(engine.dialect)
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
