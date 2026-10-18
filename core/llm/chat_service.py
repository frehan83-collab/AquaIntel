"""The chat answer path: one service, grounded, metered, and honest when it cannot answer.

Before this module the platform had two chat paths: `/api/chat` in `core/api.py`, which
string-interpolated a snapshot (all rows, no age, a wrong traffic-light sentence) straight
into a prompt, and `core/llm/chat_agent.py`, which had real tools and was used only by the
briefing job. Two paths meant two behaviours, one of them ungrounded.

This service is the single path:

* **Grounded.** Every answer is built from :mod:`core.llm.grounding`, whose facts carry
  `as_of`, `source` and a provenance verdict. The prompt forbids numbers outside that block.
* **Bounded.** A question is truncated, a short answer cap is enforced, and every call
  records tokens and cost so a plan allowance can be metered (see `core/llm/usage.py`).
* **Honest.** With no provider key, or a provider failure, the answer is composed
  deterministically from the same grounded facts and labelled `mode: "grounded_fallback"`
  — the numbers still work, and the user is told the model did not write it.
* **Legal.** Directional questions about listed shares are answered from the withdrawal
  notice in :mod:`core.legal.equity_signals` without calling a model at all.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import structlog

from config.settings import settings
from core.llm.claim_check import strip_unsupported, verify
from core.llm.grounding import (
    MAX_QUESTION_CHARS,
    PlatformContext,
    PROVENANCE_LIVE,
    build_context,
)

log = structlog.get_logger(__name__)

#: Answers are capped so one question cannot consume a month of allowance.
MAX_ANSWER_TOKENS = 900

SYSTEM_PROMPT = """You are the AquaIntel analyst. You answer questions about Norwegian \
salmon aquaculture, feed economics and market structure for farmers, buyers and analysts.

