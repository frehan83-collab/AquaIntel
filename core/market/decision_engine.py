"""
Farmer Decision Engine
=======================
Orchestrates lice data, GNN predictions, sea temperature, and treatment
economics into a single actionable DecisionCard per locality.

The engine is the bridge between raw analytics (lice_gnn, treatment_optimizer)
and the farmer-facing "Daily Check" page — delivering a one-look answer:
  "TREAT NOW, method X, 81% success, ROI 3.2x."

Singleton: decision_engine = DecisionEngine()
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Optional

import structlog
from sqlalchemy import select, func, desc

from core.models import LiceRecord, Locality, CompanyExposure
from core.async_db import get_async_session
from core.market.data_provenance import DataProvenance

log = structlog.get_logger()

# ── Treatment profiles — imported from single source of truth ────────────
# Literature-cited values: Overton et al. (2019), Mowi Handbook 2024
# See core/market/treatment_constants.py for full citations
from core.market.treatment_constants import (
    TREATMENT_PROFILES as _SHARED_PROFILES,
    REGULATORY_LIMIT, TREATMENT_TRIGGER, DAILY_MORTALITY_RATE,
    FISH_PER_CAGE, GROWTH_REDUCTION_PER_LICE, MORTALITY_PER_LICE_WEEK,
)

# Convert shared TreatmentProfile dataclasses to the dict format this engine expects
TREATMENT_PROFILES = {
    key: {
        "label": p.label,
        "base_success": p.efficacy_pct / 100.0,
        "cost_per_fish_nok": p.cost_per_fish_nok,
        "mortality_risk_pct": p.mortality_risk_pct,
        "temp_range": p.suitable_temp_range,
        "resistance_risk": p.resistance_risk,
    }
    for key, p in _SHARED_PROFILES.items()
    # Map to the 5 keys this engine uses (collapse medicinal variants)
    if key in ("mechanical", "thermal", "freshwater", "biological", "medicinal_h2o2")
}
# Alias: this engine uses "medicinal" key
if "medicinal_h2o2" in TREATMENT_PROFILES:
    TREATMENT_PROFILES["medicinal"] = TREATMENT_PROFILES.pop("medicinal_h2o2")

# Economics (structural constants)
AVG_FISH_PER_LOCALITY = 200_000
SALMON_VALUE_NOK_PER_KG = 95.0  # approximate market value
AVG_FISH_WEIGHT_KG = 4.5
GROWTH_REDUCTION_PCT_PER_LICE = 0.03  # 3% growth penalty per adult female lice
MORTALITY_PCT_PER_LICE_WEEK = 0.005  # 0.5% weekly mortality per lice above threshold

# BUG FIX (Session 22): Removed local re-declarations that shadowed the
# imports from treatment_constants.py (line 33). REGULATORY_LIMIT and
# TREATMENT_TRIGGER are now ONLY defined in treatment_constants.py.


class DecisionEngine:
    """Orchestrates multiple data sources into a farm-level decision card."""

    # ── Core decision logic ──────────────────────────────────────────

    async def get_decision(self, locality_no: int) -> dict:
        """Generate a DecisionCard for a single locality."""
        try:
            lice_data = await self._get_lice_data(locality_no)
            if not lice_data:
                return {"error": f"No lice data for locality {locality_no}"}

            current_lice = lice_data["current"]
            trend = lice_data["trend"]
            sea_temp = lice_data["sea_temp_c"]
            history = lice_data["history"]

            # Try GNN prediction (graceful fallback)
            gnn_prediction = await self._get_gnn_prediction(locality_no)

            # Try ocean forecast for better temperature data
            ocean_forecast = await self._get_ocean_forecast(locality_no)
            if ocean_forecast and ocean_forecast.get("current_c"):
                sea_temp = ocean_forecast["current_c"]  # Override stale DB temp

            # Fetch learned profiles from Efficacy Marketplace
            learned_profiles = await self._get_learned_profiles()

            # Resolve PA for this locality (for learned profile lookup)
            locality_pa = None
            try:
                async with get_async_session() as s:
                    locality_pa = (await s.execute(
                        select(Locality.production_area)
                        .where(Locality.locality_no == locality_no)
                    )).scalar()
            except Exception:
                pass

            # Compute action
            action, urgency, reasoning = self._compute_action(
                current_lice, trend, sea_temp, gnn_prediction
            )

            # Compute feature importance explanation (SHAP-style)
            explanation = self._compute_feature_importance(
                current_lice, trend, sea_temp, gnn_prediction, action
            )

            # Recommend treatment method (with learned data when available)
            method, success_prob, efficacy_source = self._recommend_method(
                sea_temp, action,
                learned_profiles=learned_profiles,
                pa=locality_pa,
            )

            # Compute ROI
            cost_treat, cost_inaction, roi = self._compute_roi(
                current_lice, method, action
            )

            # Build provenance — lice data from BarentsWatch, GNN + ocean optional
            _sources = ["BarentsWatch lice data"]
            _confidence = 0.90
            if gnn_prediction is not None:
                _sources.append("GNN lice spread model")
                _confidence = 0.85  # ML adds uncertainty
            else:
                _sources.append("rule-based fallback (GNN unavailable)")
                _confidence = 0.70
            if ocean_forecast:
                _sources.append("MET.no OceanForecast")
                _confidence = min(_confidence + 0.05, 0.95)  # Better temp = more trust
            prov = DataProvenance.live(
                " + ".join(_sources),
                confidence=_confidence,
            )

            return {
                "locality_no": locality_no,
                "action": action,
                "urgency": urgency,
                "recommended_method": method,
                "success_probability": round(success_prob, 2),
                "efficacy_source": efficacy_source,
                "roi_estimate": round(roi, 1),
                "reasoning": reasoning,
                "explanation": explanation,
                "lice_current": round(current_lice, 3),
                "lice_trend": trend,
                "lice_predicted_next_week": (
                    round(gnn_prediction, 3) if gnn_prediction is not None else None
                ),
                "sea_temp_c": round(sea_temp, 1) if sea_temp else None,
                "cost_of_treatment_nok": round(cost_treat),
                "cost_of_inaction_nok": round(cost_inaction),
                "lice_history": history,
                "ocean_forecast": ocean_forecast,
                "generated_at": dt.datetime.now(dt.UTC).isoformat(),
                "data_provenance": prov.to_dict(),
            }
        except Exception as e:
            log.error("decision_engine.error", locality_no=locality_no, error=str(e))
            return {"error": str(e), "locality_no": locality_no}

    async def portfolio_decisions(self, company_name: str) -> dict:
        """Get decision cards for all farms in a company portfolio."""
        try:
            async with get_async_session() as s:
                rows = (await s.execute(
                    select(CompanyExposure.locality_no)
                    .where(CompanyExposure.company_name.ilike(f"%{company_name}%"))
                )).fetchall()

            if not rows:
                # Fallback: search Locality.owner_company
                async with get_async_session() as s:
                    rows = (await s.execute(
                        select(Locality.locality_no)
                        .where(Locality.owner_company.ilike(f"%{company_name}%"))
                        .limit(50)
                    )).fetchall()

            locality_nos = [r[0] for r in rows]
            if not locality_nos:
                return {"company": company_name, "decisions": [], "summary": "No farms found"}

            decisions = []
            for loc in locality_nos[:30]:  # cap at 30 farms
                card = await self.get_decision(loc)
                if "error" not in card:
                    decisions.append(card)

            # Summary
            action_counts = {}
            for d in decisions:
                a = d.get("action", "UNKNOWN")
                action_counts[a] = action_counts.get(a, 0) + 1

            most_urgent = None
            for d in sorted(decisions, key=lambda x: self._urgency_rank(x.get("urgency", "")), reverse=True):
                most_urgent = d
                break

            return {
                "company": company_name,
                "farm_count": len(decisions),
                "decisions": decisions,
                "action_summary": action_counts,
                "most_urgent": most_urgent,
                "total_treatment_cost_nok": sum(d.get("cost_of_treatment_nok", 0) for d in decisions if d.get("action") in ("TREAT_NOW", "SCHEDULE_TREATMENT")),
                "generated_at": dt.datetime.now(dt.UTC).isoformat(),
                "data_provenance": DataProvenance.live(
                    "BarentsWatch + GNN + Treatment Economics",
                    confidence=0.80,
                ).to_dict(),
            }
        except Exception as e:
            log.error("portfolio_decisions.error", company=company_name, error=str(e))
            return {"company": company_name, "error": str(e)}

    async def log_outcome(self, data: dict) -> dict:
        """Log a treatment outcome for efficacy tracking."""
        try:
            from sqlalchemy import text
            async with get_async_session() as s:
                await s.execute(
                    text("""
                        INSERT INTO treatment_outcomes
                        (locality_no, treatment_date, method, pre_lice_count,
                         post_lice_count, mortality_observed, cost_nok, notes, reported_at)
                        VALUES (:loc, :td, :m, :pre, :post, :mort, :cost, :notes, :now)
                    """),
                    {
                        "loc": data["locality_no"],
                        "td": data.get("treatment_date", dt.datetime.now(dt.UTC).isoformat()),
                        "m": data.get("method", "unknown"),
                        "pre": data.get("pre_lice_count"),
                        "post": data.get("post_lice_count"),
                        "mort": data.get("mortality_observed", 0),
                        "cost": data.get("cost_nok"),
                        "notes": data.get("notes", ""),
                        "now": dt.datetime.now(dt.UTC),
                    },
                )
                # commit handled by get_async_session context manager
            return {"status": "logged", "locality_no": data["locality_no"]}
        except Exception as e:
            log.error("log_outcome.error", error=str(e))
            return {"error": str(e)}

    async def efficacy_by_method(self) -> dict:
        """Aggregate treatment efficacy from real outcomes."""
        try:
            from sqlalchemy import text
            async with get_async_session() as s:
                rows = (await s.execute(text("""
                    SELECT method,
                           COUNT(*) as n,
                           AVG(pre_lice_count) as avg_pre,
                           AVG(post_lice_count) as avg_post,
                           AVG(CASE WHEN pre_lice_count > 0
                               THEN (pre_lice_count - post_lice_count) / pre_lice_count
                               ELSE 0 END) as avg_reduction_pct,
                           AVG(mortality_observed) as avg_mortality,
                           AVG(cost_nok) as avg_cost
                    FROM treatment_outcomes
                    WHERE method IS NOT NULL
                    GROUP BY method
                    ORDER BY avg_reduction_pct DESC
                """))).fetchall()

            methods = []
            for r in rows:
                methods.append({
                    "method": r[0],
                    "sample_size": r[1],
                    "avg_pre_lice": round(r[2] or 0, 3),
                    "avg_post_lice": round(r[3] or 0, 3),
                    "avg_reduction_pct": round((r[4] or 0) * 100, 1),
                    "avg_mortality": round(r[5] or 0, 1),
                    "avg_cost_nok": round(r[6] or 0),
                })

            return {
                "methods": methods,
                "total_outcomes": sum(m["sample_size"] for m in methods),
                "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            }
        except Exception as e:
            log.error("efficacy_by_method.error", error=str(e))
            return {"methods": [], "note": "No outcome data yet or table not created", "error": str(e)}

    # ── Private helpers ──────────────────────────────────────────────

    async def _get_lice_data(self, locality_no: int) -> Optional[dict]:
        """Fetch recent lice records from DB."""
        async with get_async_session() as s:
            rows = (await s.execute(
                select(
                    LiceRecord.avg_adult_female_lice,
                    LiceRecord.sea_temp_c,
                    LiceRecord.year,
                    LiceRecord.week,
                )
                .where(LiceRecord.locality_no == locality_no)
                .order_by(desc(LiceRecord.year), desc(LiceRecord.week))
                .limit(8)
            )).fetchall()

        if not rows:
            return None

        current = rows[0][0] or 0.0
        sea_temp = rows[0][1] or 10.0

        # History for sparkline (oldest first)
        history = [
            {"lice": round(r[0] or 0, 3), "week": r[3], "year": r[2]}
            for r in reversed(rows)
        ]

        # Trend detection (last 4 weeks)
        recent = [r[0] or 0 for r in rows[:4]]
        if len(recent) >= 3:
            if recent[0] > recent[1] > recent[2]:
                trend = "rising"
            elif recent[0] < recent[1] < recent[2]:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "current": current,
            "sea_temp_c": sea_temp,
            "trend": trend,
            "history": history,
        }

    async def _get_ocean_forecast(self, locality_no: int) -> Optional[dict]:
        """Get MET.no ocean forecast for treatment timing."""
        try:
            from core.market.met_ocean import met_ocean_client
            # Find which PA this locality belongs to
            async with get_async_session() as s:
                loc = (await s.execute(
                    select(Locality.production_area_id)
                    .where(Locality.locality_no == locality_no)
                )).scalar()
            if not loc:
                return None
            pa_num = int(str(loc).replace("PA-", "").strip()) if loc else None
            if not pa_num:
                return None
            forecast = await met_ocean_client.get_pa_forecast(pa_num)
            if forecast and not forecast.get("error"):
                return {
                    "current_c": forecast.get("current_temp_c"),
                    "min_c": forecast.get("min_temp_c"),
                    "max_c": forecast.get("max_temp_c"),
                    "avg_c": forecast.get("avg_temp_c"),
                    "n_points": forecast.get("n_forecasts", 0),
                    "source": "MET.no OceanForecast 2.0",
                }
        except Exception as e:
            log.debug("decision.ocean_forecast_fallback", error=str(e)[:80])
        return None

    async def _get_gnn_prediction(self, locality_no: int) -> Optional[float]:
        """Try to get GNN next-week prediction. Returns None if unavailable."""
        try:
            from core.market.lice_gnn import lice_gnn
            result = lice_gnn.predict_locality(locality_no)
            if result and "predicted_adult_female" in result:
                return result["predicted_adult_female"]
        except Exception:
            pass
        return None

    def _compute_action(
        self,
        lice: float,
        trend: str,
        temp: float,
        gnn_pred: Optional[float],
    ) -> tuple[str, str, list[str]]:
        """Rule-based decision logic."""
        reasoning = []

        # Rule 1: Above regulatory limit and rising
        if lice > REGULATORY_LIMIT and trend == "rising":
            reasoning.append(f"Lice {lice:.2f} exceeds regulatory limit ({REGULATORY_LIMIT}) and rising")
            if gnn_pred and gnn_pred > lice:
                reasoning.append(f"GNN predicts further increase to {gnn_pred:.2f} next week")
            return "TREAT_NOW", "immediate", reasoning

        # Rule 2: Above trigger and high temperature stress
        if lice > TREATMENT_TRIGGER and temp and temp > 14.0:
            reasoning.append(f"Lice {lice:.2f} above trigger ({TREATMENT_TRIGGER}) with high temp {temp:.1f}C")
            reasoning.append("Warm water accelerates lice reproduction")
            return "SCHEDULE_TREATMENT", "this_week", reasoning

        # Rule 3: Above trigger but trend declining
        if lice > TREATMENT_TRIGGER and trend == "declining":
            reasoning.append(f"Lice {lice:.2f} above trigger but trend is declining")
            reasoning.append("Monitor closely - natural decline or prior treatment taking effect")
            return "MONITOR", "next_2_weeks", reasoning

        # Rule 4: Above trigger, stable or rising but below regulatory
        if lice > TREATMENT_TRIGGER:
            reasoning.append(f"Lice {lice:.2f} above proactive trigger ({TREATMENT_TRIGGER})")
            if trend == "rising":
                reasoning.append("Rising trend detected - schedule treatment before regulatory breach")
                return "SCHEDULE_TREATMENT", "this_week", reasoning
            reasoning.append("Stable levels - schedule preventive treatment")
            return "SCHEDULE_TREATMENT", "next_2_weeks", reasoning

        # Rule 5: GNN predicts breach
        if gnn_pred and gnn_pred > TREATMENT_TRIGGER:
            reasoning.append(f"GNN predicts lice will reach {gnn_pred:.2f} next week (above trigger)")
            return "MONITOR", "next_2_weeks", reasoning

        # Default: no action needed
        reasoning.append(f"Lice {lice:.2f} within safe range")
        if temp:
            reasoning.append(f"Sea temperature {temp:.1f}C")
        return "NO_ACTION", "preventive", reasoning

    def _compute_feature_importance(
        self,
        lice: float,
        trend: str,
        temp: Optional[float],
        gnn_pred: Optional[float],
        action: str,
    ) -> dict:
        """Compute feature importance (SHAP-style) for the decision.

        Returns a structured explanation with per-factor importance scores
        (0-1 normalized) and human-readable explanations in English and Norwegian.
        """
        factors = []
        raw_scores = {}

        # ── Factor 1: Lice level ──
        lice_ratio = min(lice / REGULATORY_LIMIT, 2.0) if REGULATORY_LIMIT > 0 else 0
        raw_scores["lice_level"] = lice_ratio
        if lice > REGULATORY_LIMIT:
            en = f"Lice level {lice:.2f} exceeds regulatory limit ({REGULATORY_LIMIT})"
            no = f"Luseniva {lice:.2f} overstiger regulatorisk grense ({REGULATORY_LIMIT})"
        elif lice > TREATMENT_TRIGGER:
            en = f"Lice level {lice:.2f} exceeds warning threshold ({TREATMENT_TRIGGER})"
            no = f"Luseniva {lice:.2f} er over varselsgrensen ({TREATMENT_TRIGGER})"
        else:
            en = f"Lice level {lice:.2f} is within safe range"
            no = f"Luseniva {lice:.2f} er innenfor trygt omrade"
        factors.append({"name": "lice_level", "importance": 0, "en": en, "no": no})

        # ── Factor 2: Lice trend ──
        trend_score = {"rising": 0.8, "stable": 0.3, "declining": 0.1}.get(trend, 0.3)
        raw_scores["lice_trend"] = trend_score
        trend_labels = {"rising": ("Rising", "Stigende"), "stable": ("Stable", "Stabil"), "declining": ("Declining", "Synkende")}
        t_en, t_no = trend_labels.get(trend, ("Unknown", "Ukjent"))
        factors.append({
            "name": "lice_trend",
            "importance": 0,
            "en": f"{t_en} lice trend increases urgency" if trend == "rising" else f"{t_en} lice trend reduces urgency",
            "no": f"{t_no} lusetrend oker hastegrad" if trend == "rising" else f"{t_no} lusetrend reduserer hastegrad",
        })

        # ── Factor 3: Sea temperature ──
        if temp is not None:
            # Warm water (>14C) accelerates lice reproduction
            temp_score = min(max(temp - 8.0, 0) / 10.0, 1.0)  # 0 at 8C, 1 at 18C
            raw_scores["sea_temperature"] = temp_score
            if temp > 14.0:
                en = f"Sea temperature {temp:.1f}C accelerates lice reproduction"
                no = f"Sjøtemperatur {temp:.1f}C akselererer luseproduksjon"
            elif temp > 10.0:
                en = f"Sea temperature {temp:.1f}C is moderate for lice growth"
                no = f"Sjøtemperatur {temp:.1f}C er moderat for lusevekst"
            else:
                en = f"Sea temperature {temp:.1f}C slows lice reproduction"
                no = f"Sjøtemperatur {temp:.1f}C bremser luseproduksjon"
        else:
            raw_scores["sea_temperature"] = 0.2
            en = "Sea temperature data unavailable"
            no = "Sjøtemperaturdata er utilgjengelig"
        factors.append({"name": "sea_temperature", "importance": 0, "en": en, "no": no})

        # ── Factor 4: GNN prediction ──
        if gnn_pred is not None:
            gnn_ratio = min(gnn_pred / REGULATORY_LIMIT, 2.0)
            raw_scores["gnn_prediction"] = gnn_ratio
            direction_en = "increase" if gnn_pred > lice else "decrease"
            direction_no = "økning" if gnn_pred > lice else "nedgang"
            en = f"GNN predicts {gnn_pred:.2f} next week ({direction_en} from {lice:.2f})"
            no = f"GNN forutsier {gnn_pred:.2f} neste uke ({direction_no} fra {lice:.2f})"
        else:
            raw_scores["gnn_prediction"] = 0.3
            en = "GNN model unavailable, using rule-based assessment"
            no = "GNN-modell utilgjengelig, bruker regelbasert vurdering"
        factors.append({"name": "gnn_prediction", "importance": 0, "en": en, "no": no})

        # ── Factor 5: Regulatory distance ──
        if lice > 0:
            reg_distance = (REGULATORY_LIMIT - lice) / REGULATORY_LIMIT
            reg_score = max(0, min(1.0 - reg_distance, 1.0))
        else:
            reg_score = 0.0
        raw_scores["regulatory_distance"] = reg_score
        margin = REGULATORY_LIMIT - lice
        if margin <= 0:
            en = f"Already exceeding regulatory limit by {abs(margin):.2f}"
            no = f"Allerede over regulatorisk grense med {abs(margin):.2f}"
        elif margin < 0.1:
            en = f"Only {margin:.2f} from regulatory limit — high breach risk"
            no = f"Bare {margin:.2f} fra regulatorisk grense — høy risiko for brudd"
        else:
            en = f"Margin of {margin:.2f} to regulatory limit"
            no = f"Margin på {margin:.2f} til regulatorisk grense"
        factors.append({"name": "regulatory_distance", "importance": 0, "en": en, "no": no})

        # ── Factor 6: Season ──
        month = dt.datetime.now(dt.UTC).month
        is_high_season = month in (5, 6, 7, 8, 9)  # May-Sep peak lice season
        season_score = 0.6 if is_high_season else 0.2
        raw_scores["season"] = season_score
        month_names_en = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                          7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
        month_names_no = {1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "mai", 6: "jun",
                          7: "jul", 8: "aug", 9: "sep", 10: "okt", 11: "nov", 12: "des"}
        if is_high_season:
            en = f"Peak lice season ({month_names_en[month]}) — elevated reproduction risk"
            no = f"Høysesong for lus ({month_names_no[month]}) — økt reproduksjonsrisiko"
        else:
            en = f"Low lice season ({month_names_en[month]}) — reduced reproduction rate"
            no = f"Lavsesong for lus ({month_names_no[month]}) — redusert reproduksjonsrate"
        factors.append({"name": "season", "importance": 0, "en": en, "no": no})

        # ── Normalize scores to 0-1 ──
        total = sum(raw_scores.values()) or 1.0
        for f in factors:
            f["importance"] = round(raw_scores[f["name"]] / total, 3)

        # ── Generate summary ──
        top_factors_en = sorted(factors, key=lambda x: x["importance"], reverse=True)[:3]
        top_factors_no = sorted(factors, key=lambda x: x["importance"], reverse=True)[:3]

        action_labels = {
            "TREAT_NOW": ("Treatment recommended immediately", "Behandling anbefalt umiddelbart"),
            "SCHEDULE_TREATMENT": ("Treatment should be scheduled", "Behandling bør planlegges"),
            "MONITOR": ("Close monitoring recommended", "Tett overvåking anbefalt"),
            "NO_ACTION": ("No action needed at this time", "Ingen handling nødvendig nå"),
        }
        summary_base_en, summary_base_no = action_labels.get(action, ("Assessment complete", "Vurdering fullført"))

        top_reasons_en = ", ".join(f["en"].split(" — ")[0].lower() for f in top_factors_en)
        top_reasons_no = ", ".join(f["no"].split(" — ")[0].lower() for f in top_factors_no)

        return {
            "factors": factors,
            "summary_en": f"{summary_base_en} due to {top_reasons_en}.",
            "summary_no": f"{summary_base_no} på grunn av {top_reasons_no}.",
        }

    async def _get_learned_profiles(self) -> dict:
        """Fetch learned efficacy profiles from the Efficacy Marketplace."""
        try:
            from core.market.efficacy_marketplace import efficacy_marketplace
            return await efficacy_marketplace.get_learned_profiles()
        except Exception as e:
            log.debug("decision.learned_profiles_fallback", error=str(e)[:80])
            return {}

    def _recommend_method(
        self, temp: float, action: str, *, learned_profiles: dict = None, pa: int = None,
    ) -> tuple[str, float, str]:
        """Pick best treatment method based on temperature and season.

        Returns:
            (method_name, success_probability, source_label)
            source_label is "literature" or "marketplace (n=X)".
        """
        if action == "NO_ACTION":
            return "none", 0.0, "literature"
        if action == "MONITOR":
            return "monitoring", 0.0, "literature"

        temp = temp or 10.0
        month = dt.datetime.now(dt.UTC).month
        is_warm_season = month in (4, 5, 6, 7, 8, 9)  # Apr-Sep

        # Temperature-based selection
        if temp > 12.0:
            # Prefer non-medicinal in warm water
            if is_warm_season:
                # Spring/summer: prefer freshwater (resistance management)
                best = "freshwater"
            else:
                best = "mechanical"
        elif temp < 8.0:
            # Cold water: medicinal works well, less resistance concern in winter
            best = "medicinal"
        else:
            # Moderate temp: mechanical is safest all-round
            best = "mechanical"

        profile = TREATMENT_PROFILES[best]

        # Adjust success probability by temperature suitability
        t_lo, t_hi = profile["temp_range"]
        if t_lo <= temp <= t_hi:
            success = profile["base_success"]
        else:
            # Out of ideal range: reduce success
            success = profile["base_success"] * 0.85

        source = "literature"

        # Override with learned marketplace data if available for this (method, PA)
        if learned_profiles and pa is not None:
            learned = learned_profiles.get((best, pa))
            if learned and learned.get("sample_size", 0) >= 5:
                learned_success = learned["reduction_pct"] / 100.0
                log.info(
                    "decision.learned_override",
                    method=best,
                    pa=pa,
                    literature_pct=round(success * 100, 1),
                    learned_pct=learned["reduction_pct"],
                    n=learned["sample_size"],
                )
                success = learned_success
                source = f"marketplace (n={learned['sample_size']})"

        return best, success, source

    def _compute_roi(
        self, lice: float, method: str, action: str
    ) -> tuple[float, float, float]:
        """Estimate treatment cost vs cost of inaction."""
        if action in ("NO_ACTION", "MONITOR") or method in ("none", "monitoring"):
            return 0.0, 0.0, 0.0

        profile = TREATMENT_PROFILES.get(method, TREATMENT_PROFILES["mechanical"])

        # Cost of treatment
        cost_treatment = profile["cost_per_fish_nok"] * AVG_FISH_PER_LOCALITY
        mortality_cost = (
            profile["mortality_risk_pct"]
            / 100
            * AVG_FISH_PER_LOCALITY
            * AVG_FISH_WEIGHT_KG
            * SALMON_VALUE_NOK_PER_KG
        )
        total_treatment_cost = cost_treatment + mortality_cost

        # Cost of inaction (4 weeks of elevated lice)
        weeks_inaction = 4
        growth_loss_per_week = (
            GROWTH_REDUCTION_PCT_PER_LICE
            * lice
            * AVG_FISH_PER_LOCALITY
            * AVG_FISH_WEIGHT_KG
            * SALMON_VALUE_NOK_PER_KG
        )
        mortality_loss_per_week = (
            MORTALITY_PCT_PER_LICE_WEEK
            * max(0, lice - TREATMENT_TRIGGER)
            * AVG_FISH_PER_LOCALITY
            * AVG_FISH_WEIGHT_KG
            * SALMON_VALUE_NOK_PER_KG
        )
        total_inaction_cost = (growth_loss_per_week + mortality_loss_per_week) * weeks_inaction

        # ROI
        roi = total_inaction_cost / total_treatment_cost if total_treatment_cost > 0 else 0.0

        return total_treatment_cost, total_inaction_cost, roi

    def _urgency_rank(self, urgency: str) -> int:
        """Rank urgency for sorting (higher = more urgent)."""
        return {
            "immediate": 4,
            "this_week": 3,
            "next_2_weeks": 2,
            "preventive": 1,
        }.get(urgency, 0)


# ── Singleton ────────────────────────────────────────────────────────────
decision_engine = DecisionEngine()
