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

from core.version import API_SCHEMA_VERSION


@dataclass
class DataProvenance:
    source: str  # e.g. "SSB Table 03024", "CDSE Sentinel-2", "simulated"
    is_live: bool  # True if fetched from authoritative source recently
    freshness: str  # ISO datetime of last successful fetch
    confidence: float  # 0.0 (fabricated) to 1.0 (government authoritative)
    fallback_reason: Optional[str] = None  # Why live data unavailable

    def to_dict(self) -> dict:
        return {**asdict(self), "schema_version": API_SCHEMA_VERSION}

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

    @staticmethod
    def from_model_result(result: dict, source: str, confidence: float = 0.7) -> "DataProvenance":
        """
        Derive honest provenance from an ML engine result dict.

        Engines tag fallback output with a "model" value containing
        "fallback" (e.g. "naive-fallback", "seasonal-naive-fallback") or
        an explicit "fallback": True. Such results are NOT live model
        output and must never be reported as live.
        """
        if not isinstance(result, dict):
            return DataProvenance.degraded(source, "unrecognised engine result", confidence=0.3)
        # Comparison results: members computed from fallbacks degrade the whole
        # result (e.g. "chronos vs naive" where chronos itself fell back).
        fb_members = result.get("fallback_members")
        if isinstance(fb_members, list) and fb_members:
            return DataProvenance.degraded(
                source,
                f"members computed from seasonal-naive fallback: {', '.join(str(m) for m in fb_members)}",
                confidence=0.4,
            )
        model = str(result.get("model", "")).lower()
        is_fallback = (
            result.get("fallback") is True
            or "fallback" in model
            or bool(result.get("error"))
        )
        if is_fallback:
            return DataProvenance.degraded(
                source,
                f"model unavailable — seasonal-naive fallback used (requested: {source})",
                confidence=0.3,
            )
        return DataProvenance.live(source, confidence=confidence)


def from_records(
    records,
    *,
    live_source: str,
    degraded_source: str,
    reason: str,
    live_confidence: float = 0.75,
    degraded_confidence: float = 0.5,
) -> DataProvenance:
    """Shared liveness helper keyed on records ACTUALLY returned (review L4).

    The R10/M1 invariant as a reusable primitive: provenance is live only
    when the upstream returned raw records — never on derived/rounded
    values that can legitimately be 0 (e.g. a rounded tonnes figure).
    Domains with the same "records or estimates" shape should use this
    instead of pasting `DataProvenance.live(...)` at each call site.

    See tests/test_provenance_contract.py — a degraded payload must not
    contain "LIVE" claims anywhere (nested engine fields included).
    """
    if records:
        return DataProvenance.live(live_source, confidence=live_confidence)
    return DataProvenance.degraded(
        degraded_source, reason=reason, confidence=degraded_confidence
    )
