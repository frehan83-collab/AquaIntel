"""Named public indices — AI-STI and AI-LPI (versioned, published).

Two weekly-measured, publicly-published indices with a versioned method, explicit
component contributions and a provenance block. They exist so that the honesty
layer is a *product feature*: every number can be traced to a source, the weights
are published, and a missing input degrades the index loudly instead of being
silently substituted (rules 1/3/4 of AGENTS.md).

  * **AI-STI** — AquaIntel Salmon Transmission Index (0-100). How much current and
    near-term *supply tension* is likely to transmit into salmon prices.
    Higher = more upward price pressure.
  * **AI-LPI** — AquaIntel Lice Pressure Index (0-100). National lice treatment
    pressure. Higher = more lice-driven production risk and cost.

Method version: ``INDEX_METHOD_VERSION``. Never publish a value without it.
Methodology: ``methodology()`` → also served at ``/api/indices/methodology``.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import structlog

from core.market.data_provenance import DataProvenance
from core.source_lineage import lineage_note

log = structlog.get_logger(__name__)

INDEX_METHOD_VERSION = "1.0.0"

AI_STI = "AI-STI"
AI_LPI = "AI-LPI"

INDEX_NAMES = {
    AI_STI: "AquaIntel Salmon Transmission Index",
    AI_LPI: "AquaIntel Lice Pressure Index",
}

# Weights are published (docs/INDICES.md + /api/indices/methodology). When a
# component's source is unavailable its weight is dropped and the rest are
# renormalised; the missing components are named in the response.
# v1.0 deliberately ships only components backed by a wired, live source; the
# planned v1.1 additions are listed in methodology()["planned_components"].
STI_WEIGHTS = {
    "biomass_momentum": 0.40,
    "harvest_pressure": 0.35,
    "quota_pressure": 0.25,
}
LPI_WEIGHTS = {
    "emission_pressure": 0.55,
    "quota_headroom": 0.45,
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

    stamp = as_of or dt.datetime.now(dt.UTC)
    return {
        "index": index,
        "name": INDEX_NAMES[index],
        "version": INDEX_METHOD_VERSION,
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
_QUOTA_SOURCE = "lice_quota_tracker (lice emission quota framework)"


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


async def _national_emission() -> dict:
    from core.market.lice_quota_tracker import lice_quota_tracker

    return await lice_quota_tracker.national_emission_overview()


async def national_totals(attribute: str = "standing_biomass_tonnes") -> dict:
    """Public adapter: national monthly totals for a biomass attribute.

    Also used by the Bio→Price Weekly digest (one implementation of the maths).
    """
    return await _totals_by_month(attribute)


def _lice_lineage_note(lineage: dict | None = None) -> str | None:
    """None when the lice lineage is verifiable, otherwise why it is not.

    WS-1: `lice_records.source` lets the quota tracker report the lineage of the
    rows it actually aggregated (``overview["lineage"]``). The note is None only
    when every used row is a reported BarentsWatch observation, every PA
    contributed without a fetch failure and the newest row is within cadence —
    column *presence* alone never earns a live claim (an all-demo CI database
    has the column too).

    Zero-arg form: reflects the tracker's LAST computation (``last_lineage``), so
    callers must compute the index first; before any computation it reports that
    no lineage was recorded, which is the honest answer.
    """
    from sqlalchemy import inspect

    from core.models import engine

    try:
        columns = {c["name"].lower() for c in inspect(engine).get_columns("lice_records")}
    except Exception:
        return "lineage unverifiable: lice_records is unreadable"
    if "source" not in columns:
        return (
            "lineage unverifiable: lice_records has no source column, so demo and "
            "reported rows cannot be distinguished"
        )
    if lineage is None:
        from core.market.lice_quota_tracker import lice_quota_tracker

        lineage = getattr(lice_quota_tracker, "last_lineage", None)
    return lineage_note(lineage)


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

    try:
        overview = await _national_emission()
        utilization = float(overview.get("national_utilization_pct") or 0.0)
        sources.append(_QUOTA_SOURCE)
        lice_note = _lice_lineage_note(overview.get("lineage"))
        if lice_note:
            lineage_notes.append(lice_note)
        components.append(
            _component(
                "quota_pressure",
                weight=STI_WEIGHTS["quota_pressure"],
                # 50% utilisation = neutral; 100% = 80; above quota = 100.
                score=_clamp((utilization - 50.0) * 1.6),
                raw={
                    "national_utilization_pct": utilization,
                    "pas_over_quota": overview.get("pas_over_quota"),
                    "total_national_emission": overview.get("total_national_emission"),
                    "total_national_quota": overview.get("total_national_quota"),
                },
                source=_QUOTA_SOURCE,
                note="quota saturation forces future biomass cuts (supply contraction)",
            )
        )
    except Exception as exc:
        missing.append("quota_pressure")
        components.append(
            _unavailable(
                "quota_pressure", STI_WEIGHTS["quota_pressure"], _QUOTA_SOURCE, exc
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


# ── AI-LPI ───────────────────────────────────────────────────────────────────

async def compute_ai_lpi(as_of: dt.datetime | None = None) -> dict:
    """AI-LPI (0-100; higher = more lice-driven production risk and cost).

    v1.0 uses the lice *emission quota* framework as the observable proxy for
    treatment pressure (independent lice-count series are a v1.1 component — see
    methodology()["planned_components"]).
    """
    components: list[dict] = []
    sources: list[str] = []
    missing: list[str] = []
    lineage: dict | None = None

    try:
        overview = await _national_emission()
        lineage = overview.get("lineage")
        utilization = float(overview.get("national_utilization_pct") or 0.0)
        sources.append(_QUOTA_SOURCE)
        components.append(
            _component(
                "emission_pressure",
                weight=LPI_WEIGHTS["emission_pressure"],
                # 40% utilisation = neutral baseline; ~107% = 100.
                score=_clamp((utilization - 40.0) * 1.5),
                raw={
                    "national_utilization_pct": utilization,
                    "pas_over_quota": overview.get("pas_over_quota"),
                },
                source=_QUOTA_SOURCE,
                note="high emission utilisation implies intensive treatment pressure",
            )
        )
        components.append(
            _component(
                "quota_headroom",
                weight=LPI_WEIGHTS["quota_headroom"],
                score=_clamp(100.0 - utilization),
                raw={"headroom_pct": round(100.0 - utilization, 1)},
                source=_QUOTA_SOURCE,
                note="little remaining headroom before mandatory cuts",
            )
        )
    except Exception as exc:
        for name in ("emission_pressure", "quota_headroom"):
            missing.append(name)
            components.append(_unavailable(name, LPI_WEIGHTS[name], _QUOTA_SOURCE, exc))

    return _assemble(
        AI_LPI,
        components,
        sources_used=sources,
        missing=missing,
        as_of=as_of,
        lineage_notes=[note for note in (_lice_lineage_note(lineage),) if note],
    )


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
    "quota_pressure": "score = clamp((national_utilisation_pct - 50) x 1.6, 0, 100)",
    "emission_pressure": "score = clamp((national_utilisation_pct - 40) x 1.5, 0, 100)",
    "quota_headroom": "score = clamp(100 - national_utilisation_pct, 0, 100)",
}


def methodology() -> dict:
    """The published, versioned method — the contract behind every value."""
    return {
        "version": INDEX_METHOD_VERSION,
        "published": "2026-10-16",
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
                "sources": [_BIOMASS_SOURCE, _QUOTA_SOURCE],
            },
            AI_LPI: {
                "name": INDEX_NAMES[AI_LPI],
                "question": "How intense is national lice treatment pressure?",
                "range": "0-100",
                "direction": "higher = more lice-driven production risk and cost",
                "components": {
                    name: {"weight": weight, "scoring": _SCORING[name]}
                    for name, weight in LPI_WEIGHTS.items()
                },
                "sources": [_QUOTA_SOURCE],
            },
        },
        "revision_policy": (
            "A published value is immutable for a given (version, week). Changing a "
            "weight, a scoring formula or a source bumps INDEX_METHOD_VERSION, and the "
            "history keeps both versions so a series break is visible rather than hidden."
        ),
        "planned_components": {
            "v1.1": [
                "feed_cost_pressure for AI-STI (feed margin squeeze, cost-push)",
                "sea_temp_anomaly for AI-LPI (SST anomaly vs 5-year baseline)",
                "independent adult-female lice count series for AI-LPI",
            ]
        },
        "limitations": [
            "AI-LPI v1.0 uses the lice emission-quota framework as a proxy for "
            "treatment pressure; it is not a direct lice-count measurement.",
            "Momentum components prefer year-over-year; when a year-back period is "
            "missing the previous period is used and raw.basis says so.",
            "Both indices are descriptive indicators, not investment advice.",
        ],
        "disclaimer": "Index output, not investment advice.",
    }


# ── History (durable, versioned) ─────────────────────────────────────────────

async def save_observation(result: dict) -> dict:
    """Persist one observation (idempotent per index + week + version)."""
    import asyncio
    import json

    def _write() -> dict:
        from sqlalchemy import select

        from core.models import IndexObservation, Session as DBSession

        with DBSession() as s:
            existing = s.execute(
                select(IndexObservation).where(
                    IndexObservation.index_code == result["index"],
                    IndexObservation.week == result["week"],
                    IndexObservation.version == result["version"],
                )
            ).scalar_one_or_none()
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
            s.commit()
            s.refresh(row)
            return {"status": "stored", "id": row.id}

    return await asyncio.to_thread(_write)


async def history(index: str, *, limit: int = 52) -> list[dict]:
    """Stored observations, newest first (empty when nothing published yet)."""
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
                }
                for r in rows
            ]

    return await asyncio.to_thread(_read)


async def publish(index: str, *, as_of: dt.datetime | None = None) -> dict:
    """Compute AND store one observation — the weekly job calls this."""
    result = await compute(index, as_of=as_of)
    result["storage"] = await save_observation(result)
    return result


async def publish_all(*, as_of: dt.datetime | None = None) -> dict[str, dict]:
    """Publish both named indices (the weekly Bio→Price job calls this)."""
    return {code: await publish(code, as_of=as_of) for code in (AI_STI, AI_LPI)}
