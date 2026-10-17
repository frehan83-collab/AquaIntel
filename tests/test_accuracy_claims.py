"""WS-23 (takedown): no route prints an accuracy figure the registry does not hold.

The price outlook printed "Backtested 4-week MAPE: 8.5% … 68% of actual prices fell
within the indicated band" from data/models/price_backtest.json — a backtest whose
loader let the 52 demo_seed SSB rows override the real history (docs/HANDOVER.md
trap 6, WS-23). The figure, a per-horizon "band_trust" coverage and the conformal
residuals all came from that run; the figure was copied into price_predictions on
every outlook request and re-served by /api/market/prediction-history. The ML
model comparisons and the supply-demand engine printed their own MAPE/coverage
outside the registry too. The registry (/api/accuracy) is the only source allowed
to back a public accuracy claim (AGENTS.md rule 1).

These tests plant artifacts shaped exactly like the contaminated ones, so they
prove the code ignores them — whatever happens to be on disk.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from core.api import app

# a percentage, or an accuracy keyword followed by a number
FIGURE = re.compile(r"\d+(?:\.\d+)?\s?%|\b(?:MAPE|coverage|RMSE)\b[^.\n]{0,40}\d", re.IGNORECASE)
METRIC_KEYS = {"mape", "rmse", "coverage_80", "mae", "smape"}


def _contaminated_backtest(model_version: str = "ensemble_v1_rule") -> dict:
    return {
        "model_version": model_version,
        "window": "2020W01–2026W40 (SSB 03024 weekly, stride 4w)",
        "generated_at": "2026-10-12T09:35:22+00:00",
        "mape": {"2": 6.22, "4": 8.49, "8": 12.02},
        "coverage_80": 67.8,
        "per_horizon": {"4": {"coverage_80": 75.0, "n": 88}},
        "script": "scripts/backtest_price_ml.py",
    }


def _residuals(model_version: str = "ensemble_v1_rule", **extra) -> dict:
    return {
        "model_version": model_version,
        "generated_at": "2026-10-12T09:35:22+00:00",
        "horizon_residuals": {"4": [-6.0, -3.0, -1.0, 0.0, 1.0, 2.5, 4.0, 7.0] * 5},
        "script": "scripts/backtest_price_ml.py",
        **extra,
    }


@pytest.fixture
def planted_artifacts(tmp_path, monkeypatch):
    """The contaminated price artifacts, planted where price_ml looks for them."""
    from core.market import price_ml

    (tmp_path / "price_backtest.json").write_text(json.dumps(_contaminated_backtest()))
    (tmp_path / "conformal_residuals.json").write_text(json.dumps(_residuals()))
    monkeypatch.setattr(price_ml, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(price_ml, "BACKTEST_ARTIFACT", tmp_path / "price_backtest.json")
    return tmp_path


@pytest.fixture
def prediction_store(tmp_path, monkeypatch):
    """A throwaway database for the routes that read and write price_predictions."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'predictions.db'}")
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(setup())

    @asynccontextmanager
    async def session():
        async with factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    monkeypatch.setattr("core.routers.market_routes.get_async_session", session)
    monkeypatch.setattr("core.async_db.get_async_session", session)

    def run(coro_fn):
        async def go():
            async with factory() as s:
                return await coro_fn(s)

        return asyncio.run(go())

    try:
        yield run
    finally:
        asyncio.run(engine.dispose())


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _no_figure(text: str) -> None:
    match = FIGURE.search(text or "")
    assert match is None, f"accuracy figure served: {match.group(0)!r} in {text!r}"


