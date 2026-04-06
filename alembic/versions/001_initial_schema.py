"""Initial schema — 19 tables from core.models + core.bloom.models.

Revision ID: 001
Revises: None
Create Date: 2026-03-31
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── localities ────────────────────────────────────────────────────
    op.create_table(
        "localities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("locality_no", sa.Integer, unique=True, index=True),
        sa.Column("name", sa.String(256)),
        sa.Column("municipality", sa.String(128)),
        sa.Column("county", sa.String(128)),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("owner_company", sa.String(256)),
        sa.Column("production_area", sa.Integer),
        sa.Column("pa_color", sa.String(16)),
        sa.Column("updated_at", sa.DateTime),
    )

    # ── lice_records ─────────────────────────────────────────────────
    op.create_table(
        "lice_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("locality_no", sa.Integer, sa.ForeignKey("localities.locality_no")),
        sa.Column("year", sa.Integer),
        sa.Column("week", sa.Integer),
        sa.Column("avg_adult_female_lice", sa.Float),
        sa.Column("avg_mobile_lice", sa.Float),
        sa.Column("avg_stationary_lice", sa.Float),
        sa.Column("has_cleaner_fish", sa.Boolean),
        sa.Column("sea_temp_c", sa.Float),
        sa.Column("fetched_at", sa.DateTime),
        sa.UniqueConstraint("locality_no", "week", "year"),
    )
    op.create_index("ix_lice_lookup", "lice_records", ["locality_no", "year", "week"])

    # ── company_exposure ─────────────────────────────────────────────
    op.create_table(
        "company_exposure",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(16)),
        sa.Column("company_name", sa.String(256)),
        sa.Column("locality_no", sa.Integer, sa.ForeignKey("localities.locality_no")),
        sa.Column("estimated_biomass_tonnes", sa.Float),
        sa.Column("weight", sa.Float),
    )

    # ── signals ──────────────────────────────────────────────────────
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("ticker", sa.String(16)),
        sa.Column("direction", sa.String(8)),
        sa.Column("strength", sa.Float),
        sa.Column("lice_score", sa.Float),
        sa.Column("exposure_score", sa.Float),
        sa.Column("price_target", sa.Float),
        sa.Column("stop_loss", sa.Float),
        sa.Column("rationale", sa.Text),
        sa.Column("status", sa.String(16)),
        sa.Column("confirmed_by_user", sa.Boolean),
        sa.Column("confirmed_at", sa.DateTime),
    )

    # ── orders ───────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id")),
        sa.Column("created_at", sa.DateTime),
        sa.Column("ticker", sa.String(16)),
        sa.Column("side", sa.String(8)),
        sa.Column("quantity", sa.Integer),
        sa.Column("price", sa.Float),
        sa.Column("order_type", sa.String(16)),
        sa.Column("broker", sa.String(32)),
        sa.Column("status", sa.String(16)),
        sa.Column("fill_price", sa.Float),
        sa.Column("filled_at", sa.DateTime),
        sa.Column("user_consent", sa.Boolean),
        sa.Column("consent_timestamp", sa.DateTime),
    )

    # ── audit_log ────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime),
        sa.Column("event_type", sa.String(64)),
        sa.Column("actor", sa.String(64)),
        sa.Column("detail", sa.Text),
        sa.Column("ip_address", sa.String(45)),
    )

    # ── performance_fees ─────────────────────────────────────────────
    op.create_table(
        "performance_fees",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("period_start", sa.DateTime),
        sa.Column("period_end", sa.DateTime),
        sa.Column("gross_profit", sa.Float),
        sa.Column("fee_rate", sa.Float),
        sa.Column("fee_amount", sa.Float),
        sa.Column("tier", sa.String(16)),
    )

    # ── stage_forecasts ──────────────────────────────────────────────
    op.create_table(
        "stage_forecasts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("locality_no", sa.Integer, sa.ForeignKey("localities.locality_no")),
        sa.Column("forecast_year", sa.Integer),
        sa.Column("forecast_week", sa.Integer),
        sa.Column("horizon_weeks", sa.Integer),
        sa.Column("pred_sessile", sa.Float),
        sa.Column("pred_mobile", sa.Float),
        sa.Column("pred_adult_female", sa.Float),
        sa.Column("pred_total", sa.Float),
        sa.Column("adult_female_lo80", sa.Float),
        sa.Column("adult_female_hi80", sa.Float),
        sa.Column("prob_exceed_threshold", sa.Float),
        sa.Column("trend", sa.String(16)),
        sa.Column("pressure_index", sa.Float),
        sa.Column("confidence", sa.Float),
    )

    # ── users ────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(256), unique=True),
        sa.Column("hashed_password", sa.String(256)),
        sa.Column("full_name", sa.String(256)),
        sa.Column("company", sa.String(256)),
        sa.Column("role", sa.String(32)),
        sa.Column("tier", sa.String(32)),
        sa.Column("is_active", sa.Boolean),
        sa.Column("created_at", sa.DateTime),
        sa.Column("locality_access", sa.Text),
    )

    # ── subscriptions ────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("tier", sa.String(32)),
        sa.Column("started_at", sa.DateTime),
        sa.Column("expires_at", sa.DateTime),
        sa.Column("is_active", sa.Boolean),
        sa.Column("monthly_price_nok", sa.Float),
        sa.Column("api_calls_month", sa.Integer),
        sa.Column("api_calls_limit", sa.Integer),
    )

    # ── treatment_recommendations ────────────────────────────────────
    op.create_table(
        "treatment_recommendations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("locality_no", sa.Integer, sa.ForeignKey("localities.locality_no")),
        sa.Column("urgency", sa.String(16)),
        sa.Column("recommended_action", sa.Text),
        sa.Column("treatment_type", sa.String(64)),
        sa.Column("optimal_timing_week", sa.Integer),
        sa.Column("estimated_cost_nok", sa.Float),
        sa.Column("estimated_mortality_pct", sa.Float),
        sa.Column("lice_reduction_expected_pct", sa.Float),
        sa.Column("rationale", sa.Text),
        sa.Column("status", sa.String(16)),
    )

    # ── supply_forecasts ─────────────────────────────────────────────
    op.create_table(
        "supply_forecasts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("production_area", sa.Integer),
        sa.Column("ticker", sa.String(16)),
        sa.Column("forecast_year", sa.Integer),
        sa.Column("forecast_week", sa.Integer),
        sa.Column("horizon_weeks", sa.Integer),
        sa.Column("predicted_harvest_tonnes", sa.Float),
        sa.Column("harvest_lo80", sa.Float),
        sa.Column("harvest_hi80", sa.Float),
        sa.Column("predicted_quality_score", sa.Float),
        sa.Column("lice_impact_on_quality_pct", sa.Float),
        sa.Column("supply_risk_level", sa.String(16)),
        sa.Column("contract_risk_flag", sa.Boolean),
        sa.Column("rationale", sa.Text),
    )

    # ── harvest_timing ───────────────────────────────────────────────
    op.create_table(
        "harvest_timing",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("locality_no", sa.Integer, sa.ForeignKey("localities.locality_no")),
        sa.Column("ticker", sa.String(16)),
        sa.Column("current_biomass_kg", sa.Float),
        sa.Column("optimal_harvest_week", sa.Integer),
        sa.Column("optimal_harvest_year", sa.Integer),
        sa.Column("reason", sa.Text),
        sa.Column("harvest_now_value_nok_per_kg", sa.Float),
        sa.Column("harvest_optimal_value_nok_per_kg", sa.Float),
        sa.Column("value_difference_pct", sa.Float),
        sa.Column("lice_risk_if_wait", sa.String(16)),
        sa.Column("treatment_probability_if_wait", sa.Float),
    )

    # ── price_predictions ────────────────────────────────────────────
    op.create_table(
        "price_predictions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("horizon_weeks", sa.Integer),
        sa.Column("current_spot_nok", sa.Float),
        sa.Column("predicted_nok", sa.Float),
        sa.Column("direction", sa.String(16)),
        sa.Column("confidence", sa.Float),
        sa.Column("price_lo95", sa.Float),
        sa.Column("price_hi95", sa.Float),
        sa.Column("price_lo80", sa.Float),
        sa.Column("price_hi80", sa.Float),
        sa.Column("price_lo50", sa.Float),
        sa.Column("price_hi50", sa.Float),
        sa.Column("lice_signal", sa.String(16)),
        sa.Column("supply_signal", sa.String(16)),
        sa.Column("seasonal_signal", sa.String(16)),
        sa.Column("export_signal", sa.String(16)),
        sa.Column("futures_signal", sa.String(16)),
        sa.Column("combined_signal", sa.String(32)),
        sa.Column("model_version", sa.String(64)),
        sa.Column("n_scenarios", sa.Integer),
        sa.Column("mape_backtest", sa.Float),
        sa.Column("rationale", sa.Text),
    )

    # ── futures_snapshots ────────────────────────────────────────────
    op.create_table(
        "futures_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fetched_at", sa.DateTime),
        sa.Column("spot_nok", sa.Float),
        sa.Column("curve_shape", sa.String(16)),
        sa.Column("avg_premium_pct", sa.Float),
        sa.Column("contracts_json", sa.Text),
    )

    # ── ssb_weekly_prices ────────────────────────────────────────────
    op.create_table(
        "ssb_weekly_prices",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("year", sa.Integer),
        sa.Column("week", sa.Integer),
        sa.Column("price_nok_kg", sa.Float),
        sa.Column("volume_tonnes", sa.Float),
        sa.Column("source", sa.String(32)),
        sa.Column("fetched_at", sa.DateTime),
        sa.UniqueConstraint("year", "week"),
    )

    # ── export_volumes ───────────────────────────────────────────────
    op.create_table(
        "export_volumes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("year", sa.Integer),
        sa.Column("month", sa.Integer),
        sa.Column("volume_tonnes", sa.Float),
        sa.Column("value_nok_millions", sa.Float),
        sa.Column("destination", sa.String(128)),
        sa.Column("source", sa.String(32)),
        sa.Column("fetched_at", sa.DateTime),
    )

    # ── chlorophyll_readings (bloom) ─────────────────────────────────
    op.create_table(
        "chlorophyll_readings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.DateTime),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("grid_cell_id", sa.String(32)),
        sa.Column("chl_a_mg_m3", sa.Float),
        sa.Column("dataset_id", sa.String(128)),
        sa.Column("fetched_at", sa.DateTime),
        sa.UniqueConstraint("date", "grid_cell_id"),
    )
    op.create_index("ix_chlorophyll_date", "chlorophyll_readings", ["date"])

    # ── bloom_risk_assessments ───────────────────────────────────────
    op.create_table(
        "bloom_risk_assessments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("locality_no", sa.Integer, sa.ForeignKey("localities.locality_no")),
        sa.Column("assessed_at", sa.DateTime),
        sa.Column("chl_a_value", sa.Float),
        sa.Column("sst_value", sa.Float),
        sa.Column("chl_a_trend", sa.Float),
        sa.Column("risk_level", sa.String(16)),
        sa.Column("risk_score", sa.Float),
        sa.Column("nearest_grid_cell_id", sa.String(32)),
        sa.Column("contributing_factors", sa.Text),
    )
    op.create_index(
        "ix_bloom_risk_lookup", "bloom_risk_assessments",
        ["locality_no", "assessed_at"],
    )

    # ── bloom_alerts ─────────────────────────────────────────────────
    op.create_table(
        "bloom_alerts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("locality_no", sa.Integer, sa.ForeignKey("localities.locality_no")),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("risk_level", sa.String(16)),
        sa.Column("sent_at", sa.DateTime),
        sa.Column("channel", sa.String(16)),
        sa.Column("delivery_status", sa.String(16)),
        sa.Column("message_text", sa.Text),
    )
    op.create_index("ix_bloom_alerts_lookup", "bloom_alerts", ["locality_no", "sent_at"])


def downgrade() -> None:
    op.drop_table("bloom_alerts")
    op.drop_table("bloom_risk_assessments")
    op.drop_table("chlorophyll_readings")
    op.drop_table("export_volumes")
    op.drop_table("ssb_weekly_prices")
    op.drop_table("futures_snapshots")
    op.drop_table("price_predictions")
    op.drop_table("harvest_timing")
    op.drop_table("supply_forecasts")
    op.drop_table("treatment_recommendations")
    op.drop_table("subscriptions")
    op.drop_table("users")
    op.drop_table("stage_forecasts")
    op.drop_table("performance_fees")
    op.drop_table("audit_log")
    op.drop_table("orders")
    op.drop_table("signals")
    op.drop_table("company_exposure")
    op.drop_table("lice_records")
    op.drop_table("localities")
