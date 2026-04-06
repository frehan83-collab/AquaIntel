"""
EU Traceability Compliance Engine
====================================
Manages catch certificates, lot tracing, IUU risk scoring, and EUDR compliance
per EU mandatory digital traceability regulation (effective January 2026).

All data stored in local DB — no external API dependencies.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any

import structlog

log = structlog.get_logger(__name__)

# IUU risk: flag states with elevated fishing violation risk (EU IUU vessel list)
HIGH_RISK_FLAG_STATES = {
    "Cambodia", "Comoros", "Saint Vincent and the Grenadines",
    "Cameroon", "Sri Lanka", "Trinidad and Tobago",
}
MEDIUM_RISK_FLAG_STATES = {
    "Panama", "Belize", "Honduras", "Sierra Leone",
    "Togo", "Vanuatu", "Fiji",
}

# EUDR: countries with high deforestation risk for soy/palm (EU benchmark)
EUDR_HIGH_RISK_COUNTRIES = {
    "Brazil", "Indonesia", "Malaysia", "Paraguay",
    "Argentina", "Bolivia", "Colombia", "Peru",
    "Democratic Republic of Congo", "Myanmar",
}


class EUTraceabilityEngine:
    """Singleton engine for EU traceability compliance."""

    # ── Catch Certificates ───────────────────────────────────────────

    async def create_certificate(self, data: dict) -> dict:
        """Create a new catch certificate."""
        from core.models import CatchCertificate
        from core.async_db import get_async_session

        cert_no = f"CC-{dt.datetime.now(dt.UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        async with get_async_session() as s:
            cert = CatchCertificate(
                certificate_no=cert_no,
                vessel_name=data.get("vessel_name", ""),
                flag_state=data.get("flag_state", "Norway"),
                catch_area=data.get("catch_area", ""),
                species=data.get("species", "Atlantic salmon"),
                quantity_kg=data.get("quantity_kg", 0),
                catch_date=dt.datetime.fromisoformat(data["catch_date"]) if data.get("catch_date") else None,
                landing_port=data.get("landing_port", ""),
                validation_authority=data.get("validation_authority", ""),
                status="draft",
                expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=365),
                notes=data.get("notes", ""),
            )
            s.add(cert)
            await s.flush()
            cert_id = cert.id

        log.info("catch_certificate_created", cert_no=cert_no)
        return {"id": cert_id, "certificate_no": cert_no, "status": "draft"}

    async def get_certificate(self, cert_id: int) -> dict | None:
        """Get certificate details by ID."""
        from core.models import CatchCertificate
        from core.async_db import get_async_session
        from sqlalchemy import select

        async with get_async_session() as s:
            result = await s.execute(
                select(CatchCertificate).where(CatchCertificate.id == cert_id)
            )
            cert = result.scalar_one_or_none()
            if not cert:
                return None
            return {
                "id": cert.id,
                "certificate_no": cert.certificate_no,
                "vessel_name": cert.vessel_name,
                "flag_state": cert.flag_state,
                "catch_area": cert.catch_area,
                "species": cert.species,
                "quantity_kg": cert.quantity_kg,
                "catch_date": cert.catch_date.isoformat() if cert.catch_date else None,
                "landing_port": cert.landing_port,
                "validation_authority": cert.validation_authority,
                "status": cert.status,
                "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
                "expires_at": cert.expires_at.isoformat() if cert.expires_at else None,
                "notes": cert.notes,
            }

    async def list_certificates(self, status: str | None = None, limit: int = 50) -> list[dict]:
        """List certificates, optionally filtered by status."""
        from core.models import CatchCertificate
        from core.async_db import get_async_session
        from sqlalchemy import select

        async with get_async_session() as s:
            q = select(CatchCertificate).order_by(CatchCertificate.issued_at.desc()).limit(limit)
            if status:
                q = q.where(CatchCertificate.status == status)
            result = await s.execute(q)
            certs = result.scalars().all()
            return [
                {
                    "id": c.id,
                    "certificate_no": c.certificate_no,
                    "vessel_name": c.vessel_name,
                    "flag_state": c.flag_state,
                    "species": c.species,
                    "quantity_kg": c.quantity_kg,
                    "status": c.status,
                    "issued_at": c.issued_at.isoformat() if c.issued_at else None,
                }
                for c in certs
            ]

    # ── Lot Tracing ──────────────────────────────────────────────────

    async def create_lot(self, data: dict) -> dict:
        """Create a new lot trace."""
        from core.models import LotTrace
        from core.async_db import get_async_session

        lot_id = f"LOT-{dt.datetime.now(dt.UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        initial_event = {
            "event": "created",
            "holder": data.get("current_holder", ""),
            "location": data.get("origin_location", ""),
            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
        }

        async with get_async_session() as s:
            lot = LotTrace(
                lot_id=lot_id,
                certificate_id=data.get("certificate_id"),
                origin_locality_no=data.get("origin_locality_no"),
                product_type=data.get("product_type", "whole"),
                quantity_kg=data.get("quantity_kg", 0),
                chain_of_custody=json.dumps([initial_event]),
                current_holder=data.get("current_holder", ""),
                status="in_transit",
            )
            s.add(lot)
            await s.flush()
            row_id = lot.id

        log.info("lot_trace_created", lot_id=lot_id)
        return {"id": row_id, "lot_id": lot_id, "status": "in_transit"}

    async def get_chain_of_custody(self, lot_id: str) -> dict | None:
        """Get full chain of custody for a lot."""
        from core.models import LotTrace
        from core.async_db import get_async_session
        from sqlalchemy import select

        async with get_async_session() as s:
            result = await s.execute(
                select(LotTrace).where(LotTrace.lot_id == lot_id)
            )
            lot = result.scalar_one_or_none()
            if not lot:
                return None
            chain = json.loads(lot.chain_of_custody) if lot.chain_of_custody else []
            return {
                "lot_id": lot.lot_id,
                "product_type": lot.product_type,
                "quantity_kg": lot.quantity_kg,
                "current_holder": lot.current_holder,
                "status": lot.status,
                "origin_locality_no": lot.origin_locality_no,
                "certificate_id": lot.certificate_id,
                "chain": chain,
                "created_at": lot.created_at.isoformat() if lot.created_at else None,
            }

    # ── IUU Risk Scoring ─────────────────────────────────────────────

    async def assess_iuu_risk(self, data: dict) -> dict:
        """Assess IUU fishing risk for a vessel."""
        from core.models import IUURiskAssessment
        from core.async_db import get_async_session

        vessel = data.get("vessel_name", "Unknown")
        flag = data.get("flag_state", "Unknown")
        imo = data.get("imo_number", "")

        # Rule-based scoring
        score = 0.0
        factors: dict[str, Any] = {}

        # Flag state risk (0-30 points)
        if flag in HIGH_RISK_FLAG_STATES:
            score += 30
            factors["flag_risk"] = {"score": 30, "detail": f"{flag} is on EU IUU high-risk list"}
        elif flag in MEDIUM_RISK_FLAG_STATES:
            score += 15
            factors["flag_risk"] = {"score": 15, "detail": f"{flag} has elevated IUU risk"}
        else:
            factors["flag_risk"] = {"score": 0, "detail": f"{flag} is low-risk"}

        # Documentation completeness (0-25 points)
        has_imo = bool(imo)
        has_catch_area = bool(data.get("catch_area"))
        has_license = bool(data.get("fishing_license"))
        doc_score = 25 - (8 * has_imo + 8 * has_catch_area + 9 * has_license)
        score += doc_score
        factors["documentation"] = {
            "score": doc_score,
            "imo": has_imo,
            "catch_area": has_catch_area,
            "license": has_license,
        }

        # Catch area risk (0-25 points)
        catch_area = data.get("catch_area", "")
        if "unregulated" in catch_area.lower() or not catch_area:
            score += 25
            factors["area_risk"] = {"score": 25, "detail": "Unregulated or unknown catch area"}
        elif catch_area.startswith("87") or catch_area.startswith("51"):
            score += 10
            factors["area_risk"] = {"score": 10, "detail": "Area with moderate IUU prevalence"}
        else:
            factors["area_risk"] = {"score": 0, "detail": "Regulated catch area"}

        # History penalty (0-20 points) — placeholder for vessel blacklist check
        factors["history"] = {"score": 0, "detail": "No prior violations recorded"}

        score = min(score, 100)
        level = "low" if score < 25 else "medium" if score < 50 else "high" if score < 75 else "critical"

        async with get_async_session() as s:
            assessment = IUURiskAssessment(
                vessel_name=vessel,
                imo_number=imo,
                flag_state=flag,
                risk_score=score,
                risk_level=level,
                factors=json.dumps(factors),
            )
            s.add(assessment)
            await s.flush()
            row_id = assessment.id

        log.info("iuu_risk_assessed", vessel=vessel, score=score, level=level)
        return {
            "id": row_id,
            "vessel_name": vessel,
            "flag_state": flag,
            "risk_score": round(score, 1),
            "risk_level": level,
            "factors": factors,
        }

    # ── EUDR Compliance ──────────────────────────────────────────────

    async def get_eudr_status(self) -> dict:
        """Get EUDR compliance overview."""
        from core.models import EUDRCompliance
        from core.async_db import get_async_session
        from sqlalchemy import select, func

        async with get_async_session() as s:
            total = (await s.execute(select(func.count(EUDRCompliance.id)))).scalar() or 0
            compliant = (await s.execute(
                select(func.count(EUDRCompliance.id)).where(
                    EUDRCompliance.status == "compliant"
                )
            )).scalar() or 0
            non_compliant = (await s.execute(
                select(func.count(EUDRCompliance.id)).where(
                    EUDRCompliance.status == "non_compliant"
                )
            )).scalar() or 0
            pending = (await s.execute(
                select(func.count(EUDRCompliance.id)).where(
                    EUDRCompliance.status == "pending"
                )
            )).scalar() or 0

            result = await s.execute(
                select(EUDRCompliance).order_by(EUDRCompliance.last_verified.desc()).limit(50)
            )
            suppliers = result.scalars().all()

        compliance_pct = round((compliant / total * 100) if total > 0 else 0, 1)

        return {
            "total_suppliers": total,
            "compliant": compliant,
            "non_compliant": non_compliant,
            "pending": pending,
            "compliance_pct": compliance_pct,
            "high_risk_countries": sorted(EUDR_HIGH_RISK_COUNTRIES),
            "suppliers": [
                {
                    "id": sup.id,
                    "supplier_name": sup.supplier_name,
                    "product": sup.product,
                    "country_of_origin": sup.country_of_origin,
                    "deforestation_free": sup.deforestation_free,
                    "status": sup.status,
                    "certification_valid_until": (
                        sup.certification_valid_until.isoformat()
                        if sup.certification_valid_until else None
                    ),
                }
                for sup in suppliers
            ],
        }

    # ── Dashboard Aggregation ────────────────────────────────────────

    async def dashboard(self) -> dict:
        """Overview KPIs for the traceability dashboard."""
        from core.models import CatchCertificate, LotTrace, IUURiskAssessment, EUDRCompliance
        from core.async_db import get_async_session
        from sqlalchemy import select, func

        async with get_async_session() as s:
            active_certs = (await s.execute(
                select(func.count(CatchCertificate.id)).where(
                    CatchCertificate.status.in_(["draft", "validated"])
                )
            )).scalar() or 0

            lots_in_transit = (await s.execute(
                select(func.count(LotTrace.id)).where(LotTrace.status == "in_transit")
            )).scalar() or 0

            iuu_alerts = (await s.execute(
                select(func.count(IUURiskAssessment.id)).where(
                    IUURiskAssessment.risk_score >= 50
                )
            )).scalar() or 0

            eudr_total = (await s.execute(select(func.count(EUDRCompliance.id)))).scalar() or 0
            eudr_compliant = (await s.execute(
                select(func.count(EUDRCompliance.id)).where(
                    EUDRCompliance.status == "compliant"
                )
            )).scalar() or 0

        eudr_pct = round((eudr_compliant / eudr_total * 100) if eudr_total > 0 else 100, 1)

        return {
            "active_certificates": active_certs,
            "lots_in_transit": lots_in_transit,
            "iuu_high_risk_alerts": iuu_alerts,
            "eudr_compliance_pct": eudr_pct,
            "eu_regulation_status": "active",
            "regulation_effective_date": "2026-01-01",
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        }


# Singleton
eu_traceability_engine = EUTraceabilityEngine()
