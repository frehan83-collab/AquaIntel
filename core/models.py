"""SQLAlchemy ORM models for AquaIntel."""
from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Boolean, Text, ForeignKey,
    UniqueConstraint, Index, create_engine, event, text, func,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config.settings import settings
from core.source_lineage import LICE_SOURCE_UNVERIFIED


def ensure_sqlite_dir(url: str) -> None:
    """Create the parent directory of a SQLite file URL if missing.

    Fresh clones and CI runners have no data/ directory; sqlite otherwise
    fails with 'unable to open database file'. No-op for postgres/memory.
    """
    if not url.startswith("sqlite"):
        return
    path = url.split("///")[-1]
    if path and path != ":memory:" and not path.startswith("file:"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)


Base = declarative_base()


class Locality(Base):
    """A single fish-farming locality."""
    __tablename__ = "localities"

    id = Column(Integer, primary_key=True)
    locality_no = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(256), nullable=False)
    municipality = Column(String(128))
    county = Column(String(128))
    latitude = Column(Float)
    longitude = Column(Float)
    owner_company = Column(String(256))  # mapped company ticker
    production_area = Column(Integer, index=True)  # PA 1-13 — indexed for PA-level queries
    pa_color = Column(String(16))  # green/yellow/red traffic-light
    updated_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))

    # ── Offshore farm support (Session 28) ─────────────────────────
    # Reference: SalMar Ocean Farm 1 (operational 2017), Ocean Farm 2 (construction)
    farm_type = Column(String(32), default="inshore")  # inshore | offshore | semi_offshore
    max_depth_m = Column(Float, nullable=True)  # Net pen depth in meters
    current_speed_avg_ms = Column(Float, nullable=True)  # Average current speed m/s
    wave_exposure_class = Column(String(32), nullable=True)  # sheltered|moderate|exposed|ocean
    structural_stress_rating = Column(Float, nullable=True)  # 0.0–1.0 risk score
    cage_volume_m3 = Column(Float, nullable=True)  # Cage volume in cubic meters
    distance_to_shore_km = Column(Float, nullable=True)  # Distance to nearest shore

    lice_records = relationship("LiceRecord", back_populates="locality")

    def __repr__(self):
        return f"<Locality {self.locality_no} {self.name}>"


class LiceRecord(Base):
    """Per-locality lice count snapshot."""
    __tablename__ = "lice_records"
    __table_args__ = (
        UniqueConstraint("locality_no", "week", "year", name="uq_lice_week"),
        Index("ix_lice_lookup", "locality_no", "year", "week"),
        # Serves /api/lice/summary (year/week predicates + latest-week ORDER BY);
        # migration 015 back-fills Alembic-managed databases.
        Index("ix_lice_year_week", "year", "week"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    locality_no = Column(Integer, ForeignKey("localities.locality_no"), nullable=False)
    year = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    avg_adult_female_lice = Column(Float)
    avg_mobile_lice = Column(Float)
    avg_stationary_lice = Column(Float)
    has_cleaner_fish = Column(Boolean, default=False)
    sea_temp_c = Column(Float)
    fetched_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    # WS-1 lineage marker: 'barentswatch' (agents/data_ingest.py), 'demo_seed'
    # (core/demo_seed.py) or 'unverified' (server default; pre-WS-1 rows). One
    # vocabulary in core/source_lineage.py; NULL/unknown never counts as real.
    # Alembic 019 adds and backfills it.
    source = Column(
        String(32),
        nullable=False,
        default=LICE_SOURCE_UNVERIFIED,
        server_default=LICE_SOURCE_UNVERIFIED,
    )

    locality = relationship("Locality", back_populates="lice_records")


class CompanyExposure(Base):
    """Maps a company/ticker to its farm localities with capacity weight."""
    __tablename__ = "company_exposure"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(16), nullable=False, index=True)  # MOWI, SALM, LSG
    company_name = Column(String(256))
    locality_no = Column(Integer, ForeignKey("localities.locality_no"), nullable=False)
    estimated_biomass_tonnes = Column(Float, default=0.0)
    weight = Column(Float, default=1.0)  # relative weight within company


class Signal(Base):
    """Generated trading signal."""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    ticker = Column(String(16), nullable=False, index=True)
    direction = Column(String(8))  # LONG / SHORT
    strength = Column(Float)  # 0-1 composite score
    lice_score = Column(Float)
    exposure_score = Column(Float)
    price_target = Column(Float)
    stop_loss = Column(Float)
    rationale = Column(Text)
    status = Column(String(16), default="pending")  # pending/confirmed/executed/expired
    confirmed_by_user = Column(Boolean, default=False)
    confirmed_at = Column(DateTime)


class Order(Base):
    """Execution log for paper and live orders."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, ForeignKey("signals.id"), index=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC), index=True)
    ticker = Column(String(16), nullable=False, index=True)
    side = Column(String(8))  # BUY / SELL
    quantity = Column(Integer)
    price = Column(Float)
    order_type = Column(String(16), default="LIMIT")
    broker = Column(String(32), default="paper")
    status = Column(String(16), default="pending")
    fill_price = Column(Float)
    filled_at = Column(DateTime)
    user_consent = Column(Boolean, default=False)
    consent_timestamp = Column(DateTime)


class AuditLog(Base):
    """Immutable compliance audit trail — tracks user actions across the platform."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)  # indexed for per-user audit queries
    action = Column(String(50), nullable=False, index=True)  # login, logout, export, create_webhook, delete_webhook, log_treatment, etc.
    resource = Column(String(100), nullable=True)  # what was acted on (e.g. "webhook:5", "api_key:oc_live_")
    details = Column(Text, nullable=True)  # JSON with extra context
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC), nullable=False, index=True)

    def __init__(self, **kwargs):
        # Agents use event_type/detail, routes use action/details — support both
        if "event_type" in kwargs and "action" not in kwargs:
            kwargs["action"] = kwargs.pop("event_type")
        if "detail" in kwargs and "details" not in kwargs:
            kwargs["details"] = kwargs.pop("detail")
        super().__init__(**kwargs)


