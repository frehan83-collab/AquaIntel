"""
Notification / Threshold Alert Routes
=======================================
Endpoints for the threshold-based alert system.
Includes notification history and mark-read for the Notification Center page.
Custom alert rules engine: user-defined threshold-based alerts with CRUD + evaluation.
Extracted as a separate router for clean decomposition.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import operator as op_mod
import structlog
from typing import Optional

log = structlog.get_logger("notification_routes")

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from core.schemas import (
    AlertsListResponse,
    ThresholdConfig,
    CustomAlertRuleCreate,
    CustomAlertRuleUpdate,
    CustomAlertRuleResponse,
    CustomAlertRulesEvaluateResponse,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# In-memory read-tracking (until persistence layer added)
_read_notification_ids: set[str] = set()

DEFAULT_PREFS = {
    "lice_critical": 0.5, "lice_warning": 0.3,
    "price_change_pct": 10.0, "sst_high": 16.0, "sst_low": 4.0,
    "email_alerts": False, "push_alerts": True,
}


@router.get("/alerts", response_model=AlertsListResponse)
async def get_active_alerts():
    """Get all currently active threshold alerts."""
    from core.market.threshold_alerts import threshold_alert_engine
    from core.source_lineage import latest_week_lineage, provenance_for
    alerts = await threshold_alert_engine.check_all()
    # WS-14: the lice alerts are computed from the newest reported week, so the
    # payload's live claim travels with that week's lineage.
    lineage = await latest_week_lineage()
    return {
        "alerts": [a.to_dict() for a in alerts],
        "count": len(alerts),
        "critical": sum(1 for a in alerts if a.severity == "critical"),
        "high": sum(1 for a in alerts if a.severity == "high"),
        "lineage": lineage,
        "data_provenance": provenance_for(
            lineage, "BarentsWatch + SSB + MET.no", 0.85
        ),
    }


@router.get("/thresholds", response_model=ThresholdConfig)
async def get_thresholds():
    """Get current alert threshold configuration."""
    from core.market.threshold_alerts import threshold_alert_engine
    return threshold_alert_engine.get_thresholds()


@router.post("/thresholds")
async def update_thresholds(request: Request):
    """Update alert thresholds."""
    from core.market.threshold_alerts import threshold_alert_engine
    data = await request.json()
    return threshold_alert_engine.update_thresholds(data)


@router.get("/preferences/{email}")
async def get_preferences(email: str):
    """Get notification preferences for a user."""
    from core.async_db import get_async_session
    from core.models import NotificationPreference
    async with get_async_session() as s:
        pref = (await s.execute(
            select(NotificationPreference).where(NotificationPreference.user_email == email)
        )).scalar()
        if not pref:
            return {"email": email, "preferences": DEFAULT_PREFS, "saved": False}
        return {
            "email": email,
            "preferences": {
                "lice_critical": pref.lice_critical_threshold,
                "lice_warning": pref.lice_warning_threshold,
                "price_change_pct": pref.price_change_pct,
                "sst_high": pref.sst_high_threshold,
                "sst_low": pref.sst_low_threshold,
                "email_alerts": pref.email_alerts,
                "push_alerts": pref.push_alerts,
            },
            "saved": True,
        }


@router.post("/preferences")
async def save_preferences(request: Request):
    """Save notification preferences for a user."""
    from core.async_db import get_async_session
    from core.models import NotificationPreference
    data = await request.json()
    email = data.get("email", "anonymous")
    async with get_async_session() as s:
        existing = (await s.execute(
            select(NotificationPreference).where(NotificationPreference.user_email == email)
        )).scalar()
        if existing:
            existing.lice_critical_threshold = data.get("lice_critical", 0.5)
            existing.lice_warning_threshold = data.get("lice_warning", 0.3)
            existing.price_change_pct = data.get("price_change_pct", 10.0)
            existing.sst_high_threshold = data.get("sst_high", 16.0)
            existing.sst_low_threshold = data.get("sst_low", 4.0)
            existing.email_alerts = data.get("email_alerts", False)
            existing.push_alerts = data.get("push_alerts", True)
        else:
            pref = NotificationPreference(
                user_email=email,
                lice_critical_threshold=data.get("lice_critical", 0.5),
                lice_warning_threshold=data.get("lice_warning", 0.3),
                price_change_pct=data.get("price_change_pct", 10.0),
                sst_high_threshold=data.get("sst_high", 16.0),
                sst_low_threshold=data.get("sst_low", 4.0),
                email_alerts=data.get("email_alerts", False),
                push_alerts=data.get("push_alerts", True),
            )
            s.add(pref)
    return {"status": "saved", "email": email}


# ── Notification History & Mark-Read ─────────────────────────────────


def _normalize_category(cat: str) -> str:
    """Map alert engine categories to frontend categories."""
    mapping = {
        "lice": "lice",
        "disease": "disease",
        "price": "price",
        "weather": "temperature",
        "regime": "disease",
        "anomaly": "lice",
        "supply": "price",
        "feed_cost": "price",
    }
    return mapping.get(cat, cat)


def _normalize_severity(sev: str) -> str:
    """Map alert severities to info/warning/critical."""
    if sev in ("critical",):
        return "critical"
    if sev in ("high", "medium"):
        return "warning"
    return "info"


@router.get("/history")
async def notification_history(
    severity: Optional[str] = Query(None, description="Filter: info, warning, critical"),
    category: Optional[str] = Query(None, description="Filter: lice, price, disease, temperature"),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Get notification history (last 100) sorted by timestamp DESC.
    Merges alerts from both ThresholdAlertEngine and AlertEngine.
    """

    notifications: list[dict] = []

    # Source 1: ThresholdAlertEngine (lice/price/temperature)
    try:
        from core.market.threshold_alerts import threshold_alert_engine
        threshold_alerts = await threshold_alert_engine.check_all()
        for a in threshold_alerts:
            d = a.to_dict() if hasattr(a, "to_dict") else a
            nid = d.get("id", hashlib.md5(f"{d.get('title','')}{d.get('created_at','')}".encode()).hexdigest()[:12])
            notifications.append({
                "id": nid,
                "title": d.get("title", "Alert"),
                "message": d.get("message", ""),
                "severity": _normalize_severity(d.get("severity", "medium")),
                "category": _normalize_category(d.get("category", "lice")),
                "timestamp": d.get("created_at", dt.datetime.now(dt.UTC).isoformat()),
                "read": nid in _read_notification_ids,
                "source": "threshold_engine",
                "metric_value": d.get("metric_value"),
                "threshold": d.get("threshold"),
            })
    except Exception as exc:
        log.warning("notification_op_failed", error=str(exc))

    # Source 2: AlertEngine (anomaly/regime/disease/price)
    try:
        from core.market.alert_engine import alert_engine
        engine_alerts = alert_engine.get_alerts(limit=100)
        for d in engine_alerts:
            nid = d.get("id", hashlib.md5(f"{d.get('title','')}{d.get('created_at','')}".encode()).hexdigest()[:12])
            notifications.append({
                "id": nid,
                "title": d.get("title", "Alert"),
                "message": d.get("message", ""),
                "severity": _normalize_severity(d.get("severity", "medium")),
                "category": _normalize_category(d.get("category", "anomaly")),
                "timestamp": d.get("created_at", dt.datetime.now(dt.UTC).isoformat()),
                "read": d.get("read", False) or nid in _read_notification_ids,
                "source": d.get("source", "alert_engine"),
                "metric_value": d.get("value"),
                "threshold": d.get("threshold"),
            })
    except Exception as exc:
        log.warning("notification_op_failed", error=str(exc))

    # Deduplicate by id
    seen_ids: set[str] = set()
    unique: list[dict] = []
    for n in notifications:
        if n["id"] not in seen_ids:
            seen_ids.add(n["id"])
            unique.append(n)
    notifications = unique

    # Apply filters
    if severity:
        notifications = [n for n in notifications if n["severity"] == severity]
    if category:
        notifications = [n for n in notifications if n["category"] == category]

    # Sort by timestamp DESC
    notifications.sort(key=lambda n: n.get("timestamp", ""), reverse=True)
    notifications = notifications[:limit]

    unread_count = sum(1 for n in notifications if not n["read"])

    # WS-14: lice-derived notifications come from the newest reported week.
    from core.source_lineage import latest_week_lineage, provenance_for
    lineage = await latest_week_lineage()
    return {
        "notifications": notifications,
        "total": len(notifications),
        "unread_count": unread_count,
        "lineage": lineage,
        "data_provenance": provenance_for(
            lineage, "ThresholdAlertEngine + AlertEngine", 0.85
        ),
    }


