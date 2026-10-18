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

import re

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from core.async_db import get_async_session
from core.auth import TokenPayload, get_current_user
from core.entitlements import get_plan, upgrade_hint
from core.llm import usage as chat_usage
from core.llm.chat_service import MAX_QUESTION_CHARS, chat_service
from core.llm.grounding import build_context

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

    if chat_usage.not_included(status_payload):
        log.info("chat.blocked_not_included", plan=plan_key)
        return JSONResponse(
            status_code=402,
            content=_payment_required(
                plan_key=plan_key,
                path="/api/chat",
                reason=(
                    f"grounded chat is not part of the {plan_name} plan; it is included "
                    "from Operator (100 questions a month) and Desk (300) upwards"
                ),
                status_payload=status_payload,
            ),
        )

    if chat_usage.exhausted(status_payload):
        log.info("chat.blocked_allowance", plan=plan_key, used=status_payload.get("used"))
        return JSONResponse(
            status_code=402,
            content=_payment_required(
                plan_key=plan_key,
                path="/api/chat",
                reason=(
                    f"the {plan_name} plan includes {status_payload['allowance']} grounded "
                    f"questions a month and all of them are used; the allowance resets "
                    f"{status_payload['resets_on']}"
                ),
                status_payload=status_payload,
            ),
        )

    site = await _resolve_site(req.locality_no) if req.locality_no else None
    answer = await chat_service.ask(
        req.message, user_id=key, history=req.history, site=site
    )

    # Only a model-backed answer consumes the allowance: a refusal or an unavailable
    # answer costs nothing, so it is not counted against a paying customer.
    if answer.mode == "grounded":
        await chat_usage.record(key, answer.usage)

    refreshed = await chat_usage.status(key, plan_key)
    refreshed["plan_name"] = plan_name
    payload = answer.to_dict()
    payload["chat"] = refreshed
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


async def _current_value(metric: str, question: str) -> float | None:
    """The platform's current value for the metric, used as the default threshold."""
    context = await build_context()
    if metric == "lice_avg":
        fact = context.get("lice.national")
        if fact and fact.usable and isinstance(fact.value, dict):
            return fact.value.get("average_per_fish")
    if metric == "spot_price":
        fact = context.get("margin.bridge")
        if fact and fact.usable and isinstance(fact.value, dict):
            return fact.value.get("spot_nok_per_kg")
    if metric == "bloom_risk":
        fact = context.get("bloom.chlorophyll")
        if fact and fact.usable and isinstance(fact.value, dict):
            return fact.value.get("mean_mg_m3")
    return None


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

    threshold = _explicit_threshold(question)
    if threshold is None:
        threshold = await _current_value(metric, question)
    if threshold is None:
        return {
            "saved": False,
            "reason": "no current value to seed the threshold",
            "metric": metric,
            "message": (
                "There is no verified current value for that metric on this deployment, so "
                "a useful threshold cannot be set. Name one explicitly — 'above 0.4' — and "
                "the watch is created."
            ),
        }

    operator = _infer_operator(question)
    area = _infer_area(question)
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
        "message": (
            f"watching {metric} {operator} {threshold:g}"
            + (f" in production area {area}" if area else " nationally")
            + " — it runs with the alert engine and appears in /notifications"
        ),
    }
