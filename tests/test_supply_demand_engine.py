"""
Supply-Demand Engine Tests (R7)
================================
Covers the pure forecast/backtest math on synthetic series (fully offline)
plus the live composition with patched sources (no network, no DB).
Run with: pytest tests/test_supply_demand_engine.py -q
"""
from __future__ import annotations

import asyncio
import datetime as dt
import math

import pytest

from core.market import supply_demand_engine as sde
from core.market.ssb_price_client import SSBPriceData, SalmonPriceWeek


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _synthetic_prices(n_weeks: int = 180, start: dt.date = dt.date(2023, 1, 2)) -> list:
    """Seasonal + mild deterministic wiggle weekly series (real ISO weeks)."""
    out = []
    for i in range(n_weeks):
        d = start + dt.timedelta(weeks=i)
        y, w, _ = d.isocalendar()
        base = 80 + 8 * math.sin((w / 52) * 2 * math.pi)
        out.append(
            SalmonPriceWeek(
                year=y, week=w, price_nok_kg=base + (i % 5) * 0.3, volume_tonnes=30_000
            )
        )
    return out


# ---------------------------------------------------------------------------
# Pure walk-forward math
# ---------------------------------------------------------------------------
class TestWalkForward:
    def test_backtest_structure(self):
        prices = _synthetic_prices(180)
        art = sde.run_walk_forward(prices, min_train_weeks=52, report_horizons=(2, 4, 8))
        assert set(art["mape"]) == {"2", "4", "8"}
        assert all(v > 0 for v in art["mape"].values())
        assert all(n > 0 for n in art["mape_n_by_horizon"].values())
        assert art["components_not_backtested"] == sde.COMPONENTS_HEURISTIC
        assert "coverage_80_band_walk_forward" in art
        assert art["n_origins"] == len(prices) - 52

    def test_insufficient_history_raises(self):
        with pytest.raises(ValueError):
            sde.run_walk_forward(_synthetic_prices(60), min_train_weeks=104)

    def test_wf_quantiles_ordered(self):
        q = sde.walk_forward_residual_quantiles(
            _synthetic_prices(180), horizons=(2, 4, 8), min_train_weeks=52
        )
        assert set(q) == {2, 4, 8}
        for h, vals in q.items():
            assert vals["p10"] <= vals["p25"] <= vals["p75"] <= vals["p90"], h
            assert vals["n"] >= 20

    def test_wf_quantiles_empty_when_short(self):
        assert sde.walk_forward_residual_quantiles(_synthetic_prices(40)) == {}


# ---------------------------------------------------------------------------
# Backtest artifact loader
# ---------------------------------------------------------------------------
class TestArtifactLoader:
    def test_missing_artifact_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sde, "BACKTEST_ARTIFACT", tmp_path / "nope.json")
        assert sde.load_backtest_artifact() is None

    def test_valid_artifact_roundtrip(self, tmp_path, monkeypatch):
        p = tmp_path / "bt.json"
        p.write_text('{"mape": {"2": 9.1, "20": 20.9}, "method": "wf"}')
        monkeypatch.setattr(sde, "BACKTEST_ARTIFACT", p)
        data = sde.load_backtest_artifact()
        assert data is not None
        assert data["mape"] == {"2": 9.1, "20": 20.9}

    def test_invalid_artifact_returns_none(self, tmp_path, monkeypatch):
        p = tmp_path / "bt.json"
        p.write_text('{"mape": {}}')
        monkeypatch.setattr(sde, "BACKTEST_ARTIFACT", p)
        assert sde.load_backtest_artifact() is None


# ---------------------------------------------------------------------------
# Live composition (patched sources: no network, no DB)
# ---------------------------------------------------------------------------

