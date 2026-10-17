"""WS-22: a decision card is not issued on lice data nobody has refreshed.

Before this rule the engine took the newest eight `lice_records` rows whatever
their age (`decision_engine.py` `_get_lice_data`), acted on them and stamped the
card live. A card whose newest count is older than two weekly reporting periods
now returns no TREAT/SCHEDULE action, says how old the count is and why, and
withholds the next-week prediction derived from the same stale rows.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from core.market import decision_engine as de


def _run(coro):
    return asyncio.run(coro)


def _lineage(week_label: str) -> dict:
    """A live lineage whose newest observation is ``week_label``."""
    return {
        "is_live": True,
        "note": None,
        "latest_week": week_label,
        "rows_used": 8,
        "year": int(week_label[:4]),
    }


def _card(monkeypatch, *, now, week_label, lice=0.9, lineage=None, gnn=None):
    """A decision card over a fake farm whose newest count is ``week_label``."""
    engine = de.DecisionEngine()
    year, week = int(week_label[:4]), int(week_label.split("-W")[1])
    data = {
        "current": lice,
        "current_year": year,
        "current_week": week,
        "sea_temp_c": 12.0,
        "trend": "rising",
        "history": [{"lice": lice, "week": week, "year": year}],
        "lineage": _lineage(week_label) if lineage is None else lineage,
    }

    async def lice_data(_):
        return data

    async def gnn_prediction(_):
        return gnn

    async def none(*_a, **_k):
        return None

    async def info(_):
        return (3, "KVINNHERAD", None)

    monkeypatch.setattr(engine, "_get_lice_data", lice_data)
    monkeypatch.setattr(engine, "_get_gnn_prediction", gnn_prediction)
    monkeypatch.setattr(engine, "_get_ocean_forecast", none)
    monkeypatch.setattr(engine, "_get_learned_profiles", none)
    monkeypatch.setattr(engine, "_locality_info", info)
    monkeypatch.setattr(de, "_now", lambda: now)
    return _run(engine.get_decision(12345))


class TestStaleLiceData:
    # 0.9 adult female lice in PA 3 (limit 0.2 all year) is a TREAT_NOW level,
    # so every "no treatment" verdict below is the age rule, not the level.

    def test_fresh_count_still_treats(self, monkeypatch):
        card = _card(monkeypatch, now=dt.datetime(2026, 4, 15, 9, tzinfo=dt.UTC),
                     week_label="2026-W16")
        assert card["action"] == "TREAT_NOW"
        assert card["data_stale"] is False
        assert card["lice_data_age_days"] == 2      # W16 Monday -> Wednesday

    def test_two_week_old_count_still_treats(self, monkeypatch):
        # Monday of W15 to Monday of W17 is exactly 14 days: not *older* than 14.
        card = _card(monkeypatch, now=dt.datetime(2026, 4, 20, 0, 0, tzinfo=dt.UTC),
                     week_label="2026-W15")
        assert card["lice_data_age_days"] == 14
        assert card["data_stale"] is False
        assert card["action"] == "TREAT_NOW"

    def test_count_older_than_two_weeks_issues_no_treatment(self, monkeypatch):
        card = _card(monkeypatch, now=dt.datetime(2026, 10, 17, 9, tzinfo=dt.UTC),
                     week_label="2026-W14", gnn=1.4)
        assert card["action"] not in ("TREAT_NOW", "SCHEDULE_TREATMENT")
        assert card["action"] == "MONITOR"
        assert card["urgency"] == "data_stale"
        assert card["data_stale"] is True
        assert card["lice_data_age_days"] > de.STALE_LICE_MAX_DAYS
        # It says why, with the age, the week and the rule.
        said = " ".join(card["reasoning"])
        assert f"{card['lice_data_age_days']} days old" in said
        assert "2026-W14" in said
        assert f"older than {de.STALE_LICE_MAX_DAYS} days" in said
        # A next-week prediction from the same stale rows is not shown.
        assert card["lice_predicted_next_week"] is None
        assert "withheld" in said

    def test_undatable_count_issues_no_treatment(self, monkeypatch):
        engine = de.DecisionEngine()

        async def lice_data(_):
            return {"current": 0.9, "sea_temp_c": 12.0, "trend": "rising",
                    "history": [], "lineage": {}}

        async def none(*_a, **_k):
            return None

        async def info(_):
            return (3, "KVINNHERAD", None)

        monkeypatch.setattr(engine, "_get_lice_data", lice_data)
        monkeypatch.setattr(engine, "_get_gnn_prediction", none)
        monkeypatch.setattr(engine, "_get_ocean_forecast", none)
        monkeypatch.setattr(engine, "_get_learned_profiles", none)
        monkeypatch.setattr(engine, "_locality_info", info)
        monkeypatch.setattr(de, "_now", lambda: dt.datetime(2026, 10, 17, tzinfo=dt.UTC))
        card = _run(engine.get_decision(12345))

        assert card["action"] == "MONITOR" and card["urgency"] == "data_stale"
        assert card["data_stale"] is True and card["lice_data_age_days"] is None
        assert any("No lice observation week is recorded" in r for r in card["reasoning"])

    def test_stale_card_still_degrades_its_provenance(self, monkeypatch):
        # The two rules compose: an unverified lineage *and* an old count are both
        # named, and the card is never live on either count.
        card = _card(
            monkeypatch, now=dt.datetime(2026, 10, 17, 9, tzinfo=dt.UTC),
            week_label="2026-W14",
            lineage={"is_live": False, "note": "lineage: newest lice observation is 2026-W14",
                     "latest_week": "2026-W14", "rows_used": 8, "year": 2026},
        )
        assert card["data_provenance"]["is_live"] is False
        assert card["data_provenance"]["freshness"] == "2026-03-30T00:00:00+00:00"
        assert card["data_stale"] is True
