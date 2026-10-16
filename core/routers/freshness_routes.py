"""Data freshness — per-source staleness and synthetic-data disclosure.

Operational honesty surface: which sources are current, which are stale, which
have no measurable freshness and which are backed only by synthetic rows.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/data-freshness", tags=["freshness"])


@router.get("")
async def data_freshness():
    """Freshness report for every monitored source (read-only, no secrets)."""
    from core.market.freshness_monitor import SOURCES, report

    data = await report()
    data["monitored"] = len(SOURCES)
    data["contract"] = (
        "status: fresh (within cadence) | stale (<= 3x cadence) | dead (> 3x) | "
        "unknown (no measurable timestamp or missing table). `synthetic_only` means "
        "the table holds only demo/seed rows. `verified_rows` / `unverified_rows` "
        "split rows by lineage where a table declares a source contract; "
        "`no_verified_rows` lists sources whose lineage is unknown — they never "
        "back a live claim."
    )
    return data


@router.get("/sources")
async def freshness_sources():
    """The monitored source registry (what exists, upstream, expected cadence)."""
    from core.market.freshness_monitor import SOURCES

    return {
        "sources": [
            {
                "key": s.key,
                "label": s.label,
                "table": s.table,
                "upstream": s.upstream,
                "expected_cadence_hours": s.expected_cadence_hours,
                "critical": s.critical,
                "refresh_hint": s.refresh_hint,
            }
            for s in SOURCES
        ]
    }
