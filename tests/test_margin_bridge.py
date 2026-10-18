"""WS-29 — the weekly margin bridge: arithmetic, level honesty, and the levers.

The bridge is the one surface that turns the live price and feed feeds into money
per kilo. These tests pin three things that a buyer would otherwise have to take on
trust:

1. **The arithmetic** — the grouped legs re-add to the feed engine's total, the
   break-even and the lever formulas are exact, and no NOK total is produced from a
   volume nobody supplied.
2. **The honesty rules** — the margin is ``modelled`` unless the caller supplied the
   price *and* the feed numbers; a stale, undated or defaulted feed basket degrades
   the leg with a named reason; a caller-supplied or unavailable price does the same;
   and the modelled feed level is checked against the last audited realised cost.
3. **The farm block** — a lice position is reported only from verified, current rows,
   never inferred from demo or stale ones.
"""
from __future__ import annotations

import datetime as dt
from collections import namedtuple

import pytest

from core.market.data_provenance import DataProvenance
from core.market.feed_cost_engine import FeedCostSnapshot, IngredientPrice
from core.market.margin_bridge import (
    BIOLOGY_LEVER_METHOD,
    FEED_LEVEL_VALIDATION_TOLERANCE_PCT,
    FEED_PRICE_MAX_AGE_DAYS,
    MARGIN_METHOD_VERSION,
    MarginBridgeEngine,
    margin_bridge,
)
from core.market.treatment_constants import TREATMENT_PROFILES

APPROX = 0.02

#: The dev box's live shape on 2026-10-18 (SSB W41, FRED July basket), used so the
#: tests describe a real payload rather than a convenient one.
LIVE_BREAKDOWN = {
    "feed_ingredients": 12.15,
    "feed_per_kg_salmon": 29.39,
    "smolt": 9.62,
    "insurance": 0.3,
    "labour": 4.29,
    "depreciation": 0.89,
    "other_operating": 23.17,
    "net_finance": 1.04,
    "slaughter": 5.33,
    "total": 74.02,
    "method": "learned_ratios",
    "feed_share_of_total": 39.7,
}


def _snapshot(**overrides) -> FeedCostSnapshot:
    data = {
        "feed_cost_usd_per_kg": 1.284,
        "feed_cost_nok_per_kg": 12.15,
        "feed_cost_nok_per_kg_salmon": 29.39,
        "non_feed_costs_nok": 44.63,
        "production_cost_nok_per_kg_salmon": 74.02,
        "salmon_spot_nok": 72.55,
        "margin_nok_per_kg": -1.47,
        "margin_pct": -2.0,
        "usd_nok": 9.46,
        "fcr": 1.30,
        "cost_breakdown": dict(LIVE_BREAKDOWN),
        "feed_prices_as_of": dt.date(2026, 7, 1),
        "feed_prices_as_of_latest": dt.date(2026, 7, 1),
        "ingredients": {
            "soy": IngredientPrice("soy", 442.5, 0.4425, "fred", observed_at=dt.date(2026, 7, 1)),
        },
    }
    data.update(overrides)
    snapshot = FeedCostSnapshot(**data)
    snapshot.using_defaults = False
    snapshot.default_ingredients = []
    return snapshot


def _price_history(*, current: float = 72.55, previous: float = 73.80) -> list[dict]:
    return [
        {"week": "W39", "year": 2026, "price_nok": 73.59, "volume_tonnes": 32385.0},
        {"week": "W40", "year": 2026, "price_nok": previous, "volume_tonnes": 30277.0},
        {"week": "W41", "year": 2026, "price_nok": current, "volume_tonnes": 27982.0},
    ]


@pytest.fixture
def stub_sources(monkeypatch):
    """Stub the three upstreams the bridge reads, with the live shape."""

    async def fake_fetch_prices(self=None):
        return _snapshot()

    async def fake_history(n=3):
        return _price_history()

    async def fake_change(self=None):
        return {
            "change_pct": 1.58,
            "period": "2026-07",
            "months": ["2026-07"],
            "by_ingredient": {},
            "excluded": ["other"],
            "weight_coverage_pct": 85.0,
        }

    monkeypatch.setattr(
        "core.market.feed_cost_engine.feed_cost_engine.fetch_prices", fake_fetch_prices
    )
    monkeypatch.setattr(
        "core.market.feed_cost_engine.feed_cost_engine.feed_index_change", fake_change
    )
    monkeypatch.setattr(
        "core.market.ssb_price_client.ssb_price_client.get_price_history", fake_history
    )
    return monkeypatch


