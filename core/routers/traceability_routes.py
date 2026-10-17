"""
EU Traceability Compliance Routes
===================================
Extracted from core/api.py for maintainability.
Catch certificates, lot tracing, IUU risk, EUDR compliance.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

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
async def traceability_list_certificates(status: str | None = None, limit: int = Query(50, ge=1, le=1000)):
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


# ──────────────────────────────────────────────────────────────────────
# Regulatory Reporting Automation (Mattilsynet / Akvakulturforskriften)
# ──────────────────────────────────────────────────────────────────────

@compliance_router.get("/deadlines")
async def compliance_deadlines(locality_no: int = None):
    """Get upcoming compliance deadlines for the next 30 days.

    Returns weekly lice report deadlines (Mattilsynet), monthly treatment
    summary deadlines, and quarterly biomass reporting deadlines.
    """
    from core.market.regulatory_reporter import regulatory_reporter
    deadlines = await regulatory_reporter.get_upcoming_deadlines(locality_no)
    return {
        "deadlines": [d.to_dict() for d in deadlines],
        "count": len(deadlines),
        "locality_filter": locality_no,
    }


@compliance_router.get("/report/weekly-lice/{locality_no}")
async def weekly_lice_report(locality_no: int, week: int, year: int):
    """Generate weekly lice report for Mattilsynet submission.

    Pulls lice data from BarentsWatch records, validates against the legal
    limit in lakselusforskriften § 8 (0.5 adult female lice; 0.2 in weeks 16-21
    for Trøndelag and southwards and weeks 21-26 for Nordland, Troms and
    Finnmark; a count equal to the limit is a breach), and flags any
    exceedances or missing data.
    """
    from core.market.regulatory_reporter import regulatory_reporter
    report = await regulatory_reporter.generate_weekly_lice_report(
        locality_no, week, year
    )
    validation_errors = await regulatory_reporter.validate_report(report)
    result = report.to_dict()
    result["validation_errors"] = validation_errors
    return result


@compliance_router.get("/report/monthly-treatment/{locality_no}")
async def monthly_treatment_report(locality_no: int, year: int, month: int):
    """Generate monthly treatment summary for regulatory reporting.

    Aggregates treatment outcomes by method with efficacy statistics,
    cost totals, and pre/post lice comparisons.
    """
    from core.market.regulatory_reporter import regulatory_reporter
    report = await regulatory_reporter.generate_monthly_treatment_summary(
        locality_no, year, month
    )
    validation_errors = await regulatory_reporter.validate_report(report)
    result = report.to_dict()
    result["validation_errors"] = validation_errors
    return result


@compliance_router.get("/score/{locality_no}")
async def compliance_score(locality_no: int):
    """Get compliance health score for a farm.

    Composite score (0-100) based on: on-time reporting rate (40%),
    data completeness (30%), discrepancy count (15%), and treatment
    documentation (15%). Grade: A (90+), B (75+), C (60+), D (<60).
    """
    from core.market.regulatory_reporter import regulatory_reporter
    return await regulatory_reporter.generate_compliance_score(locality_no)
