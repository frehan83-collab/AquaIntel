"""
Digital Twin and GNN routes.
Extracted from core/api.py (Session 10 — Router Wave 4).
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from core.models import LiceRecord, Locality
from core.async_db import get_async_session

router = APIRouter(tags=["twin"])


# ── Digital Twin ─────────────────────────────────────────────────────

@router.post("/api/twin/sync")
async def twin_sync():
    """Sync the digital twin with latest BarentsWatch data."""
    from core.twin.digital_twin import digital_twin, TwinLocality, LiceState, CleanerFishState
    async with get_async_session() as s:
        latest = (await s.execute(
            select(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(1)
        )).first()

        if not latest:
            return {"status": "no_data"}

        records = (await s.execute(
            select(
                LiceRecord.locality_no,
                LiceRecord.avg_adult_female_lice,
                LiceRecord.avg_mobile_lice,
                LiceRecord.avg_stationary_lice,
                LiceRecord.sea_temp_c,
                LiceRecord.has_cleaner_fish,
                Locality.owner_company,
            )
            .join(Locality, LiceRecord.locality_no == Locality.locality_no)
            .where(
                LiceRecord.year == latest[0],
                LiceRecord.week == latest[1],
                LiceRecord.avg_adult_female_lice.isnot(None),
            )
        )).all()

    digital_twin.localities.clear()
    for r in records:
        digital_twin.localities[r[0]] = TwinLocality(
            locality_no=r[0],
            ticker=r[6] or "",
            lice=LiceState(
                sessile=float(r[2] or 0),
                motile=float(r[2] or 0),
                adult_female=float(r[0 + 1] or 0),
                total=float((r[1] or 0) + (r[2] or 0) + (r[3] or 0)),
            ),
            sea_temp_c=float(r[4] or 8),
            cleaner_fish=CleanerFishState(
                wrasse_count=100 if r[5] else 0,
                lumpfish_count=50 if r[5] else 0,
                efficacy_pct=15.0 if r[5] else 0,
            ),
        )
    for r in records:
        if r[0] in digital_twin.localities:
            digital_twin.localities[r[0]].lice.adult_female = float(r[1] or 0)

    digital_twin.last_sync = dt.datetime.now(dt.UTC)
    return digital_twin.get_summary()


@router.get("/api/twin/status")
async def twin_status():
    """Get current digital twin state."""
    from core.twin.digital_twin import digital_twin
    return digital_twin.get_summary()


class SimulationRequest(BaseModel):
    weeks: int = 4
    temp_delta: float = 0.0
    treat_above: float | None = None
    treatment_type: str = "mechanical"
    add_cleaner_fish_pct: float = 0.0


@router.post("/api/twin/simulate")
async def twin_simulate(req: SimulationRequest):
    """Run a what-if simulation on the digital twin."""
    from core.twin.digital_twin import digital_twin
    import numpy as np

    if not digital_twin.localities:
        await digital_twin.sync_from_db()

    if not digital_twin.localities:
        return {
            "status": "uninitialized",
            "message": "Twin has no localities in database. Seed or ingest data first.",
            "weeks_simulated": 0,
            "trajectory": [],
        }

    state = digital_twin.fork()

    interventions: dict = {"temp_delta_c": req.temp_delta}

    if req.treat_above is not None:
        treat_list = [
            ln for ln, t in state.items()
            if t.lice.adult_female > req.treat_above
        ]
        interventions["treat_localities"] = treat_list
        interventions["treatment_type"] = req.treatment_type

    if req.add_cleaner_fish_pct > 0:
        interventions["add_cleaner_fish"] = {
            ln: int(req.add_cleaner_fish_pct * 10)
            for ln in state
        }

    trajectory = []
    for week in range(1, req.weeks + 1):
        state = digital_twin.simulate_step(state, weeks=1, interventions=interventions)
        if "treat_localities" in interventions:
            interventions.pop("treat_localities")

        lice_vals = [t.lice.adult_female for t in state.values()]
        biomass = sum(t.estimated_biomass_tonnes for t in state.values())
        above = sum(1 for v in lice_vals if v > 0.5)

        trajectory.append({
            "week": week,
            "avg_lice": round(float(np.mean(lice_vals)), 4) if lice_vals else 0,
            "max_lice": round(float(max(lice_vals)), 4) if lice_vals else 0,
            "above_threshold": above,
            "total_biomass_t": round(biomass, 0),
            "pct_above": round(above / max(len(lice_vals), 1) * 100, 1),
        })

    baseline_state = digital_twin.fork()
    for _ in range(req.weeks):
        baseline_state = digital_twin.simulate_step(
            baseline_state, weeks=1,
            interventions={"temp_delta_c": req.temp_delta},
        )
    baseline_lice = [t.lice.adult_female for t in baseline_state.values()]
    baseline_biomass = sum(t.estimated_biomass_tonnes for t in baseline_state.values())

    return {
        "weeks_simulated": req.weeks,
        "interventions": {
            "temp_delta": req.temp_delta,
            "treat_above": req.treat_above,
            "treatment_type": req.treatment_type,
            "cleaner_fish_boost": req.add_cleaner_fish_pct,
        },
        "trajectory": trajectory,
        "final": trajectory[-1] if trajectory else {},
        "baseline": {
            "avg_lice": round(float(np.mean(baseline_lice)), 4) if baseline_lice else 0,
            "total_biomass_t": round(baseline_biomass, 0),
            "above_threshold": sum(1 for v in baseline_lice if v > 0.5),
        },
        "impact": {
            "lice_reduction_pct": round(
                (1 - trajectory[-1]["avg_lice"] / max(float(np.mean(baseline_lice)), 0.001)) * 100, 1
            ) if trajectory and baseline_lice else 0,
            "biomass_saved_t": round(
                trajectory[-1]["total_biomass_t"] - baseline_biomass, 0
            ) if trajectory else 0,
        },
        "localities_simulated": len(state),
    }

