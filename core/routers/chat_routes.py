"""Grounded chat: one path, metered against the plan, and convertible into an alert.

This router replaces the string-interpolated `/api/chat` that lived in `core/api.py` and
bypassed both the honesty layer and the plan catalogue. Every answer here:

* is built by :mod:`core.llm.chat_service` from :mod:`core.llm.grounding` facts, each with
  `as_of`, `source` and a provenance verdict;
* is metered per user and month (:mod:`core.llm.usage`) against the plan's
  `chat_questions_per_month`, with a structured 402 that names the allowance and the
  upgrade;
* never spends a token on a request for a trade direction (the legal gate answers first).

`/api/chat/save-alert` turns a question into a **real, running** watch rule when the
question names a metric (lice, price, bloom, disease) — because the most valuable thing a
chat answer can do is stop being a chat answer and start being a monitor. When no metric
can be inferred the route refuses to invent one and says which metrics exist.
"""
from __future__ import annotations

import datetime as dt
import re

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from core.async_db import get_async_session
from core.auth import TokenPayload, get_current_user
from core.entitlements import get_plan, upgrade_hint
from core.llm import receipts as answer_receipts
from core.llm import usage as chat_usage
from core.llm.chat_service import MAX_QUESTION_CHARS, chat_service

log = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])

#: Metric names the alert evaluator understands (core/routers/notification_routes.py).
_METRIC_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("lice_avg", ("lice", "lus", "lakselus")),
    ("spot_price", ("price", "spot", "pris", "nok/kg", "margin", "cost")),
    ("bloom_risk", ("bloom", "algal", "algae", "alge", "chlorophyll", "klorofyll")),
    ("disease_count", ("disease", "sykdom", "isa", "outbreak")),
)

_OPERATORS_ABOVE = ("above", "over", "exceed", "exceeds", "higher than", "rises above", "over")
_OPERATORS_BELOW = ("below", "under", "lower than", "drops below", "falls below")


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=MAX_QUESTION_CHARS * 2)
    history: list[dict] = Field(default_factory=list)
    #: WS-45: bind the answer (and the § 8 limit) to one farm. Without it the chat is
    #: national and refuses to quote a legal limit.
    locality_no: int | None = Field(default=None, ge=1)


class SaveAlertRequest(BaseModel):
    question: str = Field(..., max_length=MAX_QUESTION_CHARS)
    name: str | None = Field(default=None, max_length=100)


def _user_key(user: TokenPayload | None) -> str:
    if user is None:
        return "anonymous"
    return f"user:{user.user_id}"


async def _resolve_site(locality_no: int) -> dict:
    """The farm a question is bound to: its name and production area, or no PA at all.

    A site whose production area is unknown is passed through with ``pa: None`` so the limit
    fact reports ``established: False`` and the chat refuses to quote one.
    """
    from sqlalchemy import select

    from core.models import Locality

    site = {"locality_no": locality_no, "pa": None, "name": None}
    try:
        async with get_async_session() as session:
            row = (
                await session.execute(
                    select(Locality).where(Locality.locality_no == locality_no)
                )
            ).scalar_one_or_none()
        if row is not None:
            site["pa"] = getattr(row, "production_area", None)
            site["name"] = getattr(row, "name", None)
    except Exception as exc:  # noqa: BLE001 — an unresolved site degrades to no PA
        log.warning("chat.site_lookup_failed", locality_no=locality_no, error=str(exc)[:100])
    return site


def _payment_required(*, plan_key: str, path: str, reason: str, status_payload: dict) -> dict:
    """One structured 402 shape, built from the catalogue rather than invented here."""
    hint = upgrade_hint(plan_key, error="chat_not_available", reason=reason, path=path)
    hint.update(
        {
            "chat": status_payload,
            "allowance": status_payload.get("allowance"),
            "used": status_payload.get("used"),
            "remaining": status_payload.get("remaining"),
            "resets_on": status_payload.get("resets_on"),
        }
    )
    return hint


@router.get("/api/chat/usage")
async def chat_usage_status(user: TokenPayload | None = Depends(get_current_user)):
    """The meter the UI renders: allowance, used, remaining, cost, reset date."""
    plan_key = (user.tier if user else None) or "free"
    status_payload = await chat_usage.status(_user_key(user), plan_key)
    status_payload["plan_name"] = get_plan(plan_key).name
    return status_payload


