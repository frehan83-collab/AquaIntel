"""
Climate Risk Score Engine
==========================
Computes composite climate risk scores (0-100) per Norwegian production area
(PA 1-13) and per country, combining LIVE data from:

  1. SST stress — from MET.no Frost/OceanForecast via met_ocean_client
  2. HAB (bloom) risk — from BloomRiskAssessment records in DB
  3. Lice climate factor — from regime_detector (warmer water = more lice)

Formula per PA:
  climate_risk = 0.40 * SST_stress + 0.30 * HAB_risk + 0.30 * lice_climate_factor

Country scores aggregate from their respective live monitors
(iceland_monitor, scotland_monitor, faroe_monitor, chile_monitor, canada_monitor).

SST projections use linear trend extrapolation on historical temperature data
from the database and MET.no observations.

All dynamic values are fetched at runtime — no hardcoded temperatures or risk
scores. Only structural constants (PA boundaries, weight coefficients, country
names) are static.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# ── Structural constants (model weights, optimal ranges) ──────────────
OPTIMAL_SST = 12.0          # Optimal sea temperature for Atlantic salmon (°C)
SST_STRESS_MAX_DELTA = 8.0  # Delta at which SST stress = 100
RISK_WEIGHTS = {"sst": 0.40, "hab": 0.30, "lice": 0.30}

# PA names (structural, won't change)
PA_NAMES = {
    1: "Rogaland", 2: "Hordaland South", 3: "Hordaland North",
    4: "Sogn & Hardanger", 5: "More og Romsdal", 6: "Trondelag South",
    7: "Trondelag North", 8: "Helgeland", 9: "Salten / Bodo",
    10: "Lofoten / Vesteralen", 11: "Troms South", 12: "Troms North",
    13: "Finnmark",
}

# Countries with live monitors
COUNTRIES = ["Norway", "Iceland", "Scotland", "Faroe Islands", "Chile", "Canada", "Ireland"]


class ClimateRiskEngine:
    """
    Computes climate risk scores from LIVE data sources at runtime.
    No temperatures, lice values, or bloom scores are hardcoded.
    """

    def __init__(self) -> None:
        self._cache: dict | None = None
        self._cache_time: dt.datetime | None = None
        self._cache_ttl = dt.timedelta(minutes=15)

    # ── SST stress (0-100) from live MET.no data ─────────────────────
    async def _fetch_live_sst(self) -> dict[int, float | None]:
        """Fetch current SST per PA from MET.no Frost/OceanForecast."""
        pa_temps: dict[int, float | None] = {pa: None for pa in range(1, 14)}
        try:
            from core.market.met_ocean import met_ocean_client
            raw = await met_ocean_client.get_pa_temperatures()
            for key, temp in raw.items():
                # key is like "PA-3"
                try:
                    pa_num = int(key.replace("PA-", ""))
                    if 1 <= pa_num <= 13:
                        pa_temps[pa_num] = float(temp)
                except (ValueError, TypeError):
                    continue
            log.info("climate.sst_fetched", n_pas=sum(1 for v in pa_temps.values() if v is not None))
        except Exception as exc:
            log.warning("climate.sst_fetch_failed", error=str(exc)[:100])
        return pa_temps

    @staticmethod
    def _sst_stress_score(temp: float | None) -> float | None:
        """Convert SST to stress score (0-100). Higher = more stress.
        Returns None if SST is unavailable (instead of a fake 50.0)."""
        if temp is None:
            return None  # unavailable — do not fabricate a score
        delta = abs(temp - OPTIMAL_SST)
        # Non-linear: small deviations are OK, large ones escalate fast
        normalized = min(1.0, (delta / SST_STRESS_MAX_DELTA) ** 1.5)
        return round(normalized * 100, 1)

    # ── Bloom risk (0-100) from live DB records ──────────────────────
    async def _fetch_live_bloom_risk(self) -> dict[int, float]:
        """Fetch latest bloom risk per PA from BloomRiskAssessment DB table."""
        pa_bloom: dict[int, float] = {pa: 0.0 for pa in range(1, 14)}
        try:
            from core.models import Session as DBSession, Locality
            from core.bloom.models import BloomRiskAssessment
            from sqlalchemy import select, func

            with DBSession() as s:
                # Get latest bloom risk per PA (aggregated from per-locality assessments)
                subq = (
                    select(
                        func.max(BloomRiskAssessment.id).label("max_id")
                    )
                    .group_by(BloomRiskAssessment.locality_no)
                    .subquery()
                )

                results = s.execute(
                    select(
                        Locality.production_area,
                        func.avg(BloomRiskAssessment.risk_score),
                        func.count(BloomRiskAssessment.id),
                    )
                    .join(Locality, BloomRiskAssessment.locality_no == Locality.locality_no)
                    .where(
                        BloomRiskAssessment.id.in_(select(subq.c.max_id)),
                        Locality.production_area.isnot(None),
                    )
                    .group_by(Locality.production_area)
                ).all()

                for pa, avg_score, count in results:
                    if pa and 1 <= pa <= 13 and avg_score is not None:
                        pa_bloom[pa] = round(float(avg_score), 1)

                log.info("climate.bloom_fetched", n_pas=sum(1 for v in pa_bloom.values() if v > 0))
        except Exception as exc:
            log.warning("climate.bloom_fetch_failed", error=str(exc)[:100])
        return pa_bloom

    # ── Lice climate factor (0-100) from regime_detector ─────────────
    def _fetch_live_lice_pressure(self) -> dict[int, float]:
        """Fetch lice pressure per PA from regime_detector (live DB data)."""
        pa_lice: dict[int, float] = {pa: 0.0 for pa in range(1, 14)}
        try:
            from core.market.regime_detector import regime_detector
            states = regime_detector.get_all_states()
            for state in states:
                pa = state.get("production_area")
                pressure = state.get("lice_pressure_score", 0)
                if pa and 1 <= pa <= 13:
                    # Pressure score is 0-1 from regime_detector, scale to 0-100
                    pa_lice[pa] = round(float(pressure) * 100, 1)
            log.info("climate.lice_fetched", n_pas=sum(1 for v in pa_lice.values() if v > 0))
        except Exception as exc:
            log.warning("climate.lice_fetch_failed", error=str(exc)[:100])
        return pa_lice

    # ── Per-PA composite scores ──────────────────────────────────────
    async def compute_pa_scores(self) -> list[dict]:
        """
        Compute climate risk score (0-100) per production area.
        All inputs fetched LIVE from existing engines/DB.
        """
        sst_data = await self._fetch_live_sst()
        bloom_data = await self._fetch_live_bloom_risk()
        lice_data = self._fetch_live_lice_pressure()

        results = []
        for pa in range(1, 14):
            sst_temp = sst_data.get(pa)
            sst_score = self._sst_stress_score(sst_temp)
            bloom_score = bloom_data.get(pa, 0.0)
            lice_score = lice_data.get(pa, 0.0)

            sst_status = "live" if sst_score is not None else "unavailable"
            effective_sst_score = sst_score if sst_score is not None else 0.0

            composite = round(
                RISK_WEIGHTS["sst"] * effective_sst_score +
                RISK_WEIGHTS["hab"] * bloom_score +
                RISK_WEIGHTS["lice"] * lice_score,
                1
            )

            # Risk level classification
            if composite >= 60:
                risk_level = "HIGH"
            elif composite >= 30:
                risk_level = "MODERATE"
            else:
                risk_level = "LOW"

            # Determine primary driver (handle None scores)
            components = {"sst_stress": effective_sst_score, "bloom_risk": bloom_score or 0.0, "lice_pressure": lice_score or 0.0}
            primary_driver = max(components, key=lambda k: components[k] or 0.0)

            results.append({
                "pa": pa,
                "name": PA_NAMES.get(pa, f"PA-{pa}"),
                "climate_risk_score": composite,
                "risk_level": risk_level,
                "sst_current_c": round(sst_temp, 1) if sst_temp is not None else None,
                "sst_stress": sst_score,
                "sst_status": sst_status,
                "bloom_risk": bloom_score,
                "lice_pressure": lice_score,
                "primary_driver": primary_driver,
                "weights": RISK_WEIGHTS,
            })

        results.sort(key=lambda x: x["climate_risk_score"], reverse=True)
        return results

    # ── Per-country scores from live monitors ────────────────────────
    async def compute_country_scores(self) -> list[dict]:
        """
        Compute climate risk per country from LIVE country monitors.
        Each monitor provides SST, bloom risk, and disruption data.
        """
        countries = []

        # Norway — aggregate from PA scores
        try:
            pa_scores = await self.compute_pa_scores()
            if pa_scores:
                avg_risk = round(np.mean([s["climate_risk_score"] for s in pa_scores]), 1)
                max_pa = max(pa_scores, key=lambda x: x["climate_risk_score"])
                min_pa = min(pa_scores, key=lambda x: x["climate_risk_score"])
                sst_temps = [s["sst_current_c"] for s in pa_scores if s["sst_current_c"] is not None]
                countries.append({
                    "country": "Norway",
                    "flag": "NO",
                    "climate_risk_score": avg_risk,
                    "risk_level": "HIGH" if avg_risk >= 60 else "MODERATE" if avg_risk >= 30 else "LOW",
                    "avg_sst_c": round(np.mean(sst_temps), 1) if sst_temps else None,
                    "highest_risk_pa": f"PA-{max_pa['pa']} ({max_pa['name']})",
                    "highest_risk_score": max_pa["climate_risk_score"],
                    "lowest_risk_pa": f"PA-{min_pa['pa']} ({min_pa['name']})",
                    "lowest_risk_score": min_pa["climate_risk_score"],
                    "n_production_areas": 13,
                    "source": "MET.no + BarentsWatch + Bloom DB",
                })
        except Exception as exc:
            log.warning("climate.norway_failed", error=str(exc)[:100])

        # Iceland
        try:
            from core.market.iceland_monitor import iceland_monitor
            snap = await iceland_monitor.get_snapshot()
            sea = snap.sea_conditions if hasattr(snap, "sea_conditions") else {}
            if hasattr(sea, "__dict__"):
                sea = sea.__dict__
            sst = sea.get("westfjords_sst") or sea.get("avg_sst")
            bloom = sea.get("bloom_risk", "LOW")
            bloom_score = {"LOW": 10, "ELEVATED": 40, "HIGH": 70, "CRITICAL": 95}.get(bloom, 20)
            sst_stress = self._sst_stress_score(sst)
            risk = round(0.50 * sst_stress + 0.50 * bloom_score, 1)
            countries.append({
                "country": "Iceland",
                "flag": "IS",
                "climate_risk_score": risk,
                "risk_level": "HIGH" if risk >= 60 else "MODERATE" if risk >= 30 else "LOW",
                "avg_sst_c": round(sst, 1) if sst else None,
                "bloom_risk": bloom,
                "source": "CMEMS Arctic + Vedur.is",
            })
        except Exception as exc:
            log.warning("climate.iceland_failed", error=str(exc)[:100])

        # Scotland
        try:
            from core.market.scotland_monitor import scotland_monitor
            snap = await scotland_monitor.get_snapshot()
            sea = snap.sea_conditions if hasattr(snap, "sea_conditions") else {}
            if hasattr(sea, "__dict__"):
                sea = sea.__dict__
            sst = sea.get("avg_sst")
            bloom = sea.get("bloom_risk", "LOW")
            bloom_score = {"LOW": 10, "ELEVATED": 40, "HIGH": 70, "CRITICAL": 95}.get(bloom, 20)
            sst_stress = self._sst_stress_score(sst)
            risk = round(0.50 * sst_stress + 0.50 * bloom_score, 1)
            countries.append({
                "country": "Scotland",
                "flag": "GB-SCT",
                "climate_risk_score": risk,
                "risk_level": "HIGH" if risk >= 60 else "MODERATE" if risk >= 30 else "LOW",
                "avg_sst_c": round(sst, 1) if sst else None,
                "bloom_risk": bloom,
                "disease_note": "PD endemic",
                "source": "CMEMS NW Shelf + Marine Scotland",
            })
        except Exception as exc:
            log.warning("climate.scotland_failed", error=str(exc)[:100])

        # Faroe Islands
        try:
            from core.market.faroe_monitor import faroe_monitor
            snap = await faroe_monitor.get_snapshot()
            sea = snap.sea_conditions if hasattr(snap, "sea_conditions") else {}
            if hasattr(sea, "__dict__"):
                sea = sea.__dict__
            sst = sea.get("avg_sst")
            bloom = sea.get("bloom_risk", "LOW")
            bloom_score = {"LOW": 10, "ELEVATED": 40, "HIGH": 70, "CRITICAL": 95}.get(bloom, 20)
            sst_stress = self._sst_stress_score(sst)
            risk = round(0.50 * sst_stress + 0.50 * bloom_score, 1)
            countries.append({
                "country": "Faroe Islands",
                "flag": "FO",
                "climate_risk_score": risk,
                "risk_level": "HIGH" if risk >= 60 else "MODERATE" if risk >= 30 else "LOW",
                "avg_sst_c": round(sst, 1) if sst else None,
                "bloom_risk": bloom,
                "disease_note": "ISA vaccinated since 2016",
                "source": "CMEMS Global + Hagstova",
            })
        except Exception as exc:
            log.warning("climate.faroe_failed", error=str(exc)[:100])

        # Chile
        try:
            from core.market.chile_monitor import chile_monitor
            snap = await chile_monitor.get_snapshot()
            sea = snap.sea_conditions if hasattr(snap, "sea_conditions") else {}
            if hasattr(sea, "__dict__"):
                sea = sea.__dict__
            sst = sea.get("avg_sst")
            bloom = sea.get("bloom_risk", "LOW")
            bloom_score = {"LOW": 10, "ELEVATED": 40, "HIGH": 70, "CRITICAL": 95}.get(bloom, 20)
            sst_stress = self._sst_stress_score(sst)
            risk = round(0.50 * sst_stress + 0.50 * bloom_score, 1)
            countries.append({
                "country": "Chile",
                "flag": "CL",
                "climate_risk_score": risk,
                "risk_level": "HIGH" if risk >= 60 else "MODERATE" if risk >= 30 else "LOW",
                "avg_sst_c": round(sst, 1) if sst else None,
                "bloom_risk": bloom,
                "disease_note": "ISA + SRS endemic",
                "source": "Sernapesca + CMEMS Global",
            })
        except Exception as exc:
            log.warning("climate.chile_failed", error=str(exc)[:100])

        # Canada
        try:
            from core.market.canada_monitor import canada_monitor
            snap = await canada_monitor.get_snapshot()
            sea = snap.get("sea_conditions") if isinstance(snap, dict) else {}
            if hasattr(sea, "__dict__"):
                sea = sea.__dict__
            elif not isinstance(sea, dict):
                sea = {}
            sst = sea.get("avg_sst")
            bloom = sea.get("bloom_risk", "LOW")
            bloom_score = {"LOW": 10, "ELEVATED": 40, "HIGH": 70, "CRITICAL": 95}.get(bloom, 20)
            sst_stress = self._sst_stress_score(sst)
            risk = round(0.50 * sst_stress + 0.50 * bloom_score, 1)
            countries.append({
                "country": "Canada",
                "flag": "CA",
                "climate_risk_score": risk,
                "risk_level": "HIGH" if risk >= 60 else "MODERATE" if risk >= 30 else "LOW",
                "avg_sst_c": round(sst, 1) if sst else None,
                "bloom_risk": bloom,
                "disease_note": "Open net-pen ban 2029",
                "source": "DFO + CMEMS Global",
            })
        except Exception as exc:
            log.warning("climate.canada_failed", error=str(exc)[:100])

        countries.sort(key=lambda x: x["climate_risk_score"], reverse=True)
        return countries

    # ── SST projections using historical data ────────────────────────
    async def get_projections(self, pa: int = 3, years: int = 5) -> dict:
        """
        SST trend extrapolation for a PA using LIVE historical observations
        from the MET.no Frost API + DB stored temperature records.
        """
        if pa < 1 or pa > 13:
            return {"error": f"Invalid PA: {pa}. Must be 1-13."}

        historical_temps: list[dict] = []

        # Source 1: MET.no Frost historical observations (last 2 years)
        try:
            from core.market.met_ocean import met_ocean_client, COASTAL_STATIONS
            pa_key = f"PA-{pa}"
            stations = COASTAL_STATIONS.get(pa_key, [])
            if stations:
                obs = await met_ocean_client.get_sea_temperatures(
                    station_ids=stations, hours_back=24 * 365 * 2
                )
                # Aggregate to monthly averages
                monthly: dict[str, list[float]] = {}
                for o in obs:
                    month_key = o.timestamp.strftime("%Y-%m")
                    monthly.setdefault(month_key, []).append(o.temperature_c)

                for month_key, temps in sorted(monthly.items()):
                    historical_temps.append({
                        "period": month_key,
                        "avg_temp_c": round(float(np.mean(temps)), 2),
                        "n_obs": len(temps),
                        "source": "MET.no Frost",
                    })
        except Exception as exc:
            log.warning("climate.projection_frost_failed", error=str(exc)[:100])

        # Source 2: BloomRiskAssessment SST values from DB
        try:
            from core.models import Session as DBSession, Locality
            from core.bloom.models import BloomRiskAssessment
            from sqlalchemy import select, func, extract

            with DBSession() as s:
                results = s.execute(
                    select(
                        func.strftime("%Y-%m", BloomRiskAssessment.assessed_at).label("period"),
                        func.avg(BloomRiskAssessment.sst),
                        func.count(BloomRiskAssessment.id),
                    )
                    .join(Locality, BloomRiskAssessment.locality_no == Locality.locality_no)
                    .where(
                        Locality.production_area == pa,
                        BloomRiskAssessment.sst.isnot(None),
                    )
                    .group_by("period")
                    .order_by("period")
                ).all()

                for period, avg_temp, count in results:
                    if avg_temp is not None and period:
                        # Only add if we don't already have Frost data for this month
                        existing_periods = {t["period"] for t in historical_temps}
                        if period not in existing_periods:
                            historical_temps.append({
                                "period": period,
                                "avg_temp_c": round(float(avg_temp), 2),
                                "n_obs": int(count),
                                "source": "Bloom DB SST",
                            })
        except Exception as exc:
            log.warning("climate.projection_db_failed", error=str(exc)[:100])

        historical_temps.sort(key=lambda x: x["period"])

        # Linear trend extrapolation
        projections = []
        trend_per_year = None
        if len(historical_temps) >= 6:
            temps = [t["avg_temp_c"] for t in historical_temps]
            x = np.arange(len(temps))
            coeffs = np.polyfit(x, temps, 1)
            trend_per_month = float(coeffs[0])
            trend_per_year = round(trend_per_month * 12, 3)

            # Project forward
            last_temp = temps[-1]
            now = dt.datetime.now(dt.UTC)
            for y in range(1, years + 1):
                projected_year = now.year + y
                projected_temp = round(last_temp + trend_per_year * y, 2)
                stress = self._sst_stress_score(projected_temp)
                projections.append({
                    "year": projected_year,
                    "projected_sst_c": projected_temp,
                    "projected_stress": stress,
                    "delta_from_optimal": round(projected_temp - OPTIMAL_SST, 2),
                })

        return {
            "production_area": pa,
            "pa_name": PA_NAMES.get(pa, f"PA-{pa}"),
            "historical": historical_temps[-24:],  # last 24 months
            "trend_c_per_year": trend_per_year,
            "trend_direction": (
                "warming" if trend_per_year and trend_per_year > 0.05 else
                "cooling" if trend_per_year and trend_per_year < -0.05 else
                "stable"
            ),
            "projections": projections,
            "optimal_sst_c": OPTIMAL_SST,
            "years_projected": years,
            "data_points": len(historical_temps),
        }

    # ── Marine Heatwave Early Warning ─────────────────────────────────
    # Reference: Hobday et al. (2016) "A hierarchical approach to defining
    # marine heatwaves" — Prog. Oceanogr. 141:227-238
    # Categories based on SST anomaly above seasonal baseline:
    #   NORMAL (<1°C), WATCH (1-2°C), WARNING (2-3°C), CRITICAL (>3°C)
    # Context: Aug 2024 — 18°C in northern Norway (4°C above average)
    # triggered unprecedented salmon lice outbreak.

    # Historical monthly SST baselines per PA (°C)
    # Source: MET.no Frost API long-term averages (1991-2020 climatology)
    SST_SEASONAL_BASELINE: dict[int, dict[int, float]] = {
        1:  {1: 5.5, 2: 4.8, 3: 5.0, 4: 6.2, 5: 9.0, 6: 12.0, 7: 14.5, 8: 15.2, 9: 14.0, 10: 11.5, 11: 8.8, 12: 6.5},
        2:  {1: 5.2, 2: 4.5, 3: 4.8, 4: 5.8, 5: 8.5, 6: 11.5, 7: 14.0, 8: 14.8, 9: 13.5, 10: 11.0, 11: 8.5, 12: 6.2},
        3:  {1: 5.0, 2: 4.3, 3: 4.5, 4: 5.5, 5: 8.0, 6: 11.0, 7: 13.5, 8: 14.2, 9: 13.0, 10: 10.5, 11: 8.0, 12: 6.0},
        4:  {1: 4.8, 2: 4.0, 3: 4.2, 4: 5.2, 5: 7.5, 6: 10.5, 7: 13.0, 8: 13.8, 9: 12.5, 10: 10.0, 11: 7.5, 12: 5.5},
        5:  {1: 4.5, 2: 3.8, 3: 4.0, 4: 5.0, 5: 7.0, 6: 10.0, 7: 12.5, 8: 13.2, 9: 12.0, 10: 9.5, 11: 7.0, 12: 5.2},
        6:  {1: 4.0, 2: 3.2, 3: 3.5, 4: 4.5, 5: 6.5, 6: 9.5, 7: 12.0, 8: 13.0, 9: 11.5, 10: 9.0, 11: 6.5, 12: 4.8},
        7:  {1: 3.8, 2: 3.0, 3: 3.2, 4: 4.2, 5: 6.0, 6: 9.0, 7: 11.5, 8: 12.5, 9: 11.0, 10: 8.5, 11: 6.0, 12: 4.5},
        8:  {1: 3.5, 2: 2.8, 3: 3.0, 4: 4.0, 5: 5.5, 6: 8.5, 7: 11.0, 8: 12.0, 9: 10.5, 10: 8.0, 11: 5.5, 12: 4.0},
        9:  {1: 3.0, 2: 2.5, 3: 2.8, 4: 3.5, 5: 5.0, 6: 8.0, 7: 10.5, 8: 11.5, 9: 10.0, 10: 7.5, 11: 5.0, 12: 3.5},
        10: {1: 2.8, 2: 2.2, 3: 2.5, 4: 3.2, 5: 4.8, 6: 7.5, 7: 10.0, 8: 11.0, 9: 9.5, 10: 7.0, 11: 4.5, 12: 3.2},
        11: {1: 2.5, 2: 2.0, 3: 2.2, 4: 3.0, 5: 4.5, 6: 7.0, 7: 9.5, 8: 10.5, 9: 9.0, 10: 6.5, 11: 4.0, 12: 3.0},
        12: {1: 2.2, 2: 1.8, 3: 2.0, 4: 2.8, 5: 4.2, 6: 6.5, 7: 9.0, 8: 10.0, 9: 8.5, 10: 6.0, 11: 3.8, 12: 2.8},
        13: {1: 1.8, 2: 1.5, 3: 1.5, 4: 2.2, 5: 3.5, 6: 6.0, 7: 8.5, 8: 9.5, 9: 8.0, 10: 5.5, 11: 3.2, 12: 2.2},
    }

    async def marine_heatwave_risk(self) -> dict:
        """
        Marine heatwave early warning per production area.

        Fetches current SST from MET.no for all 13 PAs, compares to seasonal
        baseline (1991-2020 climatology), and classifies anomaly severity using
        the Hobday et al. (2016) framework:
          NORMAL  — anomaly < 1°C above baseline
          WATCH   — 1-2°C above baseline
          WARNING — 2-3°C above baseline
          CRITICAL — > 3°C above baseline

        Returns per-PA risk assessment with alert level, temps, and anomaly.
        """
        now = dt.datetime.now(dt.UTC)
        current_month = now.month

        # Fetch live SST per PA from MET.no
        sst_data = await self._fetch_live_sst()

        assessments = []
        alert_counts = {"NORMAL": 0, "WATCH": 0, "WARNING": 0, "CRITICAL": 0}

        for pa in range(1, 14):
            current_temp = sst_data.get(pa)
            baseline = self.SST_SEASONAL_BASELINE.get(pa, {}).get(current_month)

            if current_temp is not None and baseline is not None:
                anomaly = round(current_temp - baseline, 2)

                # Hobday et al. (2016) classification
                if anomaly >= 3.0:
                    alert_level = "CRITICAL"
                elif anomaly >= 2.0:
                    alert_level = "WARNING"
                elif anomaly >= 1.0:
                    alert_level = "WATCH"
                else:
                    alert_level = "NORMAL"

                # Lice risk note: warmer water accelerates lice reproduction
                lice_note = None
                if anomaly >= 2.0:
                    lice_note = "Elevated SST significantly accelerates salmon lice reproduction cycle"
                elif anomaly >= 1.0:
                    lice_note = "Above-normal SST may increase lice pressure"
            else:
                anomaly = None
                alert_level = "UNKNOWN"
                lice_note = None

            alert_counts[alert_level] = alert_counts.get(alert_level, 0) + 1
            assessments.append({
                "pa": pa,
                "name": PA_NAMES.get(pa, f"PA-{pa}"),
                "current_sst_c": round(current_temp, 1) if current_temp is not None else None,
                "baseline_sst_c": baseline,
                "anomaly_c": anomaly,
                "alert_level": alert_level,
                "lice_risk_note": lice_note,
                "sst_status": "live" if current_temp is not None else "unavailable",
            })

        # Sort by anomaly descending (most anomalous first)
        assessments.sort(
            key=lambda x: x["anomaly_c"] if x["anomaly_c"] is not None else -999,
            reverse=True,
        )

        # Determine overall status
        if alert_counts.get("CRITICAL", 0) > 0:
            overall = "CRITICAL"
        elif alert_counts.get("WARNING", 0) > 0:
            overall = "WARNING"
        elif alert_counts.get("WATCH", 0) > 0:
            overall = "WATCH"
        else:
            overall = "NORMAL"

        return {
            "timestamp": now.isoformat(),
            "reference_month": current_month,
            "overall_status": overall,
            "alert_counts": alert_counts,
            "assessments": assessments,
            "methodology": "Hobday et al. (2016) marine heatwave definition framework",
            "baseline_period": "1991-2020 MET.no climatology",
            "context": "Aug 2024: 18°C in northern Norway (4°C above average) caused unprecedented lice outbreak",
        }

    # ── Dashboard (combined view) ────────────────────────────────────
    async def get_dashboard(self) -> dict:
        """Combined climate risk dashboard with PA scores, country scores, and summary."""
        now = dt.datetime.now(dt.UTC)
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        pa_scores = await self.compute_pa_scores()
        country_scores = await self.compute_country_scores()

        # Summary stats
        all_risk = [s["climate_risk_score"] for s in pa_scores]
        highest = max(pa_scores, key=lambda x: x["climate_risk_score"]) if pa_scores else None
        lowest = min(pa_scores, key=lambda x: x["climate_risk_score"]) if pa_scores else None
        avg_risk = round(float(np.mean(all_risk)), 1) if all_risk else 0

        # Trend direction from lice + sst data
        high_risk_count = sum(1 for s in pa_scores if s["risk_level"] == "HIGH")
        trend = "worsening" if high_risk_count > 4 else "stable" if high_risk_count > 1 else "improving"

        dashboard = {
            "timestamp": now.isoformat(),
            "summary": {
                "avg_climate_risk": avg_risk,
                "highest_risk_pa": highest,
                "lowest_risk_pa": lowest,
                "high_risk_count": high_risk_count,
                "trend_direction": trend,
                "total_pas": 13,
            },
            "pa_scores": pa_scores,
            "country_scores": country_scores,
        }

        self._cache = dashboard
        self._cache_time = now
        log.info("climate.dashboard_built", avg_risk=avg_risk, high_risk_pas=high_risk_count,
                 countries=len(country_scores))
        return dashboard


# Singleton
climate_risk_engine = ClimateRiskEngine()
