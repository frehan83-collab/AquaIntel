"""Legal foundations as an API — so the boundary is a fact, not a promise.

Serves the data-license register (allowed uses and resale per source), the
signals-vs-advice boundary, the EU AI Act transparency notes and the
performance-fee deferral status. Public read: customers and their counsel can check
what we may do with each source and what our outputs are (and are not).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.legal.equity_signals import advice_boundary_entry

router = APIRouter(prefix="/api/legal", tags=["legal"])

# Reusable, mandatory disclosure string for every signal/forecast surface.
SIGNAL_DISCLOSER = (
    "Descriptive indicator, not investment advice. No personalised recommendation "
    "is made and no execution service is provided."
)

ADVICE_BOUNDARY = {
    "what_we_are": (
        "An information and analytics service: we publish data, indicators, "
        "forecasts and their provenance for professional users to interpret."
    ),
    "what_we_are_not": [
        "Not an investment adviser and not licensed to give personal recommendations.",
        "Not a broker, not a trading venue, and we do not execute orders.",
        "Not a guarantee: forecasts are probabilistic and are published with their "
        "measured error, or with no error figure at all when none has been measured.",
    ],
    "safeguards": [
        "Every signal/forecast response carries the standard discloser string.",
        "Indices publish their method version, component weights and provenance.",
        "Accuracy figures appear only when a validated artifact produced them "
        "(see /api/accuracy/method).",
        "No output is framed as a recommendation to buy, sell or hold a security; "
        "the outputs that were, and those still under review, are listed in "
        "withdrawn_outputs.",
        "No execution, no order routing, no discretionary management.",
    ],
    "required_disclosure": SIGNAL_DISCLOSER,
    # WS-20: outputs taken down because they crossed (or may cross) this boundary
    "withdrawn_outputs": [advice_boundary_entry()],
    "jurisdiction_notes": [
        "Assessed against Norwegian and EU regimes (MiFID II perimeter, Norwegian "
        "securities law). Other jurisdictions require separate review.",
        "Marketing material must not present the platform as an adviser.",
    ],
    "classification_status": "pending_legal_review",
    "statement": (
        "Engineering position only — legal advice is required before this boundary is "
        "relied upon commercially."
    ),
}

AI_ACT_NOTES = {
    "uses_ai": True,
    "systems": [
        {
            "system": "Forecasting engines (foundation models + seasonal-naive fallback)",
            "purpose": "Probabilistic price/supply/lice forecasting for professional users.",
            "transparency": (
                "Responses state models_used vs models_fallback and set is_live=false "
                "whenever a fallback produced the number."
            ),
            "human_oversight": "No automated decision with legal effect on a person.",
            "limitation_disclosure": "/api/accuracy/method",
        },
        {
            "system": "Retrieval-augmented assistant over scientific literature",
            "purpose": "Answering questions from cited documents.",
            "transparency": "Answers cite sources; no autonomous action is taken.",
            "human_oversight": "The user interprets and decides.",
            "limitation_disclosure": "/api/accuracy/method",
        },
        {
            "system": "Grounded assistant (chat) and deep-analysis documents",
            "purpose": (
                "Answering questions and writing short documents from the platform's verified "
                "feeds for professional users."
            ),
            "transparency": (
                "Every answer carries its sources with observation dates and a provenance verdict; "
                "numbers the data cannot support are withheld and the answer says how many; a "
                "free-model answer is labelled. Article 50(1): the user is told an AI system is "
                "answering (see the notice at /chat)."
            ),
            "human_oversight": (
                "Advisory only: no automated decision with legal effect, and directional equity "
                "output is withdrawn (see /api/legal/advice-boundary)."
            ),
            "limitation_disclosure": "/api/accuracy/method and /api/chat/receipts",
        },
        {
            "system": "Anomaly and risk scoring",
            "purpose": "Flagging unusual lice/production/market patterns for review.",
            "transparency": "Scores carry provenance and are advisory signals.",
            "human_oversight": "Flags are reviewed by the user before any action.",
            "limitation_disclosure": "/api/accuracy/method",
        },
    ],
    "risk_classification": (
        "limited-risk (transparency obligations) — engineering assessment, pending "
        "legal confirmation"
    ),
    "prohibited_practices_not_used": [
        "No social scoring.",
        "No biometric categorisation or emotion recognition.",
        "No untargeted scraping of facial images.",
        "No manipulation or exploitation of vulnerabilities.",
    ],
    "data_governance": (
        "Training/ingestion rights are tracked per source in /api/legal/data-licenses, "
        "including whether AI training is permitted at all."
    ),
    "personal_data": (
        "Account and contact data, plus the text of a question asked in the assistant and the "
        "market facts assembled to answer it, which are sent to the inference sub-processor "
        "listed in /api/legal/sub-processors. That register states which transfers have a "
        "signed instrument and which do not; retention of a question is a hash, not the text "
        "(see /api/chat/receipts)."
    ),
    "statement": (
        "Transparency notes provided for customer due diligence. This is an "
        "engineering summary, not a conformity assessment."
    ),
}


@router.get("/data-licenses")
async def data_licenses():
    """The data-license register: allowed uses and resale per source."""
    from core.legal.data_licenses import USES, _index, compliance_summary

    return {
        "uses_vocabulary": list(USES),
        "sources": [
            {
                "key": s.key,
                "label": s.label,
                "upstream": s.upstream,
                "license_type": s.license_type,
                "allowed_uses": list(s.allowed_uses),
                "resale_allowed": s.resale_allowed,
                "attribution_required": s.attribution_required,
                "ai_training_allowed": s.ai_training_allowed,
                "redistribution_notes": s.redistribution_notes,
                "refresh_terms": s.refresh_terms,
                "classification_status": s.classification_status,
                "reviewed_by": s.reviewed_by,
                "contract_ref": s.contract_ref,
                "risks": list(s.risks),
            }
            for s in _index().values()
        ],
        "summary": compliance_summary(),
    }


@router.get("/data-licenses/{source_key}")
async def data_license(source_key: str):
    """One source's licence terms."""
    from core.legal.data_licenses import get

    source = get(source_key)
    if source is None:
        raise HTTPException(404, f"Source '{source_key}' is not registered")
    return {
        "key": source.key,
        "label": source.label,
        "license_type": source.license_type,
        "allowed_uses": list(source.allowed_uses),
        "resale_allowed": source.resale_allowed,
        "attribution_required": source.attribution_required,
        "ai_training_allowed": source.ai_training_allowed,
        "redistribution_notes": source.redistribution_notes,
        "risks": list(source.risks),
        "classification_status": source.classification_status,
    }


@router.get("/use-check")
async def use_check(source: str, use: str):
    """May we use `source` for `use`? (uncleared uses are refused)"""
    from core.legal.data_licenses import check_use

    try:
        return check_use(source, use)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/advice-boundary")
async def advice_boundary():
    """The signals-vs-advice boundary and the mandatory discloser string."""
    return ADVICE_BOUNDARY


@router.get("/sub-processors")
async def sub_processors():
    """Which processors can receive customer content, and what is actually in place."""
    from config.settings import settings

    from core.legal.subprocessors import disclosure

    return disclosure(getattr(settings, "llm_provider", None))


@router.get("/ai-act")
async def ai_act():
    """EU AI Act transparency notes for the AI systems actually in use."""
    return AI_ACT_NOTES


@router.get("/performance-fee")
async def performance_fee():
    """Performance-fee status — deferred, with the conditions to enable it."""
    from core.legal.performance_fee import status

    return status()
