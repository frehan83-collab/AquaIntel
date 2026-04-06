"""
Engine Output Cache
=====================
TTL-based in-memory cache for expensive engine computations.
Avoids redundant API calls to BarentsWatch, SSB, CMEMS, etc.
Replace with Redis when deploying multi-instance.

CacheManager provides:
  - 5-tier TTL categories (realtime/frequent/standard/slow/static)
  - Per-engine hit/miss tracking for monitoring
  - Selective invalidation by engine name
  - Singleton: cache_manager for global access
"""
from __future__ import annotations

import time
import asyncio
from typing import Any, Optional, Callable
from functools import wraps

import structlog

log = structlog.get_logger(__name__)


# ── TTL Categories ───────────────────────────────────────────────────
TTL_CATEGORIES = {
    "realtime": 60,       # prices, alerts
    "frequent": 300,      # lice data, forecasts
    "standard": 1800,     # analytics, benchmarks
    "slow": 3600,         # biomass, regulatory
    "static": 86400,      # constants, reference data
}


class EngineCache:
    """Simple TTL cache for engine outputs. Thread-safe via asyncio."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}  # key -> (value, expire_time)
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        value, expires = entry
        if time.time() > expires:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return value

    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        self._store[key] = (value, time.time() + ttl_seconds)

    def invalidate(self, pattern: str = ""):
        """Clear cache entries matching pattern (or all if empty)."""
        if not pattern:
            count = len(self._store)
            self._store.clear()
            log.info("cache.invalidated_all", entries_cleared=count)
        else:
            keys = [k for k in self._store if pattern in k]
            for k in keys:
                del self._store[k]
            log.info("cache.invalidated_pattern", pattern=pattern, entries_cleared=len(keys))

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "entries": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(total, 1) * 100, 1),
        }


# Singleton
engine_cache = EngineCache()


def cached(ttl: int = 300, key_prefix: str = ""):
    """Decorator for caching async function results."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix or func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cached_val = engine_cache.get(cache_key)
            if cached_val is not None:
                log.debug("cache.hit", key=cache_key[:80])
                return cached_val
            result = await func(*args, **kwargs)
            engine_cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════════════
# CACHE MANAGER — Unified Cache Abstraction Layer
# ══════════════════════════════════════════════════════════════════════

class CacheManager:
    """
    Unified cache abstraction with per-engine namespacing, 5-tier TTL
    categories, and hit/miss monitoring per engine.

    TTL Tiers:
      - realtime  (60s):    prices, alerts
      - frequent  (300s):   lice data, forecasts
      - standard  (1800s):  analytics, benchmarks
      - slow      (3600s):  biomass, regulatory
      - static    (86400s): constants, reference data

    Usage:
        from core.cache import cache_manager

        # Store with named category
        cache_manager.set("feed_cost_engine", "composite_index", data, category="frequent")

        # Retrieve
        val = cache_manager.get("feed_cost_engine", "composite_index")

        # Monitor
        stats = cache_manager.get_stats()
    """

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}  # namespaced_key -> (value, expire_time)
        self._engine_hits: dict[str, int] = {}
        self._engine_misses: dict[str, int] = {}

    def _make_key(self, engine_name: str, key: str) -> str:
        """Build namespaced cache key: engine_name::key."""
        return f"{engine_name}::{key}"

    def get(self, engine_name: str, key: str) -> Optional[Any]:
        """Retrieve a cached value by engine and key. Returns None on miss/expiry."""
        ns_key = self._make_key(engine_name, key)
        entry = self._store.get(ns_key)
        if entry is None:
            self._engine_misses[engine_name] = self._engine_misses.get(engine_name, 0) + 1
            return None
        value, expires = entry
        if time.time() > expires:
            del self._store[ns_key]
            self._engine_misses[engine_name] = self._engine_misses.get(engine_name, 0) + 1
            return None
        self._engine_hits[engine_name] = self._engine_hits.get(engine_name, 0) + 1
        return value

    def set(
        self,
        engine_name: str,
        key: str,
        value: Any,
        category: str = "standard",
        ttl_override: Optional[int] = None,
    ):
        """Store a value with TTL from category or explicit override."""
        ttl = ttl_override if ttl_override is not None else TTL_CATEGORIES.get(category, 1800)
        ns_key = self._make_key(engine_name, key)
        self._store[ns_key] = (value, time.time() + ttl)

    def clear(self, engine_name: Optional[str] = None):
        """Clear cache entries for a specific engine, or all entries if engine_name is None."""
        if engine_name is None:
            count = len(self._store)
            self._store.clear()
            self._engine_hits.clear()
            self._engine_misses.clear()
            log.info("cache_manager.cleared_all", entries_cleared=count)
            return count
        else:
            prefix = f"{engine_name}::"
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            self._engine_hits.pop(engine_name, None)
            self._engine_misses.pop(engine_name, None)
            log.info("cache_manager.cleared_engine", engine=engine_name, entries_cleared=len(keys))
            return len(keys)

    def get_stats(self) -> dict:
        """Return per-engine hit/miss ratios and global summary."""
        # Collect all known engine names
        all_engines = sorted(
            set(list(self._engine_hits.keys()) + list(self._engine_misses.keys()))
        )

        per_engine = {}
        total_hits = 0
        total_misses = 0

        for eng in all_engines:
            hits = self._engine_hits.get(eng, 0)
            misses = self._engine_misses.get(eng, 0)
            total = hits + misses
            total_hits += hits
            total_misses += misses
            per_engine[eng] = {
                "hits": hits,
                "misses": misses,
                "total": total,
                "hit_rate": round(hits / max(total, 1) * 100, 1),
            }

        grand_total = total_hits + total_misses

        return {
            "total_entries": len(self._store),
            "total_hits": total_hits,
            "total_misses": total_misses,
            "global_hit_rate": round(total_hits / max(grand_total, 1) * 100, 1),
            "ttl_categories": TTL_CATEGORIES,
            "engines": per_engine,
        }


# Singleton
cache_manager = CacheManager()
