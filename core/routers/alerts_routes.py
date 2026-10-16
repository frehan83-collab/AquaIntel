"""
Alert notification and parametric insurance routes.
Extracted from core/api.py (Session 10 — Router Wave 4).
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

router = APIRouter(tags=["alerts"])


@router.get("/api/alerts")
async def get_alerts(category: str = None, severity: str = None, unread_only: bool = False, limit: int = Query(50, ge=1, le=1000)):
    """Get alerts with optional filters."""
    from core.market.alert_engine import alert_engine
    return alert_engine.get_alerts(category=category, severity=severity, unread_only=unread_only, limit=limit)


@router.post("/api/alerts/check")
async def check_alerts():
    """Run all alert checks and return new alerts."""
    from core.market.alert_engine import alert_engine
    new_alerts = await alert_engine.check_all()
    return {"new_alerts": new_alerts, "count": len(new_alerts)}


@router.get("/api/alerts/summary")
async def alerts_summary():
    """Alert summary for notification bell badge."""
    from core.market.alert_engine import alert_engine
    from core.market.data_provenance import DataProvenance
    result = alert_engine.get_summary()
    result["data_provenance"] = DataProvenance.live(
        "Multi-engine composite (lice + disease + bloom + price)", confidence=0.75
    ).to_dict()
    return result


@router.post("/api/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str):
    """Mark a single alert as read."""
    from core.market.alert_engine import alert_engine
    return {"success": alert_engine.mark_read(alert_id)}


@router.post("/api/alerts/read-all")
async def mark_all_alerts_read():
    """Mark all alerts as read."""
    from core.market.alert_engine import alert_engine
    return {"marked": alert_engine.mark_all_read()}


@router.get("/api/alerts/preferences")
async def get_alert_preferences():
    """Get current alert preferences."""
    from core.market.alert_engine import alert_engine
    return alert_engine.get_preferences()


@router.post("/api/alerts/preferences")
async def update_alert_preferences(request: Request):
    """Update alert preferences."""
    from core.market.alert_engine import alert_engine
    try:
        body = await request.json()
    except Exception:
        body = {}
    return alert_engine.update_preferences(body)


# ── Parametric Insurance ──────────────────────────────────────────────

def _parametric_provenance():
    """Parametric insurance output is a derived trigger/payout model over internal
    lice/bloom data — never a quoted insurance price (rule 1/3)."""
    from core.market.data_provenance import DataProvenance

    return DataProvenance.degraded(
        "Parametric insurance engine (lice / bloom / temperature triggers)",
        reason=(
            "derived trigger and payout model over internal lice/bloom data — an "
            "estimate, not a quoted insurance price"
        ),
        confidence=0.4,
    )


@router.get("/api/parametric/products")
async def parametric_products():
    from core.market.parametric_insurance import parametric_insurance_engine
    return parametric_insurance_engine.get_products()


@router.post("/api/parametric/scan")
async def parametric_scan():
    from core.market.parametric_insurance import parametric_insurance_engine
    new = await parametric_insurance_engine.scan_triggers()
    return {"new_triggers": new, "count": len(new)}


@router.get("/api/parametric/triggers")
async def parametric_triggers(product: str = None, confirmed_only: bool = False):
    from core.market.parametric_insurance import parametric_insurance_engine
    result = parametric_insurance_engine.get_active_triggers(product=product, confirmed_only=confirmed_only)
    if isinstance(result, dict):
        result.setdefault("data_provenance", _parametric_provenance().to_dict())
    return result


@router.get("/api/parametric/dashboard")
async def parametric_dashboard():
    from core.market.parametric_insurance import parametric_insurance_engine
    result = parametric_insurance_engine.get_dashboard()
    if isinstance(result, dict):
        result.setdefault("data_provenance", _parametric_provenance().to_dict())
    return result


@router.get("/api/parametric/risk-profile")
async def parametric_risk_profile(locality_no: int = None, pa: int = None):
    from core.market.parametric_insurance import parametric_insurance_engine
    result = await parametric_insurance_engine.compute_risk_profile(locality_no=locality_no, production_area=pa)
    if isinstance(result, dict):
        result.setdefault("data_provenance", _parametric_provenance().to_dict())
    return result
