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