@router.post("/mark-read")
async def mark_notifications_read(request: Request):
    """
    Mark notifications as read by ID list.
    Body: { "notification_ids": ["id1", "id2", ...] }
    """
    data = await request.json()
    ids = data.get("notification_ids", [])

    # Track in our in-memory set
    for nid in ids:
        _read_notification_ids.add(str(nid))

    # Also mark in AlertEngine if the id exists there
    try:
        from core.market.alert_engine import alert_engine
        for nid in ids:
            alert_engine.mark_read(str(nid))
    except Exception as exc:
        log.warning("notification_op_failed", error=str(exc))

    return {"status": "ok", "marked": len(ids)}


@router.post("/mark-all-read")
async def mark_all_notifications_read():
    """Mark all notifications as read."""
    try:
        from core.market.alert_engine import alert_engine
        count = alert_engine.mark_all_read()
    except Exception:
        count = 0

    # Also mark everything from threshold engine
    try:
        from core.market.threshold_alerts import threshold_alert_engine
        threshold_alerts = await threshold_alert_engine.check_all()
        for a in threshold_alerts:
            d = a.to_dict() if hasattr(a, "to_dict") else a
            _read_notification_ids.add(d.get("id", ""))
            count += 1
    except Exception as exc:
        log.warning("notification_op_failed", error=str(exc))

    return {"status": "ok", "marked": count}


