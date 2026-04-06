"""
SQLite → PostgreSQL Data Migration
=====================================
Reads all rows from the SQLite database and batch-inserts into PostgreSQL.
Handles type conversions (text dates → timestamps, int bools → booleans).

Usage:
    DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/openclaw \
    python scripts/migrate_sqlite_to_pg.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.orm import sessionmaker

from config.settings import settings, ROOT_DIR

import structlog

log = structlog.get_logger(__name__)

SQLITE_URL = f"sqlite:///{ROOT_DIR / 'data' / 'openclaw.db'}"
BATCH_SIZE = 500


def migrate() -> None:
    pg_url = settings.database_url
    if pg_url.startswith("sqlite"):
        log.error("migration_abort", reason="DATABASE_URL points to SQLite, not PostgreSQL")
        sys.exit(1)

    src_engine = create_engine(SQLITE_URL, echo=False)
    dst_engine = create_engine(pg_url, echo=False)

    src_meta = MetaData()
    src_meta.reflect(bind=src_engine)

    dst_inspector = inspect(dst_engine)
    dst_tables = set(dst_inspector.get_table_names())

    SrcSession = sessionmaker(bind=src_engine)
    DstSession = sessionmaker(bind=dst_engine)

    total_rows = 0

    for table_name in src_meta.tables:
        if table_name not in dst_tables:
            log.warning("table_skip", table=table_name, reason="not in destination")
            continue

        table = src_meta.tables[table_name]

        with src_engine.connect() as src_conn:
            rows = src_conn.execute(table.select()).fetchall()

        if not rows:
            log.info("table_empty", table=table_name)
            continue

        columns = [c.name for c in table.columns]

        with dst_engine.connect() as dst_conn:
            # Clear destination table first (idempotent re-runs)
            dst_conn.execute(text(f'DELETE FROM "{table_name}"'))
            dst_conn.commit()

            batch = []
            for row in rows:
                record = {}
                for i, col_name in enumerate(columns):
                    val = row[i]
                    # SQLite stores booleans as 0/1
                    if isinstance(val, int) and col_name in (
                        "has_cleaner_fish", "confirmed_by_user", "user_consent",
                        "is_active", "contract_risk_flag", "deforestation_free",
                        "cancel_at_period_end",
                    ):
                        val = bool(val)
                    record[col_name] = val
                batch.append(record)

                if len(batch) >= BATCH_SIZE:
                    dst_conn.execute(
                        text(
                            f'INSERT INTO "{table_name}" ({", ".join(columns)}) '
                            f'VALUES ({", ".join(":" + c for c in columns)})'
                        ),
                        batch,
                    )
                    dst_conn.commit()
                    total_rows += len(batch)
                    batch = []

            if batch:
                dst_conn.execute(
                    text(
                        f'INSERT INTO "{table_name}" ({", ".join(columns)}) '
                        f'VALUES ({", ".join(":" + c for c in columns)})'
                    ),
                    batch,
                )
                dst_conn.commit()
                total_rows += len(batch)

        log.info("table_migrated", table=table_name, rows=len(rows))

    log.info("migration_complete", total_rows=total_rows)


if __name__ == "__main__":
    migrate()
