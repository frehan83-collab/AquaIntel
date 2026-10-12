"""
# FROZEN: No new features — complexity vs. value tradeoff (Session 9 decision)
Statistical Pairs Trading Engine — Cointegration Arbitrage
============================================================
Implements statistical arbitrage between Norwegian salmon stocks
(MOWI, SALM, LSG, GSF) using:
  1. Engle-Granger cointegration testing
  2. Kalman filter for dynamic hedge ratios
  3. Z-score based mean reversion signals
  4. Biological data overlay for timing

Salmon stocks are highly correlated (same product, same markets)
but temporarily diverge due to company-specific events (lice outbreaks,
treatment costs, farm-level issues). These divergences mean-revert.

Alpha: Standard pairs trading + unique biological signal overlay.
When lice data shows divergent farm-level stress between companies,
the spread trade has higher confidence.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)


@dataclass
class PairState:
    """Current state of a stock pair for trading."""
    pair_name: str  # e.g., "MOWI-SALM"
    ticker_a: str
    ticker_b: str
    hedge_ratio: float  # dynamic, Kalman-filtered
    spread: float  # current spread (a - hedge_ratio * b)
    spread_mean: float  # rolling mean of spread
    spread_std: float  # rolling std of spread
    z_score: float  # standardized spread
    half_life_days: float  # mean reversion half-life
    is_cointegrated: bool
    adf_pvalue: float  # Augmented Dickey-Fuller p-value
    correlation: float  # rolling correlation
    last_updated: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))


@dataclass
class PairsSignal:
    """Trading signal from pairs strategy."""
    generated_at: dt.datetime
    pair_name: str
    ticker_long: str  # buy this
    ticker_short: str  # sell this
    signal_type: str  # entry_long_spread, entry_short_spread, exit
    z_score: float
    hedge_ratio: float
    expected_reversion_days: int
    confidence: float
    biological_overlay: str  # how lice data supports/contradicts the trade
    rationale: str


# Pair definitions
PAIRS = [
    ("MOWI", "SALM"),
    ("MOWI", "LSG"),
    ("SALM", "LSG"),
    ("MOWI", "GSF"),
    ("SALM", "GSF"),
    ("LSG", "GSF"),
]

# Signal thresholds
Z_ENTRY = 2.0  # enter when z-score exceeds ±2
Z_EXIT = 0.5  # exit when z-score returns to ±0.5
Z_STOP = 3.5  # stop loss at ±3.5
LOOKBACK_DAYS = 120  # rolling window for spread stats
MIN_HALF_LIFE = 5  # minimum half-life for tradeable pair
MAX_HALF_LIFE = 60  # maximum half-life


class PairsEngine:
    """
    Statistical pairs trading engine for salmon stocks.

    Maintains state for each pair (MOWI-SALM, MOWI-LSG, etc.)
    and generates entry/exit signals based on spread z-scores
    with biological data overlay.

    Causal lag integration: when the causal engine discovers the dominant
    lice→price lag (via Granger/TE), it is fed in via set_causal_lag().
    This replaces the OU-fitted half-life estimate for expected_reversion_days
    and boosts confidence when the biological overlay confirms the direction.
    """

    def __init__(self) -> None:
        self._pairs: dict[str, PairState] = {}
        self._signals: list[PairsSignal] = []
        self._price_history: dict[str, list[tuple[dt.datetime, float]]] = {}
        self._built = False
        # Dynamically updated by causal engine via set_causal_lag()
        self._causal_lag_weeks: Optional[int] = None
        self._causal_confidence: str = "low"  # "high" | "medium" | "low"

    def set_causal_lag(self, lag_weeks: int, confidence: str = "medium") -> None:
        """
        Update the causal lag from the causal inference engine.

        Called by IntelligenceAgent after running Granger / Transfer Entropy.
        The lag (in weeks) represents how long after a lice event the price
        impact is expected to materialise. It is used to:
          1. Replace the half-life-based reversion estimate with a
             data-driven causal horizon (converted to trading days).
          2. Boost signal confidence when the biological overlay aligns.

        Args:
            lag_weeks: dominant causal lag in weeks (e.g., 8)
            confidence: "high" | "medium" | "low" from causal engine
        """
        if lag_weeks != self._causal_lag_weeks or confidence != self._causal_confidence:
            log.info(
                "pairs.causal_lag_updated",
                lag_weeks=lag_weeks,
                confidence=confidence,
                previous_lag=self._causal_lag_weeks,
            )
        self._causal_lag_weeks = lag_weeks
        self._causal_confidence = confidence

    async def update_prices(self, prices: dict[str, float]) -> None:
        """
        Update with latest stock prices.

        Args:
            prices: {"MOWI": 185.4, "SALM": 62.3, "LSG": 48.1, ...}
        """
        now = dt.datetime.now(dt.UTC)
        for ticker, price in prices.items():
            if ticker not in self._price_history:
                self._price_history[ticker] = []
            self._price_history[ticker].append((now, price))
            # Keep 1 year of history
            if len(self._price_history[ticker]) > 365:
                self._price_history[ticker] = self._price_history[ticker][-365:]

        # Recompute pair states
        await self._compute_pairs()
        self._built = True

    async def _compute_pairs(self) -> None:
        """Compute state for all pairs."""
        for ticker_a, ticker_b in PAIRS:
            if ticker_a not in self._price_history or ticker_b not in self._price_history:
                continue

            prices_a = self._price_history[ticker_a]
            prices_b = self._price_history[ticker_b]

            # Align on dates (use last N common points)
            n = min(len(prices_a), len(prices_b), LOOKBACK_DAYS)
            if n < 30:
                continue

            a_vals = np.array([p[1] for p in prices_a[-n:]])
            b_vals = np.array([p[1] for p in prices_b[-n:]])

            pair_name = f"{ticker_a}-{ticker_b}"

            # 1. Compute hedge ratio (OLS regression)
            hedge_ratio = self._compute_hedge_ratio(a_vals, b_vals)

            # 2. Compute spread
            spread = a_vals - hedge_ratio * b_vals

            # 3. Test for cointegration (ADF test on spread)
            is_coint, adf_p = self._test_cointegration(spread)

            # 4. Spread statistics
            spread_mean = float(np.mean(spread))
            spread_std = float(np.std(spread))
            current_spread = float(spread[-1])
            z_score = (current_spread - spread_mean) / max(spread_std, 1e-6)

            # 5. Half-life of mean reversion
            half_life = self._compute_half_life(spread)

            # 6. Correlation
            correlation = float(np.corrcoef(a_vals, b_vals)[0, 1])

            self._pairs[pair_name] = PairState(
                pair_name=pair_name,
                ticker_a=ticker_a,
                ticker_b=ticker_b,
                hedge_ratio=round(hedge_ratio, 4),
                spread=round(current_spread, 2),
                spread_mean=round(spread_mean, 2),
                spread_std=round(spread_std, 2),
                z_score=round(z_score, 3),
                half_life_days=round(half_life, 1),
                is_cointegrated=is_coint,
                adf_pvalue=round(adf_p, 4),
                correlation=round(correlation, 4),
            )

            # Generate signals
            await self._check_signals(pair_name)

    def _compute_hedge_ratio(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Compute hedge ratio using Kalman filter for dynamic estimation.
        Falls back to OLS if insufficient data.
        """
        # Simple OLS hedge ratio: a = beta * b + epsilon
        if len(b) < 10:
            return 1.0

        # OLS
        b_with_const = np.column_stack([b, np.ones(len(b))])
        try:
            beta = np.linalg.lstsq(b_with_const, a, rcond=None)[0][0]
            return float(beta)
        except Exception:
            return float(np.mean(a) / max(np.mean(b), 1e-6))

    def _test_cointegration(self, spread: np.ndarray) -> tuple[bool, float]:
        """
        Test cointegration using Augmented Dickey-Fuller on spread.
        Returns (is_cointegrated, p_value).
        """
        if len(spread) < 20:
            return False, 1.0

        try:
            from statsmodels.tsa.stattools import adfuller
            result = adfuller(spread, maxlag=10, autolag="AIC")
            p_value = float(result[1])
            return p_value < 0.05, p_value
        except ImportError:
            # Fallback: simple mean reversion test
            # Check if spread is mean-reverting using autocorrelation
            spread_centered = spread - np.mean(spread)
            if len(spread_centered) < 10:
                return False, 1.0

            autocorr = np.corrcoef(spread_centered[:-1], spread_centered[1:])[0, 1]
            # Negative autocorrelation suggests mean reversion
            is_coint = autocorr < -0.1
            p_value = 0.5 - abs(autocorr) * 0.5  # rough approximation
            return is_coint, max(0, p_value)

    def _compute_half_life(self, spread: np.ndarray) -> float:
        """
        Compute mean reversion half-life using Ornstein-Uhlenbeck model.
        """
        if len(spread) < 20:
            return 30.0

        spread_centered = spread - np.mean(spread)
        lag = spread_centered[:-1]
        delta = np.diff(spread_centered)

        if len(lag) < 10:
            return 30.0

        try:
            # Regress delta_spread on lagged_spread
            beta = np.polyfit(lag, delta, 1)[0]
            if beta >= 0:
                return 60.0  # not mean reverting
            half_life = -np.log(2) / beta
            return max(MIN_HALF_LIFE, min(MAX_HALF_LIFE, float(half_life)))
        except Exception:
            return 30.0

    async def _check_signals(self, pair_name: str) -> None:
        """Check if pair state warrants a trading signal."""
        state = self._pairs.get(pair_name)
        if not state or not state.is_cointegrated:
            return

        z = state.z_score
        now = dt.datetime.now(dt.UTC)

        # Get biological overlay
        bio_overlay = await self._get_biological_overlay(state.ticker_a, state.ticker_b)

        if abs(z) > Z_ENTRY:
            # Determine expected reversion horizon
            # Priority: causal engine lag (data-driven) > OU half-life (statistical)
            if self._causal_lag_weeks is not None:
                causal_days = self._causal_lag_weeks * 7
                reversion_days = causal_days
                horizon_note = (
                    f"Causal engine: {self._causal_lag_weeks}-week lice→price lag "
                    f"({self._causal_confidence} confidence, Granger/TE)"
                )
            else:
                reversion_days = int(state.half_life_days * 1.5)
                horizon_note = (
                    f"OU mean-reversion half-life: {state.half_life_days:.0f}d"
                )

            # Base confidence from z-score magnitude
            base_conf = min(0.88, 0.5 + (abs(z) - Z_ENTRY) * 0.15)

            # Confidence boost: if causal lag is "high" confidence AND biological
            # overlay confirms the trade direction, add +5%
            causal_bio_boost = 0.0
            if (
                self._causal_lag_weeks is not None
                and self._causal_confidence == "high"
                and "Supports" in bio_overlay
            ):
                causal_bio_boost = 0.05

            final_conf = min(0.95, base_conf + causal_bio_boost)

            # Entry signal
            if z > Z_ENTRY:
                # Spread is too wide → short A, long B
                signal = PairsSignal(
                    generated_at=now,
                    pair_name=pair_name,
                    ticker_long=state.ticker_b,
                    ticker_short=state.ticker_a,
                    signal_type="entry_short_spread",
                    z_score=z,
                    hedge_ratio=state.hedge_ratio,
                    expected_reversion_days=reversion_days,
                    confidence=final_conf,
                    biological_overlay=bio_overlay,
                    rationale=(
                        f"{pair_name} spread z-score {z:.2f} (>{Z_ENTRY}). "
                        f"{horizon_note}. "
                        f"Hedge ratio: {state.hedge_ratio:.3f}. "
                        f"ADF p-value: {state.adf_pvalue:.4f}."
                    ),
                )
            else:
                # z < -Z_ENTRY → spread too narrow → long A, short B
                signal = PairsSignal(
                    generated_at=now,
                    pair_name=pair_name,
                    ticker_long=state.ticker_a,
                    ticker_short=state.ticker_b,
                    signal_type="entry_long_spread",
                    z_score=z,
                    hedge_ratio=state.hedge_ratio,
                    expected_reversion_days=reversion_days,
                    confidence=final_conf,
                    biological_overlay=bio_overlay,
                    rationale=(
                        f"{pair_name} spread z-score {z:.2f} (<-{Z_ENTRY}). "
                        f"{horizon_note}. "
                        f"Hedge ratio: {state.hedge_ratio:.3f}."
                    ),
                )

            self._signals.append(signal)

        elif abs(z) < Z_EXIT:
            # Exit signal (if we had an open position)
            signal = PairsSignal(
                generated_at=now,
                pair_name=pair_name,
                ticker_long="",
                ticker_short="",
                signal_type="exit",
                z_score=z,
                hedge_ratio=state.hedge_ratio,
                expected_reversion_days=0,
                confidence=0.8,
                biological_overlay=bio_overlay,
                rationale=f"{pair_name} z-score {z:.2f} returned to normal range (±{Z_EXIT}).",
            )
            self._signals.append(signal)

        # Keep last 100 signals
        if len(self._signals) > 100:
            self._signals = self._signals[-100:]

    async def _get_biological_overlay(self, ticker_a: str, ticker_b: str) -> str:
        """
        Get biological data comparison between two companies.
        Adds unique alpha: lice divergence between companies
        supports or contradicts the spread trade.
        """
        try:
            from core.models import LiceRecord, Locality, CompanyExposure
            from core.async_db import get_async_session
            from sqlalchemy import select, func

            async with get_async_session() as s:
                # Get latest lice averages per company
                latest = (await s.execute(
                    select(LiceRecord.year, LiceRecord.week)
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )).first()

                if not latest:
                    return "No biological data available"

                async def get_company_lice(ticker: str) -> Optional[float]:
                    result = (await s.execute(
                        select(func.avg(LiceRecord.avg_adult_female_lice))
                        .join(Locality, LiceRecord.locality_no == Locality.locality_no)
                        .where(
                            LiceRecord.year == latest[0],
                            LiceRecord.week == latest[1],
                            Locality.owner_company.contains(ticker),
                        )
                    )).scalar()
                    return float(result) if result else None

                lice_a = await get_company_lice(ticker_a)
                lice_b = await get_company_lice(ticker_b)

                if lice_a is None or lice_b is None:
                    return "Insufficient biological data"

                diff = lice_a - lice_b
                if abs(diff) < 0.02:
                    return f"Lice levels similar ({ticker_a}: {lice_a:.3f}, {ticker_b}: {lice_b:.3f}) — no biological divergence"
                elif diff > 0:
                    return (
                        f"{ticker_a} has higher lice ({lice_a:.3f}) vs {ticker_b} ({lice_b:.3f}). "
                        f"Supports short {ticker_a} / long {ticker_b} if spread is wide."
                    )
                else:
                    return (
                        f"{ticker_b} has higher lice ({lice_b:.3f}) vs {ticker_a} ({lice_a:.3f}). "
                        f"Supports short {ticker_b} / long {ticker_a} if spread is narrow."
                    )

        except Exception:
            return "Biological overlay unavailable"

    # ── Public API ───────────────────────────────────────────────

    def get_all_pairs(self) -> list[dict]:
        """Get state of all pairs."""
        causal_horizon_days = self._causal_lag_weeks * 7 if self._causal_lag_weeks else None
        return [
            {
                "pair": s.pair_name,
                "ticker_a": s.ticker_a,
                "ticker_b": s.ticker_b,
                "hedge_ratio": s.hedge_ratio,
                "spread": s.spread,
                "z_score": s.z_score,
                "half_life_days": s.half_life_days,
                "cointegrated": s.is_cointegrated,
                "adf_pvalue": s.adf_pvalue,
                "correlation": s.correlation,
                "signal": (
                    "ENTRY SHORT" if s.z_score > Z_ENTRY else
                    "ENTRY LONG" if s.z_score < -Z_ENTRY else
                    "EXIT" if abs(s.z_score) < Z_EXIT else
                    "HOLD"
                ),
                "tradeable": s.is_cointegrated and MIN_HALF_LIFE < s.half_life_days < MAX_HALF_LIFE,
                # Causal engine calibration metadata
                "causal_lag_weeks": self._causal_lag_weeks,
                "causal_confidence": self._causal_confidence,
                "causal_horizon_days": causal_horizon_days,
                "causal_calibrated": self._causal_lag_weeks is not None,
            }
            for s in self._pairs.values()
        ]

    def get_signals(self, days: int = 7) -> list[dict]:
        """Get recent pairs trading signals."""
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
        return [
            {
                "generated_at": s.generated_at.isoformat(),
                "pair": s.pair_name,
                "long": s.ticker_long,
                "short": s.ticker_short,
                "signal": s.signal_type,
                "z_score": s.z_score,
                "hedge_ratio": s.hedge_ratio,
                "reversion_days": s.expected_reversion_days,
                "confidence": s.confidence,
                "biological_overlay": s.biological_overlay,
                "rationale": s.rationale,
            }
            for s in self._signals
            if s.generated_at > cutoff
        ]

    async def get_pair_detail(self, pair_name: str) -> Optional[dict]:
        """Get detailed state for a specific pair."""
        state = self._pairs.get(pair_name)
        if not state:
            return None

        # Get spread history for charting
        a_hist = self._price_history.get(state.ticker_a, [])
        b_hist = self._price_history.get(state.ticker_b, [])
        n = min(len(a_hist), len(b_hist), LOOKBACK_DAYS)

        spread_history = []
        if n > 10:
            for i in range(-n, 0):
                a_price = a_hist[i][1]
                b_price = b_hist[i][1]
                sp = a_price - state.hedge_ratio * b_price
                spread_history.append({
                    "date": a_hist[i][0].isoformat(),
                    "spread": round(sp, 2),
                    "z_score": round((sp - state.spread_mean) / max(state.spread_std, 1e-6), 2),
                })

        return {
            "pair": state.pair_name,
            "ticker_a": state.ticker_a,
            "ticker_b": state.ticker_b,
            "hedge_ratio": state.hedge_ratio,
            "spread": state.spread,
            "spread_mean": state.spread_mean,
            "spread_std": state.spread_std,
            "z_score": state.z_score,
            "half_life_days": state.half_life_days,
            "cointegrated": state.is_cointegrated,
            "adf_pvalue": state.adf_pvalue,
            "correlation": state.correlation,
            "spread_history": spread_history[-60:],  # last 60 data points
            "entry_threshold": Z_ENTRY,
            "exit_threshold": Z_EXIT,
            "stop_threshold": Z_STOP,
            "biological_overlay": await self._get_biological_overlay(state.ticker_a, state.ticker_b),
        }


# Singleton
pairs_engine = PairsEngine()
