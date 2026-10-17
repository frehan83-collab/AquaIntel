"""WS-23 (re-run half): the price backtest must measure real history, and the
served model must be compared with a horizon-matched carry-forward baseline.

The 2026-10-12 artifact let the 52 ``demo_seed`` SSB rows override the real CSV
history (database winning), so its MAPE — and the conformal calibration derived
from it — measured seeded data. ``scripts/backtest_price_ml.py`` now refuses
those rows and declares ``demo_rows_used``; ``scripts/publish_accuracy.py
--from-backtest`` refuses any artifact that measured demo rows or another model
tier, and publishes the model and its carry-forward baseline on the same window
with a Diebold-Mariano result.

These tests prove the refusals from the code, not from whatever is on disk.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    """Import ``scripts/<name>.py`` (scripts/ is not a package)."""
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_ws23_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def backtest_script():
    return _load_script("backtest_price_ml")


@pytest.fixture(scope="module")
def publish_script():
    return _load_script("publish_accuracy")


@pytest.fixture
def ssb_db(tmp_path, monkeypatch):
    """A DB holding one synthetic and two real SSB rows (years far from the CSV)."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base, SSBWeeklyPrice

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ssb.db'}")
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def seed():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as session:
            session.add_all([
                SSBWeeklyPrice(year=2099, week=5, price_nok_kg=1.0, source="demo_seed"),
                SSBWeeklyPrice(year=2099, week=6, price_nok_kg=90.0, source="ssb_03024"),
                SSBWeeklyPrice(year=2099, week=7, price_nok_kg=91.0, source=""),
            ])
            await session.commit()

    asyncio.run(seed())

    @asynccontextmanager
    async def _session():
        async with factory() as session:
            yield session

    import core.async_db as async_db

    monkeypatch.setattr(async_db, "get_async_session", _session)
    yield


class TestHistoryLoader:
    def test_refuses_synthetic_rows_and_counts_them(self, backtest_script, ssb_db):
        rows, prov = backtest_script.load_ssb_series_with_provenance(start_year=2099)
        assert [(w, p) for _, w, p in rows] == [(6, 90.0), (7, 91.0)]
        assert prov["synthetic_rows_skipped"] == 1
        assert prov["synthetic_rows_used"] == 0
        assert prov["db_rows_used"] == 2
        assert prov["db_rows_unverified"] == 1, "an unknown source is unverified, not real"
        assert prov["db_error"] is None

    def test_synthetic_week_never_enters_next_to_a_real_one(
        self, backtest_script, ssb_db, monkeypatch
    ):
        """The demo row sits between two real weeks — it must not fill the gap."""

        rows, prov = backtest_script.load_ssb_series_with_provenance(start_year=2099)
        assert prov["synthetic_rows_used"] == 0
        assert 5 not in [w for _, w, _ in rows]

    def test_db_unavailable_falls_back_to_csv_and_says_so(
        self, backtest_script, monkeypatch
    ):
        import core.async_db as async_db

        def _boom():
            raise RuntimeError("no db")

        monkeypatch.setattr(async_db, "get_async_session", _boom)
        rows, prov = backtest_script.load_ssb_series_with_provenance(start_year=2020)
        assert rows, "the CSV history must still load"
        assert "no db" in (prov["db_error"] or "")
        assert prov["db_rows_used"] == 0


class TestDieboldMariano:
    def test_identical_losses_are_not_significant(self, backtest_script):
        errs = [1.0, 2.0, 1.5, 2.5, 1.2, 1.8]
        out = backtest_script.diebold_mariano(errs, list(errs), horizon=4)
        assert out["dm_stat"] == 0.0
        assert out["p_value"] == 1.0
        assert out["better"] == "tie"

    def test_model_clearly_better(self, backtest_script):
        model = [0.5] * 40
        baseline = [4.0] * 40
        out = backtest_script.diebold_mariano(model, baseline, horizon=4)
        assert out["better"] == "model"
        assert out["dm_stat"] < 0
        assert out["p_value"] < 0.05
        assert out["n"] == 40

    def test_model_clearly_worse(self, backtest_script):
        out = backtest_script.diebold_mariano([4.0] * 40, [0.5] * 40, horizon=4)
        assert out["better"] == "baseline"
        assert out["dm_stat"] > 0
        assert out["p_value"] < 0.05

    def test_unpaired_series_is_refused(self, backtest_script):
        with pytest.raises(ValueError):
            backtest_script.diebold_mariano([1.0, 2.0], [1.0], horizon=2)

    def test_too_few_points_reports_no_statistic(self, backtest_script):
        out = backtest_script.diebold_mariano([1.0], [2.0], horizon=2)
        assert out["dm_stat"] is None and out["p_value"] is None