class PerformanceFee(Base):
    """Tracks performance fees."""
    __tablename__ = "performance_fees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    gross_profit = Column(Float)
    fee_rate = Column(Float, default=0.20)
    fee_amount = Column(Float)
    tier = Column(String(16), default="premium")  # free / premium


# ══════════════════════════════════════════════════════════════════════
# VALUE-CHAIN PLATFORM MODELS
# ══════════════════════════════════════════════════════════════════════

class StageForcast(Base):
    """Stage-disaggregated lice forecast (Stige model output)."""
    __tablename__ = "stage_forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    locality_no = Column(Integer, ForeignKey("localities.locality_no"), nullable=False)
    forecast_year = Column(Integer, nullable=False)
    forecast_week = Column(Integer, nullable=False)
    horizon_weeks = Column(Integer, default=1)

    # Stage-specific predictions
    pred_sessile = Column(Float)
    pred_mobile = Column(Float)
    pred_adult_female = Column(Float)
    pred_total = Column(Float)

    # Uncertainty bands (80% CI)
    adult_female_lo80 = Column(Float)
    adult_female_hi80 = Column(Float)

    # Risk
    prob_exceed_threshold = Column(Float)
    trend = Column(String(16))  # increasing/decreasing/stable
    pressure_index = Column(Float)
    confidence = Column(Float)


class User(Base):
    """Platform user with role-based access."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(256), unique=True, nullable=False)
    hashed_password = Column(String(256))
    full_name = Column(String(256))
    company = Column(String(256))
    role = Column(String(32), default="farmer")  # farmer/buyer/processor/investor/admin
    tier = Column(String(32), default="free")     # free/professional/enterprise
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))

    # Locality access (farmers see their own farms)
    locality_access = Column(Text)  # JSON list of locality_no

    # Stripe
    stripe_customer_id = Column(String(128))


class Subscription(Base):
    """SaaS subscription tracking."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tier = Column(String(32), nullable=False)  # free/professional/enterprise/investor
    started_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    monthly_price_nok = Column(Float, default=0)

    # API usage
    api_calls_month = Column(Integer, default=0)
    api_calls_limit = Column(Integer, default=100)  # free tier

    # Stripe
    stripe_customer_id = Column(String(128))
    stripe_subscription_id = Column(String(128))
    stripe_price_id = Column(String(128))
    cancel_at_period_end = Column(Boolean, default=False)
    current_period_end = Column(DateTime)


class TreatmentRecommendation(Base):
    """AI-generated treatment advisory for farmers."""
    __tablename__ = "treatment_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    locality_no = Column(Integer, ForeignKey("localities.locality_no"), nullable=False)
    urgency = Column(String(16))  # low/medium/high/critical
    recommended_action = Column(Text)
    treatment_type = Column(String(64))  # mechanical/thermal/medicinal/cleaner_fish/none
    optimal_timing_week = Column(Integer)
    estimated_cost_nok = Column(Float)
    estimated_mortality_pct = Column(Float)
    lice_reduction_expected_pct = Column(Float)
    rationale = Column(Text)
    status = Column(String(16), default="pending")  # pending/accepted/rejected