async def _build(**kwargs):
    return await MarginBridgeEngine().build(**kwargs)


# ── 1. Arithmetic ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_grouped_legs_readd_to_the_engine_total(stub_sources):
    payload = await _build()
    cost_legs = [leg for leg in payload["legs"] if leg["kind"] == "cost"]
    modelled = -sum(leg["nok_per_kg"] for leg in cost_legs)
    assert modelled == pytest.approx(LIVE_BREAKDOWN["total"] - 29.39 + 29.39, abs=APPROX)
    assert payload["reconciliation"]["ok"] is True
    assert abs(payload["reconciliation"]["difference_nok_per_kg"]) <= 0.05


@pytest.mark.asyncio
async def test_reconciliation_is_not_applicable_to_a_caller_feed_leg(stub_sources):
    """A caller's feed leg is on a different basis; a false "cost line renamed" is worse
    than saying the check does not apply (review finding 3)."""
    payload = await _build(fcr=1.40)
    reconciliation = payload["reconciliation"]
    assert reconciliation["ok"] is None
    assert reconciliation["applicable"] is False
    assert "caller-supplied" in reconciliation["note"]


@pytest.mark.asyncio
async def test_a_stale_price_week_degrades_the_price_leg(stub_sources):
    """SSB publishes weekly; a cached week five behind is not this week's price."""
    async def stale_history(n=3):
        return [
            {"week": "W37", "year": 2026, "price_nok": 70.18, "volume_tonnes": 30111.0},
            {"week": "W38", "year": 2026, "price_nok": 71.41, "volume_tonnes": 31087.0},
        ]

    stub_sources.setattr(
        "core.market.ssb_price_client.ssb_price_client.get_price_history", stale_history
    )
    payload = await _build()
    price = next(leg for leg in payload["legs"] if leg["key"] == "price")
    assert price["nok_per_kg"] == pytest.approx(71.41)
    assert price["data_provenance"]["is_live"] is False
    assert "weeks behind" in price["data_provenance"]["fallback_reason"]
    assert payload["data_provenance"]["is_live"] is False


@pytest.mark.asyncio
async def test_margin_is_spot_minus_modelled_cost(stub_sources):
    payload = await _build()
    cost = payload["margin"]["modelled_cost_nok_per_kg"]
    assert payload["margin"]["nok_per_kg"] == pytest.approx(72.55 - cost, abs=APPROX)
    assert payload["margin"]["pct"] == pytest.approx(
        (72.55 - cost) / 72.55 * 100, abs=0.2
    )


@pytest.mark.asyncio
async def test_an_unknown_cost_line_is_surfaced_not_dropped(stub_sources):
    """A renamed or added cost line must appear (as `other`), never vanish."""
    breakdown = dict(LIVE_BREAKDOWN)
    breakdown["new_line_from_a_future_migration"] = 3.0
    stub_sources.setattr(
        "core.market.feed_cost_engine.feed_cost_engine.fetch_prices",
        lambda *a, **k: _async(_snapshot(cost_breakdown=breakdown)),
    )
    payload = await _build()
    other = [leg for leg in payload["legs"] if leg["key"] == "other"]
    assert other, "the ungrouped cost line must appear as its own leg"
    assert other[0]["nok_per_kg"] == pytest.approx(-3.0, abs=APPROX)
    assert "new_line_from_a_future_migration" in other[0]["members"]


@pytest.mark.asyncio
async def test_break_even_states_the_gap_and_the_feed_fallback(stub_sources):
    payload = await _build()
    be = payload["break_even"]
    assert be["above_break_even"] is False
    assert be["distance_nok_per_kg"] == pytest.approx(-1.48, abs=APPROX)
    # 1.48 of a 29.39 feed leg would have to fall
    assert be["feed_leg_reduction_needed_pct"] == pytest.approx(1.48 / 29.39 * 100, abs=0.2)
    # The FCR that closes the gap, holding every non-feed leg constant.
    non_feed = 74.03 - 22.61 * 1.30
    assert be["fcr_at_break_even"] == pytest.approx((72.55 - non_feed) / 22.61, abs=0.02)


