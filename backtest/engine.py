"""
Backtesting Engine
==================
Replays historical lice data (2012–present) against the signal-generation
logic, simulates trades, and computes performance metrics.
Includes Monte Carlo simulation for robustness testing.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import structlog

log = structlog.get_logger(__name__)

# ── Thresholds (same as live agents) ─────────────────────────────────
LICE_THRESHOLD = 0.5
SIGNAL_THRESHOLD = 0.35
HARVEST_REDUCTION_FACTOR = 0.15
PRICE_IMPACT_PER_PCT = -0.8


@dataclass
class BacktestResult:
    ticker: str
    period: str
    total_signals: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    avg_return_per_trade: float = 0.0
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)


@dataclass
class MonteCarloResult:
    n_simulations: int
    mean_return: float
    median_return: float
    std_return: float
    percentile_5: float
    percentile_95: float
    prob_profitable: float
    distribution: list[float] = field(default_factory=list)


class BacktestEngine:
    """
    Runs historical backtests using lice data and simulated price responses.
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        position_size_pct: float = 0.05,  # 5% of capital per trade
    ) -> None:
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct

    def run(
        self,
        lice_data: pd.DataFrame,
        price_data: pd.DataFrame | None = None,
        ticker: str = "MOWI",
    ) -> BacktestResult:
        """
        Run a backtest.

        lice_data columns: year, week, avg_adult_female_lice, locality_no
        price_data columns: date, close (optional; synthesized if missing)
        """
        log.info("backtest.start", ticker=ticker, rows=len(lice_data))

        if lice_data.empty:
            return BacktestResult(ticker=ticker, period="N/A", equity_curve=[self.initial_capital])

        # Aggregate lice data by week
        weekly = (
            lice_data.groupby(["year", "week"])
            .agg(
                avg_lice=("avg_adult_female_lice", "mean"),
                max_lice=("avg_adult_female_lice", "max"),
                n_above=("avg_adult_female_lice", lambda x: (x > LICE_THRESHOLD).sum()),
                n_total=("avg_adult_female_lice", "count"),
            )
            .reset_index()
        )
        weekly["pct_above"] = weekly["n_above"] / weekly["n_total"]

        # Compute composite score
        weekly["severity"] = (weekly["avg_lice"] / 1.0).clip(0, 1)
        weekly["breadth"] = weekly["pct_above"]
        weekly["trend"] = (weekly["max_lice"] / 2.0).clip(0, 1)
        weekly["composite"] = (
            0.4 * weekly["severity"] + 0.3 * weekly["breadth"] + 0.3 * weekly["trend"]
        )

        # Generate signals
        capital = self.initial_capital
        equity_curve = [capital]
        trades: list[dict] = []
        in_trade = False
        entry_price = 0.0
        entry_week = 0
        direction = ""

        # Synthesize prices if not provided
        if price_data is None:
            base_price = 200.0  # NOK reference
            weekly["price"] = base_price + np.random.normal(0, 5, len(weekly)).cumsum()
            weekly["price"] = weekly["price"].clip(50, 500)
        else:
            weekly["price"] = price_data["close"].values[: len(weekly)]

        prev_composite = 0.0
        for row in weekly.itertuples():
            composite = row.composite

            if not in_trade and composite >= SIGNAL_THRESHOLD and composite >= prev_composite:
                # Enter SHORT
                direction = "SHORT"
                entry_price = row.price
                entry_week = row.week
                in_trade = True

            elif in_trade and (composite < 0.15 or composite < prev_composite * 0.5):
                # Exit trade
                exit_price = row.price
                if direction == "SHORT":
                    pnl_pct = (entry_price - exit_price) / entry_price
                else:
                    pnl_pct = (exit_price - entry_price) / entry_price

                trade_size = capital * self.position_size_pct
                pnl = trade_size * pnl_pct
                capital += pnl

                trades.append({
                    "year": int(row.year),
                    "entry_week": entry_week,
                    "exit_week": int(row.week),
                    "direction": direction,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct * 100, 2),
                })

                in_trade = False

            equity_curve.append(capital)
            prev_composite = composite

        # Metrics
        winning = [t for t in trades if t["pnl"] > 0]
        losing = [t for t in trades if t["pnl"] <= 0]

        returns = [t["pnl_pct"] / 100 for t in trades] if trades else [0]
        sharpe = (
            np.mean(returns) / np.std(returns) * np.sqrt(52)
            if np.std(returns) > 0
            else 0.0
        )

        # Max drawdown
        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            peak = max(peak, val)
            dd = (peak - val) / peak
            max_dd = max(max_dd, dd)

        period = f"{int(lice_data['year'].min())}-{int(lice_data['year'].max())}"

        result = BacktestResult(
            ticker=ticker,
            period=period,
            total_signals=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl=round(capital - self.initial_capital, 2),
            max_drawdown=round(max_dd * 100, 2),
            sharpe_ratio=round(float(sharpe), 3),
            win_rate=round(len(winning) / len(trades) * 100 if trades else 0, 1),
            avg_return_per_trade=round(np.mean(returns) * 100 if returns else 0, 2),
            trades=trades,
            equity_curve=equity_curve,
        )

        log.info(
            "backtest.done",
            ticker=ticker,
            trades=len(trades),
            pnl=result.total_pnl,
            sharpe=result.sharpe_ratio,
        )
        return result

    def monte_carlo(
        self,
        backtest_result: BacktestResult,
        n_simulations: int = 10_000,
    ) -> MonteCarloResult:
        """
        Monte Carlo simulation: resample trade returns with replacement
        to estimate distribution of outcomes.
        """
        if not backtest_result.trades:
            return MonteCarloResult(
                n_simulations=0,
                mean_return=0, median_return=0, std_return=0,
                percentile_5=0, percentile_95=0, prob_profitable=0,
            )

        returns = np.array([t["pnl_pct"] / 100 for t in backtest_result.trades])
        n_trades = len(returns)

        sim_results = []
        for _ in range(n_simulations):
            sampled = np.random.choice(returns, size=n_trades, replace=True)
            cumulative = np.prod(1 + sampled) - 1
            sim_results.append(cumulative * 100)  # as percentage

        arr = np.array(sim_results)

        result = MonteCarloResult(
            n_simulations=n_simulations,
            mean_return=round(float(np.mean(arr)), 2),
            median_return=round(float(np.median(arr)), 2),
            std_return=round(float(np.std(arr)), 2),
            percentile_5=round(float(np.percentile(arr, 5)), 2),
            percentile_95=round(float(np.percentile(arr, 95)), 2),
            prob_profitable=round(float(np.mean(arr > 0) * 100), 1),
            distribution=sim_results[:500],  # keep first 500 for plotting
        )

        log.info(
            "backtest.monte_carlo",
            mean=result.mean_return,
            prob_profitable=result.prob_profitable,
        )
        return result

    @staticmethod
    def generate_sample_lice_data(
        years: tuple[int, int] = (2018, 2025),
        n_localities: int = 50,
    ) -> pd.DataFrame:
        """Generate synthetic lice data for backtesting demo."""
        np.random.seed(42)
        records = []
        for year in range(years[0], years[1] + 1):
            for week in range(1, 53):
                for loc in range(1, n_localities + 1):
                    # Seasonal pattern: lice higher in summer (weeks 20-40)
                    seasonal = 0.3 * np.sin(2 * np.pi * (week - 10) / 52)
                    base = 0.2 + seasonal + np.random.exponential(0.15)
                    # Occasional outbreaks
                    if np.random.random() < 0.05:
                        base += np.random.uniform(0.5, 2.0)

                    records.append({
                        "year": year,
                        "week": week,
                        "locality_no": 10000 + loc,
                        "avg_adult_female_lice": max(0, base),
                    })

        return pd.DataFrame(records)
