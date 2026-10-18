"""Deep-analysis runs and credits: the surfaces a document is bought on.

A chat answer is included in the plan; a **document** is bought with a credit. This router
serves the run catalogue, spends exactly one credit per model-written document (a digest
written because no model was reachable costs nothing), and exposes the pack catalogue plus a
one-off Stripe checkout for top-ups.

The honest edges are deliberate:

* no credit, no run — a structured 402 names the balance and the packs;
* a `digest` run (no model) does not spend, and says so in the payload;
* the ledger is append-only, so every balance has a history (`GET /api/billing/credits`).
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.auth import TokenPayload, get_current_user
from core.billing.credits_catalog import CREDIT_VALIDITY_NOTE, catalog, pack
from core.llm import credits as credit_ledger
from core.llm.workbench import RUN_KINDS, workbench

log = structlog.get_logger(__name__)

router = APIRouter(tags=["workbench"])


class RunRequest(BaseModel):
    kind: str = Field(..., max_length=40)


class CheckoutRequest(BaseModel):
    pack: str = Field(..., max_length=32)


def _user_key(user: TokenPayload | None) -> str:
    return f"user:{user.user_id}" if user else "anonymous"


@router.get("/api/workbench/catalog")
async def workbench_catalog(user: TokenPayload | None = Depends(get_current_user)):
    """What can be run, what it reads, and how many credits are left."""
    key = _user_key(user)
    balance = await credit_ledger.balance(key)
    return {
        "runs": list(RUN_KINDS.values()),
        "packs": catalog(),
        "validity_note": CREDIT_VALIDITY_NOTE,
        "credits": balance,
        "credits_available": balance is not None,
    }


@router.post("/api/workbench/run")
async def workbench_run(
    req: RunRequest, user: TokenPayload | None = Depends(get_current_user)
):
    """Render one deep-analysis document. One credit per model-written run."""
    kind = (req.kind or "").strip()
    if kind not in RUN_KINDS:
        return JSONResponse(
            status_code=422,
            content={"error": "unknown_run", "available": list(RUN_KINDS.keys())},
        )
    if not RUN_KINDS[kind].get("sellable", True):
        # WS-43: a withdrawn run is refused with its reason, and takes no credit.
        return JSONResponse(
            status_code=409,
            content={
                "error": "run_withdrawn",
                "kind": kind,
                "message": RUN_KINDS[kind].get("withdrawn_reason"),
                "runs_url": "/api/workbench/catalog",
            },
        )
    if user is None:
        return JSONResponse(
            status_code=402,
            content={
                "error": "credits_required",
                "message": "deep-analysis runs are bought in credit packs and need an account",
                "packs_url": "/api/workbench/catalog",
            },
        )
    key = _user_key(user)
    balance = await credit_ledger.balance(key)
    if balance is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": "credits_unavailable",
                "message": "the credit ledger cannot be read, so no run can be charged",
            },
        )
    if balance < 1:
        return JSONResponse(
            status_code=402,
            content={
                "error": "credits_required",
                "message": "no credits left; a run costs one credit",
                "balance": balance,
                "packs": catalog(),
                "validity_note": CREDIT_VALIDITY_NOTE,
            },
        )

    document = await workbench.run(kind, user_id=key)

    credits_after = balance
    if document.mode == "model":
        try:
            credits_after = await credit_ledger.spend(key, 1, reason=f"run:{kind}")
        except credit_ledger.InsufficientCredits:
            # A concurrent run consumed the last credit; the document exists but must not be
            # withheld over a race — it is delivered and the balance is reported honestly.
            credits_after = await credit_ledger.balance(key) or 0
            log.warning("workbench.spend_race", kind=kind, balance=credits_after)
        document.credits_spent = 1
    document.credits_after = credits_after
    payload = document.to_dict()
    payload["charged"] = document.mode == "model"
    payload["charge_note"] = {
        "model": "one credit spent",
        "withheld": (
            "no credit spent: the generated document contained a number the verified data "
            "could not support, so the prose was withheld and the verified data delivered"
        ),
    }.get(
        document.mode,
        "no credit spent: the model was unreachable, so this run returned the verified data itself",
    )
    return payload


@router.get("/api/billing/credits")
async def credits_status(user: TokenPayload | None = Depends(get_current_user)):
    """Balance, history and packs for the caller."""
    key = _user_key(user)
    status = await credit_ledger.status(key)
    status["history"] = await credit_ledger.history(key, limit=20)
    return status


@router.post("/api/billing/credits/checkout")
async def credits_checkout(
    req: CheckoutRequest, user: TokenPayload | None = Depends(get_current_user)
):
    """Start a one-off purchase of a credit pack.

    With Stripe unconfigured this returns a deterministic mock URL, exactly like the plan
    checkout does, so the money path stays exercisable in dev and CI.
    """
    selected = pack(req.pack)
    if selected is None:
        return JSONResponse(
            status_code=422,
            content={"error": "unknown_pack", "packs": [p["key"] for p in catalog()]},
        )
    if user is None:
        return JSONResponse(
            status_code=401,
            content={"error": "login_required", "message": "credits are attached to an account"},
        )
    from core.billing import stripe_catalog

    if not stripe_catalog.is_configured():
        return {
            "pack": selected.key,
            "runs": selected.runs,
            "price_nok": selected.price_nok,
            "checkout_url": f"/billing?credits={selected.key}",
            "demo_mode": True,
            "note": (
                "Stripe is not configured on this deployment; the pack is priced and listed "
                "but no card can be charged yet"
            ),
        }
    # Real Stripe: one-off payment mode. Kept behind the configured check so a deployment
    # without keys never calls the API.
    import asyncio

    import stripe

    from config.settings import settings

    def _create() -> dict:
        stripe.api_key = settings.stripe_secret_key
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "nok",
                        "unit_amount": int(selected.price_nok * 100),
                        "product_data": {
                            "name": f"AquaIntel {selected.name} — {selected.runs} runs",
                        },
                    },
                    "quantity": 1,
                }
            ],
            success_url=settings.stripe_success_url,
            cancel_url=settings.stripe_cancel_url,
            metadata={
                "credit_pack": selected.key,
                "credit_runs": str(selected.runs),
                "user_id": str(user.user_id),
            },
        )
        return {"checkout_url": session.url, "session_id": session.id}

    result = await asyncio.to_thread(_create)
    result.update({"pack": selected.key, "runs": selected.runs, "price_nok": selected.price_nok})
    return result
