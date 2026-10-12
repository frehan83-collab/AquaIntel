"""
Async Database Session Factory
================================
Provides AsyncSession for use in async endpoints.
Migration path: replace `with Session() as s:` with `async with get_async_session() as s:`
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config.settings import settings
import structlog

log = structlog.get_logger(__name__)

def _get_async_url(url: str) -> str:
    """Convert sync database URL to async driver."""
    if "sqlite" in url:
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif "postgresql" in url:
        return url.replace("postgresql://", "postgresql+asyncpg://").replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    return url

_async_url = _get_async_url(settings.database_url)
_is_sqlite = "sqlite" in _async_url

if _is_sqlite:
    # SQLite: limited concurrency, no pool needed
    async_engine = create_async_engine(
        _async_url,
        echo=False,
        connect_args={"timeout": 30},
    )

    from sqlalchemy import event

    @event.listens_for(async_engine.sync_engine, "connect")
    def _sqlite_connect_pragmas(dbapi_connection, connection_record):
        """WAL + busy_timeout on EVERY aiosqlite connection (busy_timeout is
        per-connection state; the aiosqlite default is only 5s, which caused
        recurring "database is locked" agent tick failures)."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
else:
    # PostgreSQL/TimescaleDB: production pool tuning
    # With 4 gunicorn workers, pool_size=5 + max_overflow=10 caps peak pool at 4 x 15 = 60 connections,
    # safely within TimescaleDB's default max_connections=100 (Architecture Report 3.1).
    # pool_timeout=10 surfaces pool exhaustion quickly rather than hanging requests.
    async_engine = create_async_engine(
        _async_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_timeout=10,
        pool_recycle=3600,
        pool_pre_ping=True,
        connect_args={"server_settings": {"statement_timeout": "30000"}},  # 30s query timeout
    )

AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

@asynccontextmanager
async def get_async_session():
    """Async context manager for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
