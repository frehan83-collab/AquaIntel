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
    async_engine = create_async_engine(_async_url, echo=False)
else:
    # PostgreSQL/TimescaleDB: production pool tuning
    # pool_size=30 per worker (4 Gunicorn workers + 12 agents), max_overflow=60 for burst
    # pool_pre_ping catches stale connections after DB restart
    async_engine = create_async_engine(
        _async_url,
        echo=False,
        pool_size=30,
        max_overflow=60,
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