# ══════════════════════════════════════════════════════════════════════
# CUSTOM ALERT RULES ENGINE
# ══════════════════════════════════════════════════════════════════════

OPERATOR_MAP = {
    ">": op_mod.gt,
    "<": op_mod.lt,
    ">=": op_mod.ge,
    "<=": op_mod.le,
    "==": op_mod.eq,
}


def _row_to_response(row) -> dict:
    """Convert a CustomAlertRule ORM row to a response dict."""
    return {
        "id": row.id,
        "user_id": row.user_id,
        "name": row.name,
        "metric": row.metric,
        "operator": row.operator,
        "threshold": row.threshold,
        "production_area": row.production_area,
        "is_active": row.is_active,
        "notify_webhook": row.notify_webhook,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_triggered": row.last_triggered.isoformat() if row.last_triggered else None,
        "trigger_count": row.trigger_count or 0,
    }


@router.get("/alerts/rules", response_model=list[CustomAlertRuleResponse])
async def list_alert_rules(user_id: Optional[int] = Query(None)):
    """List all custom alert rules, optionally filtered by user_id."""
    from core.async_db import get_async_session
    from core.models import CustomAlertRule

    async with get_async_session() as s:
        q = select(CustomAlertRule).order_by(CustomAlertRule.created_at.desc())
        if user_id is not None:
            q = q.where(CustomAlertRule.user_id == user_id)
        result = await s.execute(q)
        rows = result.scalars().all()
        return [_row_to_response(r) for r in rows]


