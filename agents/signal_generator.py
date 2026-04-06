"""
Signal Generator Agent
======================
Converts ImpactScores into actionable trading signals with:
  - Direction (SHORT when lice crisis, LONG when recovery)
  - Price targets and stop-losses
  - Confidence/strength score
  - Written rationale

Signals are stored in the DB and surfaced on the dashboard for user consent.
"""
from __future__ import annotations

import datetime as dt

from agents.base import BaseAgent
from agents.correlation_engine import CorrelationEngineAgent, ImpactScore
from core.models import Signal, AuditLog
from core.async_db import get_async_session

# ── Signal thresholds ────────────────────────────────────────────────
SIGNAL_THRESHOLD = 0.35     # minimum composite to generate a signal
STRONG_SIGNAL = 0.60        # composite above this = high-confidence
RECOVERY_THRESHOLD = 0.15   # below this after being above = recovery (LONG)

# ── Estimated price impact per % harvest reduction ───────────────────
PRICE_IMPACT_PER_PCT = -0.8  # NOK per share per 1% harvest reduction (simplified)


class SignalGeneratorAgent(BaseAgent):
    name = "signal_generator"
    interval_seconds = 900

    def __init__(self, correlation_agent: CorrelationEngineAgent) -> None:
        super().__init__()
        self.correlation = correlation_agent
        self._prev_scores: dict[str, float] = {}

    async def tick(self) -> None:
        self.log.info("signal.tick_start")

        for ticker, score in self.correlation.latest_scores.items():
            signal = self._evaluate(ticker, score)
            if signal:
                # Capture values before persist closes the session
                direction = signal.direction
                strength = signal.strength
                await self._persist(signal)
                self.log.info(
                    "signal.generated",
                    ticker=ticker,
                    direction=direction,
                    strength=round(strength, 3),
                )

        # Update previous scores for trend detection
        self._prev_scores = {
            t: s.composite_score
            for t, s in self.correlation.latest_scores.items()
        }

    def _evaluate(self, ticker: str, score: ImpactScore) -> Signal | None:
        prev = self._prev_scores.get(ticker, 0.0)
        composite = score.composite_score

        # ── SHORT signal: lice crisis worsening ──────────────────────
        if composite >= SIGNAL_THRESHOLD and composite >= prev:
            strength = min(composite / STRONG_SIGNAL, 1.0)
            harvest_red = score.estimated_harvest_reduction_pct

            # Rough price target (simplified model)
            est_downside_pct = harvest_red * abs(PRICE_IMPACT_PER_PCT) / 100
            rationale = (
                f"Elevated lice levels detected across {score.n_localities} "
                f"{ticker} localities. Avg adult female lice: {score.avg_lice:.2f} "
                f"(threshold: 0.5). {score.pct_above_threshold*100:.0f}% of sites "
                f"above regulatory limit. Estimated harvest reduction: "
                f"{harvest_red:.1f}%. Composite score: {composite:.3f}."
            )

            return Signal(
                ticker=ticker,
                direction="SHORT",
                strength=strength,
                lice_score=score.weighted_lice_index,
                exposure_score=composite,
                price_target=None,  # set by execution layer using market data
                stop_loss=None,
                rationale=rationale,
                status="pending",
            )

        # ── LONG signal: recovery from crisis ────────────────────────
        if prev >= SIGNAL_THRESHOLD and composite < RECOVERY_THRESHOLD:
            rationale = (
                f"Lice levels at {ticker} localities returning to normal. "
                f"Composite dropped from {prev:.3f} to {composite:.3f}. "
                f"Avg lice: {score.avg_lice:.2f}. Recovery trade opportunity."
            )
            return Signal(
                ticker=ticker,
                direction="LONG",
                strength=min((prev - composite) / 0.3, 1.0),
                lice_score=score.weighted_lice_index,
                exposure_score=composite,
                rationale=rationale,
                status="pending",
            )

        return None

    @staticmethod
    async def _persist(signal: Signal) -> None:
        async with get_async_session() as s:
            s.add(signal)
            s.add(AuditLog(
                event_type="signal_generated",
                detail=f"{signal.ticker} {signal.direction} "
                       f"strength={signal.strength:.3f}",
            ))
