"""
API Key Management Routes
===========================
CRUD endpoints for developer API keys. Fully async.
Keys are shown in full only once at creation time; only the prefix is stored/returned after that.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select

from core.async_db import get_async_session
from core.auth import (
    get_current_user, TokenPayload, generate_api_key, hash_api_key,
)
from core.models import APIKey

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


# ── Pydantic schemas ─────────────────────────────────────────────────

class CreateKeyRequest(BaseModel):
    name: str = "My API Key"
    tier: str | None = None  # defaults to user's tier
    expires_days: int | None = None  # None = no expiry
    rate_limit: int = 100


class KeyResponse(BaseModel):
    id: int
    name: str | None
    key_prefix: str | None
    tier: str
    is_active: bool
    created_at: str
    last_used: str | None
    expires_at: str | None
    rate_limit: int


class CreatedKeyResponse(KeyResponse):
    """Returned only at creation time — includes the full raw key."""
    raw_key: str


# ── Helpers ───────────────────────────────────────────────────────────

def _key_to_dict(k: APIKey) -> dict:
    return {
        "id": k.id,
        "name": k.name,
        "key_prefix": k.key_prefix,
        "tier": k.tier or "free",
        "is_active": k.is_active,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "last_used": k.last_used.isoformat() if k.last_used else None,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "rate_limit": k.rate_limit or 100,
    }


def _require_auth(user: TokenPayload | None) -> TokenPayload:
    if not user:
        raise HTTPException(401, "Authentication required to manage API keys")
    return user


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("")
async def list_api_keys(
    user: TokenPayload | None = Depends(get_current_user),
):
    """List all API keys for the authenticated user. Never returns the full key."""
    u = _require_auth(user)
    async with get_async_session() as s:
        result = await s.execute(
            select(APIKey)
            .where(APIKey.user_id == u.user_id)
            .order_by(APIKey.created_at.desc())
        )
        keys = result.scalars().all()
        return {"keys": [_key_to_dict(k) for k in keys]}


@router.post("")
async def create_api_key(
    request: Request,
    req: CreateKeyRequest,
    user: TokenPayload | None = Depends(get_current_user),
):
    """
    Generate a new API key. The full key is returned ONCE in the response.
    Store it securely — it cannot be retrieved again.
    """
    u = _require_auth(user)

    # Limit to 10 active keys per user
    async with get_async_session() as s:
        count_result = await s.execute(
            select(APIKey)
            .where(APIKey.user_id == u.user_id, APIKey.is_active == True)  # noqa: E712
        )
        active_count = len(count_result.scalars().all())
        if active_count >= 10:
            raise HTTPException(400, "Maximum 10 active API keys per user")

        raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key)

        expires_at = None
        if req.expires_days:
            expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(days=req.expires_days)

        # Use the user's tier if none specified
        tier = req.tier or u.tier

        api_key = APIKey(
            user_id=u.user_id,
            key_hash=key_hash,
            key_prefix=raw_key[:8],
            name=req.name,
            tier=tier,
            rate_limit=req.rate_limit,
            expires_at=expires_at,
        )
        s.add(api_key)
        await s.commit()
        await s.refresh(api_key)

        response = _key_to_dict(api_key)
        response["raw_key"] = raw_key

        # Audit: API key generated
        from core.audit import log_action, get_client_ip
        await log_action(
            u.user_id, "generate_api_key",
            f"api_key:{raw_key[:8]}",
            details={"name": req.name, "tier": tier},
            ip=get_client_ip(request),
        )

        return response


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: int,
    request: Request,
    user: TokenPayload | None = Depends(get_current_user),
):
    """Revoke (deactivate) an API key. The key will immediately stop working."""
    u = _require_auth(user)
    async with get_async_session() as s:
        result = await s.execute(
            select(APIKey).where(APIKey.id == key_id, APIKey.user_id == u.user_id)
        )
        api_key = result.scalar()
        if not api_key:
            raise HTTPException(404, "API key not found")

        api_key.is_active = False
        prefix = api_key.key_prefix
        await s.commit()

    # Audit: API key revoked
    from core.audit import log_action, get_client_ip
    await log_action(
        u.user_id, "revoke_api_key",
        f"api_key:{prefix}",
        ip=get_client_ip(request),
    )

    return {"message": "API key revoked", "id": key_id}


@router.post("/{key_id}/rotate")
async def rotate_api_key(
    key_id: int,
    request: Request,
    user: TokenPayload | None = Depends(get_current_user),
):
    """
    Rotate an API key: deactivate the old key and generate a new one
    with the same configuration. Returns the new full key ONCE.
    """
    u = _require_auth(user)
    async with get_async_session() as s:
        result = await s.execute(
            select(APIKey).where(APIKey.id == key_id, APIKey.user_id == u.user_id)
        )
        old_key = result.scalar()
        if not old_key:
            raise HTTPException(404, "API key not found")

        # Deactivate old key
        old_key.is_active = False

        # Create new key with same config
        raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key)

        new_key = APIKey(
            user_id=u.user_id,
            key_hash=key_hash,
            key_prefix=raw_key[:8],
            name=old_key.name,
            tier=old_key.tier,
            rate_limit=old_key.rate_limit,
            expires_at=old_key.expires_at,
        )
        s.add(new_key)
        await s.commit()
        await s.refresh(new_key)

        response = _key_to_dict(new_key)
        response["raw_key"] = raw_key
        response["rotated_from"] = key_id
        return response
