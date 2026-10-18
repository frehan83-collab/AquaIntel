"""Deep analysis runs — the product a credit buys.

A chat answer is a paragraph. A workbench run is a **document**: it pulls several engines
together, states its assumptions, and ends with the decision and the numbers behind it. Three
runs ship here:

* ``margin_dossier`` — the price/cost/margin position, what moved, the break-even, the levers
  and the feed-data age.
* ``origin_landed_cost`` — the delivered-cost ranking with the customs-value duty basis, the
  FX observation dates and the freight assumptions.
* ``lice_pressure_review`` — verified lice coverage, the § 8 limit for the week, the
  traffic-light decision and what the data cannot say.

Every run is grounded the same way the chat is (facts with provenance), and when no model is
reachable it returns a deterministic **data digest** instead of prose — with
``mode: "digest"`` and **no credit spent**, because a customer must not pay for a document a
model did not write.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import structlog

from core.llm.claim_check import verify
from core.llm.grounding import PlatformContext, build_context

log = structlog.get_logger(__name__)

MAX_DOCUMENT_TOKENS = 2200

RUN_KINDS: dict[str, dict] = {
    "margin_dossier": {
        "key": "margin_dossier",
        "name": "Margin dossier",
        "blurb": "Where the margin is, what moved it, and what closes the gap",
        "reads": "SSB price, feed basket, margin bridge, break-even, levers",
        "credits": 1,
    },
    "origin_landed_cost": {
        "key": "origin_landed_cost",
        "name": "Origin landed cost",
        "blurb": "Delivered cost per origin with the customs-value duty basis",
        "reads": "Competitiveness index, US tariff register, Norges Bank FX, freight",
        "credits": 1,
    },
    "lice_pressure_review": {
        "key": "lice_pressure_review",
        "name": "Lice pressure review",
        "blurb": "Withdrawn until a verified lice source returns — see the notice",
        "reads": "Verified lice rows, § 8 limit, traffic-light decision, 2019/2025 event history",
        "credits": 1,
        # WS-43: the last verified lice row on this deployment is 2026-W15. Selling a document
        # whose subject feed is seven months dead is the cardinal sin with an invoice, so the
        # run stays in the catalogue with its reason and does not take credits.
        "sellable": False,
        "withdrawn_reason": (
            "no verified lice report exists on this deployment since 2026-W15, so the review "
            "would describe dead data; credits already bought are redeemable against the "
            "margin dossier or the origin landed-cost run"
        ),
    },
}

DOCUMENT_SYSTEM_PROMPT = """You are writing a short analytical document for a salmon \
industry professional. You are given a VERIFIED DATA block assembled from the platform's \
engines; every number in the document must come from it.

Structure the document exactly like this, in markdown:
1. A one-line verdict.
2. `## What the numbers say` — 3-6 bullets, each with its figure and the date it refers to.
3. `## What moved` — only if the data contains a change; otherwise say it does not.
4. `## The decision` — what a reader should do with this, and what would change it.
5. `## What this document cannot tell you` — the gaps and stale feeds, named.

