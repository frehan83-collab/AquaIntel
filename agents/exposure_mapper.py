"""
Exposure Mapping Agent
======================
Maintains the dynamic company -> locality exposure map using real
BarentsWatch licensee data and organization numbers.

Uses the licensee list API to find all subsidiaries of MOWI, SALM, LSG,
then maps their localities via the org-filtered lice data endpoint.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select, delete

from agents.base import BaseAgent
from core.barentswatch import BarentsWatchClient
from core.models import Locality, CompanyExposure, AuditLog
from core.async_db import get_async_session

# ── Real organization numbers from BarentsWatch licensee list ────────
# Each company has multiple subsidiaries; we track all org numbers.
COMPANY_ORGS: dict[str, dict] = {
    "MOWI": {
        "ticker": "MOWI",
        "company_name": "Mowi ASA",
        "org_numbers": [
            964118191,  # MOWI ASA
            959352887,  # MOWI NORWAY AS
            921668236,  # MOWI SEAWATER NORWAY AS
        ],
        "keywords": ["mowi", "marine harvest"],
    },
    "SALM": {
        "ticker": "SALM",
        "company_name": "SalMar ASA",
        "org_numbers": [
            958973306,  # SALMAR AS / SALMAR PROCESSING AS
            966840528,  # SALMAR FARMING AS
            963867212,  # SALMAR NAMDAL AS
            951661198,  # SALMAR NORD AS
            990970602,  # SALMAR FINNMARK AS
            935182484,  # SALMAR DÅFJORD AS
            928957489,  # SALMAR OPPDRETT AS
            983442404,  # SALMAR ORGANIC AS
            953529246,  # SALMAR RAUMA AS
            913866673,  # SALMAR LAKSEFJORDEN AS
            923534717,  # SALMAR AKER OCEAN AS
        ],
        "keywords": ["salmar"],
    },
    "LSG": {
        "ticker": "LSG",
        "company_name": "Lerøy Seafood Group ASA",
        "org_numbers": [
            975350940,  # LERØY SEAFOOD GROUP ASA (parent)
            996646734,  # LERØY AUSTEVOLL AS
            985848718,  # LERØY MIDNOR AS / LERØY MIDT AS
            886813082,  # LERØY VEST AS
            985940460,  # LERØY AURORA AS
            913852087,  # LERØY FINNMARK AS
            917056595,  # LERØY FOSSEN AS
            930155179,  # LERØY AURORA 2 AS / LERØY AURORA SJØ AS
            930155209,  # LERØY MIDT 2 AS / LERØY MIDT SJØ AS
            930185698,  # LERØY VEST 2 AS / LERØY VEST SJØ AS
            996542068,  # LERØY AARSKOG AS
            918904913,  # LERØY SJØTROLL KJÆRELVA AS
            820740882,  # LERØY OCEAN HARVEST AS
        ],
        "keywords": ["lerøy", "leroy", "sjøtroll", "sjotroll"],
    },
    "GSF": {
        "ticker": "GSF",
        "company_name": "Grieg Seafood ASA",
        "org_numbers": [
            946598038,  # GRIEG SEAFOOD ASA (parent)
            935496578,  # GRIEG SEAFOOD FARMING AS
            980361306,  # GRIEG SEAFOOD FINNMARK AS
            930367435,  # GRIEG SEAFOOD NORWAY AS / FINNMARK SJØ AS
            838065392,  # GRIEG SEAFOOD ROGALAND AS
            930367931,  # GRIEG SEAFOOD ROGALAND SJØ AS
            940815533,  # GRIEG SEAFOOD STJERNELAKS A/S
        ],
        "keywords": ["grieg"],
    },
}


class ExposureMapperAgent(BaseAgent):
    name = "exposure_mapper"
    interval_seconds = 3600  # refresh every hour

    def __init__(self) -> None:
        super().__init__()
        self.bw = BarentsWatchClient()

    async def tick(self) -> None:
        self.log.info("exposure.tick_start")

        now = dt.datetime.now(dt.UTC)
        year, week, _ = now.isocalendar()
        # Use previous week if current isn't available yet
        query_week = max(1, week - 1)

        # Delete old mapping ONLY after new data is fully built.
        # _map_company checks for existing rows before inserting,
        # so we can safely delete stale entries AFTER all companies mapped.
        # This avoids the race condition where other agents see empty data.
        total_mapped = 0
        for ticker, cfg in COMPANY_ORGS.items():
            mapped = await self._map_company(ticker, cfg, year, query_week)
            total_mapped += mapped
            self.log.info(
                "exposure.company_mapped",
                ticker=ticker,
                localities=mapped,
            )

        # Clean up any stale entries from companies no longer in COMPANY_ORGS
        async with get_async_session() as s:
            known_tickers = list(COMPANY_ORGS.keys())
            await s.execute(
                delete(CompanyExposure).where(
                    CompanyExposure.ticker.notin_(known_tickers)
                )
            )

        async with get_async_session() as s:
            s.add(AuditLog(
                event_type="exposure_map_refresh",
                detail=f"Mapped {total_mapped} localities across "
                       f"{len(COMPANY_ORGS)} companies",
            ))

        self.log.info("exposure.tick_done", total_mapped=total_mapped)

    async def _map_company(
        self, ticker: str, cfg: dict, year: int, week: int
    ) -> int:
        """Query BarentsWatch for each org number and map localities."""
        mapped = 0

        for org_no in cfg["org_numbers"]:
            try:
                # Use the V2 POST endpoint with organization filter
                data = await self.bw.get_locality_reports_v2(
                    year, week, filters={"organization": str(org_no)}
                )

                async with get_async_session() as s:
                    for rec in data:
                        loc_data = rec.get("locality", {})
                        locality_no = loc_data.get("no")
                        if not locality_no:
                            continue

                        # Determine weight based on whether it's active
                        lice_report = rec.get("liceReport", {})
                        is_fallow = lice_report.get("isFallow", True)
                        has_reported = lice_report.get("hasReported", False)

                        # Active sites get higher weight
                        weight = 1.5 if has_reported and not is_fallow else 0.5

                        # Check if already mapped (avoid duplicates from
                        # overlapping org numbers)
                        result = await s.execute(
                            select(CompanyExposure).where(
                                CompanyExposure.ticker == ticker,
                                CompanyExposure.locality_no == locality_no,
                            )
                        )
                        existing = result.scalar_one_or_none()

                        if not existing:
                            s.add(CompanyExposure(
                                ticker=cfg["ticker"],
                                company_name=cfg["company_name"],
                                locality_no=locality_no,
                                weight=weight,
                            ))
                            mapped += 1

                        # Also ensure locality exists in localities table
                        result = await s.execute(
                            select(Locality).where(
                                Locality.locality_no == locality_no
                            )
                        )
                        loc_exists = result.scalar_one_or_none()

                        if not loc_exists:
                            geom = rec.get("geometry", {})
                            coords = geom.get("coordinates", [None, None])
                            muni = rec.get("municipality", {})

                            s.add(Locality(
                                locality_no=locality_no,
                                name=loc_data.get("name", ""),
                                municipality=muni.get("name"),
                                latitude=coords[1] if len(coords) > 1 else None,
                                longitude=coords[0] if coords else None,
                                owner_company=cfg["company_name"],
                                updated_at=dt.datetime.now(dt.UTC),
                            ))
                        elif not loc_exists.owner_company:
                            loc_exists.owner_company = cfg["company_name"]

            except Exception as exc:
                self.log.warning(
                    "exposure.org_fetch_fail",
                    ticker=ticker,
                    org_no=org_no,
                    error=str(exc),
                )

        return mapped

    @staticmethod
    async def get_company_localities(ticker: str) -> list[int]:
        """Return list of locality_no values for a given ticker."""
        async with get_async_session() as s:
            result = await s.execute(
                select(CompanyExposure.locality_no).where(
                    CompanyExposure.ticker == ticker
                )
            )
            rows = result.scalars().all()
        return list(rows)

    @staticmethod
    async def get_exposure_summary() -> dict[str, dict]:
        """Return {ticker: {locality_count, total_weight, localities: [...]}}."""
        async with get_async_session() as s:
            result = await s.execute(select(CompanyExposure))
            all_exp = result.scalars().all()

        summary: dict[str, dict] = {}
        for exp in all_exp:
            if exp.ticker not in summary:
                summary[exp.ticker] = {
                    "company_name": exp.company_name,
                    "locality_count": 0,
                    "total_weight": 0.0,
                    "localities": [],
                }
            summary[exp.ticker]["locality_count"] += 1
            summary[exp.ticker]["total_weight"] += exp.weight
            summary[exp.ticker]["localities"].append(exp.locality_no)

        return summary

    async def shutdown(self) -> None:
        await self.bw.close()
