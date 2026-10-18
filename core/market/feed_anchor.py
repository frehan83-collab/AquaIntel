"""Realised feed-cost anchor — the number the margin model is checked against.

WS-29b (2026-10-18). The margin bridge's feed leg is a model: a FRED proxy basket times
a learned multiplier. Its *level* is only meaningful if it is compared with a realised
cost, and the last audited anchor is Fiskeridirektoratet's 2024 survey. The 2025/2026
figures are not published as this is written (checked 2026-10-18), so the platform must
not invent them.

This module is the place an operator registers a realised figure — theirs, a design
partner's, or a licensed series — without a code change:

    artifacts/feed_realised_prices.json
    {
      "year": 2025,
      "feed_nok_per_kg_salmon": 25.4,
      "scope": "Norway, grow-out, realised delivered feed per kg harvested",
      "source": "Design partner A, 2025 accounts (under NDA, aggregated)",
      "source_url": null,
      "registered_at": "2026-10-18"
    }

Rules:
* a missing file is normal and not an error — the bridge falls back to the audited
  survey and says so;
* a malformed or out-of-range file is ignored **with a reason**, never half-read;
* an anchor older than :data:`MAX_ANCHOR_AGE_YEARS` is still reported but flagged as
  stale, because a five-year-old cost says little about this year's feed leg.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

#: Where an operator drops the realised figure.
ANCHOR_PATH = Path(__file__).resolve().parents[2] / "artifacts" / "feed_realised_prices.json"

#: A cost anchor older than this is reported but flagged stale.
MAX_ANCHOR_AGE_YEARS = 2

#: Plausible bounds for delivered feed cost per kg harvested salmon (NOK). Outside this
#: range the file is treated as malformed: it is almost certainly a per-kg-of-feed figure
#: or a typo, and using it would mis-state the gap.
PLAUSIBLE_RANGE = (10.0, 60.0)


def _current_year() -> int:
    return dt.datetime.now(dt.UTC).year


def load_anchor(path: Path | None = None) -> dict | None:
    """The registered realised anchor, or None.

    Returns ``{"year", "feed_nok_per_kg_salmon", "scope", "source", "source_url",
    "registered_at", "stale", "age_years"}``. Never raises: a broken file is logged and
    ignored so the bridge degrades to the audited survey instead of 500-ing.
    """
    target = path or ANCHOR_PATH
    try:
        if not target.exists():
            return None
        raw = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — a bad file must not break the bridge
        log.warning("feed_anchor.unreadable", path=str(target), error=str(exc)[:120])
        return None

    if not isinstance(raw, dict):
        log.warning("feed_anchor.not_an_object", path=str(target))
        return None
    year = raw.get("year")
    value = raw.get("feed_nok_per_kg_salmon")
    try:
        year_int = int(year)
        value_float = float(value)
    except (TypeError, ValueError):
        log.warning("feed_anchor.missing_fields", year=year, value=value)
        return None
    low, high = PLAUSIBLE_RANGE
    if not (low <= value_float <= high):
        log.warning(
            "feed_anchor.out_of_range", value=value_float, low=low, high=high
        )
        return None
    if year_int < 2008 or year_int > _current_year():
        log.warning("feed_anchor.impossible_year", year=year_int)
        return None

    age = _current_year() - year_int
    return {
        "year": year_int,
        "feed_nok_per_kg_salmon": round(value_float, 2),
        "scope": raw.get("scope") or "unstated — treat the comparison as indicative",
        "source": raw.get("source") or "source not stated",
        "source_url": raw.get("source_url"),
        "registered_at": raw.get("registered_at"),
        "age_years": age,
        "stale": age > MAX_ANCHOR_AGE_YEARS,
    }
