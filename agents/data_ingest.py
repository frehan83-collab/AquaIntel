"""
Data Ingestion Agent
====================
Polls BarentsWatch Fishhealth API every 15 minutes using V2 endpoints.

Real V2 response structure (per locality):
{
  "locality": {"no": 35297, "name": "...", "isOnLand": false},
  "geometry": {"type": "Point", "coordinates": [lon, lat]},
  "municipality": {"no": "1108", "name": "Sandnes"},
  "hasSalmonoidLicense": true,
  "liceReport": {
    "hasReported": true,
    "isFallow": false,
    "adultFemaleLice": {"average": 0.175, "trend": "Decreasing"},
    "mobileLice": {"average": 0.2, ...},
    "stationaryLice": {"average": 0.0375, ...},
    "seaTemperature": 4.3
  },
  "diseases": [...],
  "liceTreatments": [...]
}
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from agents.base import BaseAgent
from core.barentswatch import BarentsWatchClient
from core.models import Locality, LiceRecord, AuditLog
from core.async_db import get_async_session


class DataIngestAgent(BaseAgent):
    name = "data_ingest"
    interval_seconds = 900  # 15 minutes

    def __init__(self) -> None:
        super().__init__()
        self.bw = BarentsWatchClient()

    async def tick(self) -> None:
        self.log.info("ingest.tick_start")

        # 1. Refresh locality list
        try:
            localities_raw = await self.bw.get_localities()
            await self._upsert_localities(localities_raw)
        except Exception as exc:
            self.log.warning("ingest.localities_fail", error=str(exc))
            localities_raw = []

        # 2. Fetch per-locality lice data (V2 POST)
        now = dt.datetime.now(dt.UTC)
        year, week, _ = now.isocalendar()
        inserted = 0

        try:
            lice_data = await self.bw.get_locality_reports_v2(year, week)
            inserted = await self._upsert_lice_v2(lice_data, year, week)
        except Exception as exc:
            self.log.warning("ingest.current_week_fail", error=str(exc))
            # Try previous week
            prev_week = week - 1 if week > 1 else 52
            prev_year = year if week > 1 else year - 1
            try:
                lice_data = await self.bw.get_locality_reports_v2(prev_year, prev_week)
                inserted = await self._upsert_lice_v2(lice_data, prev_year, prev_week)
            except Exception as exc2:
                self.log.error("ingest.prev_week_fail", error=str(exc2))

        self.log.info(
            "ingest.tick_done",
            localities=len(localities_raw),
            lice_records=inserted,
        )
        await self._audit(
            f"Ingested {len(localities_raw)} localities, "
            f"{inserted} new lice records for {year}-W{week:02d}"
        )

    # ── DB helpers ────────────────────────────────────────────────────
    @staticmethod
    async def _upsert_localities(raw: list[dict]) -> None:
        """From GET /v1/geodata/fishhealth/localities.

        Items: {localityNo, name, municipalityNo, municipality}
        """
        async with get_async_session() as s:
            for loc in raw:
                loc_no = loc.get("localityNo") or loc.get("id") or loc.get("no")
                if not loc_no:
                    continue

                result = await s.execute(
                    select(Locality).where(Locality.locality_no == loc_no)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.name = loc.get("name", existing.name)
                    existing.municipality = loc.get(
                        "municipality", loc.get("municipalityNo", existing.municipality)
                    )
                    existing.updated_at = dt.datetime.now(dt.UTC)
                else:
                    s.add(Locality(
                        locality_no=loc_no,
                        name=loc.get("name", ""),
                        municipality=loc.get("municipality", loc.get("municipalityNo")),
                        updated_at=dt.datetime.now(dt.UTC),
                    ))

    @staticmethod
    async def _upsert_lice_v2(raw: list[dict], year: int, week: int) -> int:
        """Parse the nested V2 LocalityWeekReportV2 structure.

        Key paths:
          locality.no -> locality_no
          liceReport.adultFemaleLice.average -> avg_adult_female_lice
          liceReport.mobileLice.average -> avg_mobile_lice
          liceReport.stationaryLice.average -> avg_stationary_lice
          liceReport.seaTemperature -> sea_temp_c
          liceReport.hasReported -> skip if false
          geometry.coordinates -> [lon, lat]
          municipality.name -> municipality
        """
        count = 0
        async with get_async_session() as s:
            for rec in raw:
                # Extract locality number from nested object
                loc_obj = rec.get("locality", {})
                locality_no = loc_obj.get("no")
                if not locality_no:
                    continue

                # Skip if no lice report
                lice = rec.get("liceReport", {})
                if not lice.get("hasReported", False):
                    continue

                # Extract lice values from nested structure
                adult_lice = lice.get("adultFemaleLice", {})
                mobile_lice = lice.get("mobileLice", {})
                stationary_lice = lice.get("stationaryLice", {})

                avg_adult = adult_lice.get("average")
                avg_mobile = mobile_lice.get("average")
                avg_stationary = stationary_lice.get("average")
                sea_temp = lice.get("seaTemperature")
                has_cleaner = False  # not in V2 response directly

                # Upsert lice record
                result = await s.execute(
                    select(LiceRecord).where(
                        LiceRecord.locality_no == locality_no,
                        LiceRecord.year == year,
                        LiceRecord.week == week,
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.avg_adult_female_lice = avg_adult
                    existing.avg_mobile_lice = avg_mobile
                    existing.avg_stationary_lice = avg_stationary
                    existing.sea_temp_c = sea_temp
                    existing.fetched_at = dt.datetime.now(dt.UTC)
                else:
                    s.add(LiceRecord(
                        locality_no=locality_no,
                        year=year,
                        week=week,
                        avg_adult_female_lice=avg_adult,
                        avg_mobile_lice=avg_mobile,
                        avg_stationary_lice=avg_stationary,
                        has_cleaner_fish=has_cleaner,
                        sea_temp_c=sea_temp,
                        fetched_at=dt.datetime.now(dt.UTC),
                    ))
                    count += 1

                # Update locality with geo data if available
                geom = rec.get("geometry", {})
                coords = geom.get("coordinates", [])
                muni = rec.get("municipality", {})

                result = await s.execute(
                    select(Locality).where(Locality.locality_no == locality_no)
                )
                loc_row = result.scalar_one_or_none()

                if loc_row:
                    if coords and len(coords) >= 2:
                        loc_row.longitude = coords[0]
                        loc_row.latitude = coords[1]
                    if muni.get("name"):
                        loc_row.municipality = muni["name"]
                    loc_row.updated_at = dt.datetime.now(dt.UTC)
                elif coords and len(coords) >= 2:
                    s.add(Locality(
                        locality_no=locality_no,
                        name=loc_obj.get("name", ""),
                        municipality=muni.get("name"),
                        latitude=coords[1],
                        longitude=coords[0],
                        updated_at=dt.datetime.now(dt.UTC),
                    ))

        return count

    @staticmethod
    async def _audit(detail: str) -> None:
        async with get_async_session() as s:
            s.add(AuditLog(event_type="data_ingest", detail=detail))

    async def shutdown(self) -> None:
        await self.bw.close()
