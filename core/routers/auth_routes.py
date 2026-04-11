"""
Authentication & User Management Routes
==========================================
Extracted from core/api.py for maintainability.
Fully async — uses get_async_session().
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.async_db import get_async_session
from core.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Stricter rate limits for auth — prevent brute-force and enumeration
_auth_limiter = Limiter(key_func=get_remote_address)


class RegisterRequest(BaseModel):
    email: str
    password: str
    company: str = ""
    role: str = "farmer"


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
@_auth_limiter.limit("5/minute")
async def register(request: Request, req: RegisterRequest):
    """Register a new user. Starts on free tier."""
    from core.auth import hash_password, create_token

    async with get_async_session() as s:
        existing = (await s.execute(
            select(User).where(User.email == req.email)
        )).scalar()
        if existing:
            raise HTTPException(400, "Email already registered")

        user = User(
            email=req.email,
            hashed_password=hash_password(req.password),
            company=req.company,
            role=req.role,
            tier="free",
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)

        token = create_token(user.id, user.email, user.tier)

        # Audit: registration
        from core.audit import log_action, get_client_ip
        await log_action(user.id, "register", f"user:{user.email}", ip=get_client_ip(request))

        return {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "company": user.company,
                "role": user.role,
                "tier": user.tier,
            },
        }


@router.post("/login")
@_auth_limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest):
    """Login and receive JWT token. Rate-limited to prevent brute-force."""
    from core.auth import verify_password, create_token, needs_rehash, hash_password

    async with get_async_session() as s:
        user = (await s.execute(
            select(User).where(User.email == req.email)
        )).scalar()
        if not user or not verify_password(req.password, user.hashed_password):
            # Audit: failed login
            from core.audit import log_action, get_client_ip
            await log_action(None, "login_failed", f"email:{req.email}", ip=get_client_ip(request))
            raise HTTPException(401, "Invalid email or password")

        if needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(req.password)
            await s.commit()

        token = create_token(user.id, user.email, user.tier)

        # Audit: successful login
        from core.audit import log_action, get_client_ip
        await log_action(user.id, "login", f"user:{user.email}", ip=get_client_ip(request))

        return {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "company": user.company,
                "role": user.role,
                "tier": user.tier,
            },
        }


@router.get("/me")
async def auth_me():
    """Get current user info from token."""
    return {"message": "Use Authorization: Bearer <token> header"}


@router.get("/tiers")
async def auth_tiers():
    """Get available subscription tiers and pricing."""
    from core.auth import TIERS
    return [
        {
            "id": tid,
            "name": t["name"],
            "price_nok": t["price_nok"],
            "api_calls_per_day": t["api_calls_per_day"],
            "features": _tier_features(tid),
        }
        for tid, t in TIERS.items()
    ]


def _tier_features(tier_id: str) -> list[str]:
    features = {
        "free": [
            "Dashboard overview",
            "Morning Brief (daily digest)",
            "Basic lice summary",
        ],
        "pro": [
            "Everything in Free",
            "Production Cost Intelligence",
            "ESG Sustainability Scores",
            "Algal Bloom Monitoring",
            "Lice Exposure Map",
            "Farm Advisory",
            "Digital Twin Simulator",
            "100+ company rankings",
        ],
        "market": [
            "Everything in Pro",
            "Trading Signals",
            "Market Terminal",
            "Price & Predictions (ML ensemble)",
            "Causal Engine",
            "Global Supply Balance",
            "Investor Intelligence",
            "AIS Vessel Tracking",
            "Macro Intelligence (12 FRED series)",
        ],
        "institutional": [
            "Everything in Market",
            "Full API access (50,000 calls/day)",
            "Custom datasets & exports",
            "White-label reports",
            "Priority support",
        ],
    }
    return features.get(tier_id, [])