@pytest.mark.asyncio
async def test_levers_are_exact_and_use_the_shared_constants(stub_sources):
    payload = await _build()
    levers = {lever["key"]: lever for lever in payload["levers"]}
    assert levers["price"]["nok_per_kg"] == pytest.approx(1.0)
    assert levers["feed_price"]["nok_per_kg"] == pytest.approx(1.30, abs=APPROX)
    assert levers["fcr"]["nok_per_kg"] == pytest.approx(0.05 * 22.61, abs=APPROX)
    treatment = TREATMENT_PROFILES[BIOLOGY_LEVER_METHOD].cost_per_fish_nok
    assert levers["treatment"]["nok_per_kg"] == pytest.approx(treatment / 5.0, abs=APPROX)
    assert levers["survival"]["nok_per_kg"] == pytest.approx(0.01 * 72.55, abs=APPROX)


@pytest.mark.asyncio
async def test_no_volume_means_no_nok_totals(stub_sources):
    payload = await _build()
    assert payload["volume"]["annual_tonnes"] is None
    assert payload["volume"]["annual_margin_nok"] is None
    assert "per kg only" in payload["volume"]["basis"]
    assert all("nok_per_year" not in lever for lever in payload["levers"])


@pytest.mark.asyncio
async def test_a_supplied_volume_produces_totals_from_it(stub_sources):
    payload = await _build(annual_tonnes=5000, standing_tonnes=2000)
    assert payload["volume"]["annual_margin_nok"] == pytest.approx(-1.48 * 5000 * 1000, rel=0.02)
    assert payload["volume"]["standing_cost_nok"] == pytest.approx(74.03 * 2000 * 1000, rel=0.01)
    assert "5,000 t" in payload["volume"]["basis"]
    assert payload["levers"][0]["nok_per_year"] == pytest.approx(5_000_000)


@pytest.mark.asyncio
async def test_caller_fcr_moves_only_the_feed_leg(stub_sources):
    base = await _build()
    mine = await _build(fcr=1.40)
    base_feed = next(leg for leg in base["legs"] if leg["key"] == "feed")
    my_feed = next(leg for leg in mine["legs"] if leg["key"] == "feed")
    assert my_feed["nok_per_kg"] == pytest.approx(-22.61 * 1.40, abs=APPROX)
    assert my_feed["nok_per_kg"] < base_feed["nok_per_kg"]
    for key in ("fish_and_harvest", "operations", "capital"):
        assert next(l for l in mine["legs"] if l["key"] == key)["nok_per_kg"] == pytest.approx(
            next(l for l in base["legs"] if l["key"] == key)["nok_per_kg"]
        )
    assert "caller-supplied; the other legs remain the modelled industry values" in my_feed["detail"]


# ── 2. Honesty rules ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_margin_is_modelled_until_the_caller_supplies_both_sides(stub_sources):
    default = await _build()
    assert default["margin"]["quality"] == "modelled"
    price_only = await _build(spot_nok_per_kg=80.0)
    assert price_only["margin"]["quality"] == "modelled"
    both = await _build(spot_nok_per_kg=80.0, fcr=1.35)
    assert both["margin"]["quality"] == "measured"
    assert "caller" in both["margin"]["quality_basis"]


@pytest.mark.asyncio
async def test_the_margin_leg_status_matches_the_headline_quality(stub_sources):
    """A derived margin must never read "measured" while the headline says modelled."""
    for kwargs, expected in (({}, "modelled"), ({"spot_nok_per_kg": 80.0}, "modelled"),
                             ({"spot_nok_per_kg": 80.0, "delivered_feed_nok_per_kg": 20.0}, "measured")):
        payload = await _build(**kwargs)
        margin_leg = next(leg for leg in payload["legs"] if leg["key"] == "margin")
        assert margin_leg["status"] == payload["margin"]["quality"] == expected


@pytest.mark.asyncio
async def test_stale_fred_observation_degrades_the_feed_leg_by_name(stub_sources):
    payload = await _build()
    feed = next(leg for leg in payload["legs"] if leg["key"] == "feed")
    assert feed["status"] == "modelled"
    assert feed["period"] == "2026-07"
    assert feed["meta"]["age_days"] > FEED_PRICE_MAX_AGE_DAYS
    assert feed["data_provenance"]["is_live"] is False
    assert "2026-07" in feed["data_provenance"]["fallback_reason"]
    assert "dated rather than current" in feed["data_provenance"]["fallback_reason"]
    # and the payload as a whole inherits the degradation
    assert payload["data_provenance"]["is_live"] is False
    assert "oldest dated ingredient" in payload["data_provenance"]["fallback_reason"]


