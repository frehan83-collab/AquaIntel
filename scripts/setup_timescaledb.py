"""
TimescaleDB Hypertable Setup
==============================
Run AFTER Alembic migrations against a PostgreSQL/TimescaleDB instance.
Converts high-volume time-series tables to hypertables for faster queries.

Usage:
    python scripts/setup_timescaledb.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from config.settings import settings
from core.models import engine, _is_sqlite

import structlog

log = structlog.get_logger(__name__)


def setup_timescaledb() -> None:
    if _is_sqlite:
        log.warning("timescaledb_skip", reason="SQLite detected, skipping hypertable setup")
        return

    with engine.connect() as conn:
        # Enable TimescaleDB extension
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        conn.commit()
        log.info("timescaledb_extension_enabled")

        # Backfill NULL fetched_at values before hypertable conversion
        for table in ("lice_records", "ssb_weekly_prices"):
            conn.execute(text(
                f"UPDATE {table} SET fetched_at = '2024-01-01 00:00:00' "
                f"WHERE fetched_at IS NULL"
            ))
        conn.execute(text(
            "UPDATE price_predictions SET created_at = '2024-01-01 00:00:00' "
            "WHERE created_at IS NULL"
        ))
        conn.commit()
        log.info("null_timestamps_backfilled")

        # Convert to hypertables
        hypertables = [
            ("lice_records", "fetched_at"),
            ("ssb_weekly_prices", "fetched_at"),
            ("price_predictions", "created_at"),
        ]
        for table, time_col in hypertables:
            try:
                conn.execute(text(
                    f"SELECT create_hypertable('{table}', '{time_col}', "
                    f"migrate_data => true, if_not_exists => true)"
                ))
                conn.commit()
                log.info("hypertable_created", table=table, time_column=time_col)
            except Exception as e:
                log.warning("hypertable_skip", table=table, error=str(e))
                conn.rollback()

    log.info("timescaledb_setup_complete")


if __name__ == "__main__":
    setup_timescaledb()
