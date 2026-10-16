"""Design-partner (paid pilot) infrastructure — admin surfaces.

Runs 5–8 paid 90-day pilots: create the partner, grant a canonical plan for the
pilot window, record the success metrics it will be judged on, and capture the
data-reciprocity terms.

Pilots grant an EXISTING canonical plan (`core/entitlements.py`) for a time box —
no new tier, so the plan table stays singular (AGENTS.md rule 8). The grant goes
through `core.billing.entitlement_sync`, so a pilot is a real, auditable,
revocable entitlement rather than a flag on a screen.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json

from fastapi import APIRouter, Depends, HTTPException, Request

from core.auth import TokenPayload, require_admin

router = APIRouter(prefix="/api/admin/partners", tags=["partner-pilots"])

PILOT_DAYS = 90
ICPS = ("desk", "processor", "producer", "insurer", "analytics", "other")
STATUSES = ("prospect", "onboarded", "active", "converted", "churned")
VALID_TRANSITIONS = {
    "prospect": ("onboarded", "churned"),
    "onboarded": ("active", "churned"),
    "active": ("converted", "churned"),
    "converted": (),
    "churned": ("onboarded",),
}


def _as_utc(value):
    """SQLite drops tzinfo on read, so a naive value is treated as UTC.

    (Without this, `days_remaining` was always None: the awareness check failed on
    datetimes read back from SQLite.)
    """
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def _row(partner, metrics=None) -> dict:
    ends_at = _as_utc(partner.ends_at)
    return {
        "id": partner.id,
        "company": partner.company,
        "contact_email": partner.contact_email,
        "contact_name": partner.contact_name,
        "icp": partner.icp,
        "sector": partner.sector,
        "country": partner.country,
        "plan_granted": partner.plan_granted,
        "user_id": partner.user_id,
        "status": partner.status,
        "is_paid": partner.is_paid,
        "monthly_price_nok": partner.monthly_price_nok,
        "starts_at": _as_utc(partner.starts_at).isoformat()
        if partner.starts_at
        else None,
        "ends_at": ends_at.isoformat() if ends_at else None,
        "days_remaining": (
            max(0, (ends_at - dt.datetime.now(dt.UTC)).days) if ends_at else None
        ),
        "reciprocity": json.loads(partner.reciprocity_json or "{}"),
        "notes": partner.notes,
        "metrics": metrics or [],
    }


def _progress(metrics) -> list[dict]:
    """Latest observation vs latest target per metric (the pilot scorecard)."""
    latest: dict[str, dict] = {}
    for metric in metrics:
        current = latest.get(metric.name)
        if current is None or (metric.recorded_at or dt.datetime.min) >= (
            current.get("_at") or dt.datetime.min
        ):
            latest[metric.name] = {
                "name": metric.name,
                "value": metric.value,
                "target": metric.target,
                "unit": metric.unit,
                "recorded_at": metric.recorded_at.isoformat()
                if metric.recorded_at
                else None,
                "achieved": (
                    None
                    if metric.value is None or metric.target is None
                    else metric.value >= metric.target
                ),
                "_at": metric.recorded_at,
            }
    for entry in latest.values():
        entry.pop("_at", None)
    return sorted(latest.values(), key=lambda e: e["name"])


def _get(session, partner_id: int):
    from core.models import DesignPartner

    partner = session.get(DesignPartner, partner_id)
    if partner is None:
        raise HTTPException(404, f"No design partner {partner_id}")
    return partner


@router.post("")
async def create_partner(request: Request, _: TokenPayload = Depends(require_admin)):
    """Create a design partner (pilot not yet granted)."""
    body = await request.json()
    company = (body.get("company") or "").strip()
    if not company:
        raise HTTPException(422, "company is required")
    icp = str(body.get("icp", "other")).lower()
    if icp not in ICPS:
        raise HTTPException(422, f"icp must be one of {sorted(ICPS)}")
    from core.entitlements import PLANS, normalize_plan

    plan_key = normalize_plan(body.get("plan_granted") or "professional")
    if plan_key not in PLANS:
        raise HTTPException(422, f"unknown plan '{body.get('plan_granted')}'")

    def _create() -> dict:
        from core.models import DesignPartner, Session as DBSession

        with DBSession() as s:
            partner = DesignPartner(
                company=company,
                contact_email=body.get("contact_email"),
                contact_name=body.get("contact_name"),
                icp=icp,
                sector=body.get("sector"),
                country=body.get("country"),
                plan_granted=plan_key,
                user_id=body.get("user_id"),
                status="prospect",
                is_paid=bool(body.get("is_paid", True)),
                monthly_price_nok=float(body.get("monthly_price_nok") or 0),
                reciprocity_json=json.dumps(body.get("reciprocity") or {}),
                notes=body.get("notes"),
            )
            s.add(partner)
            s.commit()
            s.refresh(partner)
            return _row(partner)

    return await asyncio.to_thread(_create)


@router.get("")
async def list_partners(_: TokenPayload = Depends(require_admin)):
    """All design partners with their metric scorecards."""
    def _list() -> dict:
        from sqlalchemy import select

        from core.models import DesignPartner, PartnerMetric, Session as DBSession

        with DBSession() as s:
            partners = (
                s.execute(select(DesignPartner).order_by(DesignPartner.id)).scalars().all()
            )
            out = []
            for partner in partners:
                metrics = (
                    s.execute(
                        select(PartnerMetric).where(PartnerMetric.partner_id == partner.id)
                    )
                    .scalars()
                    .all()
                )
                out.append(_row(partner, _progress(metrics)))
            return {
                "partners": out,
                "count": len(out),
                "by_status": {
                    status: sum(1 for p in out if p["status"] == status)
                    for status in STATUSES
                },
                "by_icp": {icp: sum(1 for p in out if p["icp"] == icp) for icp in ICPS},
                "target": (
                    "5-8 paid 90-day pilots (3 desks, 2 processors, 2 producers NO/CL, "
                    "1 insurer)"
                ),
            }

    return await asyncio.to_thread(_list)


@router.get("/{partner_id}")
async def get_partner(partner_id: int, _: TokenPayload = Depends(require_admin)):
    """One partner with its full metric history."""
    def _get_one() -> dict:
        from sqlalchemy import select

        from core.models import PartnerMetric, Session as DBSession

        with DBSession() as s:
            partner = _get(s, partner_id)
            metrics = (
                s.execute(
                    select(PartnerMetric)
                    .where(PartnerMetric.partner_id == partner_id)
                    .order_by(PartnerMetric.recorded_at)
                )
                .scalars()
                .all()
            )
            row = _row(partner, _progress(metrics))
            row["metric_history"] = [
                {
                    "name": m.name,
                    "value": m.value,
                    "target": m.target,
                    "unit": m.unit,
                    "note": m.note,
                    "recorded_at": m.recorded_at.isoformat() if m.recorded_at else None,
                }
                for m in metrics
            ]
            row["allowed_transitions"] = VALID_TRANSITIONS.get(partner.status, ())
            return row

    return await asyncio.to_thread(_get_one)


@router.post("/{partner_id}/onboard")
async def onboard_partner(
    partner_id: int, request: Request, _: TokenPayload = Depends(require_admin)
):
    """Grant the pilot plan for the window and start the 90-day clock."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    days = int(body.get("days") or PILOT_DAYS)

    def _prep() -> dict:
        from core.models import Session as DBSession

        with DBSession() as s:
            partner = _get(s, partner_id)
            if not partner.user_id:
                raise HTTPException(
                    422,
                    "partner has no user_id — link a user first so the pilot "
                    "entitlement has an owner",
                )
            now = dt.datetime.now(dt.UTC)
            partner.status = "onboarded"
            partner.starts_at = now
            partner.ends_at = now + dt.timedelta(days=days)
            s.commit()
            return {"user_id": partner.user_id, "plan": partner.plan_granted}

    prep = await asyncio.to_thread(_prep)
    from core.billing.entitlement_sync import activate

    grant = await asyncio.to_thread(activate, prep["user_id"], prep["plan"])
    return {"status": "onboarded", "days": days, "entitlement": grant}


