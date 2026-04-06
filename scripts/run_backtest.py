"""
Standalone backtest runner — generates sample results and prints report.

Usage: python scripts/run_backtest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest.engine import BacktestEngine


def main() -> None:
    engine = BacktestEngine(initial_capital=1_000_000, position_size_pct=0.05)

    for ticker in ["MOWI", "SALM", "LSG"]:
        print(f"\n{'='*60}")
        print(f"  BACKTEST: {ticker} (2018-2025, synthetic data)")
        print(f"{'='*60}")

        data = engine.generate_sample_lice_data(years=(2018, 2025), n_localities=50)
        result = engine.run(data, ticker=ticker)
        mc = engine.monte_carlo(result, n_simulations=10_000)

        print(f"  Period:            {result.period}")
        print(f"  Total Signals:     {result.total_signals}")
        print(f"  Winning Trades:    {result.winning_trades}")
        print(f"  Losing Trades:     {result.losing_trades}")
        print(f"  Win Rate:          {result.win_rate:.1f}%")
        print(f"  Total P&L:         NOK {result.total_pnl:,.0f}")
        print(f"  Sharpe Ratio:      {result.sharpe_ratio:.3f}")
        print(f"  Max Drawdown:      {result.max_drawdown:.1f}%")
        print(f"  Avg Return/Trade:  {result.avg_return_per_trade:.2f}%")
        print()
        print(f"  Monte Carlo ({mc.n_simulations} sims):")
        print(f"    Mean Return:     {mc.mean_return:.1f}%")
        print(f"    Median Return:   {mc.median_return:.1f}%")
        print(f"    Std Dev:         {mc.std_return:.1f}%")
        print(f"    5th Percentile:  {mc.percentile_5:.1f}%")
        print(f"    95th Percentile: {mc.percentile_95:.1f}%")
        print(f"    P(Profitable):   {mc.prob_profitable:.0f}%")

        if result.trades:
            print(f"\n  Sample Trades (first 5):")
            for t in result.trades[:5]:
                print(
                    f"    {t['year']} W{int(t['entry_week']):02d}-W{int(t['exit_week']):02d} "
                    f"{t['direction']} entry={t['entry_price']:.1f} "
                    f"exit={t['exit_price']:.1f} P&L={t['pnl']:+,.0f} "
                    f"({t['pnl_pct']:+.1f}%)"
                )


if __name__ == "__main__":
    main()
