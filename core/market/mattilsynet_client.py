"""
Mattilsynet Aquaculture API Client
====================================
Real-time disease outbreak data from the Norwegian Food Safety Authority.

APIs used:
  1. Disease Cases: ISA, PD (SAV2/SAV3), IHN — per locality with full timeline
  2. Lice Reports: Weekly counts + treatment details + resistance data

Base URL: https://akvakultur-offentlig-api.fisk.mattilsynet.io
Auth: Client-Id header (no registration needed)
License: NLOD 2.0 (free open data)

This data is UNIQUE — not available from BarentsWatch:
  - Treatment type details (medicinal/non-medicinal/combination)
  - Resistance suspicions and sensitivity test results
  - Disease diagnosis timeline (suspicion → confirmed → resolved)
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import httpx
import structlog

log = structlog.get_logger(__name__)

BASE_URL = "https://akvakultur-offentlig-api.fisk.mattilsynet.io"
CLIENT_ID = "FishIntel"
HEADERS = {"Client-Id": CLIENT_ID}


@dataclass
class DiseaseCase:
    """A single disease outbreak from Mattilsynet."""
    id: str
    locality_no: int
    locality_name: str
    disease_type: str          # PANKREASSYKDOM, ILA, etc.
    disease_subtype: str       # PD_SAV2, PD_SAV3, ILA_HPR0, etc.
    species: str               # SAL (salmon), RBT (trout)
    suspicion_date: str | None = None
    diagnosis_date: str | None = None
    resolution_date: str | None = None
    resolution_reason: str | None = None
    status: str = "active"     # active / resolved / invalidated
    created: str = ""
    updated: str = ""


@dataclass
class LiceTreatment:
    """Treatment details from a lice report."""
    locality_no: int
    locality_name: str
    company: str
    week: int
    year: int
    sea_temp: float
    adult_female_lice: float
    mobile_lice: float
    sessile_lice: float
    non_medicinal_treatments: list[str] = field(default_factory=list)
    medicinal_treatments: list[str] = field(default_factory=list)
    combination_treatments: list[str] = field(default_factory=list)
    resistance_suspicions: list[str] = field(default_factory=list)
    sensitivity_tests: list[dict] = field(default_factory=list)


def newest_first_cases(cases: list[DiseaseCase], limit: int = 20) -> list[DiseaseCase]:
    """Cases sorted newest diagnosis first, capped at ``limit``.

    Upstream order is arbitrary, so slicing it hid the most recent outbreaks:
    ``/api/disease/norway`` showed a newest date of 2026-06-09 while the geo
    view had diagnoses up to 2026-09-22. An undated case sorts last.
    """
    def _date(c: DiseaseCase) -> str:
        return c.diagnosis_date or c.suspicion_date or ""

    return sorted(cases, key=_date, reverse=True)[:limit]


class MattilsynetClient:
    """
    Client for Mattilsynet's aquaculture public APIs.
    Provides disease outbreak tracking and treatment intelligence.
    """

    _disease_cache: list[DiseaseCase] | None = None
    _disease_cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=1)
    _lice_company_cache: dict[int, str] = {}  # locality_no → company name from lice reports
    last_fetch_ok: bool = False  # did the last disease fetch get a 200 from upstream?

    async def fetch_disease_cases(self, limit: int = 100) -> list[DiseaseCase]:
        """Fetch active disease cases from Mattilsynet.

        ``last_fetch_ok`` records whether the upstream answered, so a caller
        can tell an empty answer from a failed one (the empty list alone
        conflates them).
        """
        now = dt.datetime.now(dt.UTC)
        if self._disease_cache and self._disease_cache_time and (now - self._disease_cache_time) < self._cache_ttl:
            return self._disease_cache
        self.last_fetch_ok = False

        cases: list[DiseaseCase] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{BASE_URL}/api/sykdomstilfeller/v1/rapporteringer",
                    headers=HEADERS,
                    params={"limit": limit},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for r in data:
                        # Determine status
                        status = "active"
                        if r.get("avslutningsdato"):
                            status = "resolved"
                        if r.get("ugyldiggjøringsdato"):
                            status = "invalidated"

                        species = ""
                        if r.get("arter"):
                            species = r["arter"][0].get("artskode", "") if r["arter"] else ""

                        cases.append(DiseaseCase(
                            id=r.get("id", ""),
                            locality_no=r.get("lokalitetsnummer", 0),
                            locality_name=r.get("lokalitetsnavn", ""),
                            disease_type=r.get("sykdomstype", ""),
                            disease_subtype=r.get("sykdomssubtype", ""),
                            species=species,
                            suspicion_date=r.get("kvalitetssikretMistankedato"),
                            diagnosis_date=r.get("diagnosedato"),
                            resolution_date=r.get("avslutningsdato"),
                            resolution_reason=r.get("avslutningsårsak"),
                            status=status,
                            created=r.get("opprettet", ""),
                            updated=r.get("oppdatert", ""),
                        ))

                    self.last_fetch_ok = True
                    self._disease_cache = cases
                    self._disease_cache_time = now
                    log.info("mattilsynet.diseases_fetched",
                             total=len(cases),
                             active=sum(1 for c in cases if c.status == "active"))
                else:
                    log.warning("mattilsynet.disease_error", status=resp.status_code)

        except Exception as exc:
            log.warning("mattilsynet.disease_fetch_failed", error=str(exc)[:120])

        return cases

    async def fetch_lice_treatments(self, year: int = 2026, limit: int = 50) -> list[LiceTreatment]:
        """Fetch lice reports with treatment details."""
        treatments: list[LiceTreatment] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{BASE_URL}/api/lakselus/v2/rapporteringer",
                    headers=HEADERS,
                    params={"aar": year, "limit": limit},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for r in data:
                        lice = r.get("lusetelling", {})
                        treatments.append(LiceTreatment(
                            locality_no=r.get("lokalitetsnummer", 0),
                            locality_name=r.get("lokalitetsnavn", ""),
                            company=r.get("organisasjonsnavn", ""),
                            week=r.get("uke", 0),
                            year=r.get("år", year),
                            sea_temp=r.get("sjøtemperatur", 0),
                            adult_female_lice=lice.get("voksneHunnlus", 0),
                            mobile_lice=lice.get("bevegeligeLus", 0),
                            sessile_lice=lice.get("fastsittendeLus", 0),
                            non_medicinal_treatments=[
                                t.get("type", "") for t in (r.get("ikkeMedikamentelleBehandlinger") or []) if isinstance(t, dict)
                            ],
                            medicinal_treatments=[
                                t.get("type", "") for t in (r.get("medikamentelleBehandlinger") or []) if isinstance(t, dict)
                            ],
                            combination_treatments=[
                                t.get("type", "") for t in (r.get("kombinasjonsbehandlinger") or []) if isinstance(t, dict)
                            ],
                            resistance_suspicions=[
                                t.get("type", "") for t in (r.get("resistensmistanker") or []) if isinstance(t, dict)
                            ],
                            sensitivity_tests=r.get("følsomhetsundersøkelser") or [],
                        ))

                    # Cache company names for disease lookup
                    for t in treatments:
                        if t.company and t.locality_no:
                            self._lice_company_cache[t.locality_no] = t.company

                    log.info("mattilsynet.lice_treatments_fetched",
                             total=len(treatments),
                             with_treatments=sum(1 for t in treatments
                                                 if t.non_medicinal_treatments or t.medicinal_treatments))
                else:
                    log.warning("mattilsynet.lice_error", status=resp.status_code)

        except Exception as exc:
            log.warning("mattilsynet.lice_fetch_failed", error=str(exc)[:120])

        return treatments

    async def get_disease_summary(self, cases: list[DiseaseCase]) -> dict:
        """Summarize disease cases for API response, with company names from DB."""
        active = [c for c in cases if c.status == "active"]
        resolved = [c for c in cases if c.status == "resolved"]

        # Look up company names from our Locality table
        company_map: dict[int, str] = {}
        try:
            from sqlalchemy import select
            from core.models import Locality
            from core.async_db import get_async_session
            locality_nos = [c.locality_no for c in active]
            if locality_nos:
                async with get_async_session() as s:
                    rows = (await s.execute(
                        select(Locality.locality_no, Locality.owner_company)
                        .where(Locality.locality_no.in_(locality_nos))
                    )).all()
                    for r in rows:
                        if r[1]:
                            company_map[r[0]] = r[1]
        except Exception:
            pass

        # Use cached lice treatment data for missing companies
        if self._lice_company_cache:
            for loc_no in [c.locality_no for c in active]:
                if loc_no not in company_map and loc_no in self._lice_company_cache:
                    company_map[loc_no] = self._lice_company_cache[loc_no]

        # For any still-missing localities, try a synchronous lookup from Mattilsynet lice API
        missing = [c.locality_no for c in active if c.locality_no not in company_map]
        if missing:
            try:
                import httpx
                with httpx.Client(timeout=10) as client:
                    for loc_no in missing[:15]:
                        try:
                            resp = client.get(
                                f"{BASE_URL}/api/lakselus/v2/rapporteringer",
                                headers=HEADERS,
                                params={"limit": 1, "lokalitetsnummer": loc_no},
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                if data and isinstance(data, list) and data[0].get("organisasjonsnavn"):
                                    company_map[loc_no] = data[0]["organisasjonsnavn"]
                                    self._lice_company_cache[loc_no] = data[0]["organisasjonsnavn"]
                        except Exception:
                            continue
            except Exception:
                pass

        # Count by disease type
        by_type: dict[str, int] = {}
        for c in active:
            key = c.disease_type
            by_type[key] = by_type.get(key, 0) + 1

        # Translate disease names
        DISEASE_NAMES = {
            "PANKREASSYKDOM": "Pancreas Disease (PD)",
            "ILA": "Infectious Salmon Anaemia (ISA)",
            "INFEKSIØS_LAKSEANEMI": "Infectious Salmon Anaemia (ISA)",
            "IHN": "Infectious Haematopoietic Necrosis",
            "VHS": "Viral Haemorrhagic Septicaemia",
            "FRANCISELLOSE": "Francisellosis",
            "BAKTERIELL_NYRESYKE": "Bacterial Kidney Disease (BKD)",
        }

        active_newest = newest_first_cases(active)

        return {
            "source": "Mattilsynet (Norwegian Food Safety Authority)",
            "api": "akvakultur-offentlig-api.fisk.mattilsynet.io",
            "license": "NLOD 2.0",
            "total_cases": len(cases),
            "active_cases": len(active),
            "resolved_cases": len(resolved),
            "by_disease": {
                DISEASE_NAMES.get(k, k): v for k, v in sorted(by_type.items(), key=lambda x: -x[1])
            },
            "active_outbreaks_shown": len(active_newest),
            "active_outbreaks_total": len(active),
            "active_outbreaks": [
                {
                    "id": c.id,
                    "locality_no": c.locality_no,
                    "locality_name": c.locality_name,
                    "company": company_map.get(c.locality_no, ""),
                    "disease": DISEASE_NAMES.get(c.disease_type, c.disease_type),
                    "subtype": c.disease_subtype,
                    "species": "Salmon" if c.species == "SAL" else "Trout" if c.species == "RBT" else c.species,
                    "suspicion_date": c.suspicion_date,
                    "diagnosis_date": c.diagnosis_date,
                    "status": c.status,
                    "days_active": (dt.datetime.now(dt.UTC) - dt.datetime.fromisoformat(c.suspicion_date.replace("Z", "+00:00"))).days if c.suspicion_date else 0,
                }
                for c in active_newest[:20]
            ],
        }


    async def get_company_disease_counts(self, cases: list[DiseaseCase]) -> dict[str, dict]:
        """
        Get disease counts per company. Used by Leaders, ESG, Benchmark.
        Returns: {company_name: {total: N, isa: N, pd: N, other: N, localities: [...]}}
        """
        active = [c for c in cases if c.status == "active"]

        # Build company map (reuse same logic)
        company_map: dict[int, str] = {}
        try:
            from sqlalchemy import select
            from core.models import Locality
            from core.async_db import get_async_session
            locality_nos = [c.locality_no for c in active]
            if locality_nos:
                async with get_async_session() as s:
                    rows = (await s.execute(
                        select(Locality.locality_no, Locality.owner_company)
                        .where(Locality.locality_no.in_(locality_nos))
                    )).all()
                    for r in rows:
                        if r[1]:
                            company_map[r[0]] = r[1]
        except Exception:
            pass

        # Add from lice cache
        for loc_no in [c.locality_no for c in active]:
            if loc_no not in company_map and loc_no in self._lice_company_cache:
                company_map[loc_no] = self._lice_company_cache[loc_no]

        # Aggregate by company
        result: dict[str, dict] = {}
        for c in active:
            company = company_map.get(c.locality_no, "")
            if not company:
                continue
            if company not in result:
                result[company] = {"total": 0, "isa": 0, "pd": 0, "other": 0, "localities": []}
            result[company]["total"] += 1
            if "ILA" in c.disease_type or "LAKSEANEMI" in c.disease_type:
                result[company]["isa"] += 1
            elif "PANKREAS" in c.disease_type:
                result[company]["pd"] += 1
            else:
                result[company]["other"] += 1
            result[company]["localities"].append(c.locality_name)

        return result


# Singleton
mattilsynet_client = MattilsynetClient()
