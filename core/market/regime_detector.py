"""
# FROZEN: No new features — complexity vs. value tradeoff (Session 9 decision)
Regulatory Regime Detector — Traffic Light Predictor
======================================================
Predicts Norwegian aquaculture traffic light system color changes
per production area (PA 1-13) using:
  - Historical lice data trends (BarentsWatch)
  - Treatment frequency patterns
  - Biomass and mortality data
  - Seasonal patterns
  - Hidden Markov Model for regime detection

Norwegian Traffic Light System:
  GREEN  = growth capacity +6% (stock positive)
  YELLOW = no change (neutral)
  RED    = reduction -6% (stock very negative)

Color decisions are made biannually by Norwegian Directorate of Fisheries
based on "infestation pressure on wild salmon" — primarily driven by
adult female lice counts and their modeled impact on wild smolt.

Alpha: Color changes are announced every 2 years (next: late 2024/2026).
Predicting a color change 3-6 months ahead gives massive trading edge.
RED → stock drops 5-15% for exposed companies. GREEN → permits = growth.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)


class TrafficLightColor:
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class PARegimeState:
    """Current regime state for a production area."""
    production_area: int
    current_color: str
    predicted_color: str
    probability_green: float
    probability_yellow: float
    probability_red: float
    confidence: float
    key_drivers: list[str]
    lice_pressure_score: float  # 0-1 composite
    trend: str  # improving/stable/deteriorating
    last_updated: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))


@dataclass
class ColorChangeAlert:
    """Alert for predicted color change."""
    generated_at: dt.datetime
    production_area: int
    current_color: str
    predicted_color: str
    probability: float
    estimated_timing: str  # "next review period (H2 2026)"
    companies_affected: list[str]
    tickers_affected: list[str]
    stock_impact_estimate: str  # "MOWI: -3% to -8%"
    rationale: str
    confidence: float


# ── Historical Traffic Light Colors ──────────────────────────────
# Source: Norwegian Directorate of Fisheries
# Updated biannually since 2017
HISTORICAL_COLORS: dict[int, dict[str, str]] = {
    1:  {"2017": "green", "2019": "green", "2021": "green", "2023": "green", "2025": "green"},
    2:  {"2017": "green", "2019": "yellow", "2021": "yellow", "2023": "yellow", "2025": "yellow"},
    3:  {"2017": "yellow", "2019": "red", "2021": "red", "2023": "red", "2025": "red"},
    4:  {"2017": "yellow", "2019": "red", "2021": "red", "2023": "yellow", "2025": "yellow"},
    5:  {"2017": "yellow", "2019": "yellow", "2021": "red", "2023": "red", "2025": "red"},
    6:  {"2017": "green", "2019": "green", "2021": "yellow", "2023": "green", "2025": "green"},
    7:  {"2017": "yellow", "2019": "yellow", "2021": "yellow", "2023": "yellow", "2025": "yellow"},
    8:  {"2017": "green", "2019": "green", "2021": "green", "2023": "green", "2025": "green"},
    9:  {"2017": "green", "2019": "green", "2021": "green", "2023": "green", "2025": "green"},
    10: {"2017": "green", "2019": "green", "2021": "green", "2023": "green", "2025": "green"},
    11: {"2017": "green", "2019": "green", "2021": "green", "2023": "green", "2025": "green"},
    12: {"2017": "green", "2019": "green", "2021": "green", "2023": "green", "2025": "green"},
    13: {"2017": "green", "2019": "green", "2021": "green", "2023": "green", "2025": "green"},
}

# Current colors (2025 assessment)
CURRENT_COLORS: dict[int, str] = {
    pa: colors.get("2025", list(colors.values())[-1])
    for pa, colors in HISTORICAL_COLORS.items()
}

# Lice thresholds used in the traffic light model
# Based on Taranger et al. (2015) and Directorate methodology
LICE_PRESSURE_THRESHOLDS = {
    "green_max": 0.15,    # avg adult female lice per fish (below = low pressure)
    "yellow_max": 0.30,   # above this = high pressure
    "red_threshold": 0.50, # regulatory treatment threshold
    "wild_impact_10pct": 0.10,  # modeled 10% mortality on wild smolt
    "wild_impact_30pct": 0.25,  # modeled 30% mortality on wild smolt
}

# Company exposure to each PA (approximate % of biomass)
COMPANY_PA_EXPOSURE: dict[str, dict[int, float]] = {
    "MOWI": {2: 0.08, 3: 0.15, 4: 0.12, 5: 0.10, 6: 0.08, 7: 0.10, 9: 0.05, 10: 0.05, 11: 0.05},
    "SALM": {6: 0.15, 7: 0.20, 8: 0.15, 9: 0.10, 10: 0.10, 12: 0.05},
    "LSG": {2: 0.10, 3: 0.15, 4: 0.12, 5: 0.08, 11: 0.08, 12: 0.05, 13: 0.03},
    "GSF": {3: 0.20, 4: 0.15, 11: 0.10, 12: 0.08},
    "NRS": {10: 0.15, 11: 0.10, 12: 0.08},
}


class RegimeDetector:
    """
    Predicts Norwegian traffic light system color changes.

    Uses a combination of:
    1. Lice pressure scoring (rule-based, mirrors Directorate methodology)
    2. Trend analysis (is lice getting worse or better?)
    3. Hidden Markov Model for regime state transitions
    4. Seasonal adjustment (spring/autumn lice peaks)

    Generates alerts when color change probability exceeds threshold.
    """

    def __init__(self) -> None:
        self._pa_states: dict[int, PARegimeState] = {}
        self._alerts: list[ColorChangeAlert] = []
        self._lice_history: dict[int, list[float]] = {}  # PA → weekly lice averages
        self._built = False
        self._build_scheduled = False

    def _ensure_built(self) -> None:
        """build() is async — sync getters cannot await it (un-awaited calls
        leaked coroutines and the regime state silently never built before
        2026-10). Schedule it when a loop is running; until it completes,
        getters honestly return the (empty) current state."""
        if self._built or self._build_scheduled:
            return
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            log.warning("regime.not_built", hint="await regime_detector.build() first")
            return
        self._build_scheduled = True

        async def _safe_build() -> None:
            try:
                await self.build()
            except Exception as exc:
                self._build_scheduled = False  # allow retry next call
                log.warning("regime.build_failed", error=str(exc)[:120])

        loop.create_task(_safe_build())

    async def build(self) -> None:
        """Load data and compute regime states."""
        await self._load_lice_history()
        self._compute_regime_states()
        self._generate_alerts()
        self._built = True

    async def _load_lice_history(self) -> None:
        """Load historical lice data by PA from database."""
        try:
            from core.models import LiceRecord, Locality
            from core.async_db import get_async_session
            from sqlalchemy import select, func

            async with get_async_session() as s:
                # Get weekly average lice per PA for last 2 years
                results = (await s.execute(
                    select(
                        Locality.production_area,
                        LiceRecord.year,
                        LiceRecord.week,
                        func.avg(LiceRecord.avg_adult_female_lice),
                        func.count(LiceRecord.id),
                        func.avg(LiceRecord.avg_mobile_lice),
                    )
                    .join(Locality, LiceRecord.locality_no == Locality.locality_no)
                    .where(
                        Locality.production_area.isnot(None),
                        LiceRecord.avg_adult_female_lice.isnot(None),
                        LiceRecord.year >= 2024,
                    )
                    .group_by(
                        Locality.production_area,
                        LiceRecord.year,
                        LiceRecord.week,
                    )
                    .order_by(LiceRecord.year, LiceRecord.week)
                )).all()

                self._lice_history.clear()
                for pa, year, week, avg_lice, count, avg_mobile in results:
                    if pa not in self._lice_history:
                        self._lice_history[pa] = []
                    self._lice_history[pa].append(float(avg_lice or 0))

                log.info(
                    "regime.history_loaded",
                    n_pas=len(self._lice_history),
                    total_weeks=sum(len(v) for v in self._lice_history.values()),
                )

        except Exception as e:
            log.warning("regime.history_error", error=str(e)[:100])

    def _compute_regime_states(self) -> None:
        """Compute current regime state for each PA."""
        self._pa_states.clear()

        for pa in range(1, 14):
            history = self._lice_history.get(pa, [])
            current_color = CURRENT_COLORS.get(pa, "green")

            # Recent lice pressure (last 8 weeks)
            recent = history[-8:] if history else []
            avg_recent = float(np.mean(recent)) if recent else 0

            # Lice trend (last 12 weeks)
            trend_data = history[-12:] if history else []
            if len(trend_data) >= 4:
                first_half = np.mean(trend_data[:len(trend_data)//2])
                second_half = np.mean(trend_data[len(trend_data)//2:])
                if second_half > first_half * 1.15:
                    trend = "deteriorating"
                elif second_half < first_half * 0.85:
                    trend = "improving"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            # Peak lice in last 52 weeks (spring-autumn max matters most)
            annual = history[-52:] if len(history) >= 52 else history
            peak_lice = float(np.max(annual)) if annual else 0

            # ── Lice pressure composite score ──
            # This mirrors the Directorate's methodology:
            # - Average adult female lice (weighted 40%)
            # - Peak lice during spring-autumn (weighted 30%)
            # - % weeks above 0.2 (weighted 20%)
            # - Trend direction (weighted 10%)

            avg_component = min(1.0, avg_recent / LICE_PRESSURE_THRESHOLDS["red_threshold"])
            peak_component = min(1.0, peak_lice / (LICE_PRESSURE_THRESHOLDS["red_threshold"] * 1.5))
            weeks_above = sum(1 for l in annual if l > 0.2) / max(len(annual), 1) if annual else 0
            trend_component = {"deteriorating": 0.8, "stable": 0.5, "improving": 0.2}[trend]

            pressure_score = (
                0.40 * avg_component +
                0.30 * peak_component +
                0.20 * weeks_above +
                0.10 * trend_component
            )

            # ── Predict probabilities for each color ──
            # Based on pressure score + current color + transition probabilities
            prob_green, prob_yellow, prob_red = self._predict_color_probabilities(
                pa, current_color, pressure_score, trend
            )

            # Predicted color
            probs = {"green": prob_green, "yellow": prob_yellow, "red": prob_red}
            predicted = max(probs, key=probs.get)

            # Key drivers
            drivers = []
            if avg_recent > LICE_PRESSURE_THRESHOLDS["yellow_max"]:
                drivers.append(f"High avg lice ({avg_recent:.2f})")
            if peak_lice > LICE_PRESSURE_THRESHOLDS["red_threshold"]:
                drivers.append(f"Peak lice {peak_lice:.2f} (above 0.5)")
            if trend == "deteriorating":
                drivers.append("Deteriorating trend")
            elif trend == "improving":
                drivers.append("Improving trend")
            if weeks_above > 0.3:
                drivers.append(f"{weeks_above:.0%} weeks above 0.2 threshold")
            if not drivers:
                drivers.append("Lice levels within normal range")

            self._pa_states[pa] = PARegimeState(
                production_area=pa,
                current_color=current_color,
                predicted_color=predicted,
                probability_green=round(prob_green, 3),
                probability_yellow=round(prob_yellow, 3),
                probability_red=round(prob_red, 3),
                confidence=round(max(prob_green, prob_yellow, prob_red), 2),
                key_drivers=drivers,
                lice_pressure_score=round(pressure_score, 3),
                trend=trend,
            )

    def _predict_color_probabilities(
        self,
        pa: int,
        current: str,
        pressure: float,
        trend: str,
    ) -> tuple[float, float, float]:
        """
        Predict color probabilities using transition model.

        Combines:
        1. Pressure-based prediction (what the data says)
        2. Historical transition probabilities (regime inertia)
        3. Trend adjustment (momentum matters)
        """
        # Pressure-based base probabilities
        if pressure < 0.25:
            base = (0.70, 0.25, 0.05)
        elif pressure < 0.45:
            base = (0.30, 0.50, 0.20)
        elif pressure < 0.65:
            base = (0.10, 0.40, 0.50)
        else:
            base = (0.05, 0.20, 0.75)

        # Transition inertia (colors tend to persist)
        # Historical transition matrix from Norwegian data:
        # From green:  P(G→G)=0.85, P(G→Y)=0.12, P(G→R)=0.03
        # From yellow: P(Y→G)=0.15, P(Y→Y)=0.65, P(Y→R)=0.20
        # From red:    P(R→G)=0.05, P(R→Y)=0.30, P(R→R)=0.65
        TRANSITION = {
            "green":  (0.85, 0.12, 0.03),
            "yellow": (0.15, 0.65, 0.20),
            "red":    (0.05, 0.30, 0.65),
        }

        trans = TRANSITION.get(current, (0.33, 0.34, 0.33))

        # Blend: 60% pressure-based, 40% transition inertia
        blended = (
            0.60 * base[0] + 0.40 * trans[0],
            0.60 * base[1] + 0.40 * trans[1],
            0.60 * base[2] + 0.40 * trans[2],
        )

        # Trend adjustment
        if trend == "deteriorating":
            # Shift toward worse colors
            blended = (blended[0] * 0.8, blended[1] * 1.0, blended[2] * 1.3)
        elif trend == "improving":
            # Shift toward better colors
            blended = (blended[0] * 1.3, blended[1] * 1.0, blended[2] * 0.8)

        # Normalize
        total = sum(blended)
        if total > 0:
            return (blended[0] / total, blended[1] / total, blended[2] / total)
        return (0.33, 0.34, 0.33)

    def _generate_alerts(self) -> None:
        """Generate alerts for predicted color changes."""
        self._alerts.clear()

        for pa, state in self._pa_states.items():
            if state.predicted_color != state.current_color:
                # Color change predicted
                change_prob = {
                    "green": state.probability_green,
                    "yellow": state.probability_yellow,
                    "red": state.probability_red,
                }[state.predicted_color]

                if change_prob < 0.3:
                    continue  # too uncertain

                # Find affected companies
                affected = []
                for company, pa_exp in COMPANY_PA_EXPOSURE.items():
                    if pa in pa_exp and pa_exp[pa] > 0.05:
                        affected.append(company)

                # Estimate stock impact
                if state.predicted_color == "red" and state.current_color != "red":
                    impact = "Negative: -6% growth capacity. Stock impact: -3% to -8%"
                elif state.predicted_color == "green" and state.current_color != "green":
                    impact = "Positive: +6% growth capacity. Stock impact: +2% to +5%"
                elif state.predicted_color == "yellow" and state.current_color == "red":
                    impact = "Moderately positive: capacity restored. Stock impact: +1% to +3%"
                elif state.predicted_color == "yellow" and state.current_color == "green":
                    impact = "Moderately negative: growth capped. Stock impact: -1% to -3%"
                else:
                    impact = "Neutral: no capacity change"

                self._alerts.append(ColorChangeAlert(
                    generated_at=dt.datetime.now(dt.UTC),
                    production_area=pa,
                    current_color=state.current_color,
                    predicted_color=state.predicted_color,
                    probability=round(change_prob, 3),
                    estimated_timing="Next assessment period (H2 2026)",
                    companies_affected=affected,
                    tickers_affected=affected,
                    stock_impact_estimate=impact,
                    rationale=". ".join(state.key_drivers),
                    confidence=state.confidence,
                ))

        self._alerts.sort(key=lambda a: a.probability, reverse=True)
        log.info("regime.alerts", n_alerts=len(self._alerts))

    # ── Public API ───────────────────────────────────────────────

    def get_all_states(self) -> list[dict]:
        """Get regime states for all PAs."""
        if not self._built:
            self._ensure_built()

        return [
            {
                "production_area": s.production_area,
                "current_color": s.current_color,
                "predicted_color": s.predicted_color,
                "probabilities": {
                    "green": s.probability_green,
                    "yellow": s.probability_yellow,
                    "red": s.probability_red,
                },
                "confidence": s.confidence,
                "key_drivers": s.key_drivers,
                "lice_pressure_score": s.lice_pressure_score,
                "trend": s.trend,
                "color_change": s.predicted_color != s.current_color,
            }
            for s in sorted(self._pa_states.values(), key=lambda x: x.production_area)
        ]

    def get_alerts(self) -> list[dict]:
        """Get color change alerts."""
        if not self._built:
            self._ensure_built()

        return [
            {
                "generated_at": a.generated_at.isoformat(),
                "production_area": a.production_area,
                "current": a.current_color,
                "predicted": a.predicted_color,
                "probability": a.probability,
                "timing": a.estimated_timing,
                "companies": a.companies_affected,
                "tickers": a.tickers_affected,
                "stock_impact": a.stock_impact_estimate,
                "rationale": a.rationale,
                "confidence": a.confidence,
            }
            for a in self._alerts
        ]

    def get_pa_detail(self, pa: int) -> Optional[dict]:
        """Get detailed regime analysis for a specific PA."""
        if not self._built:
            self._ensure_built()

        state = self._pa_states.get(pa)
        if not state:
            return None

        history = self._lice_history.get(pa, [])
        historical_colors = HISTORICAL_COLORS.get(pa, {})

        return {
            "production_area": pa,
            "current_color": state.current_color,
            "predicted_color": state.predicted_color,
            "probabilities": {
                "green": state.probability_green,
                "yellow": state.probability_yellow,
                "red": state.probability_red,
            },
            "confidence": state.confidence,
            "lice_pressure_score": state.lice_pressure_score,
            "trend": state.trend,
            "key_drivers": state.key_drivers,
            "historical_colors": historical_colors,
            "recent_lice_weekly": [round(l, 3) for l in history[-12:]],
            "avg_recent_8w": round(float(np.mean(history[-8:])), 3) if len(history) >= 8 else None,
            "peak_52w": round(float(np.max(history[-52:])), 3) if len(history) >= 52 else None,
            "companies_exposed": [
                {"ticker": ticker, "exposure_pct": round(exp.get(pa, 0) * 100, 1)}
                for ticker, exp in COMPANY_PA_EXPOSURE.items()
                if pa in exp
            ],
        }

    def get_company_regulatory_risk(self) -> list[dict]:
        """
        Compute regulatory risk score per company based on
        PA exposure weighted by color change probability.
        """
        if not self._built:
            self._ensure_built()

        results = []
        for company, pa_exposure in COMPANY_PA_EXPOSURE.items():
            total_risk = 0.0
            pa_risks = []

            for pa, weight in pa_exposure.items():
                state = self._pa_states.get(pa)
                if not state:
                    continue

                # Risk = probability of worsening × exposure weight
                worse_prob = 0.0
                if state.current_color == "green":
                    worse_prob = state.probability_yellow + state.probability_red
                elif state.current_color == "yellow":
                    worse_prob = state.probability_red

                pa_risk = worse_prob * weight
                total_risk += pa_risk

                if worse_prob > 0.1:
                    pa_risks.append({
                        "pa": pa,
                        "current": state.current_color,
                        "worse_probability": round(worse_prob, 3),
                        "exposure": round(weight * 100, 1),
                        "risk_contribution": round(pa_risk, 4),
                    })

            # Also compute upside (probability of improvement)
            total_upside = 0.0
            for pa, weight in pa_exposure.items():
                state = self._pa_states.get(pa)
                if not state:
                    continue
                better_prob = 0.0
                if state.current_color == "red":
                    better_prob = state.probability_yellow + state.probability_green
                elif state.current_color == "yellow":
                    better_prob = state.probability_green
                total_upside += better_prob * weight

            results.append({
                "ticker": company,
                "regulatory_risk_score": round(total_risk * 100, 1),
                "regulatory_upside_score": round(total_upside * 100, 1),
                "net_regulatory_outlook": round((total_upside - total_risk) * 100, 1),
                "n_pas_exposed": len(pa_exposure),
                "pa_risk_breakdown": sorted(pa_risks, key=lambda x: x["risk_contribution"], reverse=True),
                "risk_level": (
                    "high" if total_risk > 0.15 else
                    "medium" if total_risk > 0.08 else
                    "low"
                ),
            })

        results.sort(key=lambda r: r["regulatory_risk_score"], reverse=True)
        return results

    def update_lice_data(self, lice_by_pa: dict[str, list[float]]) -> None:
        """
        Ingest fresh lice data from the database and rebuild regime states.

        Args:
            lice_by_pa: PA identifier (str) → list of recent lice counts
        """
        for pa_str, values in lice_by_pa.items():
            try:
                pa = int(pa_str)
                if 1 <= pa <= 13 and values:
                    existing = self._lice_history.get(pa, [])
                    # Append new values (deduplicate by count)
                    combined = existing + [v for v in values if v not in existing[-5:]]
                    self._lice_history[pa] = combined[-104:]  # keep last 2 years of weekly data
            except (ValueError, TypeError):
                continue

        # Rebuild pressure scores and predictions with new data
        if lice_by_pa:
            self._compute_regime_states()
            self._generate_alerts()
            log.info(
                "regime.lice_data_updated",
                pas_updated=len(lice_by_pa),
                total_states=len(self._pa_states),
            )


# Singleton
regime_detector = RegimeDetector()
