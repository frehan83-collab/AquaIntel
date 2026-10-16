"""Data-license register — allowed uses and resale per source.

A commercial platform must answer, per source: **may we use this, and may we
resell it?** That decides whether the Data & Assurance tier is sellable at all, and
it cannot be answered by engineering alone.

Honesty rule: this module does NOT invent legal conclusions. Every entry carries
``classification_status``:

  * ``pending_legal_review`` — engineering's best understanding, **not** cleared
    for resale. The default for everything.
  * ``cleared`` — a named human (``reviewed_by``/``reviewed_at``) signed it off.

``compliance_summary()`` therefore reports how many sources are *uncleared*, which
is the honest state of the sprint: the register makes the gaps visible instead of
claiming compliance we have not obtained.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)

USES = (
    "internal_analysis",
    "public_display",
    "paid_customer_display",
    "api_redistribution",
    "ai_training",
    "derived_index_publication",
    "resale_as_data_product",
)

PENDING = "pending_legal_review"
CLEARED = "cleared"


@dataclass(frozen=True)
class SourceLicense:
    key: str
    label: str
    upstream: str
    license_type: str              # open_data | public_registry | commercial | partner | international | mixed
    allowed_uses: tuple[str, ...]
    resale_allowed: bool
    attribution_required: bool
    redistribution_notes: str
    ai_training_allowed: bool
    refresh_terms: str
    classification_status: str = PENDING
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    contract_ref: str | None = None
    risks: tuple[str, ...] = field(default_factory=tuple)


_ALL_OPEN = (
    "internal_analysis",
    "public_display",
    "paid_customer_display",
    "derived_index_publication",
)

SOURCES: tuple[SourceLicense, ...] = (
    SourceLicense(
        key="fiskeridir_lice",
        label="Sea lice counts (Fiskeridir / Mattilsynet)",
        upstream="Fiskeridir Directorate of Fisheries open API",
        license_type="public_registry",
        allowed_uses=_ALL_OPEN + ("api_redistribution",),
        resale_allowed=True,
        attribution_required=True,
        redistribution_notes="Norwegian public-sector data (NLOD); attribution required.",
        ai_training_allowed=True,
        refresh_terms="Weekly upstream cadence.",
        risks=("NLOD conditions must be reproduced verbatim in the API terms.",),
    ),
    SourceLicense(
        key="ssb_prices",
        label="Salmon export prices (SSB)",
        upstream="Statistics Norway (SSB) API",
        license_type="open_data",
        allowed_uses=_ALL_OPEN + ("api_redistribution",),
        resale_allowed=True,
        attribution_required=True,
        redistribution_notes="SSB open data; cite table numbers on every surface.",
        ai_training_allowed=True,
        refresh_terms="Weekly.",
        risks=("SSB revises history; a published index must record the table version.",),
    ),
    SourceLicense(
        key="copernicus_marine",
        label="SST / chlorophyll (Copernicus Marine)",
        upstream="Copernicus Marine Service (CMEMS)",
        license_type="international",
        allowed_uses=_ALL_OPEN,
        resale_allowed=False,
        attribution_required=True,
        redistribution_notes=(
            "Copernicus licence permits use and derived products; redistributing raw "
            "data as a standalone product is NOT permitted. Derived indices are fine."
        ),
        ai_training_allowed=True,
        refresh_terms="Daily; 3-6h latency.",
        risks=("Raw tiles must never be resold; only derived indicators published.",),
    ),
    SourceLicense(
        key="nasa_mur_sst",
        label="MUR sea-surface temperature (NASA JPL)",
        upstream="NASA JPL MUR / PO.DAAC",
        license_type="open_data",
        allowed_uses=_ALL_OPEN + ("api_redistribution",),
        resale_allowed=True,
        attribution_required=True,
        redistribution_notes="NASA open data; attribute 'Courtesy NASA/JPL-Caltech'.",
        ai_training_allowed=True,
        refresh_terms="Daily.",
    ),
    SourceLicense(
        key="fish_pool_futures",
        label="Salmon futures (Fish Pool / Euronext)",
        upstream="Fish Pool / Euronext",
        license_type="commercial",
        allowed_uses=("internal_analysis", "paid_customer_display"),
        resale_allowed=False,
        attribution_required=True,
        redistribution_notes=(
            "Exchange data is licensed per exchange agreement: display to paying "
            "customers only, no redistribution, no derived index publication without "
            "written consent."
        ),
        ai_training_allowed=False,
        refresh_terms="Per exchange agreement; delayed quotes may be public.",
        risks=(
            "Any public page showing Fish Pool/Euronext prices needs an exchange "
            "display licence — BLOCKING for public index publication.",
        ),
    ),
    SourceLicense(
        key="producer_contributed",
        label="Producer-contributed operational data",
        upstream="Design partners (lice counts, harvest plans, treatments)",
        license_type="partner",
        allowed_uses=("internal_analysis", "paid_customer_display", "ai_training"),
        resale_allowed=False,
        attribution_required=False,
        redistribution_notes=(
            "Shared under the pilot reciprocity terms: usable in aggregates and "
            "derived indices, never resold individually, never attributed to the "
            "partner without consent."
        ),
        ai_training_allowed=True,
        refresh_terms="Per reciprocity agreement (usually weekly).",
        risks=(
            "An aggregation threshold is needed so one partner cannot be "
            "de-anonymised from a published index (n>=5 producers recommended).",
        ),
    ),
    SourceLicense(
        key="eudr_submissions",
        label="EUDR / due-diligence submissions",
        upstream="Importers and producers submitting compliance records",
        license_type="partner",
        allowed_uses=("internal_analysis", "paid_customer_display"),
        resale_allowed=False,
        attribution_required=False,
        redistribution_notes=(
            "Regulatory submissions: used to serve the submitting organisation, not "
            "redistributed."
        ),
        ai_training_allowed=False,
        refresh_terms="Per submission.",
        risks=("Contains commercial/regulatory claims; treat as confidential.",),
    ),
    SourceLicense(
        key="research_literature",
        label="Scientific literature (RAG corpus)",
        upstream="Open-access papers and publisher abstracts",
        license_type="mixed",
        allowed_uses=("internal_analysis", "ai_training"),
        resale_allowed=False,
        attribution_required=True,
        redistribution_notes=(
            "Only open-access full texts may be ingested; abstracts are quoted with "
            "attribution, never reproduced in bulk."
        ),
        ai_training_allowed=True,
        refresh_terms="Ad hoc.",
        risks=("Publisher TDM rights vary; keep an allow-list of OA sources.",),
    ),
)


def _index() -> dict[str, SourceLicense]:
    return {s.key: s for s in SOURCES}


def get(source_key: str) -> SourceLicense | None:
    return _index().get(source_key)


def check_use(source_key: str, use: str) -> dict:
    """Whether a use is permitted for a source, and whether it is legally cleared.

    Never returns ``allowed: True`` for a use we have not cleared: a usage
    permitted by the licence but uncleared by legal comes back with
    ``requires_legal_signoff: True``.
    """
    if use not in USES:
        raise ValueError(f"unknown use '{use}' (expected one of {list(USES)})")
    source = get(source_key)
    if source is None:
        return {
            "source": source_key,
            "use": use,
            "allowed": False,
            "reason": "source not registered — register it before using it",
            "requires_legal_signoff": True,
        }
    permitted = use in source.allowed_uses
    cleared = source.classification_status == CLEARED
    return {
        "source": source_key,
        "use": use,
        "permitted_by_licence": permitted,
        "allowed": bool(permitted and cleared),
        "classification_status": source.classification_status,
        "requires_legal_signoff": not cleared,
        "resale_allowed": source.resale_allowed,
        "attribution_required": source.attribution_required,
        "notes": source.redistribution_notes,
    }


def compliance_summary() -> dict:
    """Honest state of the sprint: what is cleared, what still needs a lawyer."""
    index = _index()
    pending = [s.key for s in SOURCES if s.classification_status != CLEARED]
    return {
        "as_of": dt.datetime.now(dt.UTC).isoformat(),
        "registered_sources": len(index),
        "cleared": len(index) - len(pending),
        "pending_legal_review": pending,
        "resale_allowed": [s.key for s in SOURCES if s.resale_allowed],
        "resale_not_allowed": [s.key for s in SOURCES if not s.resale_allowed],
        "blocking_for_data_product": [
            f"{s.key}: {s.redistribution_notes}" for s in SOURCES if not s.resale_allowed
        ],
        "statement": (
            "Engineering classification only. Nothing here is legal advice and no "
            "entry is cleared for resale until a named reviewer signs it off "
            f"(classification_status='{CLEARED}'). {len(pending)} of {len(index)} "
            "sources are still uncleared."
        ),
    }
