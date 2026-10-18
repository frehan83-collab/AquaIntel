"""
Prediction Orchestrator Agent
==============================
Runs the full tiered prediction pipeline every 15 minutes:

  1. Compute infestation pressure field
  2. Run short-term Stige predictor (1-2 weeks)
  3. Run medium-term Prophet+LSTM ensemble (2-6 weeks)
  4. Translate predictions to harvest impacts
  5. Generate arbitrage signals
  6. Store results for dashboard + signal generator
"""
from __future__ import annotations


import numpy as np
import pandas as pd
from sqlalchemy import select

from agents.base import BaseAgent
from core.legal.equity_signals import may_persist_directional
from core.models import (
    Locality, LiceRecord, CompanyExposure, Signal, AuditLog,
)
from core.async_db import get_async_session
from core.predictors.infestation_pressure import (
    LocalityLiceState,
    compute_pressure_field,
    InfestationPressure,
)
from core.predictors.short_term import StigePredictor, StageForcast
from core.predictors.medium_term import ProphetLSTMPredictor, MediumTermForecast
from core.predictors.impact_translator import (
    compute_harvest_impact,
    generate_arbitrage_signal,
    HarvestImpact,
    ArbitrageSignal,
)

import structlog

log = structlog.get_logger(__name__)

TICKERS = ["MOWI", "SALM", "LSG", "GSF"]


