"""WS-29b — the feed-level check against a realised price an operator registers.

The margin bridge's feed leg is a model (FRED proxy basket × learned multiplier), and the
last *audited* anchor is Fiskeridirektoratet's 2024 survey. The 2025/2026 figures are not
published as this is written, so the platform must not invent them — but it must let an
operator supply one. `core/market/feed_anchor.py` reads
``artifacts/feed_realised_prices.json``; these tests pin the reading rules and the
validation block's honesty.
"""
from __future__ import annotations

import json

import pytest

from core.market import feed_anchor


def _write(tmp_path, payload):
    path = tmp_path / "feed_realised_prices.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid(**overrides):
    payload = {
        "year": 2025,
        "feed_nok_per_kg_salmon": 25.4,
        "scope": "Norway, grow-out",
        "source": "Design partner A, 2025 accounts",
        "source_url": None,
        "registered_at": "2026-10-18",
    }
    payload.update(overrides)
    return payload


# ── 1. Reading rules ───────────────────────────────────────────────────


def test_a_missing_file_is_not_an_error(tmp_path):
    assert feed_anchor.load_anchor(tmp_path / "absent.json") is None


def test_a_valid_anchor_is_read_with_its_scope_and_source(tmp_path):
    anchor = feed_anchor.load_anchor(_write(tmp_path, _valid()))
    assert anchor["year"] == 2025
    assert anchor["feed_nok_per_kg_salmon"] == pytest.approx(25.4)
    assert anchor["scope"] == "Norway, grow-out"
    assert "Design partner A" in anchor["source"]
    assert anchor["stale"] is False


def test_a_malformed_file_is_ignored_not_half_read(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    assert feed_anchor.load_anchor(path) is None


def test_a_per_kg_of_feed_figure_is_rejected_as_implausible(tmp_path):
    """Delivered feed per kg of FEED is ~15-25; per kg of salmon ~20-30. A 2.5 is a typo."""
    assert feed_anchor.load_anchor(_write(tmp_path, _valid(feed_nok_per_kg_salmon=2.5))) is None


def test_a_future_year_is_rejected(tmp_path):
    assert feed_anchor.load_anchor(_write(tmp_path, _valid(year=2099))) is None


def test_an_old_anchor_is_kept_but_flagged_stale(tmp_path):
    anchor = feed_anchor.load_anchor(_write(tmp_path, _valid(year=2019)))
    assert anchor["stale"] is True
    assert anchor["age_years"] >= 5


# ── 2. The validation block ────────────────────────────────────────────


def test_without_an_anchor_the_survey_is_used_and_the_gap_is_named(monkeypatch):
    from core.market.margin_bridge import MarginBridgeEngine

    monkeypatch.setattr(feed_anchor, "load_anchor", lambda path=None: None)
    block = MarginBridgeEngine._feed_level_validation(
        modelled_feed_per_kg_salmon=29.39, caller_feed_per_kg_salmon=None, as_of=None
    )
    assert block["anchor_is_registered"] is False
    assert block["anchor_year"] == 2024
    assert block["anchor_source"].startswith("Fiskeridirektoratet")
    # 29.39 vs the 2024 realised 25.67
    assert block["gap_pct"] == pytest.approx((29.39 - 25.67) / 25.67 * 100, abs=0.3)
    assert "do not depend on it" in block["note"]


def test_a_registered_anchor_is_preferred_and_its_scope_reported(monkeypatch):
    from core.market.margin_bridge import MarginBridgeEngine

    anchor = {
        "year": 2025,
        "feed_nok_per_kg_salmon": 21.5,
        "scope": "Norway, grow-out, realised",
        "source": "Design partner A",
        "source_url": None,
        "registered_at": "2026-10-18",
        "age_years": 1,
        "stale": False,
    }
    monkeypatch.setattr(feed_anchor, "load_anchor", lambda path=None: anchor)
    block = MarginBridgeEngine._feed_level_validation(
        modelled_feed_per_kg_salmon=29.39, caller_feed_per_kg_salmon=None, as_of=None
    )
    assert block["anchor_is_registered"] is True
    assert block["anchor_year"] == 2025
    assert block["anchor_scope"] == "Norway, grow-out, realised"
    assert block["official_feed_nok_per_kg_salmon"] == pytest.approx(21.5)
    # The model is now 37 % above a realised figure — outside the 25 % tolerance.
    assert block["within_tolerance"] is False
    assert "indicative only" in block["note"]


def test_a_stale_anchor_says_so_in_the_note(monkeypatch):
    from core.market.margin_bridge import MarginBridgeEngine

    anchor = {
        "year": 2019,
        "feed_nok_per_kg_salmon": 24.0,
        "scope": "Norway",
        "source": "old survey clipping",
        "source_url": None,
        "registered_at": None,
        "age_years": 7,
        "stale": True,
    }
    monkeypatch.setattr(feed_anchor, "load_anchor", lambda path=None: anchor)
    block = MarginBridgeEngine._feed_level_validation(
        modelled_feed_per_kg_salmon=29.39, caller_feed_per_kg_salmon=None, as_of=None
    )
    assert block["anchor_stale"] is True
    assert "years old" in block["note"]


def test_the_payload_tells_the_operator_how_to_register_one(monkeypatch):
    from core.market.margin_bridge import MarginBridgeEngine

    monkeypatch.setattr(feed_anchor, "load_anchor", lambda path=None: None)
    block = MarginBridgeEngine._feed_level_validation(
        modelled_feed_per_kg_salmon=29.39, caller_feed_per_kg_salmon=None, as_of=None
    )
    assert "artifacts/feed_realised_prices.json" in block["note"]