@router.post("/alerts/rules", response_model=CustomAlertRuleResponse, status_code=201)
async def create_alert_rule(rule: CustomAlertRuleCreate):
    """Create a new custom alert rule with validation."""
    from core.async_db import get_async_session
    from core.models import CustomAlertRule

    async with get_async_session() as s:
        new_rule = CustomAlertRule(
            name=rule.name,
            metric=rule.metric,
            operator=rule.operator,
            threshold=rule.threshold,
            production_area=rule.production_area,
            is_active=rule.is_active,
            notify_webhook=rule.notify_webhook,
            created_at=dt.datetime.now(dt.UTC),
        )
        s.add(new_rule)
        await s.flush()  # get id assigned

        # Audit: alert rule created
        from core.audit import log_action
        await log_action(
            None, "create_alert_rule",
            f"alert_rule:{new_rule.id}",
            details={"name": rule.name, "metric": rule.metric, "operator": rule.operator, "threshold": rule.threshold},
        )

        return _row_to_response(new_rule)


@router.put("/alerts/rules/{rule_id}", response_model=CustomAlertRuleResponse)
async def update_alert_rule(rule_id: int, updates: CustomAlertRuleUpdate):
    """Update an existing custom alert rule (partial update)."""
    from core.async_db import get_async_session
    from core.models import CustomAlertRule

    async with get_async_session() as s:
        result = await s.execute(
            select(CustomAlertRule).where(CustomAlertRule.id == rule_id)
        )
        rule = result.scalar()
        if not rule:
            raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

        update_data = updates.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(rule, field, value)

        await s.flush()
        return _row_to_response(rule)


@router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule(rule_id: int):
    """Delete a custom alert rule."""
    from core.async_db import get_async_session
    from core.models import CustomAlertRule

    async with get_async_session() as s:
        result = await s.execute(
            select(CustomAlertRule).where(CustomAlertRule.id == rule_id)
        )
        rule = result.scalar()
        if not rule:
            raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

        rule_name = rule.name
        await s.delete(rule)

    # Audit: alert rule deleted
    from core.audit import log_action
    await log_action(
        None, "delete_alert_rule",
        f"alert_rule:{rule_id}",
        details={"name": rule_name},
    )

    return {"status": "deleted", "id": rule_id}


async def _fetch_current_metric(metric: str, production_area: Optional[int] = None) -> Optional[float]:
    """
    Fetch the current value for a given metric from existing engines.
    Returns None if the metric cannot be fetched.
    Fully async to avoid blocking the event loop during alert rule evaluation.
    """
    try:
        if metric == "lice_avg":
            from core.async_db import get_async_session
            from core.models import LiceRecord, Locality
            from sqlalchemy import func
            async with get_async_session() as s:
                q_latest = (
                    select(LiceRecord.year, LiceRecord.week)
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )
                latest_res = await s.execute(q_latest)
                latest = latest_res.first()
                if not latest:
                    return None
                q = select(func.avg(LiceRecord.avg_adult_female_lice)).where(
                    LiceRecord.year == latest[0],
                    LiceRecord.week == latest[1],
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )
                if production_area is not None:
                    q = q.join(Locality, Locality.locality_no == LiceRecord.locality_no).where(
                        Locality.production_area == production_area
                    )
                val_res = await s.execute(q)
                val = val_res.scalar()
                return float(val) if val is not None else None

        elif metric == "spot_price":
            from core.market.ssb_price_client import ssb_price_client
            recent = await ssb_price_client.fetch_prices(n_weeks=2)
            if hasattr(recent, 'prices') and len(recent.prices) >= 1:
                p = recent.prices[-1]
                return float(p.price_nok_kg if hasattr(p, 'price_nok_kg') else p.get('price_nok_kg', 0))
            return None

        elif metric == "sst":
            from core.async_db import get_async_session
            from core.models import LiceRecord, Locality
            from sqlalchemy import func
            async with get_async_session() as s:
                q_latest = (
                    select(LiceRecord.year, LiceRecord.week)
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )
                latest_res = await s.execute(q_latest)
                latest = latest_res.first()
                if not latest:
                    return None
                q = select(func.avg(LiceRecord.sea_temp_c)).where(
                    LiceRecord.year == latest[0],
                    LiceRecord.week == latest[1],
                    LiceRecord.sea_temp_c.isnot(None),
                )
                if production_area is not None:
                    q = q.join(Locality, Locality.locality_no == LiceRecord.locality_no).where(
                        Locality.production_area == production_area
                    )
                val_res = await s.execute(q)
                val = val_res.scalar()
                return float(val) if val is not None else None

        elif metric == "disease_count":
            try:
                from core.market.mattilsynet_client import mattilsynet_client
                data = await mattilsynet_client.fetch_disease_cases()
                if isinstance(data, list):
                    if production_area is not None:
                        data = [d for d in data if d.get("production_area") == production_area]
                    return float(len(data))
                return 0.0
            except Exception:
                return 0.0

        elif metric == "bloom_risk":
            try:
                from core.async_db import get_async_session
                from core.bloom.models import BloomRiskAssessment
                from sqlalchemy import func
                async with get_async_session() as s:
                    q = select(func.avg(BloomRiskAssessment.risk_score)).where(
                        BloomRiskAssessment.risk_score.isnot(None)
                    )
                    val_res = await s.execute(q)
                    val = val_res.scalar()
                    return float(val) if val is not None else None
            except Exception:
                return None

    except Exception:
        return None

    return None


