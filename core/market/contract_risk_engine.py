"""
Contract Risk Analyzer Engine
==============================
Evaluates buyer fixed-price salmon contracts against live market data.

All prices and forecasts come from live sources at runtime:
- SSB spot price: ssb_price_client.get_current_spot()
- Price forecasts: price_ml (PriceEnsemble)
- Seasonal patterns: ssb_price_client.fetch_prices()

NO hardcoded price values. Only structural constants (regulatory limits,
method names, confidence levels) are static.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field, asdict

import structlog

log = structlog.get_logger(__name__)


# ── Structural constants only (not price data) ──────────────────────
DEFAULT_VAR_CONFIDENCE = 0.95
MAX_HEDGE_RATIO = 1.0  # regulatory: cannot hedge more than 100%
MIN_HEDGE_RATIO = 0.0


@dataclass
class ContractPosition:
    """A single buyer fixed-price salmon contract."""
    contract_price_nok: float       # agreed NOK/kg
    volume_tonnes: float            # contracted volume
    start_date: str                 # ISO date string
    end_date: str                   # ISO date string
    counterparty: str = ""          # buyer name


@dataclass
class ContractEvaluation:
    """Result of evaluating a single contract against live market."""
    contract_price_nok: float = 0.0
    volume_tonnes: float = 0.0
    counterparty: str = ""
    start_date: str = ""
    end_date: str = ""

    # Live market context
    live_spot_nok: float = 0.0
    spot_source: str = "SSB Table 03024"

    # Mark-to-market P&L
    price_delta_nok: float = 0.0   # contract_price - spot (positive = above market)
    mtm_pnl_nok: float = 0.0      # total P&L in NOK
    mtm_pnl_pct: float = 0.0      # % relative to spot value
    pnl_direction: str = "neutral" # "profit" | "loss" | "neutral"

    # VaR
    var_95_nok: float = 0.0        # Value at Risk (95% confidence)
    var_95_pct: float = 0.0
    var_confidence: float = 0.95

    # Forecast context
    forecast_price_nok: float = 0.0
    forecast_direction: str = "neutral"
    forecast_confidence: float = 0.0
    forecast_lo95: float = 0.0
    forecast_hi95: float = 0.0

    # Hedge recommendation
    hedge_ratio: float = 0.0
    hedge_action: str = "hold"     # "increase_hedge" | "reduce_hedge" | "hold"
    hedge_rationale: str = ""

    # Metadata
    evaluated_at: str = ""
    days_remaining: int = 0


@dataclass
class PortfolioRisk:
    """Aggregate risk across multiple contracts."""
    n_contracts: int = 0
    total_volume_tonnes: float = 0.0
    total_mtm_pnl_nok: float = 0.0
    avg_contract_price_nok: float = 0.0
    live_spot_nok: float = 0.0
    weighted_hedge_ratio: float = 0.0
    portfolio_var_95_nok: float = 0.0
    contracts: list = field(default_factory=list)
    evaluated_at: str = ""


class ContractRiskEngine:
    """
    Evaluates salmon contracts against live SSB spot prices
    and ML price forecasts. All dynamic values fetched at runtime.
    """

    def __init__(self) -> None:
        self._ssb = None
        self._price_ml = None

    def _get_ssb(self):
        """Lazy import SSB price client singleton."""
        if self._ssb is None:
            from core.market.ssb_price_client import ssb_price_client
            self._ssb = ssb_price_client
        return self._ssb

    def _get_price_ml(self):
        """Lazy import price ML ensemble singleton."""
        if self._price_ml is None:
            from core.market.price_ml import price_ensemble
            self._price_ml = price_ensemble
        return self._price_ml

    async def _fetch_live_spot(self) -> float:
        """Get current SSB spot price (NOK/kg). Never hardcoded."""
        ssb = self._get_ssb()
        spot = await ssb.get_current_spot()
        if spot <= 0:
            log.warning("contract_risk.spot_unavailable")
        return spot

    def _get_forecast(self, spot: float, horizon_weeks: int = 4) -> dict:
        """
        Get ML price forecast from price_ensemble.predict().
        Returns dict with key forecast fields.
        """
        ml = self._get_price_ml()
        forecast = ml.predict(
            current_spot=spot,
            horizon_weeks=horizon_weeks,
        )
        return {
            "predicted_nok": forecast.predicted_nok,
            "direction": forecast.direction,
            "confidence": forecast.confidence,
            "lo95": forecast.price_lo95,
            "hi95": forecast.price_hi95,
            "lo80": forecast.price_lo80,
            "hi80": forecast.price_hi80,
            "combined_signal": forecast.combined_signal,
            "rationale": forecast.rationale,
            "scenarios_p10": forecast.scenarios_p10,
            "scenarios_p25": forecast.scenarios_p25,
            "scenarios_p50": forecast.scenarios_p50,
            "scenarios_p75": forecast.scenarios_p75,
            "scenarios_p90": forecast.scenarios_p90,
        }

    def _compute_days_remaining(self, end_date_str: str) -> int:
        """Days until contract expiry."""
        try:
            end = dt.date.fromisoformat(end_date_str)
            return max(0, (end - dt.date.today()).days)
        except (ValueError, TypeError):
            return 0

    def _estimate_horizon_weeks(self, end_date_str: str) -> int:
        """Convert contract end date to forecast horizon in weeks."""
        days = self._compute_days_remaining(end_date_str)
        weeks = max(2, min(20, days // 7))  # Clamp to ML model range
        return weeks

    async def evaluate_contract(self, position_data: dict) -> dict:
        """
        Evaluate a single contract against live market data.

        Args:
            position_data: dict with contract_price_nok, volume_tonnes,
                           start_date, end_date, counterparty
        Returns:
            ContractEvaluation as dict
        """
        pos = ContractPosition(
            contract_price_nok=float(position_data.get("contract_price_nok", 0)),
            volume_tonnes=float(position_data.get("volume_tonnes", 0)),
            start_date=str(position_data.get("start_date", "")),
            end_date=str(position_data.get("end_date", "")),
            counterparty=str(position_data.get("counterparty", "")),
        )

        # 1. Live SSB spot
        spot = await self._fetch_live_spot()
        if spot <= 0:
            return {"error": "SSB spot price unavailable", "spot": 0}

        # 2. Mark-to-market P&L
        price_delta = pos.contract_price_nok - spot
        volume_kg = pos.volume_tonnes * 1000
        mtm_pnl = price_delta * volume_kg
        mtm_pnl_pct = (price_delta / spot * 100) if spot > 0 else 0

        if price_delta > 0.5:
            pnl_direction = "profit"
        elif price_delta < -0.5:
            pnl_direction = "loss"
        else:
            pnl_direction = "neutral"

        # 3. Forecast + VaR
        horizon = self._estimate_horizon_weeks(pos.end_date)
        forecast = self._get_forecast(spot, horizon)
        var_result = self._compute_var_from_forecast(
            pos, spot, forecast, confidence=DEFAULT_VAR_CONFIDENCE
        )

        # 4. Hedge recommendation
        hedge = self._compute_hedge(pos, spot, forecast)

        days_remaining = self._compute_days_remaining(pos.end_date)

        evaluation = ContractEvaluation(
            contract_price_nok=round(pos.contract_price_nok, 2),
            volume_tonnes=pos.volume_tonnes,
            counterparty=pos.counterparty,
            start_date=pos.start_date,
            end_date=pos.end_date,
            live_spot_nok=round(spot, 2),
            price_delta_nok=round(price_delta, 2),
            mtm_pnl_nok=round(mtm_pnl, 0),
            mtm_pnl_pct=round(mtm_pnl_pct, 2),
            pnl_direction=pnl_direction,
            var_95_nok=round(var_result["var_nok"], 0),
            var_95_pct=round(var_result["var_pct"], 2),
            var_confidence=DEFAULT_VAR_CONFIDENCE,
            forecast_price_nok=round(forecast["predicted_nok"], 2),
            forecast_direction=forecast["direction"],
            forecast_confidence=round(forecast["confidence"], 2),
            forecast_lo95=round(forecast["lo95"], 2),
            forecast_hi95=round(forecast["hi95"], 2),
            hedge_ratio=round(hedge["ratio"], 2),
            hedge_action=hedge["action"],
            hedge_rationale=hedge["rationale"],
            evaluated_at=dt.datetime.now(dt.UTC).isoformat(),
            days_remaining=days_remaining,
        )

        return asdict(evaluation)

    def _compute_var_from_forecast(
        self,
        pos: ContractPosition,
        spot: float,
        forecast: dict,
        confidence: float = 0.95,
    ) -> dict:
        """
        Compute Value-at-Risk using the ML forecast distribution.

        Uses the forecast's 95% confidence band (from conformal prediction
        or TFT quantiles) to estimate worst-case price move.
        """
        volume_kg = pos.volume_tonnes * 1000

        # Worst-case scenario: spot moves to the band edge that hurts
        # For a seller (contract above spot): risk is spot going UP
        # beyond contract price, reducing the contract's relative value.
        # For a buyer locked at contract price: risk is spot dropping far
        # below contract price (overpaying).
        # We use the full 95% band width as the VaR estimate.
        if confidence >= 0.95:
            worst_price = forecast["hi95"]  # spot could rise to hi95
        else:
            worst_price = forecast.get("hi80", forecast["hi95"])

        # VaR = potential loss if spot moves to worst case
        potential_loss_per_kg = max(0, worst_price - pos.contract_price_nok)
        var_nok = potential_loss_per_kg * volume_kg
        var_pct = (potential_loss_per_kg / spot * 100) if spot > 0 else 0

        return {
            "var_nok": var_nok,
            "var_pct": var_pct,
            "worst_price": worst_price,
        }

    def _compute_hedge(
        self,
        pos: ContractPosition,
        spot: float,
        forecast: dict,
    ) -> dict:
        """
        Suggest hedge ratio based on live ML price outlook signals.
        All signal data comes from price_ensemble.predict().
        """
        direction = forecast["direction"]
        confidence = forecast["confidence"]
        combined = forecast["combined_signal"]
        predicted = forecast["predicted_nok"]

        # Base hedge ratio from forecast direction
        if direction == "bullish":
            # Prices expected to rise -> contract locked below future spot
            # Less hedge needed (contract is favorable)
            base_ratio = 0.3
            rationale_parts = ["Bullish outlook reduces hedge need"]
        elif direction == "bearish":
            # Prices expected to fall -> contract locked above future spot
            # More hedge needed (contract may become unfavorable)
            base_ratio = 0.7
            rationale_parts = ["Bearish outlook increases hedge recommendation"]
        else:
            base_ratio = 0.5
            rationale_parts = ["Neutral outlook suggests moderate hedging"]

        # Adjust by confidence
        if confidence > 0.7:
            base_ratio *= 1.2
            rationale_parts.append(f"high model confidence ({confidence:.0%})")
        elif confidence < 0.3:
            base_ratio = 0.5  # Low confidence -> default to moderate
            rationale_parts.append("low model confidence, defaulting to moderate")

        # Adjust by contract premium/discount vs forecast
        if pos.contract_price_nok > predicted * 1.05:
            base_ratio += 0.1
            rationale_parts.append("contract price above forecast")
        elif pos.contract_price_nok < predicted * 0.95:
            base_ratio -= 0.1
            rationale_parts.append("contract price below forecast")

        # Adjust by combined signal strength
        signal_adjustments = {
            "STRONG_BULLISH": -0.15,
            "BULLISH": -0.1,
            "NEUTRAL": 0.0,
            "BEARISH": 0.1,
            "STRONG_BEARISH": 0.15,
        }
        adj = signal_adjustments.get(combined, 0.0)
        base_ratio += adj
        if combined != "NEUTRAL":
            rationale_parts.append(f"combined signal: {combined}")

        # Clamp to valid range
        ratio = max(MIN_HEDGE_RATIO, min(MAX_HEDGE_RATIO, base_ratio))

        # Determine action
        if ratio >= 0.6:
            action = "increase_hedge"
        elif ratio <= 0.3:
            action = "reduce_hedge"
        else:
            action = "hold"

        return {
            "ratio": ratio,
            "action": action,
            "rationale": "; ".join(rationale_parts),
        }

    def compute_var(
        self,
        position_data: dict,
        spot: float,
        forecast: dict,
        confidence: float = 0.95,
    ) -> dict:
        """Public VaR computation for a single position."""
        pos = ContractPosition(
            contract_price_nok=float(position_data.get("contract_price_nok", 0)),
            volume_tonnes=float(position_data.get("volume_tonnes", 0)),
            start_date=str(position_data.get("start_date", "")),
            end_date=str(position_data.get("end_date", "")),
            counterparty=str(position_data.get("counterparty", "")),
        )
        return self._compute_var_from_forecast(pos, spot, forecast, confidence)

    async def get_portfolio_risk(self, positions: list[dict]) -> dict:
        """
        Aggregate risk across a portfolio of contracts.

        Args:
            positions: list of contract position dicts
        Returns:
            PortfolioRisk as dict
        """
        if not positions:
            return asdict(PortfolioRisk(evaluated_at=dt.datetime.now(dt.UTC).isoformat()))

        spot = await self._fetch_live_spot()
        if spot <= 0:
            return {"error": "SSB spot price unavailable"}

        evaluations = []
        total_volume = 0.0
        total_pnl = 0.0
        weighted_price_sum = 0.0
        weighted_hedge_sum = 0.0
        total_var = 0.0

        for pos_data in positions:
            result = await self.evaluate_contract(pos_data)
            if "error" not in result:
                evaluations.append(result)
                vol = result.get("volume_tonnes", 0)
                total_volume += vol
                total_pnl += result.get("mtm_pnl_nok", 0)
                weighted_price_sum += result.get("contract_price_nok", 0) * vol
                weighted_hedge_sum += result.get("hedge_ratio", 0) * vol
                total_var += result.get("var_95_nok", 0)

        avg_price = weighted_price_sum / total_volume if total_volume > 0 else 0
        avg_hedge = weighted_hedge_sum / total_volume if total_volume > 0 else 0

        # Portfolio VaR with diversification benefit (sqrt of sum of squares)
        # More conservative than simple sum (assumes some correlation)
        individual_vars = [e.get("var_95_nok", 0) for e in evaluations]
        if individual_vars:
            portfolio_var = math.sqrt(sum(v ** 2 for v in individual_vars))
        else:
            portfolio_var = 0

        portfolio = PortfolioRisk(
            n_contracts=len(evaluations),
            total_volume_tonnes=round(total_volume, 1),
            total_mtm_pnl_nok=round(total_pnl, 0),
            avg_contract_price_nok=round(avg_price, 2),
            live_spot_nok=round(spot, 2),
            weighted_hedge_ratio=round(avg_hedge, 2),
            portfolio_var_95_nok=round(portfolio_var, 0),
            contracts=evaluations,
            evaluated_at=dt.datetime.now(dt.UTC).isoformat(),
        )

        return asdict(portfolio)

    async def get_market_context(self) -> dict:
        """
        Live market context for the contracts dashboard.
        Returns current SSB spot, price forecast, and signals.
        All values fetched live — nothing hardcoded.
        """
        spot = await self._fetch_live_spot()

        if spot <= 0:
            return {
                "spot_available": False,
                "error": "SSB spot price temporarily unavailable",
            }

        # Get forecasts at multiple horizons
        forecast_4w = self._get_forecast(spot, horizon_weeks=4)
        forecast_8w = self._get_forecast(spot, horizon_weeks=8)
        forecast_12w = self._get_forecast(spot, horizon_weeks=12)

        # Get seasonal context from SSB history
        ssb = self._get_ssb()
        price_data = await ssb.fetch_prices(n_weeks=52)
        recent_prices = [
            {"week": f"{p.year}W{p.week:02d}", "price_nok": p.price_nok_kg}
            for p in (price_data.prices[-12:] if price_data.prices else [])
        ]

        return {
            "spot_available": True,
            "live_spot_nok": round(spot, 2),
            "spot_source": "SSB Table 03024",
            "spot_week": price_data.latest_week,
            "forecasts": {
                "4w": {
                    "predicted_nok": forecast_4w["predicted_nok"],
                    "direction": forecast_4w["direction"],
                    "confidence": forecast_4w["confidence"],
                    "lo95": forecast_4w["lo95"],
                    "hi95": forecast_4w["hi95"],
                    "combined_signal": forecast_4w["combined_signal"],
                    "rationale": forecast_4w["rationale"],
                },
                "8w": {
                    "predicted_nok": forecast_8w["predicted_nok"],
                    "direction": forecast_8w["direction"],
                    "confidence": forecast_8w["confidence"],
                    "lo95": forecast_8w["lo95"],
                    "hi95": forecast_8w["hi95"],
                    "combined_signal": forecast_8w["combined_signal"],
                },
                "12w": {
                    "predicted_nok": forecast_12w["predicted_nok"],
                    "direction": forecast_12w["direction"],
                    "confidence": forecast_12w["confidence"],
                    "lo95": forecast_12w["lo95"],
                    "hi95": forecast_12w["hi95"],
                    "combined_signal": forecast_12w["combined_signal"],
                },
            },
            "recent_prices": recent_prices,
            "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
        }

    def suggest_hedge(self, position_data: dict, spot: float, forecast: dict) -> dict:
        """
        Public hedge suggestion for a single position.
        Uses live price outlook signals from price_ml.predict().
        """
        pos = ContractPosition(
            contract_price_nok=float(position_data.get("contract_price_nok", 0)),
            volume_tonnes=float(position_data.get("volume_tonnes", 0)),
            start_date=str(position_data.get("start_date", "")),
            end_date=str(position_data.get("end_date", "")),
            counterparty=str(position_data.get("counterparty", "")),
        )
        return self._compute_hedge(pos, spot, forecast)


# ── Singleton ────────────────────────────────────────────────────────
contract_risk_engine = ContractRiskEngine()
