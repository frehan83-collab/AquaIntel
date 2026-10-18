"""WS-37 — US duty is assessed on the customs value, not the producer's cost.

The competitiveness engine computed `tariff_cost = production_cost * rate`. US duty is
assessed on the **transaction value** of the imported good — the price the importer pays
— so charging the rate to cost understates (or, when a producer sells below its modelled
cost, overstates) the duty, and a trade-compliance reader spots it immediately.

The fix charges the rate to the best available declared value and labels the basis on
every row: the live SSB export price for Norway, production cost elsewhere with a note
saying the true duty is higher by the exporter's margin.
"""
from __future__ import annotations

import pytest

from core.market.competitiveness_engine import CompetitivenessEngine


def _engine_with_norway(monkeypatch, *, spot_usd: float, ssb_nok: float | None):
    """A payload with one Norway row, deterministic FX and cost."""
    engine = CompetitivenessEngine()

    async def fake_fx():
        engine._fx_observations = {"NOK": "2026-10-16"}
        return {"NOK": 1 / 9.44, "USD": 1.0, "EUR": 1 / 10.62, "GBP": 1 / 12.59,
                "DKK": 0.1505, "ISK": 0.00826, "CAD": 0.7062, "CLP": 0.00105}

    async def fake_norway_cost():
        engine._norway_cost_is_fallback = False
        return 74.23  # NOK/kg, the live modelled cost on 2026-10-18

    async def fake_us_spot():
        engine._us_spot_is_fallback = False
        return spot_usd

    class _SSB:
        async def get_current_spot(self):
            if ssb_nok is None:
                raise RuntimeError("SSB down")
            return ssb_nok

    monkeypatch.setattr(engine, "_fetch_fx_rates", fake_fx)
    monkeypatch.setattr(engine, "_get_norway_cost_nok", fake_norway_cost)
    monkeypatch.setattr(engine, "_get_us_spot", fake_us_spot)
    monkeypatch.setattr(
        "core.market.ssb_price_client.ssb_price_client", _SSB(), raising=False
    )
    return engine


async def _payload(engine) -> dict:
    return await engine.compute_index()


def _norway(payload: dict) -> dict:
    return next(o for o in payload["origins"] if o["country"] == "Norway")


@pytest.mark.asyncio
async def test_the_duty_is_charged_on_the_export_price_when_one_exists(monkeypatch):
    engine = _engine_with_norway(monkeypatch, spot_usd=8.0, ssb_nok=72.55)
    payload = await _payload(engine)
    norway = _norway(payload)

    assert norway["tariff_base"] == "export_price"
    assert norway["export_price_usd"] == pytest.approx(72.55 / 9.44, abs=0.02)
    # 12.5 % of the export price, not of the production cost.
    assert norway["tariff_cost_usd"] == pytest.approx(
        norway["export_price_usd"] * 0.125, abs=0.01
    )
    assert norway["tariff_at_export_price_usd"] == pytest.approx(
        norway["tariff_cost_usd"], abs=0.01
    )
    assert "transaction value" in norway["duty_base_note"]
    assert "production cost" in norway["duty_base_note"]


@pytest.mark.asyncio
async def test_a_price_below_cost_is_reported_honestly(monkeypatch):
    """With the export price under the modelled cost, the cost-base duty is the higher one."""
    engine = _engine_with_norway(monkeypatch, spot_usd=8.0, ssb_nok=60.0)
    payload = await _payload(engine)
    norway = _norway(payload)
    assert norway["export_price_usd"] < norway["production_cost_usd"]
    assert "below cost" in norway["duty_base_note"]
    assert "higher" in norway["duty_base_note"]


@pytest.mark.asyncio
async def test_without_a_price_the_cost_base_is_used_and_named(monkeypatch):
    engine = _engine_with_norway(monkeypatch, spot_usd=8.0, ssb_nok=None)
    payload = await _payload(engine)
    norway = _norway(payload)
    assert norway["tariff_base"] == "production_cost"
    assert norway["export_price_usd"] is None
    assert norway["tariff_cost_usd"] == pytest.approx(
        norway["production_cost_usd"] * 0.125, abs=0.01
    )
    assert "No live export price" in norway["duty_base_note"]


@pytest.mark.asyncio
async def test_every_origin_labels_its_duty_base(monkeypatch):
    engine = _engine_with_norway(monkeypatch, spot_usd=8.0, ssb_nok=72.55)
    payload = await _payload(engine)
    for origin in payload["origins"]:
        assert origin["tariff_base"] in ("export_price", "production_cost")
        if origin["tariff_pct"]:
            assert "transaction value" in origin["duty_base_note"]


@pytest.mark.asyncio
async def test_the_snapshot_discloses_the_basis(monkeypatch):
    engine = _engine_with_norway(monkeypatch, spot_usd=8.0, ssb_nok=72.55)
    payload = await _payload(engine)
    assert "transaction value" in payload["tariff_basis"]
    norway = _norway(payload)
    assert norway["tariff_at_export_price_usd"] is not None
    # A no-tariff origin carries no note rather than a misleading one.
    canada = next(o for o in payload["origins"] if o["country"] == "Canada")
    assert canada["tariff_pct"] == 0.0
    assert canada["duty_base_note"] == ""


def test_the_old_cost_only_formula_is_gone():
    import inspect

    from core.market import competitiveness_engine

    source = inspect.getsource(competitiveness_engine)
    assert "tariff_cost = prod_cost_usd * tariff_pct" not in source
    assert "duty_base_usd" in source
