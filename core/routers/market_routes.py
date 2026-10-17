"""
Market Terminal Routes
======================
Extracted from core/api.py for maintainability.
Price forecasts, price outlook, SSB data, futures, hedger signals, equity prices.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func

from core.async_db import get_async_session
from core.cache import cached
from core.market.data_provenance import DataProvenance, from_records
from core.models import LiceRecord, PricePrediction, Signal
from core.schemas import PriceOutlookResponse

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/price-forecast")
@cached(ttl=300, key_prefix="price_forecast")
async def price_forecast(horizon: int = 4):
    """Salmon price prediction for a given horizon (weeks)."""
    from core.market.salmon_price import price_engine

    # Get current lice data for the model
    async with get_async_session() as s:
        latest = (await s.execute(
            select(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(1)
        )).first()

        avg_lice = 0.15
        pct_above = 0.0
        if latest:
            from sqlalchemy import func as fn
            stats = (await s.execute(
                select(
                    fn.avg(LiceRecord.avg_adult_female_lice),
                    fn.count(LiceRecord.id),
                ).where(
                    LiceRecord.year == latest[0],
                    LiceRecord.week == latest[1],
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )
            )).one()
            avg_lice = float(stats[0] or 0.15)

            above = (await s.execute(
                select(fn.count(LiceRecord.id)).where(
                    LiceRecord.year == latest[0],
                    LiceRecord.week == latest[1],
                    LiceRecord.avg_adult_female_lice > 0.5,
                )
            )).scalar() or 0
            total = stats[1] or 1
            pct_above = above / total

    # Use real SSB spot price
    from core.market.ssb_price_client import ssb_price_client
    real_spot = await ssb_price_client.get_current_spot()

    forecast = price_engine.predict_price(
        current_spot=real_spot or price_engine.latest_spot or 75.0,
        national_avg_lice=avg_lice,
        lice_trend="stable",
        pct_above_threshold=pct_above,
        biomass_vs_normal=1.0,
        horizon_weeks=horizon,
    )

    return {
        "horizon_weeks": forecast.horizon_weeks,
        "current_spot_nok": forecast.current_spot,
        "predicted_nok": forecast.predicted_price,
        "direction": forecast.direction,
        "confidence": forecast.confidence,
        "price_range_80": [forecast.price_lo80, forecast.price_hi80],
        "signals": {
            "lice": forecast.lice_signal,
            "supply": forecast.supply_signal,
            "seasonal": forecast.seasonal_signal,
            "combined": forecast.combined_signal,
        },
        "rationale": forecast.rationale,
        "data_provenance": DataProvenance.degraded(
            "SSB Table 03024 spot + salmon_price model",
            reason=(
                "inputs are the SSB spot and the local lice database; the price path "
                "itself is a model estimate, not a quoted market price"
            ),
            confidence=0.5 if real_spot else 0.2,
        ).to_dict(),
    }


@router.get("/seasonal")
async def seasonal_analysis():
    """Compare current price to seasonal expectation."""
    from core.market.salmon_price import price_engine
    result = price_engine.get_seasonal_analysis()
    if isinstance(result, dict):
        result.setdefault(
            "data_provenance",
            DataProvenance.degraded(
                "SSB Table 03024 (seasonal medians)",
                reason=(
                    "seasonal expectation derived from historical SSB medians — a "
                    "comparison baseline, not a quoted price"
                ),
                confidence=0.5,
            ).to_dict(),
        )
    return result


@router.get("/biomass")
async def biomass_supply():
    """National biomass and supply model."""
    from core.market.biomass_tracker import biomass_tracker
    await biomass_tracker.fetch_biomass_data()
    model = biomass_tracker.compute_supply_model()
    # Honesty (rules 1/3): the tracker prefers the real Fiskeridirektoratet
    # ArcGIS client and records which path ran; the supply metrics themselves
    # remain model estimates, so provenance is never "live".
    provenance = biomass_tracker.provenance()
    return {
        "total_biomass_tonnes": model.total_standing_biomass_tonnes,
        "biomass_vs_historical_pct": model.biomass_vs_historical_pct,
        "harvestable_tonnes": model.estimated_harvestable_tonnes,
        "weekly_harvest_estimate": model.estimated_weekly_harvest,
        "days_of_supply": model.days_of_supply,
        "supply_outlook": model.supply_outlook,
        "yoy_change_pct": model.yoy_change_pct,
        "pa_breakdown": model.pa_biomass,
        "data_provenance": provenance.to_dict(),
    }


@router.get("/exports")
async def export_data():
    """SSB salmon export statistics."""
    from core.market.ssb_exports import SSBClient
    ssb = SSBClient()
    try:
        summary = await ssb.get_export_summary()
    finally:
        await ssb.close()
    if isinstance(summary, dict):
        summary.setdefault(
            "data_provenance",
            from_records(
                [summary] if summary else [],
                live_source="SSB export statistics (Statistics Norway)",
                degraded_source="SSB export statistics",
                reason="SSB returned an empty export summary",
            ).to_dict(),
        )
    return summary


@router.get("/price-outlook", response_model=PriceOutlookResponse)
async def price_outlook(horizon: int = 4, scenarios: int = 1000):
    """
    ML ensemble price prediction with conformal uncertainty bands.
    Replaces the basic price-forecast for advanced consumers.
    """
    import structlog
    from core.market.data_provenance import DataProvenance

    log = structlog.get_logger("price_outlook")

    # Clamp inputs
    horizon = max(2, min(horizon, 20))
    scenarios = max(100, min(scenarios, 10000))

    # --- Phase 1: Lice market state from DB ---
    avg_lice = 0.15
    avg_mobile = 0.0
    avg_sessile = 0.0
    pct_above = 0.0
    cleaner_pct = 0.0

    try:
        async with get_async_session() as s:
            latest = (await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )).first()

            if latest:
                stats = (await s.execute(
                    select(
                        func.avg(LiceRecord.avg_adult_female_lice),
                        func.avg(LiceRecord.avg_mobile_lice),
                        func.avg(LiceRecord.avg_stationary_lice),
                        func.count(LiceRecord.id),
                    ).where(
                        LiceRecord.year == latest[0],
                        LiceRecord.week == latest[1],
                        LiceRecord.avg_adult_female_lice.isnot(None),
                    )
                )).one_or_none()

                if stats and stats[0] is not None:
                    avg_lice = float(stats[0] or 0.15)
                    avg_mobile = float(stats[1] or 0)
                    avg_sessile = float(stats[2] or 0)
                    total = stats[3] or 1

                    above = (await s.execute(
                        select(func.count(LiceRecord.id)).where(
                            LiceRecord.year == latest[0],
                            LiceRecord.week == latest[1],
                            LiceRecord.avg_adult_female_lice > 0.5,
                        )
                    )).scalar() or 0
                    pct_above = above / total

                    cleaner_count = (await s.execute(
                        select(func.count(LiceRecord.id)).where(
                            LiceRecord.year == latest[0],
                            LiceRecord.week == latest[1],
                            LiceRecord.has_cleaner_fish == True,
                        )
                    )).scalar() or 0
                    cleaner_pct = cleaner_count / total
    except Exception as exc:
        log.warning("price_outlook_db_lice_failed", error=str(exc))
        # Continue with defaults

    # --- Phase 2: SSB spot price + export trend ---
    _ssb_live = True
    spot = 75.0
    export_trend = 0.0
    futures_prem = 0.0

    try:
        from core.market.ssb_price_client import ssb_price_client
        spot = await ssb_price_client.get_current_spot()
        if spot <= 0:
            spot = 75.0
            _ssb_live = False
        recent_prices = await ssb_price_client.fetch_prices(n_weeks=26)
        export_trend = ssb_price_client.compute_export_volume_trend(recent_prices.prices)
    except Exception as exc:
        log.warning("price_outlook_ssb_failed", error=str(exc))
        spot = 75.0
        _ssb_live = False

    # --- Phase 3: ML prediction ---
    try:
        from core.market.price_ml import price_ensemble
        fc = price_ensemble.predict(
            current_spot=spot,
            horizon_weeks=horizon,
            national_avg_lice=avg_lice,
            pct_above_threshold=pct_above,
            avg_mobile_lice=avg_mobile,
            avg_sessile_lice=avg_sessile,
            cleaner_fish_pct=cleaner_pct,
            export_volume_trend=export_trend,
            futures_premium_pct=futures_prem,
            n_scenarios=scenarios,
        )
    except Exception as exc:
        log.warning("price_outlook_ml_failed", error=str(exc))
        # Return degraded spot-only response
        return {
            "horizon_weeks": horizon,
            "current_spot_nok": spot,
            "predicted_nok": spot,
            "direction": "flat",
            "confidence": 0.1,
            "bands": {"p95": [spot * 0.85, spot * 1.15], "p80": [spot * 0.90, spot * 1.10], "p50": [spot * 0.95, spot * 1.05]},
            "scenarios": {"p10": spot * 0.85, "p25": spot * 0.93, "p50": spot, "p75": spot * 1.07, "p90": spot * 1.15},
            "signals": {"lice": 0, "supply": 0, "seasonal": 0, "export": 0, "futures": 0, "combined": 0},
            "model": {"version": "degraded_fallback", "n_scenarios": 0, "mape_backtest": None, "accuracy_statement": "ML unavailable — showing spot price only"},
            "rationale": f"ML prediction failed ({exc.__class__.__name__}). Showing current SSB spot price as baseline.",
            "disclaimer": "This is a degraded response. ML models are unavailable.",
            "fallback": True,
            "data_provenance": DataProvenance.degraded("SSB Table 03024", f"ML unavailable: {exc.__class__.__name__}", confidence=0.1).to_dict(),
        }

    # --- Phase 4: Store prediction (non-critical) ---
    try:
        async with get_async_session() as s:
            s.add(PricePrediction(
                horizon_weeks=fc.horizon_weeks,
                current_spot_nok=fc.current_spot_nok,
                predicted_nok=fc.predicted_nok,
                direction=fc.direction,
                confidence=fc.confidence,
                price_lo95=fc.price_lo95,
                price_hi95=fc.price_hi95,
                price_lo80=fc.price_lo80,
                price_hi80=fc.price_hi80,
                price_lo50=fc.price_lo50,
                price_hi50=fc.price_hi50,
                lice_signal=fc.lice_signal,
                supply_signal=fc.supply_signal,
                seasonal_signal=fc.seasonal_signal,
                export_signal=fc.export_signal,
                futures_signal=fc.futures_signal,
                combined_signal=fc.combined_signal,
                model_version=fc.model_version,
                n_scenarios=fc.n_scenarios,
                mape_backtest=fc.mape_backtest,
                rationale=fc.rationale,
            ))
            await s.commit()
    except Exception as exc:
        log.warning("price_outlook_db_store_failed", error=str(exc))
        # Non-critical — prediction still returned to user

    return {
        "horizon_weeks": fc.horizon_weeks,
        "current_spot_nok": fc.current_spot_nok,
        "predicted_nok": fc.predicted_nok,
        "direction": fc.direction,
        "confidence": fc.confidence,
        "bands": {
            "p95": [fc.price_lo95, fc.price_hi95],
            "p80": [fc.price_lo80, fc.price_hi80],
            "p50": [fc.price_lo50, fc.price_hi50],
        },
        "scenarios": {
            "p10": fc.scenarios_p10,
            "p25": fc.scenarios_p25,
            "p50": fc.scenarios_p50,
            "p75": fc.scenarios_p75,
            "p90": fc.scenarios_p90,
        },
        "signals": {
            "lice": fc.lice_signal,
            "supply": fc.supply_signal,
            "seasonal": fc.seasonal_signal,
            "export": fc.export_signal,
            "futures": fc.futures_signal,
            "combined": fc.combined_signal,
        },
        "model": {
            "version": fc.model_version,
            "n_scenarios": fc.n_scenarios,
            "mape_backtest": fc.mape_backtest,
            "band_trust": fc.band_trust,
            "accuracy_statement": fc.accuracy_statement,
        },
        "rationale": fc.rationale,
        "disclaimer": fc.disclaimer,
        "data_provenance": (
            (
                DataProvenance.degraded(
                    f"SSB Table 03024 + price ensemble ({fc.model_version})",
                    "ML tiers unavailable — rule-based forecast",
                    confidence=0.4,
                )
                if fc.model_quality == "rule_based_fallback"
                else DataProvenance.live(
                    f"SSB Table 03024 + price ensemble ({fc.model_version})",
                    confidence=0.85,
                )
            )
            if _ssb_live
            else DataProvenance.degraded("SSB Table 03024", "SSB unreachable — using NOK 75.0 fallback", confidence=0.3)
        ).to_dict(),
    }


@router.get("/price-outlook/explain")
async def price_outlook_explain(horizon: int = 4):
    """TFT model interpretability — feature importance + temporal attention weights."""
    from core.market.tft_predictor import tft_predictor
    if not tft_predictor.is_available:
        raise HTTPException(
            status_code=503,
            detail="TFT model not available. Model weights not trained or PyTorch Forecasting missing.",
        )

    result = await tft_predictor.predict(horizon)
    if not result:
        raise HTTPException(
            status_code=502,
            detail="TFT prediction calculation failed.",
        )

    attention = tft_predictor.get_attention()
    return {
        "horizon_weeks": horizon,
        "predicted_nok": result["predicted_nok"],
        "model": "tft",
        "attention": attention,
        "top_drivers": sorted(
            [{"feature": k, "importance": v}
             for k, v in (attention or {}).get("encoder_variables", {}).items()],
            key=lambda x: x["importance"], reverse=True,
        )[:8] if attention else [],
    }


@router.get("/price-outlook/multi")
@cached(ttl=300, key_prefix="price_outlook_multi")
async def price_outlook_multi():
    """Price outlook across all horizons (for the Price Outlook widget)."""
    from core.market.price_ml import price_ensemble

    # Get market state once
    async with get_async_session() as s:
        latest = (await s.execute(
            select(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(1)
        )).first()

        avg_lice = 0.15
        pct_above = 0.0
        if latest:
            stats = (await s.execute(
                select(
                    func.avg(LiceRecord.avg_adult_female_lice),
                    func.count(LiceRecord.id),
                ).where(
                    LiceRecord.year == latest[0],
                    LiceRecord.week == latest[1],
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )
            )).one()
            avg_lice = float(stats[0] or 0.15)

            above = (await s.execute(
                select(func.count(LiceRecord.id)).where(
                    LiceRecord.year == latest[0],
                    LiceRecord.week == latest[1],
                    LiceRecord.avg_adult_female_lice > 0.5,
                )
            )).scalar() or 0
            pct_above = (above or 0) / max(stats[1] or 1, 1)

    # Real SSB spot price
    from core.market.ssb_price_client import ssb_price_client
    spot = await ssb_price_client.get_current_spot()
    if spot <= 0:
        spot = 75.0

    horizons = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
    results = []
    for h in horizons:
        fc = price_ensemble.predict(
            current_spot=spot,
            horizon_weeks=h,
            national_avg_lice=avg_lice,
            pct_above_threshold=pct_above,
            n_scenarios=200,  # lighter for multi-horizon
        )
        results.append({
            "horizon": h,
            "predicted": fc.predicted_nok,
            "lo80": fc.price_lo80,
            "hi80": fc.price_hi80,
            "lo95": fc.price_lo95,
            "hi95": fc.price_hi95,
            "direction": fc.direction,
            "mape": fc.mape_backtest,
            "combined": fc.combined_signal,
        })

    return {
        "current_spot_nok": round(spot, 1),
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "horizons": results,
        "data_provenance": DataProvenance.degraded(
            "SSB Table 03024 spot + price_ml ensemble",
            reason=(
                "multi-horizon paths are model estimates (Monte Carlo + rule-based "
                "signals), not quoted forward prices"
            ),
            confidence=0.5 if spot > 0 and spot != 75.0 else 0.2,
        ).to_dict(),
    }


@router.get("/futures-curve")
async def futures_curve():
    """Real salmon price history from SSB (replaces synthetic Fish Pool curve)."""
    from core.market.ssb_price_client import ssb_price_client
    history = await ssb_price_client.get_price_history(n_weeks=52)
    spot = await ssb_price_client.get_current_spot()
    return {
        "spot_nok": spot,
        "source": "SSB table 03024 (Statistics Norway)",
        "license": "CC BY 4.0",
        "history": history,
        "data_provenance": from_records(
            history,
            live_source="SSB Table 03024 (Statistics Norway)",
            degraded_source="SSB Table 03024",
            reason="SSB returned no price rows",
        ).to_dict(),
    }


@router.get("/hedger-signals")
async def hedger_signals():
    """Latest Market Hedger Agent signals."""
    async with get_async_session() as s:
        signals = (await s.execute(
            select(Signal)
            .where(Signal.rationale.like("[HEDGER]%"))
            # WS-20: the hedger also writes LONG/SHORT rows on listed shares
            # (MOWI/SALM/LSG/GSF); only the salmon-price rows are served.
            .where(Signal.ticker == "SALMON_SPOT")
            .order_by(Signal.created_at.desc())
            .limit(20)
        )).scalars().all()

    return [
        {
            "id": sig.id,
            "ticker": sig.ticker,
            "direction": sig.direction,
            "strength": sig.strength,
            "rationale": sig.rationale,
            "status": sig.status,
            "created_at": sig.created_at.isoformat() if sig.created_at else None,
        }
        for sig in signals
    ]


@router.get("/prediction-history")
async def prediction_history(horizon: int = 4, days: int = 30):
    """Historical ML price predictions for accuracy tracking."""
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    async with get_async_session() as s:
        preds = (await s.execute(
            select(PricePrediction)
            .where(
                PricePrediction.horizon_weeks == horizon,
                PricePrediction.created_at >= cutoff,
            )
            .order_by(PricePrediction.created_at.desc())
            .limit(100)
        )).scalars().all()

    return [
        {
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "predicted_nok": p.predicted_nok,
            "current_spot_nok": p.current_spot_nok,
            "direction": p.direction,
            "combined_signal": p.combined_signal,
            "mape_backtest": p.mape_backtest,
            "model_version": p.model_version,
        }
        for p in preds
    ]


@router.get("/ssb-price-history")
async def ssb_price_history(weeks: int = 52):
    """Real SSB salmon export price history (table 03024)."""
    from core.market.ssb_price_client import ssb_price_client
    weeks = max(4, min(weeks, 1400))
    history = await ssb_price_client.get_price_history(n_weeks=weeks)
    spot = await ssb_price_client.get_current_spot()
    return {
        "spot_nok": spot,
        "n_weeks": len(history),
        "source": "SSB table 03024 (Statistics Norway)",
        "license": "CC BY 4.0",
        "history": history,
        "data_provenance": from_records(
            history,
            live_source="SSB Table 03024 (Statistics Norway)",
            degraded_source="SSB Table 03024",
            reason="SSB returned no price rows",
        ).to_dict(),
    }


@router.get("/ssb-seasonal")
async def ssb_seasonal_analysis():
    """Real seasonal pattern computed from 6+ years of SSB data."""
    from core.market.ssb_price_client import ssb_price_client
    bulk = await ssb_price_client.fetch_bulk_history(start_year=2020)
    pattern = ssb_price_client.compute_seasonal_pattern(bulk.prices)
    current_week = dt.datetime.now(dt.UTC).isocalendar()[1]
    spot = await ssb_price_client.get_current_spot()
    seasonal_expected = pattern.get(current_week, 75)
    deviation_pct = (spot - seasonal_expected) / seasonal_expected * 100 if seasonal_expected > 0 else 0
    return {
        "seasonal_pattern": pattern,
        "current_week": current_week,
        "current_spot": spot,
        "seasonal_expected": round(seasonal_expected, 1),
        "deviation_pct": round(deviation_pct, 1),
        "data_years": f"2020-{dt.datetime.now(dt.UTC).year}",
        "source": "SSB table 03024",
        "data_provenance": from_records(
            pattern,
            live_source="SSB Table 03024 (Statistics Norway)",
            degraded_source="SSB Table 03024",
            reason="SSB returned no rows to compute a seasonal pattern from",
        ).to_dict(),
    }


@router.get("/export-destinations")
async def export_destinations(months: int = 12):
    """Salmon export breakdown by destination country (table 08799)."""
    from core.market.ssb_exports import SSBClient
    ssb = SSBClient()
    try:
        breakdown = await ssb.get_destination_breakdown(months=months)
        series = await ssb.get_monthly_volume_series(months=months)
    finally:
        await ssb.close()
    return {
        "months_analyzed": months,
        "n_destinations": len(breakdown),
        "destinations": breakdown,
        "monthly_series": series,
        "source": "SSB table 08799 (Statistics Norway)",
        "license": "CC BY 4.0",
        "data_provenance": from_records(
            breakdown,
            live_source="SSB Table 08799 (Statistics Norway)",
            degraded_source="SSB Table 08799",
            reason="SSB returned no destination rows",
        ).to_dict(),
    }


@router.get("/equity-prices")
async def equity_prices():
    """
    Latest prices for Oslo-listed salmon equities + Fish Pool Index.
    Used by the PairsEngine for daily spread calculation.
    Oslo Børs tickers: MOWI.OL, SALM.OL, LSG.OL, GSF.OL, BAKKA.OL
    """
    from core.market.salmon_price import get_latest_prices
    prices = await get_latest_prices()
    return {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "source": "Yahoo Finance (unofficial, ~15min delay) + SSB fallback",
        "exchange": "Oslo Børs (OSE) — .OL suffix",
        "prices_nok": {k: v for k, v in prices.items() if k not in ("FPI_EUR", "SSB_NOK")},
        "benchmarks": {
            "fpi_eur_per_kg": prices.get("FPI_EUR"),
            "ssb_nok_per_kg": prices.get("SSB_NOK"),
        },
        "all_prices": prices,
    }


@router.get("/spot-price")
async def market_spot_price(source: str = "auto"):
    """Get current salmon spot price from priority cascade."""
    from core.market.price_feed_hub import price_feed_hub
    return await price_feed_hub.get_spot_price(source)


@router.get("/forward-curve")
async def market_forward_curve(months: int = 12):
    """Synthesized forward curve from SSB seasonal patterns."""
    from core.market.price_feed_hub import price_feed_hub
    return await price_feed_hub.get_forward_curve(months)


@router.get("/feed-status")
async def market_feed_status():
    """Health check and status of all configured price feeds."""
    from core.market.price_feed_hub import price_feed_hub
    return await price_feed_hub.list_feeds()


# ══════════════════════════════════════════════════════════════════════
# EUMOFA — European Market Observatory for Fisheries and Aquaculture
# ══════════════════════════════════════════════════════════════════════

@router.get("/eumofa/salmon-prices")
@cached(ttl=21600, key_prefix="eumofa_salmon_prices")
async def eumofa_salmon_prices():
    """Weekly European salmon prices by country from EUMOFA.

    Returns import prices across major EU markets (France, Poland,
    Germany, Italy, etc.) with differentials vs Norway origin price.
    Falls back to SSB + EU premium model if EUMOFA API is unavailable.
    """
    from core.market.eumofa_client import eumofa_client
    return await eumofa_client.get_salmon_prices()


@router.get("/eumofa/trade-flows")
@cached(ttl=21600, key_prefix="eumofa_trade_flows")
async def eumofa_trade_flows():
    """Salmon import/export volumes by EU country from EUMOFA.

    Returns trade flow data showing import volumes, values, and
    average prices per country. Used for understanding European
    demand distribution and identifying premium markets.
    """
    from core.market.eumofa_client import eumofa_client
    return await eumofa_client.get_trade_flows()


# ══════════════════════════════════════════════════════════════════════
# Euronext Salmon Futures (ESF) — Replaced Fish Pool NOK futures end-2024
# Settlement against weekly SISALMONI spot index.
# FPI still published at fishpool.eu as settlement price.
# ══════════════════════════════════════════════════════════════════════

futures_router = APIRouter(prefix="/api/futures", tags=["futures"])


@futures_router.get("/forward-curve")
@cached(ttl=600, key_prefix="futures_forward_curve")
async def futures_forward_curve(months: int = 12):
    """
    Full salmon forward curve with NOK conversion.
    Priority: Fish Pool live forward prices -> SSB seasonal synthesis fallback.
    Includes EUR->NOK conversion, spot reference, and data provenance.
    """
    from core.market.euronext_futures import euronext_futures_engine
    months = max(3, min(months, 24))
    return await euronext_futures_engine.get_forward_curve(months=months)


from core.market.provenance_envelope import with_provenance


@futures_router.get("/basis")
@cached(ttl=600, key_prefix="futures_basis")
@with_provenance(
    "Euronext ESF / Fish Pool (licensed exchange data)",
    degraded_reason=(
        "basis is derived from the forward curve and spot series available to this "
        "deployment; a missing exchange feed degrades it, it is not a quoted price"
    ),
)
async def futures_basis():
    """
    Spot vs forward basis analysis.
    Positive basis = contango (forward > spot).
    Negative basis = backwardation (forward < spot).
    """
    from core.market.euronext_futures import euronext_futures_engine
    return await euronext_futures_engine.get_basis_analysis()


@futures_router.get("/settlement")
@cached(ttl=600, key_prefix="futures_settlement")
async def futures_settlement():
    """
    Latest FPI (Fish Pool Index) settlement data.
    The FPI is used for cash settlement of Euronext ESF contracts.
    Falls back to SSB weekly spot price as proxy when FPI unavailable.
    """
    from core.market.euronext_futures import euronext_futures_engine
    return await euronext_futures_engine.get_settlement_data()


@futures_router.get("/term-structure")
@cached(ttl=600, key_prefix="futures_term_structure")
@with_provenance(
    "Euronext ESF / Fish Pool (licensed exchange data)",
    degraded_reason=(
        "term structure is derived from the forward curve available to this "
        "deployment; a missing exchange feed degrades it"
    ),
)
async def futures_term_structure():
    """
    Contango/backwardation term structure analysis.
    Includes slope, curvature, near vs far term averages,
    and visualization data for charting.
    """
    from core.market.euronext_futures import euronext_futures_engine
    return await euronext_futures_engine.get_term_structure()


# ── EUMOFA Trade Flows ───────────────────────────────────────────────

@router.get("/eumofa/imports/{country}")
async def eumofa_imports_by_country(country: str):
    """EU salmon import volumes for a specific country (e.g. FR, DE, ES)."""
    from core.market.eumofa_trade_client import eumofa_trade_client
    return await eumofa_trade_client.fetch_salmon_imports_by_country(country.upper())


@router.get("/eumofa/exports/{origin}")
async def eumofa_exports_by_origin(origin: str):
    """Salmon export volumes from an origin country (e.g. NO, CL, GB)."""
    from core.market.eumofa_trade_client import eumofa_trade_client
    return await eumofa_trade_client.fetch_salmon_exports_by_origin(origin.upper())


@router.get("/eumofa/trade-summary")
async def eumofa_trade_summary():
    """Comprehensive bilateral EU salmon trade flow summary."""
    from core.market.eumofa_trade_client import eumofa_trade_client
    return await eumofa_trade_client.fetch_trade_flow_summary()
