"""
Integration routes for third-party farm management systems.
Currently supports: Fishtalk 5 (AKVA Group).
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["integrations"])


# ── Fishtalk 5 Integration ──────────────────────────────────────────

@router.get("/api/integrations/fishtalk/status")
async def fishtalk_status():
    """Check Fishtalk 5 API connection status and health."""
    from core.integrations.fishtalk_client import fishtalk_client
    return await fishtalk_client.sync_status()


@router.get("/api/integrations/fishtalk/farm/{site_id}")
async def fishtalk_farm_data(site_id: str):
    """Fetch daily feed, mortality, and biomass data from Fishtalk for a site."""
    from core.integrations.fishtalk_client import fishtalk_client
    return await fishtalk_client.get_farm_data(site_id)


@router.get("/api/integrations/fishtalk/lice/{site_id}")
async def fishtalk_lice_data(site_id: str):
    """Fetch lice count data from Fishtalk automated counting systems."""
    from core.integrations.fishtalk_client import fishtalk_client
    return await fishtalk_client.get_lice_counts(site_id)


@router.get("/api/integrations/fishtalk/treatments/{site_id}")
async def fishtalk_treatments(site_id: str):
    """Fetch treatment history records from Fishtalk for a site."""
    from core.integrations.fishtalk_client import fishtalk_client
    return await fishtalk_client.get_treatment_history(site_id)