@router.post("/api/chat")
async def chat(
    req: ChatRequest,
    request: Request,
    user: TokenPayload | None = Depends(get_current_user),
):
    """Answer a question from the platform's verified data, within the plan's allowance."""
    plan_key = (user.tier if user else None) or "free"
    key = _user_key(user)
    status_payload = await chat_usage.status(key, plan_key)
    plan_name = get_plan(plan_key).name

    # WS-50: the allowance bounds model spend; it does not gate the product. When it is spent
    # (or the plan has none) the answer is assembled deterministically from the verified facts,
    # costs nothing and says so — a 402 that upsold a 4,900 customer to a 2,990 plan was the
    # wrong instrument.
    included = bool(status_payload.get("included"))
    model_allowed = included and not chat_usage.exhausted(status_payload)
    allowance_note = None
    if not model_allowed:
        if included:
            allowance_note = (
                f"the {plan_name} plan's model allowance is used up "
                f"({status_payload.get('used')}/{status_payload.get('allowance')}); this "
                "answer was assembled directly from the verified facts at no model cost"
            )
        else:
            allowance_note = (
                f"the {plan_name} plan does not include model-written answers; this "
                "answer was assembled directly from the verified facts at no model cost. "
                "Operator includes 100 a month and Desk 300"
            )

    site = await _resolve_site(req.locality_no) if req.locality_no else None
    answer = await chat_service.ask(
        req.message,
        user_id=key,
        history=req.history,
        site=site,
        allow_model=bool(model_allowed),
    )
    # Only a model-backed answer consumes the allowance: a refusal, a fallback or an
    # unavailable answer costs nothing, so it is not counted against a paying customer.
    if answer.mode == "grounded":
        await chat_usage.record(key, answer.usage)

    payload = answer.to_dict()
    # WS-49: a receipt for what the model was given and what it was allowed to say.
    payload["receipt_id"] = await answer_receipts.record(key, payload)
    refreshed = await chat_usage.status(key, plan_key)
    refreshed["plan_name"] = plan_name
    payload["chat"] = refreshed
    payload["allowance_note"] = allowance_note
    payload["request_id"] = getattr(request.state, "request_id", None)
    return payload


def _infer_metric(question: str) -> str | None:
    lowered = question.lower()
    for metric, keywords in _METRIC_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return metric
    return None


def _infer_operator(question: str) -> str:
    lowered = question.lower()
    if any(token in lowered for token in _OPERATORS_BELOW):
        return "<"
    return ">"


def _infer_area(question: str) -> int | None:
    match = re.search(r"\b(?:pa|production area|produksjonsområde)\s*(\d{1,2})\b", question.lower())
    if not match:
        return None
    area = int(match.group(1))
    return area if 1 <= area <= 13 else None


def _explicit_threshold(question: str) -> float | None:
    match = re.search(r"\b(?:above|over|below|under|exceeds?)\s+([0-9]+(?:[.,][0-9]+)?)", question.lower())
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


async def _current_value(metric: str, question: str, area: int | None) -> dict:
    """The verified current value of the metric, or a dated reason there is none."""
    from core.market.verified_metrics import verified_current

    state = await verified_current(metric, production_area=area)
    return state.to_dict()


async def _lice_limit_check(area: int | None, threshold: float) -> str | None:
    """Refuse a lice threshold below the legal limit for that site's week.

    A rule that fires only after a breach is a compliance alarm, not a watch; a rule *below*
    the limit fires constantly and teaches the customer to ignore it. The chat's own example —
    "lice in PA 3 above 0.4" — is twice the limit in the southern spring window.
    """
    from core.regulatory_facts import lice_limit

    decision = lice_limit(pa=area, iso_week=dt.datetime.now(dt.UTC).isocalendar().week)
    if not decision.established or decision.limit is None:
        return None
    if threshold < decision.limit:
        return (
            f"{threshold:g} is below the § 8 limit for this site in this week "
            f"({decision.limit} per fish, {decision.region or 'region unknown'}"
            f"{', inside' if decision.in_spring_window else ', outside'} the spring window), "
            "so the watch would fire on a legal level. Set it at or above the limit."
        )
    return None


