"""
Market Hedger Agent
=====================
Autonomous agent that:
  1. Consumes ML price predictions (from PriceEnsemble)
  2. Fetches Fish Pool futures curve for arbitrage signals
  3. Correlates biological risk (lice forecasts) with price impact
  4. Generates hedging recommendations for salmon equities + futures
  5. Publishes to shared memory for swarm collaboration

Runs every 30 minutes during market hours.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import structlog
from sqlalchemy import select, func

from agents.base import BaseAgent
from core.legal.equity_signals import may_persist_directional
from core.models import LiceRecord, Signal, CompanyExposure
from core.async_db import get_async_session

log = structlog.get_logger(__name__)


class MarketHedgerAgent(BaseAgent):
    name = "market_hedger"
    interval_seconds = 1800  # 30 minutes

    def __init__(self) -> None:
        super().__init__()
        self.latest_forecast = None
        self.forward_curve = None
        self.hedging_signals: list[dict] = []

    async def tick(self) -> None:
        self.log.info("hedger.tick_start")

        try:
            # 1. Get ML price forecast for multiple horizons
            forecasts = await self._get_price_forecasts()

            # 2. Fetch futures curve
            futures_data = await self._get_futures_curve()

            # 3. Get biological risk from latest lice data
            bio_risk = await self._get_biological_risk()

            # 4. Generate hedging signals
            self.hedging_signals = self._generate_hedging_signals(
                forecasts, futures_data, bio_risk,
            )

            # 5. Store signals
            await self._store_signals(self.hedging_signals)

            # 6. Publish to shared memory
            self._publish_to_memory(self.hedging_signals)

            self.log.info(
                "hedger.tick_done",
                n_signals=len(self.hedging_signals),
                horizons=len(forecasts),
            )

        except Exception as e:
            self.log.error("hedger.tick_error", error=str(e)[:200])

    async def _get_price_forecasts(self) -> list[dict]:
        """Get ML price forecasts for key horizons."""
        from core.market.price_ml import price_ensemble

        # Get current market state
        async with get_async_session() as s:
            result = await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )
            latest = result.first()

            avg_lice = 0.15
            pct_above = 0.0
            if latest:
                result = await s.execute(
                    select(
                        func.avg(LiceRecord.avg_adult_female_lice),
                        func.avg(LiceRecord.avg_mobile_lice),
                        func.avg(LiceRecord.avg_stationary_lice),
                    ).where(
                        LiceRecord.year == latest[0],
                        LiceRecord.week == latest[1],
                        LiceRecord.avg_adult_female_lice.isnot(None),
                    )
                )
                stats = result.one()
                avg_lice = float(stats[0] or 0.15)

                result = await s.execute(
                    select(func.count(LiceRecord.id)).where(
                        LiceRecord.year == latest[0],
                        LiceRecord.week == latest[1],
                        LiceRecord.avg_adult_female_lice > 0.5,
                    )
                )
                above_count = result.scalar() or 0
                result = await s.execute(
                    select(func.count(LiceRecord.id)).where(
                        LiceRecord.year == latest[0],
                        LiceRecord.week == latest[1],
                        LiceRecord.avg_adult_female_lice.isnot(None),
                    )
                )
                total = result.scalar() or 1
                pct_above = above_count / total

        # Get SSB spot price (Fish Pool removed — dead since 2025)
        from core.market.ssb_price_client import ssb_price_client
        spot = await ssb_price_client.get_current_spot() or 75.0

        forecasts = []
        for h in [2, 4, 8, 12, 20]:
            futures_prem = 0.0  # No futures curve available (Fish Pool dead)
            fc = price_ensemble.predict(
                current_spot=spot,
                horizon_weeks=h,
                national_avg_lice=avg_lice,
                pct_above_threshold=pct_above,
                futures_premium_pct=futures_prem,
                n_scenarios=500,  # lighter for frequent runs
            )
            forecasts.append({
                "horizon": h,
                "predicted": fc.predicted_nok,
                "direction": fc.direction,
                "confidence": fc.confidence,
                "combined": fc.combined_signal,
                "lo80": fc.price_lo80,
                "hi80": fc.price_hi80,
                "mape": fc.mape_backtest,
                "rationale": fc.rationale,
            })

        self.latest_forecast = forecasts
        return forecasts

    async def _get_futures_curve(self) -> dict:
        """Get current price as proxy (Fish Pool futures unavailable since 2025)."""
        from core.market.ssb_price_client import ssb_price_client
        spot = await ssb_price_client.get_current_spot() or 75.0
        self.forward_curve = {
            "spot": spot,
            "shape": "flat",
            "premium_pct": 0.0,
            "quotes": [
            ],
        }
        return self.forward_curve

    async def _get_biological_risk(self) -> dict:
        """Assess biological risk from lice data."""
        async with get_async_session() as s:
            result = await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )
            latest = result.first()

            if not latest:
                return {"risk_level": "unknown", "tickers": {}}

            # Per-ticker risk assessment
            tickers = {}
            for ticker in ["MOWI", "SALM", "LSG", "GSF"]:
                result = await s.execute(
                    select(CompanyExposure.locality_no)
                    .where(CompanyExposure.ticker == ticker)
                )
                exposures = result.scalars().all()

                if not exposures:
                    continue

                result = await s.execute(
                    select(LiceRecord.avg_adult_female_lice)
                    .where(
                        LiceRecord.year == latest[0],
                        LiceRecord.week == latest[1],
                        LiceRecord.locality_no.in_(exposures),
                        LiceRecord.avg_adult_female_lice.isnot(None),
                    )
                )
                lice_vals = result.scalars().all()

                if lice_vals:
                    arr = np.array(lice_vals)
                    tickers[ticker] = {
                        "avg_lice": round(float(np.mean(arr)), 3),
                        "max_lice": round(float(np.max(arr)), 3),
                        "pct_above": round(float(np.mean(arr > 0.5)), 2),
                        "n_sites": len(lice_vals),
                        "risk": (
                            "HIGH" if np.mean(arr > 0.5) > 0.2
                            else "ELEVATED" if np.mean(arr) > 0.3
                            else "NORMAL"
                        ),
                    }

        overall = "NORMAL"
        if any(t.get("risk") == "HIGH" for t in tickers.values()):
            overall = "HIGH"
        elif any(t.get("risk") == "ELEVATED" for t in tickers.values()):
            overall = "ELEVATED"

        return {"risk_level": overall, "tickers": tickers}

    def _generate_hedging_signals(
        self,
        forecasts: list[dict],
        futures: dict,
        bio_risk: dict,
    ) -> list[dict]:
        """Generate actionable hedging recommendations."""
        signals = []

        # Short-term (2-4w): directional view based on ML forecast
        short_fc = next((f for f in forecasts if f["horizon"] == 4), None)
        if short_fc:
            signals.append({
                "type": "spot_directional",
                "horizon": "4w",
                "direction": short_fc["direction"],
                "strength": short_fc["confidence"],
                "entry_rationale": short_fc["rationale"],
                "price_target": short_fc["predicted"],
                "range_80": [short_fc["lo80"], short_fc["hi80"]],
            })

        # Medium-term (8-12w): equity impact per ticker
        med_fc = next((f for f in forecasts if f["horizon"] == 8), None)
        if med_fc and bio_risk.get("tickers"):
            for ticker, risk in bio_risk["tickers"].items():
                if risk["risk"] == "HIGH":
                    # High lice risk → negative for equity
                    signals.append({
                        "type": "equity_risk",
                        "ticker": ticker,
                        "horizon": "8w",
                        "direction": "bearish",
                        "strength": 0.7,
                        "entry_rationale": (
                            f"{ticker}: {risk['pct_above']:.0%} farms above lice limit, "
                            f"avg {risk['avg_lice']:.2f}. Treatment costs and harvest "
                            f"acceleration expected."
                        ),
                        "lice_risk": risk["risk"],
                    })
                elif risk["risk"] == "NORMAL" and med_fc["direction"] == "bullish":
                    # Clean farms + bullish price = positive for equity
                    signals.append({
                        "type": "equity_opportunity",
                        "ticker": ticker,
                        "horizon": "8w",
                        "direction": "bullish",
                        "strength": 0.5,
                        "entry_rationale": (
                            f"{ticker}: Clean lice profile (avg {risk['avg_lice']:.2f}). "
                            f"Price outlook {med_fc['combined']}. Well-positioned."
                        ),
                        "lice_risk": risk["risk"],
                    })

        # Futures curve arbitrage
        if futures.get("shape") == "contango" and short_fc:
            if short_fc["direction"] == "bearish":
                signals.append({
                    "type": "futures_arb",
                    "horizon": "1-3mo",
                    "direction": "sell_forward",
                    "strength": 0.6,
                    "entry_rationale": (
                        f"Forward curve in contango ({futures['premium_pct']:+.1f}% premium). "
                        f"ML model bearish short-term. Consider selling forward contracts."
                    ),
                })
        elif futures.get("shape") == "backwardation" and short_fc:
            if short_fc["direction"] == "bullish":
                signals.append({
                    "type": "futures_arb",
                    "horizon": "1-3mo",
                    "direction": "buy_forward",
                    "strength": 0.55,
                    "entry_rationale": (
                        f"Forward curve in backwardation ({futures['premium_pct']:+.1f}%). "
                        f"ML model bullish. Forward contracts underpriced."
                    ),
                })

        return signals

    async def _store_signals(self, signals: list[dict]) -> None:
        """Store hedging signals to database.

        Listed-equity direction rows are withheld while the WS-20/WS-28 withdrawal
        stands (``core.legal.equity_signals``); the salmon-price rows this agent also
        produces are unaffected.
        """
        if not may_persist_directional(instrument="equity"):
            equities = [
                s.get("ticker") for s in signals
                if s.get("ticker") and s.get("ticker") != "SALMON_SPOT"
            ]
            if equities:
                self.log.info("hedger.equity_signals_withheld", tickers=equities)
            return
        async with get_async_session() as s:
            for sig in signals:
                ticker = sig.get("ticker")
                if not ticker or ticker == "SALMON_SPOT":
                    continue  # skip non-equity signals
                direction = "LONG" if sig["direction"] in ("bullish", "buy_forward") else "SHORT"
                s.add(Signal(
                    ticker=ticker,
                    direction=direction,
                    strength=sig.get("strength", 0.5),
                    rationale=f"[HEDGER] {sig.get('entry_rationale', '')}",
                    status="pending",
                ))

    def _publish_to_memory(self, signals: list[dict]) -> None:
        """Publish hedging signals to shared memory for swarm."""
        try:
            from core.twin.shared_memory import shared_memory
            for sig in signals:
                shared_memory.store(
                    category="decision",
                    subject=f"hedge_{sig.get('type', 'unknown')}",
                    content={
                        "agent": "market_hedger",
                        "signal": sig,
                        "timestamp": dt.datetime.now(dt.UTC).isoformat(),
                    },
                    confidence=sig.get("strength", 0.5),
                    source_agent="market_hedger",
                    ttl_hours=12,
                )
        except Exception:
            pass  # Shared memory not always available

    def get_latest_signals(self) -> list[dict]:
        """Public accessor for latest hedging signals."""
        return self.hedging_signals