Rules: cite only figures from the block; give every stale or modelled figure its age or \
label; never estimate a missing number; no financial advice and no share-price direction; \
no preamble and no "as an AI"."""


@dataclass
class WorkbenchDocument:
    kind: str
    title: str
    document: str
    mode: str  # model | digest
    sources: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    credits_spent: int = 0
    credits_after: int | None = None
    generated_at: str = ""
    degraded: bool = False
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "title": self.title,
            "document": self.document,
            "mode": self.mode,
            "sources": self.sources,
            "usage": self.usage,
            "verification": self.verification,
            "credits_spent": self.credits_spent,
            "credits_after": self.credits_after,
            "generated_at": self.generated_at,
            "degraded": self.degraded,
            "latency_ms": self.latency_ms,
        }


def _margin_payload(bridge: dict) -> str:
    margin = bridge.get("margin") or {}
    legs = {leg.get("key"): leg for leg in (bridge.get("legs") or [])}
    feed = legs.get("feed") or {}
    price = legs.get("price") or {}
    changes = bridge.get("changes") or {}
    break_even = bridge.get("break_even") or {}
    levers = bridge.get("levers") or []
    lines = [
        f"Week: {bridge.get('week')}",
        f"Spot: {margin.get('spot_nok_per_kg')} NOK/kg",
        f"Modelled cost: {margin.get('modelled_cost_nok_per_kg')} NOK/kg",
        f"Margin: {margin.get('nok_per_kg')} NOK/kg ({margin.get('pct')} %)",
        f"Quality: {margin.get('quality')} ({margin.get('quality_basis')})",
        f"Feed leg: {feed.get('nok_per_kg')} NOK/kg, period {feed.get('period')} "
        f"(status {feed.get('status')})",
        f"Price week-on-week: {((price.get('meta') or {}).get('week_on_week_nok_per_kg'))} NOK/kg",
        f"Feed month-on-month: {changes.get('feed_change_nok_per_kg')} NOK/kg",
        f"Break-even: {break_even}",
    ]
    for lever in levers[:5]:
        lines.append(
            f"Lever: {lever.get('name')} — {lever.get('effect_nok_per_kg')} NOK/kg"
        )
    return "\n".join(lines)


def _competitiveness_payload(index: dict) -> str:
    lines = [
        f"US spot used: {index.get('us_spot_usd_kg')} USD/kg",
        f"Duty basis: {index.get('tariff_basis')}",
        f"FX: {index.get('fx_rates')}",
        # WS-43: the engine's own honesty fields, so the model cannot present a fallback
        # spot or a constant FX rate as verified data.
        f"Data quality: {index.get('data_quality')}",
        f"FX fallbacks: {index.get('fx_fallbacks')}",
        f"Fallback reason: {index.get('fallback_reason')}",
    ]
    for origin in index.get("origins") or []:
        lines.append(
            f"{origin.get('country')}: production {origin.get('production_cost_usd')} USD/kg, "
            f"tariff {origin.get('tariff_pct')} on {origin.get('tariff_base')}"
            + (f" (export price {origin.get('export_price_usd')} USD/kg)"
               if origin.get("export_price_usd") else "")
            + f", freight {origin.get('freight_usd')} USD/kg, "
            f"delivered {origin.get('total_delivered_usd')} USD/kg"
        )
    return "\n".join(lines)


def _digest(kind: str, context: PlatformContext, payload: str) -> str:
    """Deterministic document used when no model is reachable. No credit is spent."""
    lines = [
        f"# {RUN_KINDS[kind]['name']}",
        "",
        "A verified model document was not delivered for this run, so the verified data itself "
        "is returned instead of generated prose. Every figure below carries its as_of and its "
        "basis; none is estimated.",
        "",
        "## Verified facts",
    ]
    for fact in context.facts:
        lines.append(f"- {fact.line().lstrip('- ').strip()}")
    lines.extend(["", "## Engine detail", "```", payload, "```"])
    return "\n".join(lines)


class Workbench:
    """Runs the deep analyses. `complete` is injectable so tests never touch the network."""

    def __init__(self, complete=None) -> None:
        self._complete = complete

    async def _run_model(self, prompt: str, system: str, user_id: str):
        if self._complete is not None:
            return await self._complete(prompt=prompt, system=system, user_id=user_id)
        from core.llm.client import llm_client

        return await llm_client.complete(
            prompt=prompt,
            system=system,
            max_tokens=MAX_DOCUMENT_TOKENS,
            temperature=0.2,
            user_id=user_id,
        )

    async def _engine_detail(self, kind: str) -> str:
        if kind == "margin_dossier":
            from core.market.margin_bridge import margin_bridge

            return _margin_payload(await margin_bridge.build())
        if kind == "origin_landed_cost":
            from core.market.competitiveness_engine import competitiveness_engine

            return _competitiveness_payload(await competitiveness_engine.compute_index())
        if kind == "lice_pressure_review":
            lines = []
            try:
                from core.bloom.context import REGIONAL_EVENTS

                for event in REGIONAL_EVENTS:
                    lines.append(
                        f"Historical event: {event.get('year')} {event.get('species')} — "
                        f"{event.get('mortality')}"
                    )
            except Exception:  # noqa: BLE001 — optional context
                pass
            return "\n".join(lines) or "No additional engine detail available."
        return ""

    async def run(self, kind: str, *, user_id: str = "anonymous") -> WorkbenchDocument:
        started = dt.datetime.now(dt.UTC)
        if kind not in RUN_KINDS:
            raise ValueError(f"unknown run kind: {kind}")
        context = await build_context()
        detail = await self._engine_detail(kind)
        prompt = (
            f"{context.block()}\n\nENGINE DETAIL ({kind}):\n{detail}\n\n"
            f"Write the {RUN_KINDS[kind]['name']} now, following the structure exactly."
        )
        mode = "model"
        usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        try:
            response = await self._run_model(prompt, DOCUMENT_SYSTEM_PROMPT, user_id)
            provider_error = getattr(response, "error", None)
            if provider_error:
                raise RuntimeError(f"provider error: {provider_error}"[:200])
            document = (getattr(response, "content", "") or "").strip()
            if not document:
                raise RuntimeError("empty document")
            usage = {
                "input_tokens": int(getattr(response, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(response, "output_tokens", 0) or 0),
                "cost_usd": round(float(getattr(response, "cost_usd", 0.0) or 0.0), 6),
            }
        except Exception as exc:  # noqa: BLE001 — degrade to the data digest
            log.warning("workbench.model_unavailable", kind=kind, error=str(exc)[:160])
            document = _digest(kind, context, detail)
            mode = "digest"

        # WS-43: verify the document before anyone is charged for it. An unmatched number
        # withholds the prose — a caveat does not travel with a forwarded PDF, and the
        # verified data does.
        verification = verify(document, [fact.to_dict() for fact in context.facts])
        if mode == "model" and not verification.clean:
            log.warning(
                "workbench.withheld",
                kind=kind,
                unmatched=len(verification.unverified),
                numbers=verification.checked,
            )
            document = _digest(kind, context, detail)
            mode = "withheld"
            usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

        elapsed = (dt.datetime.now(dt.UTC) - started).total_seconds() * 1000
        return WorkbenchDocument(
            kind=kind,
            title=RUN_KINDS[kind]["name"],
            document=document,
            mode=mode,
            sources=context.sources(),
            usage=usage,
            verification=verification.to_dict(),
            generated_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            degraded=context.degraded,
            latency_ms=round(elapsed, 1),
        )


workbench = Workbench()
