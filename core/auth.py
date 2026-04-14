"""
Authentication & Authorization System
=======================================
JWT-based authentication with 4-tier subscription access control.

Tiers (aligned with core/valuechain/subscription.py):
  - free: Dashboard, Morning Brief, basic lice summary
  - professional: + Production Costs, ESG, Bloom, Exposure, Farm Advisory, ML Baselines
  - enterprise: + Signals, Market Terminal, Price Outlook, Causal, Global Supply, Traceability
  - investor: + Full API access, custom datasets, all features

Security:
  - Passwords hashed with bcrypt via passlib
  - JWT tokens with 24h expiry (configurable)
  - Token refresh endpoint
  - Rate limiting per tier
"""
from __future__ import annotations

import datetime as dt
import secrets
from dataclasses import dataclass

import hashlib
import os

import bcrypt as _bcrypt
import jwt
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select

import structlog

log = structlog.get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
_env_secret = os.environ.get("FISHINTEL_JWT_SECRET", "")
if not _env_secret:
    # In development, generate an ephemeral secret with a loud warning
    if os.environ.get("FISHINTEL_ENV", "development") == "production":
        raise RuntimeError(
            "FISHINTEL_JWT_SECRET must be set in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    log.warning("FISHINTEL_JWT_SECRET not set — generating ephemeral secret (dev only, tokens won't survive restarts)")
    _env_secret = secrets.token_urlsafe(64)
if len(_env_secret) < 32 or _env_secret in ("change-me", "secret", "test"):
    log.warning("FISHINTEL_JWT_SECRET is too short or insecure — please use a strong random secret")
SECRET_KEY = _env_secret
ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24
security = HTTPBearer(auto_error=False)


# ── Tier definitions (aligned with core/valuechain/subscription.py) ───────────
TIERS = {
    "free": {
        "name": "Free",
        "price_nok": 0,
        "routes": [
            "/api/health", "/api/brief", "/api/lice/summary",
            "/api/signals", "/api/auth/", "/api/billing/",
        ],
        "pages": ["/", "/brief", "/settings", "/billing"],
        "api_calls_per_day": 100,
    },
    "professional": {
        "name": "Professional",
        "price_nok": 2990,
        "routes": [
            "/api/health", "/api/brief", "/api/lice/", "/api/signals",
            "/api/bloom/", "/api/exposure/", "/api/feed-cost/",
            "/api/esg/", "/api/leaders/", "/api/regime/",
            "/api/farmer-advisory/", "/api/farm-graph/",
            "/api/production/", "/api/gnn/", "/api/twin/",
            "/api/harvest/", "/api/ml/chronos/",
            "/api/auth/", "/api/billing/",
        ],
        "pages": ["/", "/brief", "/leaders", "/esg", "/bloom", "/exposure",
                  "/feed-cost", "/farmer", "/twin", "/predictions",
                  "/harvest", "/ml-baselines", "/settings", "/billing"],
        "api_calls_per_day": 5000,
    },
    "enterprise": {
        "name": "Enterprise",
        "price_nok": 14900,
        "routes": [
            "/api/health", "/api/brief", "/api/lice/", "/api/signals",
            "/api/bloom/", "/api/exposure/", "/api/feed-cost/",
            "/api/esg/", "/api/leaders/", "/api/regime/",
            "/api/farmer-advisory/", "/api/farm-graph/",
            "/api/production/", "/api/gnn/", "/api/twin/",
            "/api/harvest/", "/api/ml/chronos/",
            "/api/market/", "/api/price-outlook", "/api/causal/",
            "/api/global-supply", "/api/macro/", "/api/ais/",
            "/api/pairs/", "/api/chile/", "/api/backtest/",
            "/api/biomass/", "/api/disease/", "/api/ocean/",
            "/api/intelligence/", "/api/sentiment/",
            "/api/traceability/", "/api/supply/",
            "/api/auth/", "/api/billing/",
        ],
        "pages": "all",
        "api_calls_per_day": 50000,
    },
    "investor": {
        "name": "Investor",
        "price_nok": 24900,
        "routes": "all",
        "pages": "all",
        "api_calls_per_day": 100000,
    },
}

# Backwards-compat mapping for tokens issued with old tier names
_TIER_ALIASES = {"pro": "professional", "market": "enterprise", "institutional": "investor"}


@dataclass
class TokenPayload:
    """Decoded JWT payload."""
    user_id: int
    email: str
    tier: str
    exp: dt.datetime


def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against stored hash. Supports both bcrypt and legacy SHA-256."""
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    # Legacy SHA-256 support — auto-migrate on next login
    if "$" not in hashed:
        return False
    salt, stored_hash = hashed.split("$", 1)
    h = hashlib.sha256(f"{salt}:{plain}".encode()).hexdigest()
    return h == stored_hash


def needs_rehash(hashed: str) -> bool:
    """Check if a password hash should be upgraded to bcrypt."""
    return not (hashed.startswith("$2b$") or hashed.startswith("$2a$"))


def create_token(user_id: int, email: str, tier: str) -> str:
    """Create a JWT token."""
    payload = {
        "user_id": user_id,
        "email": email,
        "tier": tier,
        "exp": dt.datetime.now(dt.UTC) + dt.timedelta(hours=TOKEN_EXPIRY_HOURS),
        "iat": dt.datetime.now(dt.UTC),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(
            user_id=payload["user_id"],
            email=payload["email"],
            tier=payload["tier"],
            exp=dt.datetime.fromtimestamp(payload["exp"]),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


def hash_api_key(raw_key: str) -> str:
    """Hash an API key with bcrypt for storage."""
    return _bcrypt.hashpw(raw_key.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_api_key(raw_key: str, hashed: str) -> bool:
    """Verify a raw API key against its stored bcrypt hash."""
    try:
        return _bcrypt.checkpw(raw_key.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def generate_api_key() -> str:
    """Generate a new random API key with oc_live_ prefix."""
    random_part = secrets.token_urlsafe(32)
    return f"oc_live_{random_part}"


async def _authenticate_via_api_key(request: Request) -> TokenPayload | None:
    """
    Check for X-API-Key header or api_key query param.
    If found, validate and return a TokenPayload for the key's user.
    """
    raw_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not raw_key:
        return None

    # Lazy import to avoid circular dependency
    from core.async_db import get_async_session
    from core.models import APIKey, User

    async with get_async_session() as s:
        # Look up active keys matching the prefix
        prefix = raw_key[:8]
        result = await s.execute(
            select(APIKey).where(
                APIKey.key_prefix == prefix,
                APIKey.is_active == True,  # noqa: E712
            )
        )
        candidate_keys = result.scalars().all()

        for api_key in candidate_keys:
            if verify_api_key(raw_key, api_key.key_hash):
                # Check expiry
                if api_key.expires_at and api_key.expires_at < dt.datetime.now(dt.UTC):
                    raise HTTPException(401, "API key expired")

                # Update last_used
                api_key.last_used = dt.datetime.now(dt.UTC)
                await s.commit()

                # Get user
                user_result = await s.execute(
                    select(User).where(User.id == api_key.user_id)
                )
                user = user_result.scalar()
                if not user or not user.is_active:
                    raise HTTPException(401, "User account inactive")

                return TokenPayload(
                    user_id=user.id,
                    email=user.email,
                    tier=api_key.tier or user.tier,
                    exp=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
                )

        raise HTTPException(401, "Invalid API key")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> TokenPayload | None:
    """
    Extract current user from JWT token or API key.
    Checks: 1) Bearer JWT token, 2) X-API-Key header / api_key query param.
    Returns None if no auth provided (allows public access to free endpoints).
    """
    # Try JWT first
    if credentials:
        return decode_token(credentials.credentials)

    # Try API key
    api_key_result = await _authenticate_via_api_key(request)
    if api_key_result:
        return api_key_result

    return None


def _resolve_tier(tier: str) -> str:
    """Resolve old tier names to new ones."""
    return _TIER_ALIASES.get(tier, tier)


def check_tier_access(user: TokenPayload | None, path: str) -> bool:
    """
    Check if user's tier allows access to a given API path.
    None user = free tier.
    """
    tier = _resolve_tier(user.tier) if user else "free"
    tier_config = TIERS.get(tier, TIERS["free"])

    allowed = tier_config["routes"]
    if allowed == "all":
        return True

    return any(path.startswith(route) for route in allowed)


def require_tier(minimum_tier: str):
    """
    FastAPI dependency that enforces minimum tier access.
    Usage: @app.get("/api/premium", dependencies=[Depends(require_tier("professional"))])
    """
    tier_order = ["free", "professional", "enterprise", "investor"]

    async def _check(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ):
        if not credentials:
            raise HTTPException(401, "Authentication required")

        payload = decode_token(credentials.credentials)
        resolved = _resolve_tier(payload.tier)
        user_level = tier_order.index(resolved) if resolved in tier_order else 0
        required_level = tier_order.index(minimum_tier) if minimum_tier in tier_order else 0

        if user_level < required_level:
            raise HTTPException(
                403,
                f"Requires {minimum_tier} tier or higher. Your tier: {resolved}"
            )
        return payload

    return _check
