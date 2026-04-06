"""
TFT Data Pipeline
==================
Builds the training/inference DataFrame for the Temporal Fusion Transformer.
Fuses SSB weekly salmon prices with BarentsWatch national lice aggregates.

Output: pandas DataFrame with one row per week, ~22 features, ready for
pytorch_forecasting.TimeSeriesDataSet.

Sources:
  - SSB Table 03024 (salmon export prices, NOK/kg) — 1,300+ weeks
  - LiceRecord DB table (national weekly averages) — 2012+
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd
import structlog

from sqlalchemy import select, func
from core.models import LiceRecord

log = structlog.get_logger(__name__)

# Default lice values for weeks before BarentsWatch data (pre-2012)
DEFAULT_LICE = 0.15
DEFAULT_TEMP = 8.0


async def build_weekly_dataframe(start_year: int = 2012) -> pd.DataFrame:
    """
    Build the unified weekly DataFrame from SSB prices + lice DB.

    Returns DataFrame with columns:
      time_idx, group_id, price_nok, volume_tonnes,
      week_of_year, month, sin_week, cos_week,
      avg_adult_lice, avg_mobile_lice, avg_sessile_lice,
      pct_above_05, cleaner_fish_pct, sea_temp_avg,
      price_lag_1, price_lag_4, price_lag_12,
      price_return_4w, volume_lag_1, log_price
    """
    # ── 1. Fetch SSB price history ────────────────────────────────────
    from core.market.ssb_price_client import ssb_price_client
    ssb_data = await ssb_price_client.fetch_bulk_history(start_year=start_year)

    if not ssb_data or not ssb_data.prices:
        log.error("tft_data.no_ssb_prices")
        return pd.DataFrame()

    # Build price DataFrame
    price_rows = []
    for p in ssb_data.prices:
        price_rows.append({
            "year": p.year,
            "week": p.week,
            "price_nok": p.price_nok_kg,
            "volume_tonnes": getattr(p, "volume_tonnes", 0) or 0,
        })

    df_price = pd.DataFrame(price_rows)
    df_price = df_price.sort_values(["year", "week"]).reset_index(drop=True)
    df_price = df_price.drop_duplicates(subset=["year", "week"], keep="last")

    # ── 2. Aggregate national lice data ───────────────────────────────
    from sqlalchemy import case, Integer
    from core.async_db import get_async_session
    async with get_async_session() as s:
        rows = (await s.execute(
            select(
                LiceRecord.year,
                LiceRecord.week,
                func.avg(LiceRecord.avg_adult_female_lice),
                func.avg(LiceRecord.avg_mobile_lice),
                func.avg(LiceRecord.avg_stationary_lice),
                func.avg(LiceRecord.sea_temp_c),
                func.sum(case((LiceRecord.has_cleaner_fish == True, 1), else_=0)),
                func.count(LiceRecord.id),
            )
            .where(LiceRecord.avg_adult_female_lice.isnot(None))
            .group_by(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year, LiceRecord.week)
        )).all()

    lice_rows = []
    for r in rows:
        n = max(r[7], 1)
        lice_rows.append({
            "year": r[0],
            "week": r[1],
            "avg_adult_lice": float(r[2] or DEFAULT_LICE),
            "avg_mobile_lice": float(r[3] or 0),
            "avg_sessile_lice": float(r[4] or 0),
            "sea_temp_avg": float(r[5] or DEFAULT_TEMP),
            "cleaner_fish_pct": float((r[6] or 0) / n),
        })

    df_lice = pd.DataFrame(lice_rows) if lice_rows else pd.DataFrame()

    # Also compute pct_above_05
    if not df_lice.empty:
        above_rows = []
        async with get_async_session() as s:
            above_data = (await s.execute(
                select(
                    LiceRecord.year,
                    LiceRecord.week,
                    func.count(LiceRecord.id),
                )
                .where(
                    LiceRecord.avg_adult_female_lice > 0.5,
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )
                .group_by(LiceRecord.year, LiceRecord.week)
            )).all()

        total_by_week = {}
        async with get_async_session() as s:
            total_data = (await s.execute(
                select(
                    LiceRecord.year,
                    LiceRecord.week,
                    func.count(LiceRecord.id),
                )
                .where(LiceRecord.avg_adult_female_lice.isnot(None))
                .group_by(LiceRecord.year, LiceRecord.week)
            )).all()
            for t in total_data:
                total_by_week[(t[0], t[1])] = t[2]

        above_map = {(r[0], r[1]): r[2] for r in above_data}
        keys = list(zip(df_lice["year"], df_lice["week"]))
        df_lice["pct_above_05"] = [above_map.get(k, 0) / max(total_by_week.get(k, 1), 1) for k in keys]

    # ── 3. Merge ──────────────────────────────────────────────────────
    df = df_price.copy()
    if not df_lice.empty:
        df = df.merge(df_lice, on=["year", "week"], how="left")

    # Fill missing lice data with defaults
    for col, default in [
        ("avg_adult_lice", DEFAULT_LICE),
        ("avg_mobile_lice", 0.0),
        ("avg_sessile_lice", 0.0),
        ("sea_temp_avg", DEFAULT_TEMP),
        ("cleaner_fish_pct", 0.0),
        ("pct_above_05", 0.0),
    ]:
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].fillna(default)

    # ── 4. Feature engineering ────────────────────────────────────────
    df["time_idx"] = range(len(df))
    df["group_id"] = "salmon_national"

    # Calendar features (known in advance)
    # Calendar features — compute numeric sin/cos first, then convert to string for categoricals
    week_num = df["week"].astype(int)
    df["sin_week"] = np.sin(2 * math.pi * week_num / 52)
    df["cos_week"] = np.cos(2 * math.pi * week_num / 52)
    df["week_of_year"] = week_num.astype(str)
    df["month"] = df.apply(
        lambda r: str(dt.date.fromisocalendar(int(r["year"]), max(1, min(52, int(r["week"]))), 1).month),
        axis=1,
    )

    # Lag features
    df["price_lag_1"] = df["price_nok"].shift(1)
    df["price_lag_4"] = df["price_nok"].shift(4)
    df["price_lag_12"] = df["price_nok"].shift(12)
    df["price_return_4w"] = (df["price_nok"] - df["price_lag_4"]) / df["price_lag_4"].clip(lower=1)
    df["volume_lag_1"] = df["volume_tonnes"].shift(1)
    df["log_price"] = np.log(df["price_nok"].clip(lower=1))

    # Fill volume if missing
    df["volume_tonnes"] = df["volume_tonnes"].fillna(0)

    # Drop first 12 rows (missing lag features)
    df = df.iloc[12:].reset_index(drop=True)
    df["time_idx"] = range(len(df))

    # Ensure no NaNs in critical columns
    df = df.ffill().bfill()

    log.info("tft_data.built", rows=len(df), years=f"{df['year'].min()}-{df['year'].max()}",
             price_range=f"{df['price_nok'].min():.1f}-{df['price_nok'].max():.1f}")

    return df


def get_dataset_config() -> dict:
    """Return the TimeSeriesDataSet configuration for TFT."""
    return {
        "time_idx": "time_idx",
        "target": "price_nok",
        "group_ids": ["group_id"],
        "max_encoder_length": 52,
        "max_prediction_length": 20,
        "static_categoricals": ["group_id"],
        "time_varying_known_reals": ["sin_week", "cos_week"],
        "time_varying_known_categoricals": ["week_of_year", "month"],
        "time_varying_unknown_reals": [
            "price_nok", "volume_tonnes",
            "avg_adult_lice", "avg_mobile_lice", "avg_sessile_lice",
            "pct_above_05", "cleaner_fish_pct", "sea_temp_avg",
            "price_lag_1", "price_lag_4", "price_lag_12",
            "price_return_4w", "volume_lag_1", "log_price",
        ],
        "add_relative_time_idx": True,
        "add_target_scales": True,
        "add_encoder_length": True,
    }