@router.get("/api/chat/receipts")
async def chat_receipts(
    limit: int = 50, user: TokenPayload | None = Depends(get_current_user)
):
    """The caller's own answer receipts: what was given, which model answered, at what cost.

    No question text is stored (it is hashed), and the facts carry their `as_of`, so a customer
    can check what the system knew at the time rather than take a transcript on trust.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="receipts belong to an account")
    from core.llm.receipts import RETENTION_MONTHS

    return {
        "receipts": await answer_receipts.list_for(_user_key(user), limit=max(1, min(limit, 200))),
        "retention_months": RETENTION_MONTHS,
        "note": (
            "the question is stored as a hash, not as text; the answer text is not stored. "
            "Retention is 24 months, after which the row is purged."
        ),
    }


@router.post("/api/chat/save-alert")
async def save_alert(
    req: SaveAlertRequest,
    user: TokenPayload | None = Depends(get_current_user),
):
    """Turn a question into a running alert rule, or say why it cannot be one."""
    from core.models import CustomAlertRule

    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="a question is required")

    metric = _infer_metric(question)
    if metric is None:
        return {
            "saved": False,
            "reason": "no metric found in the question",
            "available_metrics": [m for m, _ in _METRIC_KEYWORDS],
            "message": (
                "This watch needs a metric. Ask about lice, price, bloom or disease — "
                "for example 'tell me when lice in PA 3 goes above 0.4' — and it becomes "
                "a running alert."
            ),
        }

    area = _infer_area(question)
    threshold = _explicit_threshold(question)
    state = await _current_value(metric, question, area)
    if threshold is None:
        if not state.get("current"):
            return {
                "saved": False,
                "reason": "no verified current value to seed the threshold",
                "metric": metric,
                "metric_state": state,
                "message": (
                    "There is no verified current value for that metric on this deployment "
                    + (f"({state.get('note')})" if state.get("note") else "")
                    + ", so a threshold cannot be seeded honestly. Name one explicitly — "
                    "'above 0.4' — and the watch is created."
                ),
            }
        threshold = state.get("value")
    if threshold is None:
        return {
            "saved": False,
            "reason": "no threshold",
            "metric": metric,
            "message": "Name a threshold explicitly, for example 'above 0.5'.",
        }

    from core.market.verified_metrics import plausibility

    plausible, why = plausibility(metric, float(threshold))
    if not plausible:
        return {"saved": False, "reason": "implausible_threshold", "metric": metric,
                "message": why}

    if metric == "lice_avg":
        legal = await _lice_limit_check(area, float(threshold))
        if legal:
            return {"saved": False, "reason": "below_legal_limit", "metric": metric,
                    "message": legal}

    operator = _infer_operator(question)
    name = (req.name or question)[:100]

    async with get_async_session() as session:
        existing = (
            await session.execute(
                select(CustomAlertRule).where(
                    CustomAlertRule.name == name,
                    CustomAlertRule.metric == metric,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {
                "saved": False,
                "duplicate": True,
                "alert_id": existing.id,
                "name": existing.name,
                "metric": existing.metric,
                "operator": existing.operator,
                "threshold": existing.threshold,
                "production_area": existing.production_area,
                "message": "a watch with this wording and metric already exists",
            }
        rule = CustomAlertRule(
            name=name,
            metric=metric,
            operator=operator,
            threshold=round(float(threshold), 4),
            production_area=area,
            is_active=True,
            user_id=user.user_id if user else None,
        )
        session.add(rule)
        await session.commit()
        rule_id = rule.id

    log.info("chat.saved_alert", alert_id=rule_id, metric=metric, area=area, user=_user_key(user))
    return {
        "saved": True,
        "alert_id": rule_id,
        "name": name,
        "metric": metric,
        "operator": operator,
        "threshold": round(float(threshold), 4),
        "production_area": area,
        "is_active": True,
        "seeded_from": "explicit number in the question" if _explicit_threshold(question) else "the current verified value",
        "metric_state": state,
        "message": (
            f"watching {metric} {operator} {threshold:g}"
            + (f" in production area {area}" if area else " nationally")
            + " — it runs with the alert engine and appears in /notifications"
        ),
    }
