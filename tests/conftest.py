"""
Shared pytest fixtures for FishIntel test suite.
=================================================
Provides common fixtures used across multiple test files:
  - event_loop: session-scoped async event loop
  - test_client: FastAPI TestClient for API route tests
  - sample_lice_data: realistic lice record data for unit tests
"""
import asyncio

import pytest
from fastapi.testclient import TestClient


# ── Test-database bootstrap (CI runners & fresh clones) ─────────────────────
# TestClient(app) does NOT run the FastAPI lifespan, so on a machine without
# a populated data/openclaw.db (CI!) the schema was never created and every
# DB-touching test failed with "no such table" / "unable to open database
# file". Build the schema explicitly and seed the deterministic demo dataset
# when the lice table is empty. No-op on a populated dev DB (this box: 186k rows).
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