@pytest.mark.asyncio
async def test_a_current_fred_observation_does_not_degrade(stub_sources):
    today = dt.date.today()
    stub_sources.setattr(
        "core.market.feed_cost_engine.feed_cost_engine.fetch_prices",
        lambda *a, **k: _async(
            _snapshot(feed_prices_as_of=today, feed_prices_as_of_latest=today)
        ),
    )
    payload = await _build()
    feed = next(leg for leg in payload["legs"] if leg["key"] == "feed")
    assert feed["data_provenance"]["is_live"] is True
    assert payload["data_provenance"]["is_live"] is True


@pytest.mark.asyncio
async def test_an_undated_basket_is_never_current(stub_sources):
    stub_sources.setattr(
        "core.market.feed_cost_engine.feed_cost_engine.fetch_prices",
        lambda *a, **k: _async(
            _snapshot(feed_prices_as_of=None, feed_prices_as_of_latest=None)
        ),
    )
    payload = await _build()
    feed = next(leg for leg in payload["legs"] if leg["key"] == "feed")
    assert feed["data_provenance"]["is_live"] is False
    assert "no observation date" in feed["data_provenance"]["fallback_reason"]


@pytest.mark.asyncio
async def test_a_defaulted_ingredient_degrades_the_feed_leg(stub_sources):
    def snapshot_with_default():
        snap = _snapshot()
        snap.using_defaults = True
        snap.default_ingredients = ["fish_oil"]
        return snap

    stub_sources.setattr(
        "core.market.feed_cost_engine.feed_cost_engine.fetch_prices",
        lambda *a, **k: _async(snapshot_with_default()),
    )
    payload = await _build()
    feed = next(leg for leg in payload["legs"] if leg["key"] == "feed")
    assert feed["data_provenance"]["is_live"] is False
    assert "fish_oil" in feed["data_provenance"]["fallback_reason"]


@pytest.mark.asyncio
async def test_a_slow_feed_history_does_not_hold_the_margin(stub_sources):
    """The month-on-month change is secondary: a slow FRED window must not block the
    bridge (found when a full suite run stalled on one)."""
    import asyncio as _asyncio

    from core.market.margin_bridge import FEED_CHANGE_TIMEOUT_S

    async def hanging_change(self=None):
        await _asyncio.sleep(FEED_CHANGE_TIMEOUT_S * 3)
        return {"change_pct": 1.0}

    stub_sources.setattr(
        "core.market.feed_cost_engine.feed_cost_engine.feed_index_change", hanging_change
    )
    payload = await _build()
    feed = next(leg for leg in payload["legs"] if leg["key"] == "feed")
    assert feed["nok_per_kg"] is not None
    assert payload["changes"]["feed_mom_nok_per_kg"] is None
    assert "did not answer within" in feed["data_provenance"]["fallback_reason"]


@pytest.mark.asyncio
async def test_a_feed_change_outage_is_disclosed_without_hiding_the_level(stub_sources):
    async def failing_change(self=None):
        return {"error": "fewer than three feed ingredients have two comparable FRED months"}

    stub_sources.setattr(
        "core.market.feed_cost_engine.feed_cost_engine.feed_index_change", failing_change
    )
    payload = await _build()
    feed = next(leg for leg in payload["legs"] if leg["key"] == "feed")
    assert feed["nok_per_kg"] is not None  # the level survives
    assert payload["changes"]["feed_mom_nok_per_kg"] is None
    assert "month-on-month change is unavailable" in feed["data_provenance"]["fallback_reason"]


@pytest.mark.asyncio
async def test_when_ssb_is_down_the_price_leg_degrades_and_the_margin_is_unpriced(stub_sources):
    async def failing_history(n=3):
        raise RuntimeError("SSB timeout")

    stub_sources.setattr(
        "core.market.ssb_price_client.ssb_price_client.get_price_history", failing_history
    )
    payload = await _build()
    price = next(leg for leg in payload["legs"] if leg["key"] == "price")
    assert price["nok_per_kg"] is None
    assert price["status"] == "unpriced"
    assert "SSB price history unavailable" in price["data_provenance"]["fallback_reason"]
    assert payload["margin"]["nok_per_kg"] is None
    assert payload["margin"]["quality"] == "unpriced"