class TestPriceEnsembleClaims:
    def test_forecast_carries_no_unregistered_accuracy(self, planted_artifacts):
        from core.market.price_ml import PriceEnsemble

        ensemble = PriceEnsemble()
        for horizon in (2, 4, 8):
            fc = ensemble.predict(current_spot=72.55, horizon_weeks=horizon)
            assert fc.mape_backtest is None, fc.mape_backtest
            assert fc.band_trust is None, fc.band_trust
            _no_figure(fc.accuracy_statement)
            assert "/api/accuracy" in fc.accuracy_statement

    def test_contaminated_calibration_is_not_loaded(self, planted_artifacts):
        """Residuals from the same run calibrated the bands; an artifact that does
        not declare it used no demo rows is refused (the bands then say they are
        not calibrated, which is true)."""
        from core.market.price_ml import PriceEnsemble

        ensemble = PriceEnsemble()
        assert ensemble._conformal_residuals_by_h == {}
        fc = ensemble.predict(current_spot=72.55, horizon_weeks=4)
        assert "not calibrated" in fc.accuracy_statement

        # only an explicit integer zero proves it (False == 0 in Python)
        for value in (False, "0", None, 3):
            (planted_artifacts / "conformal_residuals.json").write_text(
                json.dumps(_residuals(demo_rows_used=value))
            )
            assert PriceEnsemble()._conformal_residuals_by_h == {}, value

        # an artifact that declares it used no demo rows is still accepted
        (planted_artifacts / "conformal_residuals.json").write_text(
            json.dumps(_residuals(demo_rows_used=0))
        )
        assert PriceEnsemble()._conformal_residuals_by_h, "a clean calibration must load"

    def test_tft_statement_describes_its_own_bands(self, planted_artifacts, monkeypatch):
        """The TFT tier's bands are its own quantiles: the statement must say so,
        not "not calibrated" nor "backtest residuals"."""
        from core.market import tft_predictor as tft_module
        from core.market.price_ml import PriceEnsemble

        class StubTFT:
            is_available = True

            async def predict(self, horizon_weeks):
                keys = ("lo95", "hi95", "lo80", "hi80", "lo50", "hi50",
                        "p10", "p25", "p50", "p75", "p90")
                return {"predicted_nok": 75.0, "bands": {k: 75.0 for k in keys}}

        monkeypatch.setattr(tft_module, "tft_predictor", StubTFT())

        async def from_a_route():  # the TFT tier runs inside a running loop, as in a route
            return PriceEnsemble().predict(current_spot=72.55, horizon_weeks=4)

        fc = asyncio.run(from_a_route())
        assert fc.model_version.endswith("_tft"), fc.model_version
        assert "TFT model's own quantiles" in fc.accuracy_statement
        assert fc.mape_backtest is None and fc.band_trust is None
        _no_figure(fc.accuracy_statement)