class PredictionAgent(BaseAgent):
    name = "prediction"
    interval_seconds = 900  # 15 minutes

    def __init__(self) -> None:
        super().__init__()
        self.short_term = StigePredictor()
        self.medium_term = ProphetLSTMPredictor()

        # Latest results (shared with dashboard)
        self.pressure_field: list[InfestationPressure] = []
        self.short_forecasts: dict[str, list[StageForcast]] = {}
        self.medium_forecasts: dict[str, MediumTermForecast] = {}
        self.harvest_impacts: dict[str, HarvestImpact] = {}
        self.arb_signals: dict[str, ArbitrageSignal] = {}

        self._model_trained = False

    async def tick(self) -> None:
        self.log.info("prediction.tick_start")

        # ── Step 1: Load current data from DB ────────────────────────
        locality_states, lice_df = await self._load_current_data()
        if lice_df.empty:
            self.log.warning("prediction.no_data")
            return

        # ── Step 2: Compute infestation pressure field ───────────────
        self.pressure_field = compute_pressure_field(locality_states)
        pressure_map = {p.locality_no: p.pressure_index for p in self.pressure_field}

        # Add pressure to lice dataframe
        lice_df["pressure_index"] = lice_df["locality_no"].map(pressure_map).fillna(0)

        # ── Step 3: Train short-term model (periodic) ────────────────
        if not self._model_trained:
            history = await self._load_history()
            if len(history) >= 50:
                # Subsample if too large (>20k rows slows PyMC/GLM)
                if len(history) > 20000:
                    self.log.info("prediction.subsample", original=len(history), target=20000)
                    history = history.sample(n=20000, random_state=42).sort_values(
                        ["locality_no", "year", "week"]
                    ).reset_index(drop=True)
                self.short_term.fit(history)
                self._model_trained = True

        # ── Step 4: Run predictions per company ──────────────────────
        for ticker in TICKERS:
            company_lice = await self._get_company_lice(ticker, lice_df)
            if company_lice.empty:
                continue

            # Short-term (1-2 weeks)
            st_1w = self.short_term.predict(company_lice, horizon_weeks=1)
            st_2w = self.short_term.predict(company_lice, horizon_weeks=2)
            self.short_forecasts[ticker] = st_1w + st_2w

            # Medium-term (4 weeks) — needs aggregated company history
            company_history = await self._get_company_history(ticker)
            mt_forecast = self.medium_term.predict(
                company_history, ticker=ticker, horizon_weeks=4
            )
            self.medium_forecasts[ticker] = mt_forecast

            # ── Step 5: Impact translation ───────────────────────────
            avg_predicted = np.mean([f.pred_adult_female for f in st_1w]) if st_1w else 0
            pct_above = np.mean([f.prob_exceed_threshold for f in st_1w]) if st_1w else 0
            n_sites = len(company_lice)

            # Dominant trend
            trends = [f.trend for f in st_1w]
            trend = max(set(trends), key=trends.count) if trends else "stable"

            impact = compute_harvest_impact(
                ticker=ticker,
                avg_predicted_lice=avg_predicted,
                pct_sites_above_threshold=pct_above,
                n_active_sites=n_sites,
            )
            self.harvest_impacts[ticker] = impact

            # ── Step 6: Generate arbitrage signal ────────────────────
            avg_prob_exceed = np.mean([f.prob_exceed_threshold for f in st_1w]) if st_1w else 0

            arb_signal = generate_arbitrage_signal(
                ticker=ticker,
                impact=impact,
                lice_trend=trend,
                prob_exceed=avg_prob_exceed,
            )

            if arb_signal:
                self.arb_signals[ticker] = arb_signal
                await self._persist_signal(arb_signal)
                self.log.info(
                    "prediction.signal",
                    ticker=ticker,
                    direction=arb_signal.direction,
                    strength=arb_signal.strength,
                    expected_move=arb_signal.expected_move_pct,
                )

        # Audit
        await self._audit()
        self.log.info(
            "prediction.tick_done",
            signals=len(self.arb_signals),
            pressure_computed=len(self.pressure_field),
        )

    # ── Data loading helpers ─────────────────────────────────────────
    @staticmethod
    async def _load_current_data() -> tuple[list[LocalityLiceState], pd.DataFrame]:
        """Load the most recent week(s) of lice data with geo info.

        If the latest week has fewer than 100 records (incomplete reporting),
        also includes the previous week so all companies get coverage.
        """
        async with get_async_session() as s:
            # Find latest 2 year/week combos
            result = await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .where(LiceRecord.avg_adult_female_lice.isnot(None))
                .group_by(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(2)
            )
            latest_weeks = result.all()

            if not latest_weeks:
                return [], pd.DataFrame()

            year, week = latest_weeks[0]

            # Count records in latest week
            from sqlalchemy import func
            result = await s.execute(
                select(func.count(LiceRecord.id))
                .where(LiceRecord.year == year, LiceRecord.week == week)
                .where(LiceRecord.avg_adult_female_lice.isnot(None))
            )
            latest_count = result.scalar()

            # If latest week is incomplete (<100 records), include previous week too
            week_filters = [(year, week)]
            if latest_count < 100 and len(latest_weeks) > 1:
                prev_year, prev_week = latest_weeks[1]
                week_filters.append((prev_year, prev_week))
                log.info(
                    "prediction.sparse_week_fallback",
                    latest_count=latest_count,
                    using_weeks=week_filters,
                )

            # Build OR filter for selected weeks
            from sqlalchemy import or_, and_
            week_conditions = or_(
                *[and_(LiceRecord.year == y, LiceRecord.week == w) for y, w in week_filters]
            )

            # Join lice records with locality geo data
            result = await s.execute(
                select(LiceRecord, Locality)
                .join(Locality, LiceRecord.locality_no == Locality.locality_no)
                .where(week_conditions)
                .where(LiceRecord.avg_adult_female_lice.isnot(None))
            )
            records = result.all()

        # If we loaded multiple weeks, keep only the latest record per locality
        seen_localities: set[int] = set()
        # Sort records so latest week comes first
        records_sorted = sorted(
            records,
            key=lambda r: (r[0].year, r[0].week),
            reverse=True,
        )

        states = []
        rows = []
        for lice, loc in records_sorted:
            if lice.locality_no in seen_localities:
                continue  # Already have newer data for this locality
            seen_localities.add(lice.locality_no)

            if loc.latitude and loc.longitude:
                states.append(LocalityLiceState(
                    locality_no=lice.locality_no,
                    lat=loc.latitude,
                    lon=loc.longitude,
                    avg_adult_female=lice.avg_adult_female_lice or 0,
                    avg_mobile=lice.avg_mobile_lice or 0,
                    sea_temp=lice.sea_temp_c or 8.0,
                    has_cleaner_fish=lice.has_cleaner_fish or False,
                ))

            rows.append({
                "locality_no": lice.locality_no,
                "year": lice.year,
                "week": lice.week,
                "avg_adult_female_lice": lice.avg_adult_female_lice,
                "avg_mobile_lice": lice.avg_mobile_lice,
                "avg_stationary_lice": lice.avg_stationary_lice,
                "sea_temp_c": lice.sea_temp_c,
                "has_cleaner_fish": lice.has_cleaner_fish,
            })

        return states, pd.DataFrame(rows)

    @staticmethod
    async def _load_history() -> pd.DataFrame:
        """Load full lice history for model training."""
        async with get_async_session() as s:
            result = await s.execute(
                select(LiceRecord)
                .where(LiceRecord.avg_adult_female_lice.isnot(None))
                .order_by(LiceRecord.locality_no, LiceRecord.year, LiceRecord.week)
            )
            records = result.scalars().all()

        if not records:
            return pd.DataFrame()

        return pd.DataFrame([{
            "locality_no": r.locality_no,
            "year": r.year,
            "week": r.week,
            "avg_adult_female_lice": r.avg_adult_female_lice,
            "avg_mobile_lice": r.avg_mobile_lice or 0,
            "avg_stationary_lice": r.avg_stationary_lice or 0,
            "sea_temp_c": r.sea_temp_c or 8,
            "has_cleaner_fish": r.has_cleaner_fish or False,
        } for r in records])

    @staticmethod
    async def _get_company_lice(ticker: str, lice_df: pd.DataFrame) -> pd.DataFrame:
        """Filter lice data to a specific company's localities."""
        async with get_async_session() as s:
            result = await s.execute(
                select(CompanyExposure.locality_no).where(
                    CompanyExposure.ticker == ticker
                )
            )
            locality_nos = result.scalars().all()

        return lice_df[lice_df["locality_no"].isin(locality_nos)].copy()

    @staticmethod
    async def _get_company_history(ticker: str) -> pd.DataFrame:
        """Get weekly-aggregated lice history for a company."""
        async with get_async_session() as s:
            result = await s.execute(
                select(CompanyExposure.locality_no).where(
                    CompanyExposure.ticker == ticker
                )
            )
            locality_nos = result.scalars().all()

            result = await s.execute(
                select(LiceRecord)
                .where(
                    LiceRecord.locality_no.in_(list(locality_nos)),
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )
                .order_by(LiceRecord.year, LiceRecord.week)
            )
            records = result.scalars().all()

        if not records:
            return pd.DataFrame(columns=["year", "week", "avg_lice", "sea_temp"])

        df = pd.DataFrame([{
            "year": r.year,
            "week": r.week,
            "avg_lice": r.avg_adult_female_lice,
            "sea_temp": r.sea_temp_c or 8,
        } for r in records])

        # Aggregate by week
        return df.groupby(["year", "week"]).agg(
            avg_lice=("avg_lice", "mean"),
            sea_temp=("sea_temp", "mean"),
        ).reset_index()

    @staticmethod
    async def _persist_signal(arb: ArbitrageSignal) -> None:
        """Store prediction-based signal in DB.

        Withheld while the WS-20/WS-28 withdrawal stands (``core.legal.equity_signals``):
        this row carries a trade direction on a listed share. The harvest-impact
        numbers this agent produces are still published through the investor surface.
        """
        if not may_persist_directional(instrument="equity"):
            log.info(
                "prediction.equity_signal_withheld",
                ticker=arb.ticker,
                direction=arb.direction,
            )
            return
        async with get_async_session() as s:
            s.add(Signal(
                ticker=arb.ticker,
                direction=arb.direction,
                strength=arb.strength,
                lice_score=arb.prob_exceed_threshold,
                exposure_score=arb.harvest_impact.total_harvest_reduction_pct if arb.harvest_impact else 0,
                rationale=arb.rationale,
                status="pending",
            ))

    async def _audit(self) -> None:
        async with get_async_session() as s:
            summary = "; ".join(
                f"{t}: impact={self.harvest_impacts.get(t, HarvestImpact(ticker=t)).total_harvest_reduction_pct:.1f}%"
                for t in TICKERS
                if t in self.harvest_impacts
            )
            s.add(AuditLog(
                event_type="prediction_cycle",
                detail=f"Pressure field: {len(self.pressure_field)} sites. {summary}",
            ))
