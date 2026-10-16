"""Provenance envelope — attach `data_provenance` to a dict-returning handler.

Rule 3 says every data route must carry provenance. Most routers return a plain
dict, so this decorator is the reviewable, one-line pattern to satisfy the rule
without rewriting a handler:

    @router.get("/api/example")
    @with_provenance("lice_records (Fiskeridir/Mattilsynet)")
    async def example(): ...

A handler that already sets `data_provenance` (usually because the engine did) is
left untouched, so nesting this is safe. Pass `degraded_reason` for routes that are
known model estimates rather than measurements — a degraded envelope, never a live
one (rule 1).

The envelope is applied OUTSIDE `@cached` when placed as shown, so the freshness
timestamp reflects the response, not the cache fill.
"""
from __future__ import annotations

import functools

from core.market.data_provenance import DataProvenance


def with_provenance(
    source: str,
    *,
    confidence: float = 0.9,
    degraded_reason: str | None = None,
):
    """Decorate an async handler to guarantee a provenance envelope on dicts."""

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            result = await fn(*args, **kwargs)
            if isinstance(result, dict) and "data_provenance" not in result:
                provenance = (
                    DataProvenance.degraded(source, degraded_reason, confidence=0.5)
                    if degraded_reason
                    else DataProvenance.live(source, confidence=confidence)
                )
                result = {**result, "data_provenance": provenance.to_dict()}
            return result

        return wrapper

    return decorator
