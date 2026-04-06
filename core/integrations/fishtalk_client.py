"""
Fishtalk 5 API Integration Client
====================================
Integrates with AKVA Group's Fishtalk 5 cloud-native farm management system.
Fishtalk holds ~60% market share among Norwegian salmon farmers, making it
the single most important data source for operational farm data.

Architecture:
  - Configurable via FISHTALK_API_URL and FISHTALK_API_KEY env vars
  - When credentials are NOT configured, every method returns a
    {"status": "not_configured"} stub with instructions to connect
  - When credentials ARE set, uses httpx with timeout/retry to call
    the Fishtalk 5 REST API
  - DataProvenance attached to every response

Reference: AKVA Group Fishtalk 5 (launched end-2025)
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.market.data_provenance import DataProvenance

log = structlog.get_logger(__name__)

# ── Configuration from environment ──────────────────────────────────
FISHTALK_API_URL = os.environ.get("FISHTALK_API_URL", "")
FISHTALK_API_KEY = os.environ.get("FISHTALK_API_KEY", "")


def _is_configured() -> bool:
    """Check if Fishtalk credentials are set."""
    return bool(FISHTALK_API_URL and FISHTALK_API_KEY)


def _not_configured_response(endpoint: str) -> dict:
    """Standard response when Fishtalk is not connected."""
    return {
        "status": "not_configured",
        "message": "Connect your Fishtalk account in Settings",
        "endpoint": endpoint,
        "data_provenance": DataProvenance.degraded(
            "Fishtalk 5 API",
            reason="FISHTALK_API_KEY not configured",
            confidence=0.0,
        ).to_dict(),
    }


class FishtalkClient:
    """
    Client for AKVA Group Fishtalk 5 REST API.

    When FISHTALK_API_KEY is not set, all methods return a stub response
    prompting the user to connect their account. When configured, methods
    call the live Fishtalk 5 API with retry and timeout handling.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=FISHTALK_API_URL,
                headers={
                    "Authorization": f"Bearer {FISHTALK_API_KEY}",
                    "Accept": "application/json",
                    "User-Agent": "OpenClaw/2.3.0",
                },
                timeout=30.0,
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an authenticated request to Fishtalk 5 API."""
        client = self._get_client()
        resp = await client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    # ── Public Methods ──────────────────────────────────────────────

    async def sync_status(self) -> dict:
        """
        Check Fishtalk API connection health.
        Returns connectivity status and last sync time.
        """
        if not _is_configured():
            return {
                "connected": False,
                "status": "not_configured",
                "message": "Connect your Fishtalk account in Settings",
                "fishtalk_url": "",
                "data_provenance": DataProvenance.degraded(
                    "Fishtalk 5 API",
                    reason="FISHTALK_API_KEY not configured",
                    confidence=0.0,
                ).to_dict(),
            }

        try:
            data = await self._request("GET", "/api/v1/status")
            return {
                "connected": True,
                "status": "connected",
                "fishtalk_url": FISHTALK_API_URL,
                "api_version": data.get("version", "5.x"),
                "last_sync": dt.datetime.now(dt.UTC).isoformat(),
                "data_provenance": DataProvenance.live(
                    "Fishtalk 5 API",
                    confidence=0.95,
                ).to_dict(),
            }
        except Exception as e:
            log.warning("fishtalk.status_error", error=str(e)[:100])
            return {
                "connected": False,
                "status": "error",
                "message": f"Connection failed: {str(e)[:100]}",
                "fishtalk_url": FISHTALK_API_URL,
                "data_provenance": DataProvenance.degraded(
                    "Fishtalk 5 API",
                    reason=f"API error: {str(e)[:80]}",
                    confidence=0.0,
                ).to_dict(),
            }

    async def get_farm_data(self, site_id: str) -> dict:
        """
        Fetch daily operational data for a farm site from Fishtalk.
        Includes feed consumption, mortality, and biomass.

        Args:
            site_id: Fishtalk site identifier
        """
        if not _is_configured():
            return _not_configured_response(f"farm_data/{site_id}")

        try:
            data = await self._request("GET", f"/api/v1/sites/{site_id}/daily")
            return {
                "site_id": site_id,
                "feed_kg": data.get("feed_kg", 0),
                "mortality_count": data.get("mortality_count", 0),
                "biomass_kg": data.get("biomass_kg", 0),
                "temperature_c": data.get("temperature_c"),
                "date": data.get("date", dt.date.today().isoformat()),
                "data_provenance": DataProvenance.live(
                    "Fishtalk 5 API",
                    confidence=0.95,
                ).to_dict(),
            }
        except Exception as e:
            log.warning("fishtalk.farm_data_error", site_id=site_id, error=str(e)[:100])
            return {
                "site_id": site_id,
                "error": f"Failed to fetch farm data: {str(e)[:100]}",
                "data_provenance": DataProvenance.degraded(
                    "Fishtalk 5 API",
                    reason=str(e)[:80],
                    confidence=0.0,
                ).to_dict(),
            }

    async def get_lice_counts(self, site_id: str) -> dict:
        """
        Fetch lice count data from Fishtalk's automated counting systems.

        Args:
            site_id: Fishtalk site identifier
        """
        if not _is_configured():
            return _not_configured_response(f"lice_counts/{site_id}")

        try:
            data = await self._request("GET", f"/api/v1/sites/{site_id}/lice")
            return {
                "site_id": site_id,
                "adult_female_avg": data.get("adult_female_avg", 0.0),
                "mobile_avg": data.get("mobile_avg", 0.0),
                "caligus_avg": data.get("caligus_avg", 0.0),
                "count_date": data.get("count_date", dt.date.today().isoformat()),
                "counting_method": data.get("counting_method", "automated"),
                "sample_size": data.get("sample_size", 0),
                "data_provenance": DataProvenance.live(
                    "Fishtalk 5 API",
                    confidence=0.92,
                ).to_dict(),
            }
        except Exception as e:
            log.warning("fishtalk.lice_error", site_id=site_id, error=str(e)[:100])
            return {
                "site_id": site_id,
                "error": f"Failed to fetch lice data: {str(e)[:100]}",
                "data_provenance": DataProvenance.degraded(
                    "Fishtalk 5 API",
                    reason=str(e)[:80],
                    confidence=0.0,
                ).to_dict(),
            }

    async def get_treatment_history(self, site_id: str) -> dict:
        """
        Fetch treatment records from Fishtalk for a farm site.

        Args:
            site_id: Fishtalk site identifier
        """
        if not _is_configured():
            return _not_configured_response(f"treatments/{site_id}")

        try:
            data = await self._request("GET", f"/api/v1/sites/{site_id}/treatments")
            treatments = data.get("treatments", [])
            return {
                "site_id": site_id,
                "treatments": [
                    {
                        "date": t.get("date", ""),
                        "method": t.get("method", ""),
                        "product": t.get("product", ""),
                        "duration_hours": t.get("duration_hours", 0),
                        "pre_lice_avg": t.get("pre_lice_avg", 0.0),
                        "post_lice_avg": t.get("post_lice_avg"),
                        "mortality_during": t.get("mortality_during", 0),
                    }
                    for t in treatments
                ],
                "total_treatments": len(treatments),
                "data_provenance": DataProvenance.live(
                    "Fishtalk 5 API",
                    confidence=0.93,
                ).to_dict(),
            }
        except Exception as e:
            log.warning("fishtalk.treatment_error", site_id=site_id, error=str(e)[:100])
            return {
                "site_id": site_id,
                "treatments": [],
                "total_treatments": 0,
                "error": f"Failed to fetch treatments: {str(e)[:100]}",
                "data_provenance": DataProvenance.degraded(
                    "Fishtalk 5 API",
                    reason=str(e)[:80],
                    confidence=0.0,
                ).to_dict(),
            }

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton
fishtalk_client = FishtalkClient()