@pytest.mark.asyncio
async def test_a_caller_price_is_labelled_and_degrades_on_purpose(stub_sources):
    payload = await _build(spot_nok_per_kg=68.0)
    price = next(leg for leg in payload["legs"] if leg["key"] == "price")
    assert price["nok_per_kg"] == 68.0
    assert price["status"] == "caller_supplied"
    assert price["data_provenance"]["is_live"] is False
    assert "caller-supplied" in price["data_provenance"]["fallback_reason"]


@pytest.mark.asyncio
async def test_price_leg_carries_the_week_and_week_on_week(stub_sources):
    payload = await _build()
    price = next(leg for leg in payload["legs"] if leg["key"] == "price")
    assert price["period"] == "2026-W41"
    assert price["meta"]["week_on_week_nok_per_kg"] == pytest.approx(72.55 - 73.80, abs=APPROX)
    assert price["meta"]["previous_week"] == "2026-W40"
    assert price["meta"]["reported_volume_tonnes"] == 27982.0
    assert payload["changes"]["price_wow_nok_per_kg"] == pytest.approx(-1.25, abs=APPROX)


@pytest.mark.asyncio
async def test_the_change_total_is_the_margin_change_not_a_sum(stub_sources):
    """Price is revenue and feed is a cost: adding them overstates the move.

    Review finding (2026-10-18): the first version summed them and reported -0.79
    where the margin actually moved -1.71 (price -1.25, feed cost +0.46).
    """
    payload = await _build()
    changes = payload["changes"]
    expected = changes["price_wow_nok_per_kg"] - changes["feed_mom_nok_per_kg"]
    assert changes["margin_change_nok_per_kg"] == pytest.approx(expected, abs=APPROX)
    assert changes["margin_change_nok_per_kg"] == pytest.approx(-1.71, abs=APPROX)
    assert changes["feed_weight_coverage_pct"] == pytest.approx(85.0)
    assert changes["feed_excluded_ingredients"] == ["other"]


@pytest.mark.asyncio
async def test_feed_change_is_converted_to_nok_per_kg_exactly(stub_sources):
    payload = await _build()
    # current = previous x (1 + p) -> delta = current x p / (1 + p)
    expected = 22.61 * 1.30 * 1.58 / 101.58
    assert payload["changes"]["feed_mom_nok_per_kg"] == pytest.approx(expected, abs=APPROX)


@pytest.mark.asyncio
async def test_the_modelled_level_is_validated_against_the_audited_anchor(stub_sources):
    payload = await _build()
    validation = payload["validation"]
    assert validation["available"] is True
    assert validation["anchor_year"] == 2024
    assert validation["official_feed_nok_per_kg_salmon"] == pytest.approx(25.67)
    assert validation["gap_pct"] == pytest.approx((29.39 - 25.67) / 25.67 * 100, abs=0.3)
    assert validation["within_tolerance"] is (
        abs(validation["gap_pct"]) <= FEED_LEVEL_VALIDATION_TOLERANCE_PCT
    )
    assert "indicative only" in validation["note"]


@pytest.mark.asyncio
async def test_the_payload_states_its_method_version_and_assumptions(stub_sources):
    payload = await _build()
    assert payload["method_version"] == MARGIN_METHOD_VERSION
    keys = {item["key"] for item in payload["assumptions"]}
    assert {"feed_composition", "fcr", "delivered_feed_price", "cost_structure", "fx"} <= keys
    for item in payload["assumptions"]:
        assert item["source"], f"{item['key']} must say where it comes from"
    assert payload["currency"] == "NOK"
    assert "per kg" in payload["unit"]
    assert payload["scope"]["biological_drag_priced"] is False
    assert "operations leg" in payload["scope"]["reason"]


@pytest.mark.asyncio
async def test_assumption_fcr_flips_to_caller_supplied(stub_sources):
    payload = await _build(fcr=1.42)
    fcr = next(item for item in payload["assumptions"] if item["key"] == "fcr")
    assert fcr["value"] == pytest.approx(1.42)
    assert fcr["source"] == "caller-supplied"


# ── 3. The farm block ────────────────────────────────────────────────────

LiceRow = namedtuple(
    "LiceRow", "avg_adult_female_lice sea_temp_c year week source fetched_at"
)
LocalityRow = namedtuple("LocalityRow", "name production_area municipality county owner_company")


