"""GTM endpoints — the ROI calculator, driven by the customer's own numbers.

Deliberately public and parameterised: a prospect can compute their own case without
talking to us, and every output states which values were assumptions. The platform
asserts no market value it cannot measure (rule 3).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/gtm", tags=["gtm"])


@router.get("/roi")
async def roi_defaults(icp: str = "producer", months: int = 12):
    """Default ROI case for an ICP, with every assumption labelled."""
    from core.gtm.roi import ICP_DEFAULTS, ICP_LABELS, calculate

    try:
        return {
            "result": calculate(icp, months=months),
            "ssot": False,
            "icps": list(ICP_DEFAULTS),
            "labels": ICP_LABELS,
            "hint": "POST /api/gtm/roi with your own inputs to replace the assumptions.",
        }
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/roi")
async def roi_calculate(request: Request):
    """Compute ROI from supplied inputs.

    Body: {"icp": "producer", "months": 12, "inputs": {"annual_tonnes": 12000}}
    """
    from core.gtm.roi import calculate

    body = await request.json()
    icp = body.get("icp", "producer")
    months = int(body.get("months") or 12)
    if months < 1 or months > 60:
        raise HTTPException(422, "months must be between 1 and 60")
    try:
        return calculate(icp, body.get("inputs") or {}, months=months)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/kit")
async def gtm_kit():
    """The GTM assets and where they live (one-pager, demo, events, LinkedIn)."""
    return {
        "assets": [
            {
                "name": "Security & architecture one-pager",
                "path": "docs/GTM_SECURITY_ONE_PAGER.md",
                "audience": "Enterprise procurement, security review",
            },
            {
                "name": "3-minute demo script",
                "path": "docs/GTM_DEMO_SCRIPT.md",
                "audience": "First call, trade-show stand, webinar",
            },
            {
                "name": "LinkedIn content pack",
                "path": "docs/GTM_LINKEDIN_PACK.md",
                "audience": "Founder + domain experts (2-3 posts/week)",
            },
            {
                "name": "Event playbook (AquaNor, NASF)",
                "path": "docs/GTM_EVENTS.md",
                "audience": "Events team",
            },
        ],
        "roi_calculator": {
            "get": "/api/gtm/roi?icp=producer",
            "post": "/api/gtm/roi",
            "icps": ["producer", "processor", "desk", "insurer"],
        },
        "live_proof_points": [
            "/api/indices — published AI-STI with method version and provenance (AI-LPI v1.0 withdrawn, reason served)",
            "/api/accuracy — artifact-backed metrics, or an explicit 'not yet published'",
            "/api/data-freshness — per-source freshness, including synthetic-data flags",
            "/api/billing/catalog — real plans and prices",
            "/api/legal/data-licenses — what we may do with each source",
        ],
    }