async def evaluate_custom_rules() -> dict:
    """
    Evaluate all active custom alert rules against current metric data.
    Returns triggered rules with current values.
    """
    from core.async_db import get_async_session
    from core.models import CustomAlertRule
    from core.source_lineage import latest_week_lineage, provenance_for

    results: list[dict] = []
    triggered_count = 0

    async with get_async_session() as s:
        result = await s.execute(
            select(CustomAlertRule).where(CustomAlertRule.is_active == True)  # noqa: E712
        )
        rules = result.scalars().all()

        for rule in rules:
            current_value = await _fetch_current_metric(rule.metric, rule.production_area)
            triggered = False
            message = None

            if current_value is not None:
                cmp_fn = OPERATOR_MAP.get(rule.operator)
                if cmp_fn and cmp_fn(current_value, rule.threshold):
                    triggered = True
                    triggered_count += 1
                    message = (
                        f"{rule.name}: {rule.metric} = {current_value:.3f} "
                        f"{rule.operator} {rule.threshold} (TRIGGERED)"
                    )

                    # Update trigger metadata
                    rule.last_triggered = dt.datetime.now(dt.UTC)
                    rule.trigger_count = (rule.trigger_count or 0) + 1
                else:
                    message = (
                        f"{rule.name}: {rule.metric} = {current_value:.3f} "
                        f"{rule.operator} {rule.threshold} (OK)"
                    )
            else:
                message = f"{rule.name}: could not fetch current value for {rule.metric}"

            results.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "metric": rule.metric,
                "operator": rule.operator,
                "threshold": rule.threshold,
                "current_value": current_value,
                "triggered": triggered,
                "production_area": rule.production_area,
                "message": message,
            })

    # WS-14: the lice metrics evaluated here come from the newest reported week.
    lineage = await latest_week_lineage()
    return {
        "evaluated": len(results),
        "triggered": triggered_count,
        "results": results,
        "lineage": lineage,
        "data_provenance": provenance_for(
            lineage, "BarentsWatch + SSB + Mattilsynet + CMEMS", 0.80
        ),
    }


@router.get("/alerts/rules/evaluate", response_model=CustomAlertRulesEvaluateResponse)
async def evaluate_alert_rules():
    """Evaluate all active custom alert rules against current data."""
    return await evaluate_custom_rules()