class _FakeResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, results):
        self._results = list(results)
        self._index = 0

    async def execute(self, stmt):
        result = self._results[self._index]
        self._index += 1
        return result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _patch_session(monkeypatch, *, locality, lice_rows):
    import core.async_db as async_db

    monkeypatch.setattr(
        async_db,
        "get_async_session",
        lambda: _FakeSession([_FakeResult([locality]), _FakeResult(lice_rows)]),
    )


@pytest.mark.asyncio
async def test_farm_block_reports_a_measured_position_only_from_verified_rows(
    stub_sources, monkeypatch
):
    from core.market.decision_engine import _oslo_iso_week

    year, week = _oslo_iso_week(dt.datetime.now(dt.UTC))
    _patch_session(
        monkeypatch,
        locality=LocalityRow("Testfjord", 5, "Alver", "Vestland", "Test AS"),
        lice_rows=[
            LiceRow(0.42, 12.1, year, week, "barentswatch", dt.datetime.now(dt.UTC))
        ],
    )
    payload = await margin_bridge.for_farm(24035)
    farm = payload["farm"]
    assert farm["production_area"] == 5
    assert farm["lice_limit"]["limit"] == 0.5
    assert farm["lice_position"]["status"] == "measured"
    assert farm["lice_position"]["current_adult_female"] == pytest.approx(0.42)
    assert farm["lice_position"]["distance_to_limit"] == pytest.approx(0.08)
    assert farm["lice_position"]["at_or_above_limit"] is False


@pytest.mark.asyncio
async def test_farm_block_never_infers_a_position_from_demo_rows(stub_sources, monkeypatch):
    from core.market.decision_engine import _oslo_iso_week

    year, week = _oslo_iso_week(dt.datetime.now(dt.UTC))
    _patch_session(
        monkeypatch,
        locality=LocalityRow("Testfjord", 5, "Alver", "Vestland", "Test AS"),
        lice_rows=[LiceRow(0.9, 12.1, year, week, "demo_seed", dt.datetime.now(dt.UTC))],
    )
    payload = await margin_bridge.for_farm(24035)
    position = payload["farm"]["lice_position"]
    assert position["status"] == "unknown"
    assert "synthetic" in position["reason"]
    # the limit itself is a dated official fact, so it is still served
    assert payload["farm"]["lice_limit"]["established"] is True


@pytest.mark.asyncio
async def test_farm_block_marks_stale_verified_rows_unknown(stub_sources, monkeypatch):
    _patch_session(
        monkeypatch,
        locality=LocalityRow("Testfjord", 5, "Alver", "Vestland", "Test AS"),
        lice_rows=[LiceRow(0.42, 12.1, 2026, 15, "barentswatch", dt.datetime.now(dt.UTC))],
    )
    payload = await margin_bridge.for_farm(24035)
    position = payload["farm"]["lice_position"]
    assert position["status"] == "unknown"
    assert "weeks" in position["reason"]


@pytest.mark.asyncio
async def test_farm_block_failure_does_not_sink_the_bridge(stub_sources, monkeypatch):
    import core.async_db as async_db

    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr(async_db, "get_async_session", broken)
    payload = await margin_bridge.for_farm(24035)
    assert payload["farm"]["error"].startswith("farm position unavailable")
    assert payload["margin"]["nok_per_kg"] is not None


# ── 4. The feed engine's month-on-month change ───────────────────────────


def _history(series: dict[str, list[tuple[str, float]]]) -> dict:
    return {
        "ingredients": {
            name: {"data": [{"date": date, "price_usd_tonne": price} for date, price in rows]}
            for name, rows in series.items()
        }
    }


@pytest.mark.asyncio
async def test_feed_index_change_weights_like_the_basket_and_names_gaps(monkeypatch):
    from core.market.feed_cost_engine import FeedCostEngine

    engine = FeedCostEngine()
    series = {
        "soy": [("2026-06", 400.0), ("2026-07", 440.0)],
        "wheat": [("2026-06", 200.0), ("2026-07", 220.0)],
        "fishmeal": [("2026-06", 2000.0), ("2026-07", 2400.0)],
        # fish oil and rapeseed have only one point: excluded, named
        "fish_oil": [("2026-07", 1590.0)],
    }

    async def fake_history(years=1):
        return _history(series)

    monkeypatch.setattr(engine, "fetch_historical_prices", fake_history)
    change = await engine.feed_index_change()
    # Exact weighted move, not merely "positive": an unweighted mean or the wrong
    # two points would still be positive (review finding 11).
    expected = (440 * 0.30 + 220 * 0.12 + 2400 * 0.15) / (400 * 0.30 + 200 * 0.12 + 2000 * 0.15)
    assert change["change_pct"] == pytest.approx((expected - 1) * 100, abs=0.02)
    assert set(change["by_ingredient"]) == {"soy", "wheat", "fishmeal"}
    assert "fish_oil" in change["excluded"]
    assert change["months"] == ["2026-07"]
    assert change["weight_coverage_pct"] == pytest.approx(57.0)
    assert "excludes FX" in change["note"]


