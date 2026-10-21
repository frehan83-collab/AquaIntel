"""WS-53 — the lice payload shape and what the ingest refuses to store.

The v2 payload nests the counts under `liceReport`; a row with `hasReported: false` is a locality
that did not report, and storing it as a zero-count observation would be a fabrication.
"""
from __future__ import annotations

import pytest

from agents.data_ingest import DataIngestAgent


def _row(locality_no=17575, reported=True, fallow=False, adult=0.638):
    return {
        "locality": {"no": locality_no, "name": "Tollaksholmen", "isOnLand": False},
        "geometry": {"type": "Point", "coordinates": [5.2, 59.4]},
        "municipality": {"no": "1145", "name": "Bokn"},
        "hasSalmonoidLicense": True,
        "isSlaughterHoldingCage": False,
        "diseases": [],
        "liceReport": {
            "hasReported": reported,
            "isFallow": fallow,
            "adultFemaleLice": {"average": adult, "averageOfPreviousWeek": 0.471, "trend": "Increasing"},
            "mobileLice": {"average": 1.53},
            "stationaryLice": {"average": 0.0},
            "totalLice": {"average": 2.168},
            "seaTemperature": 13.339,
        },
        "liceTreatments": [],
    }


@pytest.mark.asyncio
async def test_a_reported_row_is_stored_with_its_values_and_source():
    from sqlalchemy import select

    from core.async_db import get_async_session
    from core.models import LiceRecord

    written = await DataIngestAgent._upsert_lice_v2([_row(locality_no=99001)], 2026, 41)
    # The method returns *new* rows; a rerun updates the existing one, so 0 is also correct.
    assert written in (0, 1)
    async with get_async_session() as session:
        stored = (
            await session.execute(
                select(LiceRecord).where(
                    LiceRecord.locality_no == 99001,
                    LiceRecord.year == 2026,
                    LiceRecord.week == 41,
                )
            )
        ).scalar_one()
    assert stored.avg_adult_female_lice == pytest.approx(0.638)
    assert stored.avg_mobile_lice == pytest.approx(1.53)
    assert stored.sea_temp_c == pytest.approx(13.339)
    assert stored.source == "barentswatch"


@pytest.mark.asyncio
async def test_a_site_that_did_not_report_stores_nothing():
    written = await DataIngestAgent._upsert_lice_v2([_row(locality_no=99002, reported=False)], 2026, 41)
    assert written == 0


@pytest.mark.asyncio
async def test_a_fallow_site_is_skipped():
    written = await DataIngestAgent._upsert_lice_v2([_row(locality_no=99003, fallow=True)], 2026, 41)
    assert written == 0


def test_the_restored_week_matches_the_published_figures():
    """2026-W41: 585 sites, average 0.18, worst 3.15 — cross-checked against oppdrett.info.

    Reads the DEV database on purpose (it is the one the backfill ran against),
    not the throwaway copy the rest of the suite uses (WS-24); conftest records
    its path in FISHINTEL_DEV_DB.
    """
    import os
    import sqlite3

    dev_db = os.environ.get("FISHINTEL_DEV_DB", "")
    if not dev_db:
        pytest.skip("no dev database on this box (CI/fresh clone)")
    conn = sqlite3.connect(dev_db)
    try:
        rows, average, peak = conn.execute(
            "select count(*), round(avg(avg_adult_female_lice),2), round(max(avg_adult_female_lice),2) "
            "from lice_records where source='barentswatch' and year=2026 and week=41 and locality_no < 99000"
        ).fetchone()
    except sqlite3.Error:
        pytest.skip("lice table not available")
    finally:
        conn.close()
    if not rows:
        pytest.skip("lice backfill has not been run on this database")
    assert rows == 585
    assert average == pytest.approx(0.18, abs=0.01)
    assert peak == pytest.approx(3.15, abs=0.01)