def _patch_good_sources(monkeypatch, prices: list) -> None:
    async def fake_bulk(start_year: int = 2020) -> SSBPriceData:
        return SSBPriceData(prices=prices, n_weeks=len(prices))

    async def fake_biomass() -> dict:
        return {"current_biomass_tonnes": 24796.2, "utilization_pct": 2.6, "national_mab": 947943}

    async def fake_global() -> dict:
        return {
            "balance": "tight",
            "supply_deficit_pct": 5.8,
            "norway_premium_pct": 7.3,
            "effective_production_tonnes": 2_900_000,
        }

    async def fake_lice() -> dict:
        return {
            "avg_adult_female_lice": 0.09,
            "lice_pressure": 0.09,
            "delay_adjustment_pct": -0.18,
        }

    async def fake_demand(prices_arg) -> dict:
        return {
            "china_signal_score": 0.2,
            "china_signal_label": "Growing Demand",
            "china_yoy_growth_pct": 12.0,
            "export_volume_trend_pct": 3.4,
        }

    monkeypatch.setattr(sde.ssb_price_client, "fetch_bulk_history", fake_bulk)
    monkeypatch.setattr(sde.SupplyDemandEngine, "_biomass_context", staticmethod(fake_biomass))
    monkeypatch.setattr(sde.SupplyDemandEngine, "_global_context", staticmethod(fake_global))
    monkeypatch.setattr(sde.SupplyDemandEngine, "_lice_pressure", staticmethod(fake_lice))
    monkeypatch.setattr(sde.SupplyDemandEngine, "_demand_context", staticmethod(fake_demand))


class TestEngineComposition:
    def test_compute_shape_and_forecast(self, monkeypatch):
        _patch_good_sources(monkeypatch, _synthetic_prices(180))
        engine = sde.SupplyDemandEngine()
        r = run_async(engine.compute())

        assert r["integration"]["fallbacks"] == []
        assert len(r["integration"]["sources"]) == 6
        assert r["supply_breakdown"]["lice_delay_adjustment_pct"] == -0.18
        assert r["demand_breakdown"]["china_signal_label"] == "Growing Demand"

        pf = r["price_forecast"]
        assert pf is not None
        assert pf["bands_source"] == "walk_forward_residuals"
        assert len(pf["weekly"]) == 19
        assert pf["weekly"][0]["horizon_weeks"] == 2
        assert pf["weekly"][-1]["horizon_weeks"] == 20
        for pt in pf["weekly"]:
            assert pt["p10"] <= pt["p25"] <= pt["p75"] <= pt["p90"]
            assert pt["p10"] <= pt["mid_nok_kg"] <= pt["p90"]
            assert pt["mid_nok_kg"] > 0
        # provenance is live when nothing fell back
        assert r["data_provenance"]["is_live"] is True

    def test_forecast_reference_is_latest_published_week(self, monkeypatch):
        # H2 regression guard: horizons are measured from the newest published
        # SSB week (the calibration reference), not from today's week.
        prices = _synthetic_prices(180)
        _patch_good_sources(monkeypatch, prices)
        r = run_async(sde.SupplyDemandEngine().compute())
        pf = r["price_forecast"]
        last = max(prices, key=lambda p: (p.year, p.week))
        first = pf["weekly"][0]
        assert (first["year"], first["iso_week"]) == sde._target_week(last.year, last.week, 2)
        assert pf["spot_week"] == f"{last.year}W{last.week:02d}"
        assert pf["horizon_reference"]
        assert pf["spot_lag_weeks"] >= 0

    def test_deterministic_across_calls(self, monkeypatch):
        _patch_good_sources(monkeypatch, _synthetic_prices(180))
        engine = sde.SupplyDemandEngine()
        a = run_async(engine.compute())
        b = run_async(engine.compute())
        assert a["price_forecast"]["weekly"] == b["price_forecast"]["weekly"]

    def test_fallbacks_degrade_provenance_not_data(self, monkeypatch):
        _patch_good_sources(monkeypatch, _synthetic_prices(180))

        async def boom():
            raise RuntimeError("source down")

        monkeypatch.setattr(sde.SupplyDemandEngine, "_lice_pressure", staticmethod(boom))

        async def boom_demand(prices_arg):
            raise RuntimeError("source down")

        monkeypatch.setattr(sde.SupplyDemandEngine, "_demand_context", staticmethod(boom_demand))

        engine = sde.SupplyDemandEngine()
        r = run_async(engine.compute())

        assert any(f.startswith("lice pressure") for f in r["integration"]["fallbacks"])
        assert any(f.startswith("china demand") for f in r["integration"]["fallbacks"])
        assert r["data_provenance"]["is_live"] is False
        assert r["data_provenance"]["fallback_reason"]
        # Forecast still present (SSB history fine); lice tilt defaults to 0.
        assert r["price_forecast"] is not None
        assert r["price_forecast"]["lice_tilt_pct"] == 0.0