@pytest.mark.asyncio
async def test_feed_index_change_refuses_to_report_zero_on_thin_data(monkeypatch):
    from core.market.feed_cost_engine import FeedCostEngine

    engine = FeedCostEngine()

    async def thin_history(years=1):
        return _history({"soy": [("2026-06", 400.0), ("2026-07", 440.0)]})

    monkeypatch.setattr(engine, "fetch_historical_prices", thin_history)
    change = await engine.feed_index_change()
    assert "change_pct" not in change
    assert "fewer than three feed ingredients" in change["error"]


@pytest.mark.asyncio
async def test_feed_index_change_reports_a_history_outage(monkeypatch):
    from core.market.feed_cost_engine import FeedCostEngine

    engine = FeedCostEngine()

    async def failing(years=1):
        raise RuntimeError("FRED down")

    monkeypatch.setattr(engine, "fetch_historical_prices", failing)
    change = await engine.feed_index_change()
    assert "FRED down" in change["error"]
    assert "change_pct" not in change


# ── 5. The feed cost snapshot's own provenance contract ──────────────────


def _priced_snapshot(**overrides) -> FeedCostSnapshot:
    fields = {
        "feed_cost_nok_per_kg": 12.15,
        "feed_cost_nok_per_kg_salmon": 29.39,
        "production_cost_nok_per_kg_salmon": 74.02,
        "feed_prices_as_of": dt.date(2026, 7, 1),
        "feed_prices_as_of_latest": dt.date(2026, 7, 1),
    }
    fields.update(overrides)
    return FeedCostSnapshot(**fields)


def test_price_provenance_degrades_on_a_usd_fallback():
    """The whole NOK base is converted at USD/NOK; a constant must not read live."""
    snapshot = _priced_snapshot(usd_nok_is_fallback=True)
    provenance = snapshot.price_provenance()
    assert provenance["is_live"] is False
    assert "USD/NOK" in provenance["fallback_reason"]
    assert "constant" in provenance["fallback_reason"]


def test_price_provenance_degrades_on_an_undated_live_ingredient():
    snapshot = _priced_snapshot(undated_live_ingredients=["fish_oil"])
    provenance = snapshot.price_provenance()
    assert provenance["is_live"] is False
    assert "fish_oil" in provenance["fallback_reason"]


def test_price_provenance_names_the_oldest_dated_ingredient():
    """`feed_prices_as_of` is the OLDEST leg of the basket, not the newest."""
    snapshot = _priced_snapshot(
        feed_prices_as_of=dt.date(2026, 5, 1),
        feed_prices_as_of_latest=dt.date(2026, 7, 1),
    )
    provenance = snapshot.price_provenance()
    assert provenance["is_live"] is False
    assert "oldest dated ingredient" in provenance["fallback_reason"]
    assert "2026-05-01" in provenance["fallback_reason"]
    assert "2026-07-01" in provenance["fallback_reason"]


def test_price_provenance_is_live_on_a_current_dated_basket():
    today = dt.date.today()
    provenance = _priced_snapshot(
        feed_prices_as_of=today, feed_prices_as_of_latest=today
    ).price_provenance()
    assert provenance["is_live"] is True
    assert provenance["freshness"].startswith(today.isoformat())


# ── 6. The decision card's price leg ─────────────────────────────────────


