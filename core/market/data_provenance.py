"""
Data Provenance System
========================
Every engine response must include provenance metadata so users
know whether data is live, stale, degraded, or simulated.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class DataProvenance:
    source: str  # e.g. "SSB Table 03024", "CDSE Sentinel-2", "simulated"
    is_live: bool  # True if fetched from authoritative source recently
    freshness: str  # ISO datetime of last successful fetch
    confidence: float  # 0.0 (fabricated) to 1.0 (government authoritative)
    fallback_reason: Optional[str] = None  # Why live data unavailable

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def live(source: str, confidence: float = 0.9) -> "DataProvenance":
        return DataProvenance(
            source=source,
            is_live=True,
            freshness=dt.datetime.now(dt.UTC).isoformat(),
            confidence=confidence,
        )

    @staticmethod
    def degraded(source: str, reason: str, confidence: float = 0.5) -> "DataProvenance":
        return DataProvenance(
            source=source,
            is_live=False,
            freshness=dt.datetime.now(dt.UTC).isoformat(),
            confidence=confidence,
            fallback_reason=reason,
        )

    @staticmethod
    def simulated(reason: str) -> "DataProvenance":
        return DataProvenance(
            source="simulated",
            is_live=False,
            freshness=dt.datetime.now(dt.UTC).isoformat(),
            confidence=0.0,
            fallback_reason=reason,
        )
