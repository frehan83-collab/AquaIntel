"""
AquaIntel global settings loaded from environment / .env file.
"""
from __future__ import annotations

import logging
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

ROOT_DIR = Path(__file__).resolve().parent.parent

# Canonical dev SQLite DB is data/aquaintel.db. Fall back to the pre-rename
# data/openclaw.db so an existing populated dev database is not orphaned by
# the OpenClaw -> AquaIntel rename (a fresh clone gets the canonical name).
_LEGACY_DB = ROOT_DIR / "data" / "openclaw.db"
_CANONICAL_DB = ROOT_DIR / "data" / "aquaintel.db"
_DEFAULT_DB = _CANONICAL_DB if (_CANONICAL_DB.exists() or not _LEGACY_DB.exists()) else _LEGACY_DB


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # BarentsWatch
    barentswatch_client_id: str = ""
    barentswatch_client_secret: str = ""
    barentswatch_token_url: str = "https://id.barentswatch.no/connect/token"
    barentswatch_api_base: str = (
        "https://www.barentswatch.no/bwapi/v1/geodata/fishhealth"
    )

    # Fish Pool
    fishpool_api_key: str = ""

    # Broker
    broker_mode: str = "paper"  # paper | live
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497
    ib_client_id: int = 1
    nordnet_username: str = ""
    nordnet_password: str = ""

    # Dashboard
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8501
    secret_key: str = "change-me"

    # Database (override with DATABASE_URL env var for PostgreSQL)
    database_url: str = f"sqlite:///{_DEFAULT_DB}"

    # Stripe billing
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_success_url: str = "http://localhost:3000/billing?success=true"
    stripe_cancel_url: str = "http://localhost:3000/billing?cancelled=true"

    # Notifications
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email_to: str = ""
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_from: str = ""
    twilio_to: str = ""

    # Logging
    log_level: str = "INFO"
    log_file: str = str(ROOT_DIR / "logs" / "aquaintel.log")

    # Performance fee
    performance_fee_rate: float = 0.20

    # Polling
    poll_interval_minutes: int = 15

    # Copernicus Marine (CMEMS) — free registration at data.marine.copernicus.eu
    cmems_username: str = ""
    cmems_password: str = ""

    # Copernicus Data Space Ecosystem (CDSE) Sentinel Hub — free tier:
    # 10,000 requests + 10,000 PU/month. OAuth client from
    # https://shapps.dataspace.copernicus.eu/dashboard/ (Account → OAuth clients)
    sentinel_hub_client_id: str = ""
    sentinel_hub_client_secret: str = ""

    # Bloom alert thresholds (mg/m3 chlorophyll-a)
    bloom_chl_elevated: float = 2.0
    bloom_chl_high: float = 5.0
    bloom_chl_critical: float = 10.0
    bloom_alert_cooldown_hours: int = 24

    # Fish Pool / Futures
    fishpool_api_key: str = ""

    # External Compute (for heavy ML training)
    compute_backend: str = "local"  # local | runpod | truefoundry | northflank
    compute_api_key: str = ""
    compute_endpoint_url: str = ""

    # Price ML Ensemble
    price_retrain_hour: int = 2  # nightly retrain at 02:00 UTC
    price_monte_carlo_scenarios: int = 1000
    price_backtest_start_year: int = 2020

    # LLM
    llm_provider: str = "openrouter"  # anthropic | openai | openrouter | gemini
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_model: str = "anthropic/claude-sonnet-4-20250514"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.3
    llm_monthly_budget_usd: float = 100.0


    # Environment (set FISHINTEL_ENV=production for production checks)
    fishintel_env: str = "development"

    @model_validator(mode="after")
    def _production_checks(self) -> "Settings":
        """Fail fast on insecure production configuration."""
        if self.fishintel_env != "production":
            return self
        errors = []
        if self.database_url.startswith("sqlite://"):
            errors.append("SQLite is not supported in production — set DATABASE_URL to PostgreSQL")
        if self.secret_key == "change-me":
            errors.append("Default secret_key is insecure — set a strong secret_key")
        if errors:
            raise ValueError("Production configuration errors:\n  - " + "\n  - ".join(errors))
        if not self.barentswatch_client_id:
            logging.getLogger("aquaintel.settings").warning(
                "BARENTSWATCH_CLIENT_ID not set — live lice data will be unavailable"
            )
        return self


settings = Settings()
