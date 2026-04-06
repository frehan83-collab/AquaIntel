"""
EU Traceability Compliance Routes
===================================
Extracted from core/api.py for maintainability.
Catch certificates, lot tracing, IUU risk, EUDR compliance.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from core.market.data_provenance import DataProvenance

router = APIRouter(prefix="/api/traceability", tags=["traceability"])


@router.get("/dashboard")
async def traceability_dashboard():
    """EU traceability compliance overview KPIs."""
    from core.market.eu_traceability_engine import eu_traceability_engine
    result = await eu_traceability_engine.dashboard()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Internal compliance database", confidence=0.95).to_dict()
    return result


@router.post("/certificate")
async def traceability_create_certificate(request: Request):
    """Create a new catch certificate."""
    from core.market.eu_traceability_engine import eu_traceability_engine
    data = await request.json()
    result = await eu_traceability_engine.create_certificate(data)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Internal compliance database", confidence=0.95).to_dict()
    return result


@router.get("/certificate/{cert_id}")
async def traceability_get_certificate(cert_id: int):
    """Get catch certificate details."""
    from core.market.eu_traceability_engine import eu_traceability_engine
    result = await eu_traceability_engine.get_certificate(cert_id)
    if not result:
        raise HTTPException(404, "Certificate not found")
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Internal compliance database", confidence=0.95).to_dict()
    return result


@router.get("/certificates")
async def traceability_list_certificates(status: str | None = None, limit: int = 50):
    """List catch certificates, optionally filtered by status."""
    from core.market.eu_traceability_engine import eu_traceability_engine
    result = await eu_traceability_engine.list_certificates(status=status, limit=limit)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Internal compliance database", confidence=0.95).to_dict()
    return result


@router.post("/lot")
async def traceability_create_lot(request: Request):
    """Create a new lot trace for product tracking."""
    from core.market.eu_traceability_engine import eu_traceability_engine
    data = await request.json()
    result = await eu_traceability_engine.create_lot(data)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Internal compliance database", confidence=0.95).to_dict()
    return result


@router.get("/lot/{lot_id}/chain")
async def traceability_chain_of_custody(lot_id: str):
    """Get full chain of custody timeline for a lot."""
    from core.market.eu_traceability_engine import eu_traceability_engine
    result = await eu_traceability_engine.get_chain_of_custody(lot_id)
    if not result:
        raise HTTPException(404, "Lot not found")
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Internal compliance database", confidence=0.95).to_dict()
    return result


@router.post("/iuu-risk")
async def traceability_iuu_risk(request: Request):
    """Assess IUU fishing risk for a vessel."""
    from core.market.eu_traceability_engine import eu_traceability_engine
    data = await request.json()
    result = await eu_traceability_engine.assess_iuu_risk(data)
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Internal compliance database", confidence=0.95).to_dict()
    return result


@router.get("/eudr-status")
async def traceability_eudr_status():
    """Get EUDR compliance overview for feed suppliers."""
    from core.market.eu_traceability_engine import eu_traceability_engine
    result = await eu_traceability_engine.get_eudr_status()
    if isinstance(result, dict):
        result["data_provenance"] = DataProvenance.live("Internal compliance database", confidence=0.95).to_dict()
    return result


# ──────────────────────────────────────────────────────────────────────
# ASC Farm Standard v1.0 Compliance
# ──────────────────────────────────────────────────────────────────────

compliance_router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@compliance_router.get("/asc/readiness/{locality_no}")
async def asc_readiness(locality_no: int):
    """ASC Farm Standard v1.0 audit readiness for a single farm.

    Checks data completeness across 10 indicators: lice monitoring,
    treatment records, mortality data, feed traceability, temperature,
    welfare indicators, and reporting continuity.
    """
    from core.market.asc_compliance import asc_compliance
    return await asc_compliance.audit_readiness(locality_no)


@compliance_router.get("/asc/readiness-summary")
async def asc_readiness_summary():
    """ASC Farm Standard v1.0 readiness overview across all farms.

    Returns per-farm readiness scores, overall average, and distribution
    of audit-ready vs needs-work vs not-ready farms.
    """
    from core.market.asc_compliance import asc_compliance
    return await asc_compliance.readiness_summary()


@compliance_router.get("/asc/checklist")
async def asc_checklist():
    """Full ASC Farm Standard v1.0 indicator checklist.

    Returns all 10 indicators with categories, descriptions, and weights.
    Includes days until mandatory date (May 1, 2027).
    """
    from core.market.asc_compliance import asc_compliance
    return asc_compliance.get_checklist()
