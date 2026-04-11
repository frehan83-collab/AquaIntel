"""
BarentsWatch Fishhealth API client with OAuth2 client_credentials flow.

API spec: https://www.barentswatch.no/bwapi/openapi/fishhealth/openapi.json
Swagger:  https://www.barentswatch.no/bwapi/openapi/index.html?urls.primaryName=Fishhealth%20API
Register: https://www.barentswatch.no/minside/ -> "Mine klienter"

Base URL: https://www.barentswatch.no/bwapi

──────────────────────────────────────────────────────────────────────────
APRIL-MAY 2025 API CHANGES (BarentsWatch breaking changes):
  - Sustainability in Aquaculture API REMOVED on April 7, 2025.
    All /v1/geodata/sustainability/* endpoints are gone.
  - Treatment data model updated: medicinal treatments no longer carry
    start/end dates — only a treatment week.  New field: NumberOfCages.
    Combination treatments (multiple methods in same week) now tracked.
  - New disease endpoints added for diseases beyond PD/ISA (e.g. CMS,
    HSMI, AGD).  The v3 disease endpoint already covers these.
  - GET /v1/geodata/fishhealth/treatmenttypes added — canonical list of
    treatment method codes.
  - GET /v2/geodata/fishhealth/locality/{localityNo}/treatments/{year}
    returns the updated treatment model with NumberOfCages and
    combination treatment fields.
  - GET /v1/geodata/fishhealth/disease/{year} added for national
    disease summary by year.
──────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

log = structlog.get_logger(__name__)

BASE_URL = "https://www.barentswatch.no/bwapi"


class BarentsWatchClient:
    """Handles OAuth2 token lifecycle and all Fishhealth API calls."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires: dt.datetime = dt.datetime.min
        self._client = httpx.AsyncClient(timeout=30.0)

    # ── OAuth2 ────────────────────────────────────────────────────────
    async def _ensure_token(self) -> None:
        if self._token and dt.datetime.now(dt.UTC) < self._token_expires:
            return
        log.info("barentswatch.token_refresh")
        resp = await self._client.post(
            settings.barentswatch_token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.barentswatch_client_id,
                "client_secret": settings.barentswatch_client_secret,
                "scope": "api",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._token_expires = dt.datetime.now(dt.UTC) + dt.timedelta(
            seconds=body.get("expires_in", 3600) - 60
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    # ── HTTP helpers ──────────────────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def _get(self, path: str, params: dict | None = None) -> Any:
        await self._ensure_token()
        url = f"{BASE_URL}{path}"
        log.debug("barentswatch.get", url=url, params=params)
        resp = await self._client.get(url, headers=self._headers, params=params or {})
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def _post(self, path: str, json_body: dict | None = None) -> Any:
        await self._ensure_token()
        url = f"{BASE_URL}{path}"
        log.debug("barentswatch.post", url=url)
        resp = await self._client.post(
            url, headers=self._headers, json=json_body or {}
        )
        resp.raise_for_status()
        return resp.json()

    # ══════════════════════════════════════════════════════════════════
    # LOCALITY LISTING
    # ══════════════════════════════════════════════════════════════════
    async def get_localities(self, query: str | None = None) -> list[dict]:
        """
        GET /v1/geodata/fishhealth/localities
        Returns list of LocalityNameIdMunicipalityDto.
        Optional: ?query=<name or site ID>
        """
        params = {}
        if query:
            params["query"] = query
        return await self._get("/v1/geodata/fishhealth/localities", params)

    async def get_localities_with_salmonoids(self) -> list[dict]:
        """
        GET /v1/geodata/fishhealth/localitieswithsalmonoids
        Returns localities that currently have salmonoid licenses.
        """
        return await self._get("/v1/geodata/fishhealth/localitieswithsalmonoids")

    async def get_licensee_list(self) -> list[dict]:
        """
        GET /v1/geodata/fishhealth/licenseelist
        Returns all organizations holding aquaculture licenses.
        Useful for building company -> locality mapping.
        """
        return await self._get("/v1/geodata/fishhealth/licenseelist")

    async def get_species(self) -> list[dict]:
        """
        GET /v1/geodata/fishhealth/species
        List of all species in the system.
        """
        return await self._get("/v1/geodata/fishhealth/species")

    # ══════════════════════════════════════════════════════════════════
    # NATIONAL REPORT (lice data + filters) — V2 (current)
    # ══════════════════════════════════════════════════════════════════
    async def get_national_report_v2(
        self,
        year: int,
        week: int,
        filters: dict | None = None,
    ) -> dict:
        """
        POST /v2/geodata/fishhealth/{year}/{week}
        Returns NationalReportV2 with full lice data.

        filters (NationalReportQueryV2) can include:
          - organization: str (org number)
          - productionArea: int (1-13)
          - aboveLiceThreshold: bool (above 0.5 avg female lice)
          - belowLiceThreshold: bool
          - aboveMinimumLiceThreshold: bool (above 0.2)
          - hasSubstanceTreatments: bool
          - cleanerFish: bool
          - species: list[int]
          - etc.
        """
        return await self._post(
            f"/v2/geodata/fishhealth/{year}/{week}",
            json_body=filters,
        )

    # ══════════════════════════════════════════════════════════════════
    # LOCALITY-LEVEL REPORTS — V2 (current)
    # ══════════════════════════════════════════════════════════════════
    async def get_locality_reports_v2(
        self,
        year: int,
        week: int,
        filters: dict | None = None,
    ) -> list[dict]:
        """
        POST /v2/geodata/fishhealth/locality/{year}/{week}
        Returns array of LocalityWeekReportV2 — per-locality lice data.
        This is the PRIMARY endpoint for per-farm lice data.
        """
        return await self._post(
            f"/v2/geodata/fishhealth/locality/{year}/{week}",
            json_body=filters,
        )

    async def get_single_locality_report_v2(
        self,
        locality_no: int,
        year: int,
        week: int,
    ) -> dict:
        """
        GET /v2/geodata/fishhealth/locality/{localityNo}/{year}/{week}
        Returns LocalityReportV2 for a single locality.
        """
        return await self._get(
            f"/v2/geodata/fishhealth/locality/{locality_no}/{year}/{week}"
        )

    # ══════════════════════════════════════════════════════════════════
    # DISEASE DATA
    # ══════════════════════════════════════════════════════════════════
    async def get_locality_diseases_v3(
        self,
        locality_no: int,
        year: int | None = None,
    ) -> list[dict]:
        """
        GET /v3/geodata/fishhealth/locality/{localityNo}/disease/{year}
        GET /v3/geodata/fishhealth/locality/{localityNo}/disease
        Returns array of Disease objects (ILA, PD, etc.)
        """
        if year:
            return await self._get(
                f"/v3/geodata/fishhealth/locality/{locality_no}/disease/{year}"
            )
        return await self._get(
            f"/v3/geodata/fishhealth/locality/{locality_no}/disease"
        )

    async def get_disease_zone_history(
        self,
        locality_no: int,
        year: int | None = None,
        week: int | None = None,
    ) -> dict:
        """
        GET /v1/geodata/fishhealth/locality/diseasezonehistory/{localityNo}/{year}/{week}
        GET /v1/geodata/fishhealth/locality/diseasezonehistory/{localityNo}
        """
        if year and week:
            return await self._get(
                f"/v1/geodata/fishhealth/locality/diseasezonehistory"
                f"/{locality_no}/{year}/{week}"
            )
        return await self._get(
            f"/v1/geodata/fishhealth/locality/diseasezonehistory/{locality_no}"
        )

    # ══════════════════════════════════════════════════════════════════
    # LICE THRESHOLD / STATISTICS
    # ══════════════════════════════════════════════════════════════════
    async def get_localities_over_limit_by_week(
        self,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[dict]:
        """
        GET /v1/geodata/fishhealth/localitiesoverlimitbyweek
        How many localities exceed the 0.5 lice limit, per week.
        """
        params: dict[str, Any] = {}
        if start_year:
            params["startYear"] = start_year
        if end_year:
            params["endYear"] = end_year
        return await self._get(
            "/v1/geodata/fishhealth/localitiesoverlimitbyweek", params
        )

    async def get_localities_over_limit_by_year(
        self,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[dict]:
        """
        GET /v1/geodata/fishhealth/localitiesoverlimitbyyear
        Annual stats on localities exceeding lice threshold.
        """
        params: dict[str, Any] = {}
        if start_year:
            params["startYear"] = start_year
        if end_year:
            params["endYear"] = end_year
        return await self._get(
            "/v1/geodata/fishhealth/localitiesoverlimitbyyear", params
        )

    async def get_localities_over_limit_by_year_and_region(
        self,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[dict]:
        """
        GET /v1/geodata/fishhealth/localitiesoverlimitbyyearandregion
        Annual stats by production area (PA 1-13).
        """
        params: dict[str, Any] = {}
        if start_year:
            params["startYear"] = start_year
        if end_year:
            params["endYear"] = end_year
        return await self._get(
            "/v1/geodata/fishhealth/localitiesoverlimitbyyearandregion", params
        )

    # ══════════════════════════════════════════════════════════════════
    # EXPORT RESTRICTIONS
    # ══════════════════════════════════════════════════════════════════
    async def get_export_restrictions(self, year: int, week: int) -> list[dict]:
        """
        GET /v1/geodata/fishhealth/exportrestrictions/{year}/{week}
        Localities with export restrictions for a given week.
        """
        return await self._get(
            f"/v1/geodata/fishhealth/exportrestrictions/{year}/{week}"
        )

    async def get_locality_export_restriction(
        self, locality_no: int, year: int, week: int
    ) -> dict:
        """
        GET /v1/geodata/fishhealth/exportrestrictions/{localityNo}/{year}/{week}
        """
        return await self._get(
            f"/v1/geodata/fishhealth/exportrestrictions/{locality_no}/{year}/{week}"
        )

    # ══════════════════════════════════════════════════════════════════
    # ILA (ISA) PROTECTION ZONES
    # ══════════════════════════════════════════════════════════════════
    async def get_ila_protection_zones_v2(self, year: int, week: int) -> dict:
        """
        GET /v2/geodata/fishhealth/ilaprotectionzone/{year}/{week}
        Returns GeoJSON FeatureCollection of ILA/ISA protection zones.
        """
        return await self._get(
            f"/v2/geodata/fishhealth/ilaprotectionzone/{year}/{week}"
        )

    # ══════════════════════════════════════════════════════════════════
    # BULK DOWNLOAD
    # ══════════════════════════════════════════════════════════════════
    async def get_download_count(
        self,
        report_type: str,
        locality_no: int | None = None,
        from_year: int | None = None,
        from_week: int | None = None,
        to_year: int | None = None,
        to_week: int | None = None,
    ) -> int:
        """
        GET /v1/geodata/download/fishhealth/count
        report_type: 'disease', 'lice', or 'treatments'
        Returns count of records available for download.
        """
        params: dict[str, Any] = {"reporttype": report_type}
        if locality_no:
            params["localityno"] = locality_no
        if from_year:
            params["fromyear"] = from_year
        if from_week:
            params["fromweek"] = from_week
        if to_year:
            params["toyear"] = to_year
        if to_week:
            params["toweek"] = to_week
        return await self._get("/v1/geodata/download/fishhealth/count", params)

    async def get_download_preview(
        self,
        report_type: str,
        locality_no: int | None = None,
        from_year: int | None = None,
        from_week: int | None = None,
        to_year: int | None = None,
        to_week: int | None = None,
    ) -> list[dict]:
        """
        GET /v1/geodata/download/fishhealth/preview
        Returns first 10 rows of a download query. Useful for testing.
        """
        params: dict[str, Any] = {"reporttype": report_type}
        if locality_no:
            params["localityno"] = locality_no
        if from_year:
            params["fromyear"] = from_year
        if from_week:
            params["fromweek"] = from_week
        if to_year:
            params["toyear"] = to_year
        if to_week:
            params["toweek"] = to_week
        return await self._get("/v1/geodata/download/fishhealth/preview", params)

    # ══════════════════════════════════════════════════════════════════
    # TREATMENTS — V2 (updated April 2025)
    # ══════════════════════════════════════════════════════════════════
    async def get_locality_treatments_v2(
        self,
        locality_no: int,
        year: int,
    ) -> list[dict]:
        """
        GET /v2/geodata/fishhealth/locality/{localityNo}/treatments/{year}
        Returns treatment history for a locality in a given year.

        Updated April 2025: medicinal treatments no longer have start/end
        dates.  New fields: NumberOfCages, combination treatment data.
        """
        return await self._get(
            f"/v2/geodata/fishhealth/locality/{locality_no}/treatments/{year}"
        )

    async def get_treatment_types(self) -> list[dict]:
        """
        GET /v1/geodata/fishhealth/treatmenttypes
        Returns canonical list of treatment type codes used by BarentsWatch.
        Added in 2025 API update.
        """
        return await self._get("/v1/geodata/fishhealth/treatmenttypes")

    # ══════════════════════════════════════════════════════════════════
    # NATIONAL DISEASE SUMMARY (added 2025)
    # ══════════════════════════════════════════════════════════════════
    async def get_national_disease_summary(self, year: int) -> dict:
        """
        GET /v1/geodata/fishhealth/disease/{year}
        Returns national disease summary for a given year, covering all
        registered diseases (ISA/ILA, PD, CMS, HSMI, AGD, etc.).
        Added in 2025 API expansion.
        """
        return await self._get(f"/v1/geodata/fishhealth/disease/{year}")

    # ── Convenience helpers ───────────────────────────────────────────
    async def get_current_week_lice(
        self,
        organization: str | None = None,
        production_area: int | None = None,
    ) -> list[dict]:
        """
        Convenience: get per-locality lice data for the current ISO week.
        Uses the V2 POST endpoint with optional company/PA filter.
        """
        now = dt.datetime.now(dt.UTC)
        year, week, _ = now.isocalendar()

        filters: dict[str, Any] = {}
        if organization:
            filters["organization"] = organization
        if production_area:
            filters["productionArea"] = production_area

        return await self.get_locality_reports_v2(year, week, filters or None)

    async def get_historical_lice(
        self,
        year: int,
        week: int,
        organization: str | None = None,
    ) -> list[dict]:
        """Convenience: get per-locality lice data for a specific past week."""
        filters: dict[str, Any] = {}
        if organization:
            filters["organization"] = organization
        return await self.get_locality_reports_v2(year, week, filters or None)

    async def close(self) -> None:
        await self._client.aclose()


# ── Module-level singleton ────────────────────────────────────────────────────
bw_client = BarentsWatchClient()


async def get_barentswatch_token() -> str | None:
    """
    Convenience function used by ais_tracker and other modules that need a
    raw Bearer token for direct BarentsWatch API calls.
    Returns None if credentials are not configured.
    """
    try:
        if not settings.barentswatch_client_id or not settings.barentswatch_client_secret:
            return None
        await bw_client._ensure_token()
        return bw_client._token
    except Exception as exc:
        log.warning("barentswatch.token_failed", error=str(exc)[:120])
        return None
