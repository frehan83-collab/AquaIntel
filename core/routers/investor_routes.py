"""
Investor event impact + saved scenario routes.
Extracted from core/api.py (Session 8).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from core.models import SavedScenario
from core.async_db import get_async_session

router = APIRouter(prefix="/api", tags=["investor", "scenarios"])


def _event_impact_provenance():
    """Event-impact output is a modelled counterfactual, not an observed market
    move (AGENTS.md rule 1/3)."""
    from core.market.data_provenance import DataProvenance

    return DataProvenance.degraded(
        "Event impact model (scenario simulation)",
        reason=(
            "modelled impact of a hypothetical event — a scenario estimate, not an "
            "observed market move"
        ),
        confidence=0.4,
    )


# ══════════════════════════════════════════════════════════════════════
# EVENT IMPACT MODEL (Investor/Trader Edge)
# ══════════════════════════════════════════════════════════════════════

@router.get("/investor/event-impact/isa")
async def event_impact_isa(production_area: int = 3):
    """Model financial impact of ISA outbreak in a production area."""
    from core.predictors.event_impact_model import event_impact_model
    result = await event_impact_model.model_isa_outbreak(production_area)
    if isinstance(result, dict):
        result.setdefault("data_provenance", _event_impact_provenance().to_dict())
    return result


@router.get("/investor/event-impact/traffic-light")
async def event_impact_traffic_light(pa: int = 3, color: str = "red"):
    """Model financial impact of traffic light color change."""
    from core.predictors.event_impact_model import event_impact_model
    result = await event_impact_model.model_traffic_light_change(pa, color)
    if isinstance(result, dict):
        result.setdefault("data_provenance", _event_impact_provenance().to_dict())
    return result


@router.get("/investor/event-impact/feed-shock")
async def event_impact_feed_shock(fishmeal_change_pct: float = 15.0):
    """Model financial impact of fishmeal price spike."""
    from core.predictors.event_impact_model import event_impact_model
    result = await event_impact_model.model_feed_price_shock(fishmeal_change_pct)
    if isinstance(result, dict):
        result.setdefault("data_provenance", _event_impact_provenance().to_dict())
    return result


@router.post("/investor/event-impact/custom")
async def event_impact_custom(request: Request):
    """Model financial impact of a custom event."""
    from core.predictors.event_impact_model import event_impact_model
    try:
        body = await request.json()
    except Exception:
        body = {}
    event_type = body.get("event_type", "generic")
    params = body.get("params", {})
    return await event_impact_model.model_custom_event(event_type, params)


# ══════════════════════════════════════════════════════════════════════
# SAVED SCENARIOS
# ══════════════════════════════════════════════════════════════════════

@router.post("/scenarios/save")
async def save_scenario(request: Request):
    """Save an event impact scenario for later review."""
    import json as _json
    data = await request.json()
    async with get_async_session() as s:
        scenario = SavedScenario(
            user_email=data.get("user_email", "anonymous"),
            scenario_type=data.get("scenario_type", "custom"),
            scenario_name=data.get("scenario_name", "Untitled"),
            parameters=_json.dumps(data.get("parameters", {})),
            results=_json.dumps(data.get("results", {})),
            notes=data.get("notes", ""),
        )
        s.add(scenario)
        await s.commit()
        await s.refresh(scenario)
        return {"id": scenario.id, "status": "saved", "name": scenario.scenario_name}


@router.get("/scenarios/list")
async def list_scenarios(user_email: str = "anonymous"):
    """List saved scenarios for a user."""
    import json as _json
    async with get_async_session() as s:
        rows = (await s.execute(
            select(SavedScenario)
            .where(SavedScenario.user_email == user_email)
            .order_by(SavedScenario.created_at.desc())
            .limit(50)
        )).scalars().all()
    return [
        {
            "id": r.id,
            "scenario_type": r.scenario_type,
            "scenario_name": r.scenario_name,
            "parameters": _json.loads(r.parameters) if r.parameters else {},
            "results": _json.loads(r.results) if r.results else {},
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: int):
    """Delete a saved scenario."""
    async with get_async_session() as s:
        scenario = await s.get(SavedScenario, scenario_id)
        if not scenario:
            raise HTTPException(404, "Scenario not found")
        await s.delete(scenario)
        await s.commit()
    return {"status": "deleted", "id": scenario_id}


# ══════════════════════════════════════════════════════════════════════
# COMPOUND SCENARIO ENGINE
# ══════════════════════════════════════════════════════════════════════

@router.post("/scenarios/compound")
async def compound_scenario(request: Request):
    """Run compound scenario with multiple simultaneous events.

    Body: { "events": [ {"type": "isa", "params": {"production_area": 3}}, ... ] }
    """
    from core.predictors.compound_scenario import compound_scenario_engine
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    events = body.get("events", [])
    if not events:
        raise HTTPException(400, "No events provided")
    return await compound_scenario_engine.run_compound(events)