class TestRoutes:
    def test_price_outlook_serves_no_unregistered_accuracy(
        self, client, planted_artifacts, prediction_store
    ):
        body = client.get("/api/market/price-outlook?horizon=4&scenarios=200").json()
        model = body["model"]
        assert model["mape_backtest"] is None and model["band_trust"] is None, model
        _no_figure(model["accuracy_statement"])

        multi = client.get("/api/market/price-outlook/multi").json()
        for row in multi.get("horizons", []):
            assert row.get("mape") is None, row

    def test_outlook_stores_at_most_one_prediction_per_week_and_horizon(
        self, client, planted_artifacts, prediction_store
    ):
        from sqlalchemy import func, select

        from core.models import PricePrediction

        for _ in range(3):
            assert client.get("/api/market/price-outlook?horizon=4&scenarios=200").status_code == 200
        client.get("/api/market/price-outlook?horizon=6&scenarios=200")

        async def count(s):
            rows = (await s.execute(
                select(PricePrediction.horizon_weeks, func.count()).group_by(PricePrediction.horizon_weeks)
            )).all()
            return dict(rows)

        assert prediction_store(count) == {4: 1, 6: 1}

    def test_outlook_stores_nothing_on_a_fallback_spot(
        self, client, planted_artifacts, prediction_store, monkeypatch
    ):
        """With no live SSB spot the route forecasts from a 75.0 placeholder; that
        must not become the week's only stored prediction."""
        from sqlalchemy import func, select

        from core.market.ssb_price_client import ssb_price_client
        from core.models import PricePrediction

        async def no_spot():
            return 0.0

        monkeypatch.setattr(ssb_price_client, "get_current_spot", no_spot)
        assert client.get("/api/market/price-outlook?horizon=4&scenarios=200").status_code == 200

        async def count(s):
            return (await s.execute(select(func.count()).select_from(PricePrediction))).scalar()

        assert prediction_store(count) == 0

    def test_prediction_history_never_reserves_a_stored_figure(self, client, prediction_store):
        from core.models import PricePrediction

        async def seed(s):
            s.add(
                PricePrediction(
                    horizon_weeks=4, current_spot_nok=72.5, predicted_nok=74.0,
                    direction="up", confidence=0.5, model_version="ensemble_v1_rule",
                    mape_backtest=8.49, created_at=dt.datetime.now(dt.UTC),
                )
            )
            await s.commit()

        prediction_store(seed)
        rows = client.get("/api/market/prediction-history?horizon=4&days=30").json()
        assert rows, "the seeded prediction must be listed"
        assert all(row["mape_backtest"] is None for row in rows), rows

    def test_chat_forecast_answer_prints_no_figure(self, planted_artifacts, prediction_store):
        import core.api as api_module

        out = asyncio.run(api_module._rule_based_chat_response("what is the price forecast?"))
        text = json.dumps(out)
        assert "MAPE on validated backtest" not in text
        assert "8.5" not in text

    @pytest.mark.parametrize("engine", ["chronos", "timesfm", "moirai"])
    def test_model_comparisons_withhold_unregistered_metrics(self, client, monkeypatch, engine):
        """A 4-point holdout on the DB's (demo) SSB rows is not a backtest: the
        comparison may show forecasts, never a MAPE/RMSE/coverage figure."""
        module = {
            "chronos": ("core.ml.chronos_baseline", "chronos_baseline"),
            "timesfm": ("core.ml.timesfm_engine", "timesfm_engine"),
            "moirai": ("core.ml.moirai_engine", "moirai_engine"),
        }[engine]
        import importlib

        singleton = getattr(importlib.import_module(module[0]), module[1])

        async def stub_compare(series="price", horizon=4):
            return {
                "series": series, "horizon": horizon, "actual": [70.0, 71.0, 72.0, 73.0],
                "models": {
                    "candidate": {"median": [70.5, 71.5, 72.5, 73.5], "mape": 0.7, "rmse": 0.5,
                                  "coverage_80": 100.0},
                    "seasonal-naive": {"median": [69.0, 70.0, 71.0, 72.0], "mape": 1.4, "rmse": 1.0},
                },
                "fallback_members": [],
            }

        monkeypatch.setattr(singleton, "compare_models", stub_compare)
        body = client.get(f"/api/ml/{engine}/model-comparison?series=price&horizon=4").json()
        models = body.get("models") or {}
        assert models, body
        for name, entry in models.items():
            assert not METRIC_KEYS & set(entry), (name, entry)
            assert entry.get("median"), "forecasts stay visible"
        assert "/api/accuracy" in json.dumps(body["metrics_withheld"])


class TestSupplyDemandClaims:
    def test_method_note_and_payload_carry_no_unregistered_figure(self, tmp_path, monkeypatch):
        from core.market import supply_demand_engine as sde

        # the note keeps its method parameters (tilt caps); it states no accuracy figure
        # ("pipeline coverage ~-80%" is the supply balance, not a forecast accuracy)
        accuracy_wording = r"(out-of-sample coverage|band coverage|MAPE|RMSE|accuracy)[^.;]{0,60}\d"
        assert not re.search(accuracy_wording, sde.METHOD_NOTE, re.I), sde.METHOD_NOTE
        assert "/api/accuracy" in sde.METHOD_NOTE
        from core.ml import accuracy_registry

        artifact = tmp_path / "supply_demand_backtest.json"
        monkeypatch.setattr(sde, "BACKTEST_ARTIFACT", artifact)
        monkeypatch.setattr(
            accuracy_registry, "registry",
            lambda: {"artifacts": [{"artifact_id": "supply_demand_walk_forward"}]},
        )
        body = {"mape": {"4": 7.1}, "coverage_80_band_walk_forward": {"4": 81.0}}
        for unregistered in ({}, {"artifact_id": "something_else"}):
            artifact.write_text(json.dumps({**body, **unregistered}))
            assert sde.served_backtest() is None, unregistered
        artifact.write_text(json.dumps({**body, "artifact_id": "supply_demand_walk_forward"}))
        served = sde.served_backtest()
        assert served is not None and served["artifact_id"] == "supply_demand_walk_forward"