@router.post("/{partner_id}/metrics")
async def record_metric(
    partner_id: int, request: Request, _: TokenPayload = Depends(require_admin)
):
    """Record a pilot success metric (value vs target)."""
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(422, "name is required")

    def _record() -> dict:
        from core.models import PartnerMetric, Session as DBSession

        with DBSession() as s:
            _get(s, partner_id)
            metric = PartnerMetric(
                partner_id=partner_id,
                name=name,
                value=body.get("value"),
                target=body.get("target"),
                unit=body.get("unit"),
                note=body.get("note"),
                recorded_at=dt.datetime.now(dt.UTC),
            )
            s.add(metric)
            s.commit()
            s.refresh(metric)
            return {
                "id": metric.id,
                "partner_id": partner_id,
                "name": metric.name,
                "value": metric.value,
                "target": metric.target,
                "unit": metric.unit,
            }

    return await asyncio.to_thread(_record)


@router.post("/{partner_id}/reciprocity")
async def record_reciprocity(
    partner_id: int, request: Request, _: TokenPayload = Depends(require_admin)
):
    """Record data-reciprocity terms (what the partner shares back, how often)."""
    body = await request.json()
    shares = body.get("shares")
    if not isinstance(shares, list) or not shares:
        raise HTTPException(
            422,
            "`shares` must be a non-empty list of the datasets the partner provides "
            "(e.g. ['lice_counts_weekly','harvest_plan'])",
        )

    def _record() -> dict:
        from core.models import Session as DBSession

        with DBSession() as s:
            partner = _get(s, partner_id)
            partner.reciprocity_json = json.dumps(
                {
                    "shares": shares,
                    "cadence": body.get("cadence", "weekly"),
                    "agreement_ref": body.get("agreement_ref"),
                    "restrictions": body.get("restrictions"),
                }
            )
            s.commit()
            return {
                "partner_id": partner_id,
                "reciprocity": json.loads(partner.reciprocity_json),
            }

    return await asyncio.to_thread(_record)


@router.post("/{partner_id}/status")
async def set_status(
    partner_id: int, request: Request, _: TokenPayload = Depends(require_admin)
):
    """Transition a pilot's status (enforces the allowed state machine)."""
    body = await request.json()
    target = str(body.get("status", "")).lower()
    if target not in STATUSES:
        raise HTTPException(422, f"status must be one of {list(STATUSES)}")

    def _set() -> dict:
        from core.models import Session as DBSession

        with DBSession() as s:
            partner = _get(s, partner_id)
            allowed = VALID_TRANSITIONS.get(partner.status, ())
            if target not in allowed:
                raise HTTPException(
                    409,
                    f"cannot move '{partner.status}' -> '{target}'; allowed: {list(allowed)}",
                )
            previous, partner.status = partner.status, target
            if body.get("note"):
                partner.notes = body["note"]
            s.commit()
            return {"id": partner_id, "from": previous, "to": target}

    return await asyncio.to_thread(_set)