Non-negotiable rules:
1. Every number you state must come from the VERIFIED DATA block or from a tool result in \
this conversation. If a number is not there, say what is missing; never estimate it, never \
recall one from training.
2. Respect the provenance labels. A fact marked STALE or DEGRADED is stated with its age \
and the reason, never in the present tense. An UNAVAILABLE fact is reported as a gap.
3. You are not a financial adviser. Never state or imply whether to buy, sell, hold or \
short a listed security, and never forecast a share price. If asked, explain that \
directional equity signals are withdrawn and point to the operating data instead.
4. Be brief and concrete: answer in at most 5 short paragraphs or a short list. Put the \
answer first, then the supporting numbers, then the caveat. No preamble, no filler, no \
"as an AI".
5. When the data does not support a confident answer, say so plainly and name what would \
be needed to answer properly."""

#: Questions that ask for a trade direction are answered from the legal notice.
_DIRECTIONAL_PATTERNS = (
    r"\bshould\s+i\s+(buy|sell|short|hold|invest)",
    r"\b(buy|sell|short)\s+(mowi|salm|lsg|gsf|salmar|leroy|lerøy|grieg|bakkafrost|salmon\s+stock)",
    r"\b(mowi|salm|lsg|gsf)\.?\s*(ol|stock|share|price\s+target|upside|downside)",
    r"\bprice\s+target\b",
    r"\bwill\s+the\s+(share|stock)\s+price\b",
    r"\bis\s+it\s+a\s+(buy|sell)\b",
    r"\b(mowi|salm|lsg|gsf|salmar|leroy)\b[^.?!]{0,40}\b(a\s+)?(buy|sell|short|hold)\b",
)

_DEFAULT_FOLLOWUPS = (
    "What moved the margin this week?",
    "How does lice pressure compare with the spring limit?",
    "Which origin is cheapest to land in the US right now?",
    "What would raise the break-even FCR?",
)


@dataclass
class ChatAnswer:
    """What the UI renders. `mode` says whether a model wrote the prose."""

    answer: str
    sources: list[dict] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)
    followups: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    model: str = ""
    #: True when a free OpenRouter model wrote this (WS-46): the quality of a paid
    #: seat's answer must be visible, not guessed.
    model_is_free: bool = False
    mode: str = "grounded"  # grounded | grounded_fallback | refusal | unavailable
    degraded: bool = False
    refusal: str | None = None
    #: Which numbers in the answer the verified data can support (WS-40).
    verification: dict = field(default_factory=dict)
    latency_ms: float = 0.0
    question: str = ""

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "sources": self.sources,
            "facts": self.facts,
            "followups": self.followups,
            "usage": self.usage,
            "model": self.model,
            "model_is_free": self.model_is_free,
            "mode": self.mode,
            "degraded": self.degraded,
            "verification": self.verification,
            "refusal": self.refusal,
            "latency_ms": self.latency_ms,
            "question": self.question,
        }


def is_directional(question: str) -> bool:
    """True when the question asks for a trade call on a listed security."""
    lowered = (question or "").lower()
    return any(re.search(pattern, lowered) for pattern in _DIRECTIONAL_PATTERNS)


def _truncate(question: str) -> str:
    text = (question or "").strip()
    if len(text) <= MAX_QUESTION_CHARS:
        return text
    log.info("chat.question_truncated", chars=len(text), kept=MAX_QUESTION_CHARS)
    return text[:MAX_QUESTION_CHARS]


def _fallback_answer(context: PlatformContext, question: str) -> str:
    """A deterministic answer from the grounded facts, used when no model is reachable.

    It is deliberately plain: the point is that the numbers and their caveats still reach
    the reader, and the UI says a model did not write it.
    """
    usable = [f for f in context.facts if f.usable]
    if not usable:
        return (
            "I cannot answer that from verified data: none of the platform's feeds are "
            "returning values on this deployment right now. Nothing here is estimated — "
            "check the data status before relying on any figure."
        )
    lines = ["Here are the verified numbers behind that question:", ""]
    for fact in usable:
        lines.append(f"• {fact.line().lstrip('- ').strip()}")
    stale = [f for f in context.facts if f.provenance != PROVENANCE_LIVE and f.usable]
    if stale:
        lines.append("")
        lines.append(
            "Note the labels: "
            + ", ".join(f"{f.label} ({f.provenance}" + (f", {f.age_days}d old)" if f.age_days is not None else ")") for f in stale)
            + "."
        )
    missing_facts = [f for f in context.facts if not f.usable]
    if missing_facts:
        lines.append("Not available on this deployment (I will not estimate them):")
        for fact in missing_facts:
            lines.append(f"• {fact.label} — {fact.note or 'no data'}")
    lines.append("")
    lines.append(
        "This answer was assembled directly from the platform's verified feeds because the "
        "language model is not configured or could not be reached; every figure above is real."
    )
    return "\n".join(lines)


def _followups(context: PlatformContext) -> list[str]:
    suggestions: list[str] = []
    margin = context.get("margin.bridge")
    if margin and margin.usable:
        suggestions.append("What moved the margin this week?")
        suggestions.append("What would bring the feed leg down?")
    lice = context.get("lice.national")
    if lice and lice.usable:
        suggestions.append("Which production areas are near the § 8 limit?")
    elif lice is not None:
        suggestions.append("When was the last verified lice report?")
    bloom = context.get("bloom.chlorophyll")
    if bloom and bloom.usable:
        suggestions.append("How old is the newest chlorophyll scene?")
    suggestions.append("Which origin is cheapest to land in the US right now?")
    for candidate in _DEFAULT_FOLLOWUPS:
        if candidate not in suggestions:
            suggestions.append(candidate)
    return suggestions[:4]


def _data_status(context: PlatformContext) -> str:
    """A deterministic data-status line, built only from the facts."""
    parts: list[str] = []
    for fact in context.facts:
        if fact.provenance == "unavailable":
            parts.append(f"{fact.label} is unavailable")
        elif fact.provenance != "live":
            age = f", {fact.age_days}d old" if fact.age_days is not None else ""
            parts.append(f"{fact.label} is {fact.provenance}{age}")
    return ("Data status: " + "; ".join(parts) + ".") if parts else ""


class ChatService:
    """One answer path. Call `ask()`; it never raises for a data or provider problem."""

    def __init__(self, complete=None) -> None:
        # Injectable so tests never touch the network.
        self._complete = complete

    async def _run_model(self, prompt: str, system: str, user_id: str):
        if self._complete is not None:
            return await self._complete(prompt=prompt, system=system, user_id=user_id)
        from core.llm.client import llm_client

        return await llm_client.complete(
            prompt=prompt,
            system=system,
            max_tokens=MAX_ANSWER_TOKENS,
            temperature=0.2,
            user_id=user_id,
        )

    async def ask(
        self,
        question: str,
        *,
        user_id: str = "anonymous",
        history: list[dict] | None = None,
        site: dict | None = None,
        allow_model: bool = True,
    ) -> ChatAnswer:
        started = dt.datetime.now(dt.UTC)
        question = _truncate(question)
        if not question:
            return ChatAnswer(
                answer="Ask a question about lice, feed costs, margin, bloom risk or "
                       "origin competitiveness and I will answer from the platform's data.",
                mode="unavailable",
                followups=list(_DEFAULT_FOLLOWUPS),
                question="",
            )

        if is_directional(question):
            from core.legal.equity_signals import chat_answer

            return ChatAnswer(
                answer=chat_answer(),
                mode="refusal",
                refusal=chat_answer(),
                followups=[
                    "How are lice trends developing by production area?",
                    "What is the current margin per kg?",
                    "Which origin is cheapest to land in the US?",
                ],
                question=question,
                degraded=False,
            )

        context = await build_context(site=site)
        prompt = self._build_prompt(context, question, history or [])

        model_is_free = False
        try:
            if not allow_model:
                # WS-50: the plan's model allowance is spent (or the plan has none). The
                # deterministic path still answers from the verified facts and costs nothing.
                raise RuntimeError("model not allowed for this plan state")
            response = await self._run_model(prompt, SYSTEM_PROMPT, user_id)
            provider_error = getattr(response, "error", None)
            if provider_error:
                raise RuntimeError(f"provider error: {provider_error}"[:200])
            text = (getattr(response, "content", "") or "").strip()
            if not text:
                raise RuntimeError("empty completion")
            mode = "grounded"
            model = getattr(response, "model", "") or settings.llm_model
            model_is_free = bool(getattr(response, "is_free", False))
            usage = {
                "input_tokens": int(getattr(response, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(response, "output_tokens", 0) or 0),
                "cost_usd": round(float(getattr(response, "cost_usd", 0.0) or 0.0), 6),
            }
        except Exception as exc:  # noqa: BLE001 — degrade, never 500 into the chat
            log.warning("chat.model_unavailable", error=str(exc)[:160])
            text = _fallback_answer(context, question)
            mode = "grounded_fallback"
            model = ""
            usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

        # WS-40: check the digits, not the citations. A number that appears in no fact is
        # kept (a model may legitimately derive a percentage) but named in the payload and
        # badged in the UI, and the answer carries one honest caveat sentence.
        verification = verify(text, [fact.to_dict() for fact in context.facts])
        if not verification.clean:
            # WS-44: fail closed. The sentence carrying an unsupported number is removed
            # and the answer says so; a caveat beside an invented figure is not enough.
            cleaned, removed = strip_unsupported(text, verification)
            log.info(
                "chat.numbers_withheld",
                sentences=removed,
                count=len(verification.unverified),
                checked=verification.checked,
            )
            text = cleaned or (
                "I cannot give a verified answer to that: the numbers produced could "
                "not be matched to the platform's data, so they were withheld."
            )
            if removed:
                # WS-47: stripping can remove the sentence that carried the honesty caveat, so
                # the data status is reattached from the facts themselves — never from the
                # model — or a withheld answer would read as a confident one.
                status = _data_status(context)
                text = (
                    text
                    + f"\n\n({len(verification.unverified)} number(s) were withheld "
                    "because the verified data could not support them.)"
                    + (f"\n{status}" if status else "")
                )

        elapsed = (dt.datetime.now(dt.UTC) - started).total_seconds() * 1000
        return ChatAnswer(
            answer=text,
            sources=context.sources(),
            facts=[fact.to_dict() for fact in context.facts],
            followups=_followups(context),
            usage=usage,
            model=model,
            model_is_free=model_is_free,
            mode=mode,
            degraded=context.degraded or not verification.clean,
            verification=verification.to_dict(),
            latency_ms=round(elapsed, 1),
            question=question,
        )

    @staticmethod
    def _build_prompt(context: PlatformContext, question: str, history: list[dict]) -> str:
        parts = [context.block(), ""]
        recent = [h for h in history if h.get("role") in ("user", "assistant")][-4:]
        if recent:
            parts.append("EARLIER IN THIS CONVERSATION (context only — it contains no "
                         "additional verified numbers):")
            for entry in recent:
                role = "User" if entry.get("role") == "user" else "You"
                content = str(entry.get("content", ""))[:600]
                parts.append(f"{role}: {content}")
            parts.append("")
        parts.append(f"QUESTION: {question}")
        parts.append("")
        parts.append(
            "Answer per the rules. If the verified data cannot settle the question, say "
            "what is missing instead of guessing."
        )
        return "\n".join(parts)


chat_service = ChatService()