@pytest.mark.asyncio
async def test_decision_salmon_value_uses_the_live_week(monkeypatch):
    from core.market.decision_engine import (
        SALMON_VALUE_LIVE_SOURCE,
        DecisionEngine,
        _oslo_iso_week,
    )

    year, week = _oslo_iso_week(dt.datetime.now(dt.UTC))
    rows = [
        {"week": f"W{week - 1:02d}", "year": year, "price_nok": 73.80},
        {"week": f"W{week:02d}", "year": year, "price_nok": 72.55},
    ]

    async def fake_history(n=2):
        return rows

    monkeypatch.setattr(
        "core.market.ssb_price_client.ssb_price_client.get_price_history", fake_history
    )
    value, source, is_live = await DecisionEngine()._salmon_value()
    assert value == pytest.approx(72.55)
    assert is_live is True
    assert SALMON_VALUE_LIVE_SOURCE in source
    assert f"{year}-W{week:02d}" in source


@pytest.mark.asyncio
async def test_decision_salmon_value_marks_a_stale_week(monkeypatch):
    from core.market.decision_engine import DecisionEngine

    async def stale_history(n=2):
        return [{"week": "W05", "year": 2026, "price_nok": 101.0}]

    monkeypatch.setattr(
        "core.market.ssb_price_client.ssb_price_client.get_price_history", stale_history
    )
    value, source, is_live = await DecisionEngine()._salmon_value()
    assert value == pytest.approx(101.0)
    assert is_live is False
    assert "stale" in source


@pytest.mark.asyncio
async def test_decision_salmon_value_falls_back_to_the_constant(monkeypatch):
    from core.market.decision_engine import (
        SALMON_VALUE_FALLBACK_SOURCE,
        SALMON_VALUE_NOK_PER_KG,
        DecisionEngine,
    )

    async def failing(n=2):
        raise RuntimeError("SSB down")

    monkeypatch.setattr(
        "core.market.ssb_price_client.ssb_price_client.get_price_history", failing
    )
    value, source, is_live = await DecisionEngine()._salmon_value()
    assert value == pytest.approx(SALMON_VALUE_NOK_PER_KG)
    assert source == SALMON_VALUE_FALLBACK_SOURCE
    assert is_live is False


def test_degrade_provenance_keeps_the_earlier_reason():
    from core.market.decision_engine import DecisionEngine

    base = DataProvenance.degraded("lice rows", reason="lineage: demo rows", confidence=0.4).to_dict()
    merged = DecisionEngine._degrade_provenance(base, "biomass valued at the constant")
    assert merged["is_live"] is False
    assert "lineage: demo rows" in merged["fallback_reason"]
    assert "biomass valued at the constant" in merged["fallback_reason"]
    assert merged["confidence"] <= 0.4
    live = DataProvenance.live("lice rows", confidence=0.9).to_dict()
    assert DecisionEngine._degrade_provenance(live, "constant")["is_live"] is False


# ── 7. Route wiring and the public contract ──────────────────────────────

@pytest.mark.asyncio
async def test_route_serves_the_bridge_and_reports_provenance(stub_sources):
    from fastapi.testclient import TestClient

    from core.api import app

    client = TestClient(app)
    response = client.get("/api/margin/bridge", params={"annual_tonnes": 1000})
    assert response.status_code == 200
    body = response.json()
    assert body["method_version"] == MARGIN_METHOD_VERSION
    assert body["data_provenance"]["source"]
    assert "schema_version" in body["data_provenance"]


@pytest.mark.asyncio
async def test_route_rejects_an_impossible_fcr(stub_sources):
    from fastapi.testclient import TestClient

    from core.api import app

    client = TestClient(app)
    assert client.get("/api/margin/bridge", params={"fcr": 0}).status_code == 422


def test_route_is_in_the_frozen_contract():
    import json
    from pathlib import Path

    frozen = json.loads(Path("docs/openapi.frozen.json").read_text(encoding="utf-8"))
    assert "/api/margin/bridge" in frozen["paths"]
    assert "/api/margin/bridge/{locality_no}" in frozen["paths"]


def test_provenance_helper_widens_a_date_to_a_timestamp():
    """A bare date must not reach DataProvenance.freshness (it raises on .tzinfo)."""
    from core.market.margin_bridge import _as_datetime

    assert _as_datetime(dt.date(2026, 7, 1)) == dt.datetime(2026, 7, 1, tzinfo=dt.UTC)
    assert _as_datetime("2026-07-01") == dt.datetime(2026, 7, 1, tzinfo=dt.UTC)
    assert _as_datetime(None) is None
    assert DataProvenance.live("x", observed_at=_as_datetime(dt.date(2026, 7, 1))).to_dict()[
        "freshness"
    ].startswith("2026-07-01")


def _async(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner()
