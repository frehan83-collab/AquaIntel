"""
Treatment Resistance Tracker
==============================
Tracks treatment frequency per method per production area from Mattilsynet
treatment data and estimates resistance risk.

Resistance classification:
  HIGH — >10 treatments of same method in PA in trailing 12 months
  MODERATE — 5-10 treatments of same method in PA in trailing 12 months
  LOW — <5 treatments of same method in PA in trailing 12 months

Freshwater resistance flag:
  Emerging per Norwegian Veterinary Institute (2025) annual report.
  Previously considered resistance-free; recent evidence of reduced
  efficacy in PA 3-7 where freshwater treatments are heavily used.

References:
  - Azamethiphos resistance mapping 2014-2022 (ScienceDirect, Jan 2026)
  - Norwegian Veterinary Institute (2025) annual lice treatment report
  - Overton et al. (2019) "Salmon lice treatments and mortality"
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

import structlog

from core.market.data_provenance import DataProvenance

log = structlog.get_logger(__name__)

# Treatment method categories for normalization
# Mattilsynet reports use Norwegian names; we map to standard keys
METHOD_MAP = {
    # Non-medicinal
    "HYDROLICER": "mechanical",
    "OPTILICER": "mechanical",
    "FLATSETSUND": "mechanical",
    "FLUSH": "mechanical",
    "TERMISK": "thermal",
    "THERMOLICER": "thermal",
    "FERSKVANN": "freshwater",
    "FRESHWATER": "freshwater",
    # Medicinal
    "AZAMETIFOS": "azamethiphos",
    "AZAMETHIPHOS": "azamethiphos",
    "HYDROGENPEROKSID": "h2o2",
    "H2O2": "h2o2",
    "EMAMEKTIN": "emamectin",
    "EMAMECTIN": "emamectin",
    # Biological
    "RENSEFISK": "cleaner_fish",
    "LUMPFISH": "cleaner_fish",
    "WRASSE": "cleaner_fish",
}

# Methods with known resistance issues
RESISTANCE_PROFILE = {
    "azamethiphos": {
        "risk": "high",
        "note": "Widespread resistance documented PA 3-7 since 2014 (ScienceDirect Jan 2026)",
    },
    "h2o2": {
        "risk": "high",
        "note": "Efficacy declined from 85% to 40-70% due to widespread resistance",
    },
    "emamectin": {
        "risk": "emerging",
        "note": "Sensitivity declining in some areas; monitor local test results",
    },
    "freshwater": {
        "risk": "emerging",
        "note": "Freshwater resistance emerging per Norwegian Veterinary Institute (2025)",
    },
    "mechanical": {
        "risk": "none",
        "note": "No biological resistance mechanism; physical removal",
    },
    "thermal": {
        "risk": "none",
        "note": "No biological resistance mechanism; thermal exposure",
    },
    "cleaner_fish": {
        "risk": "none",
        "note": "Biological predation; no resistance mechanism",
    },
}

# PAs where freshwater resistance is emerging (Norwegian Vet Institute 2025)
FRESHWATER_RESISTANCE_PAS = {3, 4, 5, 6, 7}


class ResistanceTracker:
    """
    Tracks treatment frequency and estimates resistance risk per PA per method.
    Uses Mattilsynet treatment data (lice reports with treatment details).

    Singleton pattern with 1-hour cache.
    """

    _cache: dict | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=1)

    async def _fetch_treatment_data(self) -> list:
        """Fetch treatment reports from Mattilsynet for current + previous year."""
        treatments = []
        try:
            from core.market.mattilsynet_client import mattilsynet_client
            now = dt.datetime.now(dt.UTC)
            current_year = now.year

            # Fetch current year + previous year for 12-month trailing window
            for year in [current_year, current_year - 1]:
                try:
                    batch = await mattilsynet_client.fetch_lice_treatments(
                        year=year, limit=500
                    )
                    treatments.extend(batch)
                except Exception as exc:
                    log.warning("resistance.fetch_year_failed", year=year, error=str(exc)[:80])

            log.info("resistance.data_fetched", total=len(treatments))
        except Exception as exc:
            log.warning("resistance.fetch_failed", error=str(exc)[:100])

        return treatments

    def _normalize_method(self, raw_method: str) -> str:
        """Normalize treatment method name to standard key."""
        upper = raw_method.upper().strip()
        return METHOD_MAP.get(upper, raw_method.lower().replace(" ", "_"))

    async def _extract_pa(self, locality_no: int) -> int | None:
        """Look up production area for a locality number."""
        try:
            from sqlalchemy import select
            from core.models import Locality
            from core.async_db import get_async_session
            async with get_async_session() as s:
                row = (await s.execute(
                    select(Locality.production_area)
                    .where(Locality.locality_no == locality_no)
                )).scalar()
                return int(row) if row else None
        except Exception:
            return None

    async def build_resistance_matrix(self) -> dict:
        """
        Build PA x method resistance matrix.

        Returns dict with:
          - matrix: {pa: {method: {count, risk_level, resistance_profile}}}
          - summary: overall resistance landscape
          - freshwater_flag: emerging resistance warning
        """
        now = dt.datetime.now(dt.UTC)
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        treatments = await self._fetch_treatment_data()

        # Build PA lookup cache
        pa_cache: dict[int, int | None] = {}

        # Count treatments per PA per method (trailing 12 months)
        cutoff = now - dt.timedelta(days=365)
        pa_method_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        pa_resistance_reports: dict[int, list[str]] = defaultdict(list)

        for t in treatments:
            # Check if within 12-month window
            # Use week/year to approximate date
            try:
                treat_date = dt.datetime.fromisocalendar(t.year, max(1, t.week), 1).replace(tzinfo=dt.UTC)
            except (ValueError, AttributeError):
                continue

            if treat_date < cutoff:
                continue

            # Look up PA for this locality
            loc_no = t.locality_no
            if loc_no not in pa_cache:
                pa_cache[loc_no] = await self._extract_pa(loc_no)
            pa = pa_cache[loc_no]
            if not pa or pa < 1 or pa > 13:
                continue

            # Count non-medicinal treatments
            for method_raw in (t.non_medicinal_treatments or []):
                method = self._normalize_method(method_raw)
                if method:
                    pa_method_counts[pa][method] += 1

            # Count medicinal treatments
            for method_raw in (t.medicinal_treatments or []):
                method = self._normalize_method(method_raw)
                if method:
                    pa_method_counts[pa][method] += 1

            # Count combination treatments
            for method_raw in (t.combination_treatments or []):
                method = self._normalize_method(method_raw)
                if method:
                    pa_method_counts[pa][method] += 1

            # Track resistance suspicions
            for susp in (t.resistance_suspicions or []):
                if susp:
                    pa_resistance_reports[pa].append(susp)

        # Build the matrix
        all_methods = set()
        for methods in pa_method_counts.values():
            all_methods.update(methods.keys())

        matrix: dict[int, dict] = {}
        high_risk_count = 0

        for pa in range(1, 14):
            pa_entry: dict[str, dict] = {}
            counts = pa_method_counts.get(pa, {})

            for method in sorted(all_methods):
                count = counts.get(method, 0)

                # Classify resistance risk by treatment frequency
                if count > 10:
                    frequency_risk = "HIGH"
                    high_risk_count += 1
                elif count >= 5:
                    frequency_risk = "MODERATE"
                else:
                    frequency_risk = "LOW"

                # Get inherent resistance profile for this method
                profile = RESISTANCE_PROFILE.get(method, {"risk": "unknown", "note": ""})

                # Freshwater resistance flag
                freshwater_flag = (
                    method == "freshwater" and pa in FRESHWATER_RESISTANCE_PAS
                )

                pa_entry[method] = {
                    "treatment_count_12m": count,
                    "frequency_risk": frequency_risk,
                    "inherent_resistance_risk": profile["risk"],
                    "resistance_note": profile["note"],
                    "freshwater_resistance_emerging": freshwater_flag,
                }

            # Add resistance suspicion reports
            suspicions = pa_resistance_reports.get(pa, [])

            matrix[pa] = {
                "pa": pa,
                "name": self._pa_name(pa),
                "methods": pa_entry,
                "total_treatments_12m": sum(counts.values()),
                "resistance_suspicions": len(suspicions),
                "resistance_types": list(set(suspicions))[:5],
            }

        # Summary
        total_treatments = sum(
            sum(counts.values()) for counts in pa_method_counts.values()
        )
        total_suspicions = sum(len(v) for v in pa_resistance_reports.values())

        result = {
            "timestamp": now.isoformat(),
            "matrix": matrix,
            "all_methods": sorted(all_methods),
            "summary": {
                "total_treatments_12m": total_treatments,
                "total_resistance_suspicions": total_suspicions,
                "high_risk_pa_method_combos": high_risk_count,
                "pas_with_suspicions": len(pa_resistance_reports),
            },
            "freshwater_resistance": {
                "status": "emerging",
                "affected_pas": sorted(FRESHWATER_RESISTANCE_PAS),
                "source": "Norwegian Veterinary Institute (2025)",
                "note": "Previously considered resistance-free; reduced efficacy observed in PA 3-7",
            },
            "references": [
                "Hobday et al. (2016) marine heatwave framework",
                "Azamethiphos resistance study (ScienceDirect, Jan 2026)",
                "Norwegian Veterinary Institute (2025) annual lice treatment report",
                "Overton et al. (2019) salmon lice treatments and mortality",
            ],
        }

        self._cache = result
        self._cache_time = now
        log.info(
            "resistance.matrix_built",
            total_treatments=total_treatments,
            high_risk=high_risk_count,
            suspicions=total_suspicions,
        )
        return result

    async def get_pa_resistance(self, pa: int) -> dict:
        """Get resistance profile for a single production area."""
        full = await self.build_resistance_matrix()
        pa_data = full.get("matrix", {}).get(pa)
        if not pa_data:
            return {"error": f"PA {pa} not found. Must be 1-13."}

        return {
            "timestamp": full["timestamp"],
            **pa_data,
            "freshwater_resistance": full["freshwater_resistance"],
            "data_provenance": DataProvenance.live(
                "Mattilsynet treatment reports + Norwegian Veterinary Institute",
                confidence=0.80,
            ).to_dict(),
        }

    @staticmethod
    def _pa_name(pa: int) -> str:
        """Get PA name (avoid circular import)."""
        names = {
            1: "Rogaland", 2: "Hordaland South", 3: "Hordaland North",
            4: "Sogn & Hardanger", 5: "More og Romsdal", 6: "Trondelag South",
            7: "Trondelag North", 8: "Helgeland", 9: "Salten / Bodo",
            10: "Lofoten / Vesteralen", 11: "Troms South", 12: "Troms North",
            13: "Finnmark",
        }
        return names.get(pa, f"PA-{pa}")


# Singleton
resistance_tracker = ResistanceTracker()