class TreatmentOutcome(Base):
    """Farmer-reported treatment results for efficacy tracking."""
    __tablename__ = "treatment_outcomes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    locality_no = Column(Integer, ForeignKey("localities.locality_no"), nullable=False)
    treatment_date = Column(DateTime, nullable=False)
    method = Column(String(64))  # mechanical/thermal/freshwater/medicinal/biological
    pre_lice_count = Column(Float)
    post_lice_count = Column(Float)
    mortality_observed = Column(Integer, default=0)
    cost_nok = Column(Float)
    notes = Column(Text)
    resistance_observed = Column(Boolean, default=False)
    reported_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))


class SupplyForecast(Base):
    """Regional supply volume forecast for buyers/processors."""
    __tablename__ = "supply_forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    production_area = Column(Integer)  # PA 1-13
    ticker = Column(String(16))  # company (optional)
    forecast_year = Column(Integer)
    forecast_week = Column(Integer)
    horizon_weeks = Column(Integer)

    # Volume predictions
    predicted_harvest_tonnes = Column(Float)
    harvest_lo80 = Column(Float)
    harvest_hi80 = Column(Float)

    # Quality
    predicted_quality_score = Column(Float)  # 0-100
    lice_impact_on_quality_pct = Column(Float)

    # Risk
    supply_risk_level = Column(String(16))  # low/medium/high
    contract_risk_flag = Column(Boolean, default=False)
    rationale = Column(Text)


class HarvestTimingAdvice(Base):
    """Optimal harvest timing recommendation."""
    __tablename__ = "harvest_timing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    locality_no = Column(Integer, ForeignKey("localities.locality_no"), nullable=False)
    ticker = Column(String(16))

    current_biomass_kg = Column(Float)
    optimal_harvest_week = Column(Integer)
    optimal_harvest_year = Column(Integer)
    reason = Column(Text)

    # Economics
    harvest_now_value_nok_per_kg = Column(Float)
    harvest_optimal_value_nok_per_kg = Column(Float)
    value_difference_pct = Column(Float)

    # Risk of waiting
    lice_risk_if_wait = Column(String(16))
    treatment_probability_if_wait = Column(Float)


# ══════════════════════════════════════════════════════════════════════
# PRICE PREDICTION MODELS
# ══════════════════════════════════════════════════════════════════════

class PricePrediction(Base):
    """ML ensemble price prediction snapshot."""
    __tablename__ = "price_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    horizon_weeks = Column(Integer, nullable=False)
    current_spot_nok = Column(Float)
    predicted_nok = Column(Float)
    direction = Column(String(16))
    confidence = Column(Float)

    # Conformal prediction bands
    price_lo95 = Column(Float)
    price_hi95 = Column(Float)
    price_lo80 = Column(Float)
    price_hi80 = Column(Float)
    price_lo50 = Column(Float)
    price_hi50 = Column(Float)

    # Component signals
    lice_signal = Column(String(16))
    supply_signal = Column(String(16))
    seasonal_signal = Column(String(16))
    export_signal = Column(String(16))
    futures_signal = Column(String(16))
    combined_signal = Column(String(32))

    # Model metadata
    model_version = Column(String(64))
    n_scenarios = Column(Integer)
    mape_backtest = Column(Float)
    rationale = Column(Text)


class FuturesSnapshot(Base):
    """Fish Pool forward curve snapshot."""
    __tablename__ = "futures_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fetched_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    spot_nok = Column(Float)
    curve_shape = Column(String(16))  # contango / backwardation / flat
    avg_premium_pct = Column(Float)
    contracts_json = Column(Text)  # JSON array of contract quotes


class SSBWeeklyPrice(Base):
    """Real weekly salmon export price from SSB table 03024."""
    __tablename__ = "ssb_weekly_prices"
    __table_args__ = (
        UniqueConstraint("year", "week", name="uq_ssb_price_week"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    price_nok_kg = Column(Float, nullable=False)
    volume_tonnes = Column(Float, default=0.0)
    source = Column(String(32), default="ssb_03024")
    fetched_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))


class ExportVolume(Base):
    """SSB salmon export volume record."""
    __tablename__ = "export_volumes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    volume_tonnes = Column(Float)
    value_nok_millions = Column(Float)
    destination = Column(String(128))  # EU, Asia, USA, Other
    source = Column(String(32), default="ssb")
    fetched_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))


# ── EU Traceability models ────────────────────────────────────────────


