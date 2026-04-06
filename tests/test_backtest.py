"""Tests for the backtesting engine."""
import pytest
from backtest.engine import BacktestEngine


@pytest.fixture
def engine():
    return BacktestEngine(initial_capital=1_000_000, position_size_pct=0.05)


@pytest.fixture
def sample_data(engine):
    return engine.generate_sample_lice_data(years=(2020, 2022), n_localities=20)


def test_generate_sample_data(engine):
    data = engine.generate_sample_lice_data(years=(2020, 2021), n_localities=10)
    assert len(data) > 0
    assert "year" in data.columns
    assert "avg_adult_female_lice" in data.columns
    assert data["year"].min() == 2020
    assert data["year"].max() == 2021


def test_backtest_runs(engine, sample_data):
    result = engine.run(sample_data, ticker="MOWI")
    assert result.ticker == "MOWI"
    assert result.total_pnl != 0 or result.total_signals == 0
    assert len(result.equity_curve) > 0


def test_monte_carlo(engine, sample_data):
    result = engine.run(sample_data, ticker="SALM")
    mc = engine.monte_carlo(result, n_simulations=100)
    assert mc.n_simulations == 100 or mc.n_simulations == 0
    assert 0 <= mc.prob_profitable <= 100


def test_backtest_no_data(engine):
    import pandas as pd
    empty = pd.DataFrame(columns=["year", "week", "locality_no", "avg_adult_female_lice"])
    result = engine.run(empty, ticker="LSG")
    assert result.total_signals == 0