def _backtest_artifact(**over) -> dict:
    per_h = {
        "2": {"mape": 6.4, "coverage_80": 72.7, "n": 88, "carry_forward_mape": 6.52,
              "diebold_mariano": {"n": 88, "dm_stat": -1.0, "p_value": 0.3228,
                                  "better": "model", "mean_loss_diff": -0.1,
                                  "loss": "squared NOK/kg error", "lags": 1}},
        "4": {"mape": 9.05, "coverage_80": 71.6, "n": 88, "carry_forward_mape": 9.44,
              "diebold_mariano": {"n": 88, "dm_stat": -2.95, "p_value": 0.0031,
                                  "better": "model", "mean_loss_diff": -0.4,
                                  "loss": "squared NOK/kg error", "lags": 3}},
    }
    artifact = {
        "model_version": "ensemble_v1_rule",
        "window": "2020W01–2026W40 (SSB 03024 weekly, stride 4w)",
        "generated_at": "2026-10-17T23:20:49+00:00",
        "mape": {h: v["mape"] for h, v in per_h.items()},
        "coverage_80": 64.8,
        "per_horizon": per_h,
        "demo_rows_used": 0,
        "rows_used": 353,
        "history_provenance": {"csv_rows": 1396, "db_rows_used": 0,
                               "db_rows_unverified": 0, "synthetic_rows_skipped": 52,
                               "synthetic_rows_used": 0, "db_error": None},
        "baselines": {"carry_forward": {
            "definition": "forecast(t+h) = observed price at t (no change)",
            "mape": {h: v["carry_forward_mape"] for h, v in per_h.items()},
        }},
        "method": "walk-forward; synthetic history rows are refused",
    }
    artifact.update(over)
    return artifact


class TestPublishFromBacktest:
    def test_refuses_missing_artifact(self, publish_script, tmp_path):
        code, published = publish_script.publish_from_backtest(
            tmp_path / "absent.json", ensemble_version="ensemble_v1_rule",
        )
        assert (code, published) == (2, [])

    @pytest.mark.parametrize("declared", [None, 52, "0", True])
    def test_refuses_artifact_that_used_demo_rows(
        self, publish_script, tmp_path, declared
    ):
        artifact = _backtest_artifact()
        if declared is None:
            artifact.pop("demo_rows_used")
        else:
            artifact["demo_rows_used"] = declared
        path = tmp_path / "bt.json"
        path.write_text(json.dumps(artifact))
        written: list[dict] = []
        code, published = publish_script.publish_from_backtest(
            path, ensemble_version="ensemble_v1_rule", publish_fn=written.append,
        )
        assert (code, published, written) == (2, [], [])

    def test_refuses_artifact_for_another_tier(self, publish_script, tmp_path):
        """A backtest of a tier this deployment does not serve proves nothing."""
        path = tmp_path / "bt.json"
        path.write_text(json.dumps(_backtest_artifact(model_version="ensemble_v1_xgb")))
        written: list[dict] = []
        code, published = publish_script.publish_from_backtest(
            path, ensemble_version="ensemble_v1_rule", publish_fn=written.append,
        )
        assert (code, published, written) == (2, [], [])


    def test_publishes_model_and_baseline_on_one_window(self, publish_script, tmp_path):
        path = tmp_path / "bt.json"
        path.write_text(json.dumps(_backtest_artifact()))
        written: list[dict] = []

        def _publish(artifact):
            written.append(artifact)
            return {"path": f"artifacts/accuracy/{artifact['artifact_id']}.json",
                    "artifact_id": artifact["artifact_id"]}

        code, published = publish_script.publish_from_backtest(
            path, ensemble_version="ensemble_v1_rule", publish_fn=_publish,
        )
        assert code == 0 and len(published) == 2
        model, baseline = written
        assert model["artifact_id"] == "price_ensemble_walk_forward"
        assert baseline["artifact_id"] == "carry_forward_weekly_prices"
        # same window and evaluation points, or the comparison is meaningless
        assert model["window"] == baseline["window"]
        assert model["n_obs"] == baseline["n_obs"] == 88
        assert model["metrics"]["horizon_weeks"] == publish_script.HEADLINE_HORIZON
        assert model["metrics"]["mape_pct"] == 9.05
        assert model["metrics"]["carry_forward_mape_pct"] == 9.44
        assert model["metrics"]["diebold_mariano_p"] == 0.0031
        assert model["metrics"]["diebold_mariano_better"] == "model"
        assert baseline["metrics"]["mape_pct"] == 9.44
        assert model["fallback_used"] is True, "the rule tier is a fallback, say so"
        # the served outlook adds signals the backtest holds neutral — say so where
        # /api/accuracy surfaces it (the registry exposes `method`, not `notes`)
        assert "price-only" in model["method"] and "lice" in model["method"]
        from core.ml.accuracy_registry import validate

        for artifact in written:
            assert validate(artifact) == [], artifact["artifact_id"]

    def test_published_artifacts_are_served_by_the_registry(
        self, publish_script, tmp_path, monkeypatch
    ):
        from core.ml import accuracy_registry

        monkeypatch.setattr(accuracy_registry, "ARTIFACT_DIR", tmp_path / "acc")
        path = tmp_path / "bt.json"
        path.write_text(json.dumps(_backtest_artifact()))
        code, published = publish_script.publish_from_backtest(
            path, ensemble_version="ensemble_v1_rule",
        )
        assert code == 0 and len(published) == 2
        served = accuracy_registry.registry()
        assert served["count"] == 2 and served["invalid"] == []
        ids = {a["artifact_id"] for a in served["artifacts"]}
        assert ids == {"price_ensemble_walk_forward", "carry_forward_weekly_prices"}