class CatchCertificate(Base):
    """EU catch certificate for product origin verification."""
    __tablename__ = "catch_certificates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    certificate_no = Column(String(64), unique=True, nullable=False)
    vessel_name = Column(String(256))
    flag_state = Column(String(64))
    catch_area = Column(String(128))  # FAO area code
    species = Column(String(128), default="Atlantic salmon")
    quantity_kg = Column(Float)
    catch_date = Column(DateTime)
    landing_port = Column(String(128))
    validation_authority = Column(String(256))
    status = Column(String(32), default="draft")  # draft/validated/rejected/expired
    issued_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    expires_at = Column(DateTime)
    notes = Column(Text)


class LotTrace(Base):
    """Product lot tracking with chain-of-custody."""
    __tablename__ = "lot_traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_id = Column(String(64), unique=True, nullable=False)
    certificate_id = Column(Integer, ForeignKey("catch_certificates.id"))
    origin_locality_no = Column(Integer, ForeignKey("localities.locality_no"))
    product_type = Column(String(64))  # whole/fillet/smoked/frozen
    quantity_kg = Column(Float)
    chain_of_custody = Column(Text)  # JSON array of handoff events
    current_holder = Column(String(256))
    status = Column(String(32), default="in_transit")  # in_transit/delivered/recalled
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    delivered_at = Column(DateTime)


class IUURiskAssessment(Base):
    """IUU (Illegal, Unreported, Unregulated) fishing risk scoring."""
    __tablename__ = "iuu_risk_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vessel_name = Column(String(256), nullable=False)
    imo_number = Column(String(32))
    flag_state = Column(String(64))
    risk_score = Column(Float)  # 0-100
    risk_level = Column(String(16))  # low/medium/high/critical
    factors = Column(Text)  # JSON: {flag_risk, area_risk, documentation, history}
    assessed_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    assessed_by = Column(String(64), default="system")


class EUDRCompliance(Base):
    """EU Deforestation Regulation compliance for feed suppliers."""
    __tablename__ = "eudr_compliance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_name = Column(String(256), nullable=False)
    product = Column(String(64))  # soy/rapeseed/palm_oil
    country_of_origin = Column(String(128))
    geolocation = Column(String(256))  # lat,lon of production plot
    deforestation_free = Column(Boolean, default=False)
    certification_body = Column(String(256))
    certification_valid_until = Column(DateTime)
    status = Column(String(32), default="pending")  # pending/compliant/non_compliant/expired
    last_verified = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    notes = Column(Text)


# ── Bloom models (imported so Base.metadata.create_all picks them up) ─
from core.bloom.models import ChlorophyllReading, BloomRiskAssessment, BloomAlert  # noqa: E402, F401


# ── Engine & session factory ─────────────────────────────────────────
_is_sqlite = settings.database_url.startswith("sqlite")
if _is_sqlite:
    ensure_sqlite_dir(settings.database_url)
    engine = create_engine(
        settings.database_url,
        echo=False,
        connect_args={"timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _sqlite_connect_pragmas(dbapi_connection, connection_record):
        """WAL + busy_timeout on EVERY connection (the init_db PRAGMAs only
        affect one connection; busy_timeout is per-connection state)."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
else:
    # PostgreSQL / TimescaleDB
    engine = create_engine(
        settings.database_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )


class SavedScenario(Base):
    """Trader-saved event impact scenarios for replay and comparison."""
    __tablename__ = "saved_scenarios"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String, index=True)
    scenario_type = Column(String)  # isa, traffic_light, feed_shock, custom
    scenario_name = Column(String)
    parameters = Column(Text)  # JSON-encoded input parameters
    results = Column(Text)  # JSON-encoded output
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=func.now())


class WebhookConfig(Base):
    """User-configured webhook for external alert delivery (Slack, Teams, generic)."""
    __tablename__ = "webhook_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(100))
    url = Column(String(500), nullable=False)
    webhook_type = Column(String(20), default="generic")  # generic, slack, teams
    events = Column(Text)  # JSON array: ["lice_alert", "price_alert", "disease_alert"]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    last_triggered = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0)


class APIKey(Base):
    """Developer API key for programmatic access."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_hash = Column(String(128), nullable=False)  # bcrypt hash of key
    key_prefix = Column(String(8))  # first 8 chars for identification (e.g., "oc_live_")
    name = Column(String(100))
    tier = Column(String(20), default="free")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    last_used = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    rate_limit = Column(Integer, default=100)  # requests per minute

    user = relationship("User", backref="api_keys")


class CustomAlertRule(Base):
    """User-defined threshold-based alert rules."""
    __tablename__ = "custom_alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(100), nullable=False)
    metric = Column(String(50), nullable=False)  # lice_avg, spot_price, sst, disease_count, bloom_risk
    operator = Column(String(5), nullable=False)  # >, <, >=, <=, ==
    threshold = Column(Float, nullable=False)
    production_area = Column(Integer, nullable=True)  # optional PA 1-13 filter
    is_active = Column(Boolean, default=True)
    notify_webhook = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    last_triggered = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0)


class NotificationPreference(Base):
    """Per-user notification threshold preferences."""
    __tablename__ = "notification_preferences"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String, index=True, unique=True)
    lice_critical_threshold = Column(Float, default=0.5)
    lice_warning_threshold = Column(Float, default=0.3)
    price_change_pct = Column(Float, default=10.0)
    sst_high_threshold = Column(Float, default=16.0)
    sst_low_threshold = Column(Float, default=4.0)
    email_alerts = Column(Boolean, default=False)
    push_alerts = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


