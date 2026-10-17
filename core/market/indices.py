"""Named public indices — AI-STI (versioned, published); AI-LPI v1.0 withdrawn.

A weekly-measured, publicly-published index with a versioned method, explicit
component contributions and a provenance block. It exists so that the honesty
layer is a *product feature*: every number can be traced to a source, the weights
are published, and a missing input degrades the index loudly instead of being
silently substituted (rules 1/3/4 of AGENTS.md).

  * **AI-STI** — AquaIntel Salmon Transmission Index (0-100). How much current and
    near-term *supply tension* is likely to transmit into salmon prices.
    Higher = more upward price pressure.
  * **AI-LPI** — AquaIntel Lice Pressure Index. **Withdrawn** with method 2.0.0
    (WS-19): v1.0 was built only on the lice-quota tracker's utilisation, which
    divides a lice count by constants labelled tonnes for a quota regime that is
    still a proposal. The code still answers, with no value and the reason
    (``WITHDRAWN_INDICES``); it is never computed, published or stored.

Method version: ``INDEX_METHOD_VERSION``. Never publish a value without it.
Methodology: ``methodology()`` → also served at ``/api/indices/methodology``.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import structlog

from core.market.data_provenance import DataProvenance
from core.source_lineage import to_utc

log = structlog.get_logger(__name__)

INDEX_METHOD_VERSION = "2.0.0"

AI_STI = "AI-STI"
AI_LPI = "AI-LPI"

INDEX_NAMES = {
    AI_STI: "AquaIntel Salmon Transmission Index",
    AI_LPI: "AquaIntel Lice Pressure Index",
}

#: The indices computed, published and stored at this method version. The
#: publisher, the publication status and the verifier read this set (one
#: definition, projected as ``index_publication.INDEX_CODES``).
PUBLISHED_INDICES: tuple[str, ...] = (AI_STI,)

#: Indices that are known codes but are no longer computed. Their permalink and
#: history still answer; the value is null and the reason is served with it.
WITHDRAWN_INDICES: dict[str, dict] = {
    AI_LPI: {
        "version": "1.0.0",
        "withdrawn": "2026-10-17",
        "reason": (
            "AI-LPI v1.0 was built only on the lice-quota tracker's national "
            "utilisation, which divides a lice count by constants labelled tonnes "
            "for a quota regime that is still a proposal with no published "
            "allocations, so the utilisation has no meaningful unit; its "
            "quota_headroom component was also inverted, so the index could only "
            "read between about 27 and 55"
        ),
        "successor": None,
        "plan": (
            "a lice index may return only when rebuilt on observable facts (for "
            "example the biomass-weighted share of sites above the lice limit, "
            "weeks to the limit) and on verified lice rows (WS-16)"
        ),
    },
}

#: Method versions whose stored observations are superseded (revision policy:
#: never edited, never deleted; migration 020 marks the rows).
SUPERSEDED_VERSIONS: tuple[dict, ...] = (
    {
        "version": "1.0.0",
        "superseded_by": "2.0.0",
        "date": "2026-10-17",
        "changes": [
            "AI-STI: quota_pressure removed (it read the lice-quota tracker's "
            "utilisation, a lice count divided by constants labelled tonnes); "
            "biomass_momentum and harvest_pressure keep their 0.40:0.35 ratio",
            "AI-LPI v1.0 withdrawn (built only on the same utilisation)",
        ],
    },
)

# Weights are published (docs/INDICES.md + /api/indices/methodology). When a
# component's source is unavailable its weight is dropped and the rest are
# renormalised; the missing components are named in the response.
# Only components backed by a wired source ship; planned additions are listed in
# methodology()["planned_components"]. 2.0.0: v1.0's 0.40 / 0.35 renormalised
# after quota_pressure (0.25) was removed — the ratio is unchanged.
STI_WEIGHTS = {
    "biomass_momentum": 0.5333,
    "harvest_pressure": 0.4667,
}

BANDS = ((80, "severe"), (60, "elevated"), (40, "moderate"), (20, "low"), (0, "minimal"))


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _band(score: float) -> str:
    for threshold, label in BANDS:
        if score >= threshold:
            return label
    return "minimal"


def _component(
    name: str,
    *,
    weight: float,
    score: float,
    raw: Any,
    source: str,
    used: bool = True,
    note: str | None = None,
) -> dict:
    return {
        "name": name,
        "weight": weight,
        "score": round(_clamp(score), 1),
        "raw": raw,
        "source": source,
        "used": used,
        "note": note,
    }


def _assemble(
    index: str,
    components: list[dict],
    *,
    sources_used: list[str],
    missing: list[str],
    as_of: dt.datetime | None = None,
    lineage_notes: list[str] | None = None,
) -> dict:
    """Weighted mean over the *used* components, renormalised; provenance.

    ``lineage_notes`` carries provenance problems that do not stop a value being
    computed but must prevent a clean "live" claim (an estimated-biomass fallback,
    or an input table with no verifiable source column).
    """
    notes = list(lineage_notes or [])
    used = [c for c in components if c["used"]]
    total_weight = sum(c["weight"] for c in used)
    if not used or total_weight <= 0:
        value = None
        provenance = DataProvenance.degraded(
            "core.market.indices",
            "no index component could be computed from live sources",
            0.0,
        )
    else:
        value = sum(c["score"] * c["weight"] for c in used) / total_weight
        reasons = list(missing) + notes
        if reasons:
            provenance = DataProvenance.degraded(
                f"core.market.indices::{index}",
                "; ".join(
                    (["missing components: " + ", ".join(missing)] if missing else [])
                    + notes
                ),
                round(0.5 + 0.4 * (len(used) / max(1, len(components))), 2),
            )
        else:
            provenance = DataProvenance.live(f"core.market.indices::{index}", 0.85)

    stamp = to_utc(as_of)  # the stored week label is always the UTC ISO week
    return {
        "index": index,
        "name": INDEX_NAMES[index],
        "version": INDEX_METHOD_VERSION,
        "status": "published",
        "value": None if value is None else round(value, 1),
        "band": None if value is None else _band(value),
        "as_of": stamp.isoformat(),
        "week": stamp.strftime("%G-W%V"),
        "components": components,
        "components_used": len(used),
        "components_missing": missing,
        "lineage_notes": notes,
        "sources": sources_used,
        "provenance": provenance.to_dict(),
        "permalink": f"/indices/{index.lower()}",
        "api": f"/api/indices/{index.lower()}",
        "methodology_url": "/api/indices/methodology",
        "disclaimer": (
            "Index output, not investment advice. Reproducible from the published "
            "method and the cited sources; see /api/indices/methodology."
        ),
    }


# ── Data adapters ────────────────────────────────────────────────────────────

_BIOMASS_SOURCE = "Fiskeridir biomass (SSB)"


async def _totals_by_month(attribute: str) -> dict[tuple[int, int], float]:
    """National monthly totals for a BiomassRecord field."""
    from core.market.biomass_tracker import biomass_tracker

    records = await biomass_tracker.fetch_biomass_data()
    totals: dict[tuple[int, int], float] = {}
    for record in records:
        key = (int(record.year), int(record.month))
        totals[key] = totals.get(key, 0.0) + float(getattr(record, attribute, 0) or 0.0)
    return {k: v for k, v in totals.items() if v > 0}


async def _momentum_component(attribute: str, *, rising_means_tighter: bool) -> dict:
    """Momentum of a national monthly total, scored as supply tension.

    Year-over-year is preferred; the immediately previous period is used only when
    a year-back period is unavailable (and the raw block says which was used).

    The `source` is taken from the tracker's OWN lineage (`last_source` /
    `last_is_live`), not hardcoded: `biomass_tracker` filters synthetic records out
    and falls back to a historical-pattern estimate, so claiming a live Fiskeridir
    source here would have been false whenever that fallback ran.
    """
    from core.market.biomass_tracker import biomass_tracker

    totals = await _totals_by_month(attribute)
    if not totals:
        raise RuntimeError(f"no {attribute} data")
    lineage_source = getattr(biomass_tracker, "last_source", None) or _BIOMASS_SOURCE
    lineage_live = bool(getattr(biomass_tracker, "last_is_live", False))

    keys = sorted(totals)
    latest = keys[-1]
    yoy = (latest[0] - 1, latest[1])
    if yoy in totals:
        prev_key, basis = yoy, "year_over_year"
    elif len(keys) > 1:
        prev_key, basis = keys[-2], "previous_period"
    else:
        raise RuntimeError("no comparable prior period")
    if totals[prev_key] <= 0:
        raise RuntimeError("prior period is zero")

    growth_pct = (totals[latest] - totals[prev_key]) / totals[prev_key] * 100.0
    direction = 1.0 if rising_means_tighter else -1.0
    return {
        "score": _clamp(50 + direction * growth_pct * 5),
        "raw": {
            "growth_pct": round(growth_pct, 2),
            "latest": round(totals[latest], 1),
            "prior": round(totals[prev_key], 1),
            "period": f"{latest[0]}-{latest[1]:02d}",
            "basis": basis,
        },
        "source": lineage_source,
        "is_live": lineage_live,
        "estimated": not lineage_live,
    }


async def national_totals(attribute: str = "standing_biomass_tonnes") -> dict:
    """Public adapter: national monthly totals for a biomass attribute.

    Also used by the Bio→Price Weekly digest (one implementation of the maths).
    """
    return await _totals_by_month(attribute)


def _unavailable(name: str, weight: float, source: str, exc: Exception) -> dict:
    return _component(
        name, weight=weight, score=0.0, raw=None, source=source, used=False,
        note=f"unavailable: {exc}",
    )


# ── AI-STI ───────────────────────────────────────────────────────────────────

async def _sti_components() -> tuple[list[dict], list[str], list[str], list[str]]:
    components: list[dict] = []
    sources: list[str] = []
    missing: list[str] = []
    lineage_notes: list[str] = []

    try:
        momentum = await _momentum_component(
            "standing_biomass_tonnes", rising_means_tighter=False
        )
        sources.append(momentum["source"])
        if momentum.get("estimated"):
            lineage_notes.append(
                "biomass_momentum used the fallback '" + str(momentum["source"]) + "', not reported biomass"
            )
        components.append(
            _component(
                "biomass_momentum",
                weight=STI_WEIGHTS["biomass_momentum"],
                score=momentum["score"],
                raw=momentum["raw"],
                source=momentum["source"],
                note="falling standing biomass tightens supply",
            )
        )
    except Exception as exc:
        missing.append("biomass_momentum")
        components.append(
            _unavailable(
                "biomass_momentum", STI_WEIGHTS["biomass_momentum"], _BIOMASS_SOURCE, exc
            )
        )

    try:
        harvest = await _momentum_component("harvest_tonnes", rising_means_tighter=False)
        sources.append(harvest["source"])
        if harvest.get("estimated"):
            lineage_notes.append(
                "harvest_pressure used the fallback '" + str(harvest["source"]) + "', not reported biomass"
            )
        components.append(
            _component(
                "harvest_pressure",
                weight=STI_WEIGHTS["harvest_pressure"],
                score=harvest["score"],
                raw=harvest["raw"],
                source=harvest["source"],
                note="near-term harvest volume loosens supply",
            )
        )
    except Exception as exc:
        missing.append("harvest_pressure")
        components.append(
            _unavailable(
                "harvest_pressure", STI_WEIGHTS["harvest_pressure"], _BIOMASS_SOURCE, exc
            )
        )

    return components, sources, missing, lineage_notes


async def compute_ai_sti(as_of: dt.datetime | None = None) -> dict:
    """AI-STI (0-100; higher = more upward price pressure)."""
    components, sources, missing, lineage_notes = await _sti_components()
    return _assemble(
        AI_STI,
        components,
        sources_used=sources,
        missing=missing,
        as_of=as_of,
        lineage_notes=lineage_notes,
    )


# ── Withdrawn indices ────────────────────────────────────────────────────────

def _withdrawn(index: str, as_of: dt.datetime | None = None) -> dict:
    """The answer for a withdrawn index: same shape, no value, the reason.

    Nothing is computed (no source is read), so it can never be stored: the store
    refuses a null value and the publication set excludes it.
    """
    entry = WITHDRAWN_INDICES[index]
    stamp = to_utc(as_of)
    reason = f"withdrawn: {index} v{entry['version']} on {entry['withdrawn']} — {entry['reason']}"
    return {
        "index": index,
        "name": INDEX_NAMES[index],
        "version": INDEX_METHOD_VERSION,
        "status": "withdrawn",
        "withdrawn": dict(entry),
        "value": None,
        "band": None,
        "as_of": stamp.isoformat(),
        "week": stamp.strftime("%G-W%V"),
        "components": [],
        "components_used": 0,
        "components_missing": [],
        "lineage_notes": [],
        "sources": [],
        "provenance": DataProvenance.degraded(
            f"core.market.indices::{index}", reason, 0.0
        ).to_dict(),
        "permalink": f"/indices/{index.lower()}",
        "api": f"/api/indices/{index.lower()}",
        "methodology_url": "/api/indices/methodology",
        "disclaimer": (
            "Withdrawn index: no value is published. Stored observations remain in "
            "the history, marked superseded; see /api/indices/methodology."
        ),
    }


async def compute_ai_lpi(as_of: dt.datetime | None = None) -> dict:
    """AI-LPI: withdrawn with method 2.0.0 (WS-19) — see ``WITHDRAWN_INDICES``."""
    return _withdrawn(AI_LPI, as_of)


COMPUTERS = {AI_STI: compute_ai_sti, AI_LPI: compute_ai_lpi}


async def compute(index: str, as_of: dt.datetime | None = None) -> dict:
    """Compute an index by code ('AI-STI' | 'AI-LPI', case-insensitive)."""
    key = index.strip().upper()
    if key not in COMPUTERS:
        raise ValueError(f"unknown index '{index}' (expected one of {sorted(COMPUTERS)})")
    return await COMPUTERS[key](as_of=as_of)


# ── Published methodology ────────────────────────────────────────────────────

_SCORING = {
    "biomass_momentum": "score = clamp(50 - 5 x growth_pct, 0, 100)",
    "harvest_pressure": "score = clamp(50 - 5 x growth_pct, 0, 100)",
}


def methodology() -> dict:
    """The published, versioned method — the contract behind every value."""
    return {
        "version": INDEX_METHOD_VERSION,
        "published": "2026-10-17",
        "aggregation": (
            "Weighted mean of the component scores. Weights are renormalised over the "
            "components whose source was actually available; any dropped component is "
            "named in `components_missing` and downgrades provenance status."
        ),
        "bands": [
            {"band": label, "minimum": threshold}
            for threshold, label in reversed(BANDS)
        ],
        "indices": {
            AI_STI: {
                "name": INDEX_NAMES[AI_STI],
                "question": "How much supply tension is likely to transmit into salmon prices?",
                "range": "0-100",
                "direction": "higher = more upward price pressure",
                "components": {
                    name: {"weight": weight, "scoring": _SCORING[name]}
                    for name, weight in STI_WEIGHTS.items()
                },
                "sources": [_BIOMASS_SOURCE],
            },
        },
        "withdrawn": {code: dict(entry) for code, entry in WITHDRAWN_INDICES.items()},
        "superseded_versions": [dict(entry) for entry in SUPERSEDED_VERSIONS],
        "revision_policy": (
            "A published value is immutable for a given (version, week). Changing a "
            "weight, a scoring formula or a source bumps INDEX_METHOD_VERSION, and the "
            "history keeps both versions so a series break is visible rather than hidden. "
            "Observations of a withdrawn method are never edited or deleted: they stay "
            "in the history marked superseded (superseded_by, superseded_reason)."
        ),
        "planned_components": {
            "next": [
                "feed_cost_pressure for AI-STI (feed margin squeeze, cost-push)",
                "a lice index rebuilt on observable facts (biomass-weighted share of "
                "sites above the lice limit, weeks to the limit), only on verified "
                "lice rows (WS-16)",
            ]
        },
        "limitations": [
            "AI-STI 2.0.0 has two components and both come from one source "
            "(Fiskeridir biomass); when it is unavailable there is no value, and "
            "when the tracker falls back to an estimate the value is degraded.",
            "Momentum components prefer year-over-year; when a year-back period is "
            "missing the previous period is used and raw.basis says so.",
            "AI-LPI v1.0 is withdrawn; no lice index is published.",
            "A descriptive indicator, not investment advice.",
        ],
        "disclaimer": "Index output, not investment advice.",
    }


# ── History (durable, versioned) ─────────────────────────────────────────────

async def save_observation(result: dict) -> dict:
    """Persist one observation (idempotent per index + week + version)."""
    import asyncio
    import json

    if result.get("value") is None:
        # An observation is immutable for its week; a value that was never computed
        # must not occupy that slot, whoever is writing (agent, admin, test).
        raise ValueError(
            f"refusing to store {result.get('index')} {result.get('week')}: no value was "
            "computed (components unavailable) — nothing to publish"
        )

    def _write() -> dict:
        from sqlalchemy import select
        from sqlalchemy.exc import IntegrityError

        from core.models import IndexObservation, Session as DBSession

        def _existing(s):
            return s.execute(
                select(IndexObservation).where(
                    IndexObservation.index_code == result["index"],
                    IndexObservation.week == result["week"],
                    IndexObservation.version == result["version"],
                )
            ).scalar_one_or_none()

        with DBSession() as s:
            existing = _existing(s)
            if existing is not None:
                return {"status": "duplicate", "id": existing.id}
            row = IndexObservation(
                index_code=result["index"],
                week=result["week"],
                as_of=dt.datetime.fromisoformat(result["as_of"]),
                version=result["version"],
                value=result["value"],
                band=result["band"],
                components_json=json.dumps(result["components"]),
                provenance_json=json.dumps(result["provenance"]),
            )
            s.add(row)
            try:
                s.commit()
            except IntegrityError:
                # A concurrent writer (admin POST /api/indices/publish, a second
                # agents replica) won the race between the duplicate check and the
                # insert. The week IS published: report the duplicate, never fail.
                s.rollback()
                winner = _existing(s)
                if winner is None:
                    raise  # not the unique race — a real integrity failure
                return {"status": "duplicate", "id": winner.id}
            s.refresh(row)
            return {"status": "stored", "id": row.id}

    return await asyncio.to_thread(_write)


async def history(index: str, *, limit: int = 52) -> list[dict]:
    """Stored observations, newest first (empty when nothing published yet).

    Every version is returned, so a series break stays visible; an observation of
    a withdrawn method carries ``superseded: true`` with ``superseded_by`` and the
    reason (WS-19) — its stored value is never edited.
    """
    import asyncio
    import json

    code = index.strip().upper()

    def _read() -> list[dict]:
        from sqlalchemy import select

        from core.models import IndexObservation, Session as DBSession

        with DBSession() as s:
            rows = (
                s.execute(
                    select(IndexObservation)
                    .where(IndexObservation.index_code == code)
                    .order_by(IndexObservation.as_of.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [
                {
                    "week": r.week,
                    "as_of": r.as_of.isoformat() if r.as_of else None,
                    "version": r.version,
                    "value": r.value,
                    "band": r.band,
                    "components": json.loads(r.components_json or "[]"),
                    "provenance": json.loads(r.provenance_json or "{}"),
                    "superseded": r.superseded_by is not None,
                    "superseded_by": r.superseded_by,
                    "superseded_reason": r.superseded_reason,
                }
                for r in rows
            ]

    return await asyncio.to_thread(_read)


async def publish(index: str, *, as_of: dt.datetime | None = None) -> dict:
    """Compute AND store one observation, ungated (tests and tooling; the
    publisher goes through ``index_publication.readiness()``)."""
    result = await compute(index, as_of=as_of)
    result["storage"] = await save_observation(result)
    return result


async def publish_all(*, as_of: dt.datetime | None = None) -> dict[str, dict]:
    """Publish every published index, ungated (tests and tooling)."""
    return {code: await publish(code, as_of=as_of) for code in PUBLISHED_INDICES}