_background_tasks: set[asyncio.Task] = set()


def init_db() -> None:
    Base.metadata.create_all(engine)
    if _is_sqlite:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA busy_timeout=30000"))
            conn.commit()

    # Seed demo treatment outcomes for the Efficacy Marketplace
    try:
        import asyncio
        from core.market.efficacy_marketplace import seed_demo_outcomes
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(seed_demo_outcomes())
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
        except RuntimeError:
            asyncio.run(seed_demo_outcomes())
    except Exception:
        pass  # Non-critical — marketplace works without seed data


Session = sessionmaker(bind=engine)


class IndexObservation(Base):
    """A published observation of a named public index (AI-STI; AI-LPI until 1.0.0).

    Immutable for a given (index_code, week, version): the revision policy in
    `core.market.indices.methodology()` promises that a change to the method
    creates a new version rather than silently restating history. A withdrawn
    method's rows are marked ``superseded_by`` (migration 020, WS-19); the value,
    band, components and provenance are never edited and the row is never deleted.
    """
    __tablename__ = "index_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_code = Column(String(16), nullable=False, index=True)
    week = Column(String(12), nullable=False)          # ISO week, e.g. 2026-W42
    as_of = Column(DateTime, nullable=False)
    version = Column(String(16), nullable=False)
    value = Column(Float)
    band = Column(String(16))
    components_json = Column(Text)
    provenance_json = Column(Text)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    superseded_by = Column(String(16), nullable=True)   # method version that withdrew it
    superseded_reason = Column(Text, nullable=True)
    superseded_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "index_code", "week", "version", name="uq_index_observations_week_version"
        ),
    )




class DesignPartner(Base):
    """A paid 90-day pilot customer (design partner).

    Pilots are time-boxed grants of an existing canonical plan — deliberately NOT a
    separate tier, so `core/entitlements.py` stays the single plan table. The row
    tracks the grant, its expiry, the success metrics it is judged on and the
    data-reciprocity terms.
    """
    __tablename__ = "design_partners"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company = Column(String(256), nullable=False)
    contact_email = Column(String(256))
    contact_name = Column(String(256))
    icp = Column(String(64))            # desk | processor | producer | insurer | other
    sector = Column(String(128))
    country = Column(String(8))
    plan_granted = Column(String(32))   # canonical plan key from entitlements
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    starts_at = Column(DateTime)
    ends_at = Column(DateTime)
    status = Column(String(24), default="prospect")
    is_paid = Column(Boolean, default=False)
    monthly_price_nok = Column(Float, default=0)
    reciprocity_json = Column(Text)     # what the partner shares back, and cadence
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))


class PartnerMetric(Base):
    """A success metric recorded during a pilot (target vs observed)."""
    __tablename__ = "partner_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    partner_id = Column(Integer, ForeignKey("design_partners.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    value = Column(Float)
    target = Column(Float)
    unit = Column(String(32))
    note = Column(Text)
    recorded_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))

class ChatUsage(Base):
    """One row per user per month: the grounded-chat meter (WS-38).

    The allowance is a fair-use meter, not a revenue line — it stops one power user
    consuming the platform's model budget and gives the plan a number it can state.
    ``user_key`` is the authenticated user (or an API-key principal); anonymous
    visitors are never metered because they never get an answer.
    """
    __tablename__ = "chat_usage"
    __table_args__ = (
        UniqueConstraint("user_key", "month", name="uq_chat_usage_user_month"),
        Index("ix_chat_usage_month", "month"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_key = Column(String(128), nullable=False)
    month = Column(String(7), nullable=False)          # YYYY-MM
    questions = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
