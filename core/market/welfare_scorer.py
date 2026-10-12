"""
Fish Welfare Scoring Engine
============================
Computes a holistic welfare score (0-100) from 5 components:
1. Lice Burden (35% weight) -- penalized nonlinearly above 0.3
2. Thermal Stress (15%) -- distance from optimal 12 deg C
3. Mortality Trend (20%) -- recent mortality rate vs baseline
4. Oxygen/Environment (15%) -- SST-derived oxygen proxy + bloom risk
5. Treatment Stress (15%) -- recency and frequency of treatments

Also predicts 7-day mortality using a heuristic model fitted to
treatment outcome data.

Reference: Stien et al. (2013) "Salmon Welfare Index Model (SWIM)"
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

from sqlalchemy import select, desc

logger = logging.getLogger(__name__)

# ── Component weights (sum to 1.0) ──────────────────────────────────
WEIGHTS = {
    "lice": 0.35,
    "thermal": 0.15,
    "mortality": 0.20,
    "environment": 0.15,
    "treatment_stress": 0.15,
}

# ── Defaults when external data unavailable ─────────────────────────
DEFAULT_LICE = 0.2
DEFAULT_SST = 10.0
DEFAULT_MORTALITY_PCT = 0.5
DEFAULT_BLOOM_RISK = 0.1
DEFAULT_WEEKS_SINCE_TREATMENT = 8
DEFAULT_TREATMENTS_90D = 0


@dataclass
class WelfareScore:
    """Holistic welfare assessment for a single farm."""
    total_score: float                  # 0-100
    grade: str                          # A+ through F
    components: dict                    # {lice: 0-1, thermal: 0-1, ...}
    predicted_mortality_7d: float       # percent
    alert_reason: str                   # human-readable explanation
    factors: list = field(default_factory=list)  # contributing factors
    locality_no: int = 0
    scored_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class WelfareScorer:
    """
    Scores fish welfare on a 0-100 scale using 5 biologically grounded
    components, with 7-day mortality prediction.
    """

    # ── Component scoring functions ─────────────────────────────────

    @staticmethod
    def _lice_component(lice: float) -> float:
        """
        Score lice burden 0-1 (1 = excellent, 0 = critical).
        Nonlinear penalty above 0.3 adult female lice per fish.
        Norwegian regulatory limit: 0.5 (spring) / 0.2 (spring-summer protection).
        """
        if lice <= 0.0:
            return 1.0
        if lice <= 0.1:
            return 1.0 - (lice / 0.5) * 0.1  # minimal penalty below 0.1
        # Nonlinear: (lice/0.5)^1.5 -- accelerating penalty above 0.3
        penalty = min((lice / 0.5) ** 1.5, 1.0)
        return max(1.0 - penalty, 0.0)

    @staticmethod
    def _thermal_component(sst: float) -> float:
        """
        Score thermal stress 0-1 (1 = optimal).
        Optimal range: 10-14 deg C, center at 12 deg C.
        Ref: Oppedal et al. (2011) "Environmental drivers of Atlantic salmon behaviour"
        """
        optimal = 12.0
        distance = abs(sst - optimal)
        # Gentle penalty within optimal band, steep outside
        if distance <= 2.0:
            return 1.0 - (distance / 8.0) * 0.3  # minimal penalty in 10-14 range
        return max(1.0 - min(distance / 8.0, 1.0), 0.0)

    @staticmethod
    def _mortality_component(mortality_pct: float) -> float:
        """
        Score mortality trend 0-1 (1 = low mortality).
        Normal baseline: <0.5%/month. Alarm: >3%.
        Ref: Mowi Handbook 2024, industry avg mortality ~15% over production cycle.
        """
        if mortality_pct <= 0.0:
            return 1.0
        return max(1.0 - min(mortality_pct / 3.0, 1.0), 0.0)

    @staticmethod
    def _environment_component(sst: float, bloom_risk: float) -> float:
        """
        Combined oxygen/environment score 0-1.
        Oxygen proxy: dissolved oxygen inversely correlates with SST above 16 deg C.
        Bloom risk adds additional stress (gill damage, toxins).
        """
        # Oxygen proxy: good below 14 deg C, drops above 16 deg C
        if sst <= 14.0:
            oxygen_score = 1.0
        elif sst <= 20.0:
            oxygen_score = max(1.0 - (sst - 14.0) / 6.0 * 0.8, 0.2)
        else:
            oxygen_score = 0.1

        # Bloom penalty: linear 0-1 where 1.0 bloom_risk = 0.4 penalty
        bloom_penalty = min(bloom_risk, 1.0) * 0.4

        return max(oxygen_score - bloom_penalty, 0.0)

    @staticmethod
    def _treatment_stress(weeks_since_treatment: int, treatments_90d: int) -> float:
        """
        Treatment stress score 0-1 (1 = no recent stress).
        Recent treatments cause handling stress, appetite loss, mortality.
        Multiple treatments in 90 days compound stress.
        Ref: Overton et al. (2019) "Salmon lice treatments and salmon mortality in Norwegian
        aquaculture"
        """
        # Recency: full stress if treated this week, decays over 6 weeks
        if weeks_since_treatment <= 0:
            recency_score = 0.2  # just treated
        elif weeks_since_treatment <= 2:
            recency_score = 0.4
        elif weeks_since_treatment <= 4:
            recency_score = 0.6
        elif weeks_since_treatment <= 6:
            recency_score = 0.8
        else:
            recency_score = 1.0

        # Frequency penalty: each additional treatment in 90d = -0.15
        frequency_penalty = min(treatments_90d * 0.15, 0.6)

        return max(recency_score - frequency_penalty, 0.0)

    @staticmethod
    def _predict_mortality_7d(
        lice: float,
        sst: float,
        weeks_since_treatment: int,
        current_mortality: float,
    ) -> float:
        """
        Predict 7-day mortality percentage using a heuristic regression.
        Fitted to treatment outcome patterns from Norwegian farm data.

        Factors:
        - High lice -> mechanical/medicinal treatment likely -> handling mortality
        - Extreme SST -> physiological stress
        - Recent treatment -> elevated post-treatment mortality
        - Current mortality trend -> persistence/momentum

        Returns: predicted mortality % for next 7 days (0-5+ range typical)
        """
        base_mortality = 0.05  # 0.05% weekly baseline for healthy farms

        # Lice contribution: above 0.3 -> increasing treatment-related mortality
        lice_factor = max(0, (lice - 0.1)) * 0.8

        # Thermal stress: mortality rises sharply above 18 deg C or below 4 deg C
        if sst > 18.0:
            thermal_factor = (sst - 18.0) * 0.3
        elif sst < 4.0:
            thermal_factor = (4.0 - sst) * 0.15
        else:
            thermal_factor = 0.0

        # Post-treatment spike: peaks in week 1, decays
        if weeks_since_treatment <= 1:
            treatment_factor = 0.4
        elif weeks_since_treatment <= 2:
            treatment_factor = 0.2
        elif weeks_since_treatment <= 4:
            treatment_factor = 0.1
        else:
            treatment_factor = 0.0

        # Momentum: current mortality predicts near-term continuation
        momentum = current_mortality * 0.3

        predicted = base_mortality + lice_factor + thermal_factor + treatment_factor + momentum
        return round(max(predicted, 0.01), 3)

    @staticmethod
    def _grade(score: float) -> str:
        """Map 0-100 score to letter grade."""
        if score >= 90:
            return "A+"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B+"
        elif score >= 60:
            return "B"
        elif score >= 50:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"

    @staticmethod
    def _alert_reason(components: dict) -> str:
        """Generate human-readable alert from the lowest-scoring component."""
        if not components:
            return "Insufficient data for welfare assessment"

        labels = {
            "lice": "Lice burden is elevated",
            "thermal": "Sea temperature is outside optimal range",
            "mortality": "Mortality rate is above normal",
            "environment": "Environmental conditions (oxygen/bloom) are stressed",
            "treatment_stress": "Recent treatments are causing handling stress",
        }

        # Find the weakest component
        worst_key = min(components, key=components.get)
        worst_val = components[worst_key]

        if worst_val >= 0.7:
            return "All welfare indicators are within acceptable range"
        elif worst_val >= 0.4:
            return f"Warning: {labels.get(worst_key, worst_key)} (score: {worst_val:.0%})"
        else:
            return f"Critical: {labels.get(worst_key, worst_key)} (score: {worst_val:.0%})"

    # ── Main scoring method ─────────────────────────────────────────

    async def score_farm(self, locality_no: int) -> WelfareScore:
        """
        Compute welfare score for a single farm, pulling live data from
        BarentsWatch (lice), MET.no (SST), and internal DB.
        """
        factors: list[str] = []

        # ── Fetch lice data ─────────────────────────────────────────
        lice = DEFAULT_LICE
        mortality_pct = DEFAULT_MORTALITY_PCT
        sea_temp_db: Optional[float] = None
        weeks_since_treatment = DEFAULT_WEEKS_SINCE_TREATMENT
        treatments_90d = DEFAULT_TREATMENTS_90D

        try:
            from core.models import LiceRecord, Locality
            from core.async_db import get_async_session

            async with get_async_session() as session:
                # Latest lice record
                latest = (await session.execute(
                    select(LiceRecord)
                    .where(LiceRecord.locality_no == locality_no)
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )).scalar_one_or_none()

                if latest:
                    lice = float(latest.avg_adult_female_lice or DEFAULT_LICE)
                    sea_temp_db = float(latest.sea_temp_c) if latest.sea_temp_c else None
                    factors.append(f"Lice: {lice:.3f} adult female/fish (week {latest.year}W{latest.week:02d})")
                else:
                    factors.append(f"Lice: using default {DEFAULT_LICE} (no data)")

                # Mortality: estimate from treatment outcomes if available
                try:
                    from core.models import TreatmentOutcome
                    recent_outcomes = (await session.execute(
                        select(TreatmentOutcome)
                        .where(TreatmentOutcome.locality_no == locality_no)
                        .order_by(desc(TreatmentOutcome.treatment_date))
                        .limit(5)
                    )).scalars().all()

                    if recent_outcomes:
                        # Use mortality from most recent treatment outcome
                        latest_outcome = recent_outcomes[0]
                        if hasattr(latest_outcome, "mortality_pct") and latest_outcome.mortality_pct is not None:
                            mortality_pct = float(latest_outcome.mortality_pct)

                        # Count treatments in last 90 days
                        cutoff_date = dt.date.today() - dt.timedelta(days=90)
                        treatments_90d = sum(
                            1 for o in recent_outcomes
                            if o.treatment_date and o.treatment_date >= cutoff_date
                        )

                        # Weeks since most recent treatment
                        if latest_outcome.treatment_date:
                            days_since = (dt.date.today() - latest_outcome.treatment_date).days
                            weeks_since_treatment = max(days_since // 7, 0)

                        factors.append(f"Treatments in 90d: {treatments_90d}, weeks since last: {weeks_since_treatment}")
                    else:
                        factors.append("No treatment history found, using defaults")
                except Exception:
                    factors.append("Treatment data unavailable, using defaults")

        except Exception as e:
            logger.warning("welfare_scorer: DB query failed for locality %d: %s", locality_no, e)
            factors.append(f"DB unavailable, using defaults: {e}")

        # ── Fetch SST from MET.no (preferred over DB value) ─────────
        sst = DEFAULT_SST
        try:
            from core.market.met_ocean import met_ocean_client
            # Get locality PA for ocean forecast
            from core.models import Locality
            from core.async_db import get_async_session

            async with get_async_session() as session:
                locality = (await session.execute(
                    select(Locality).where(Locality.locality_no == locality_no)
                )).scalar_one_or_none()

            if locality and locality.production_area:
                forecast = await met_ocean_client.get_forecast_for_pa(locality.production_area)
                if forecast and isinstance(forecast, dict):
                    current_sst = forecast.get("current_sst") or forecast.get("sst")
                    if current_sst is not None:
                        sst = float(current_sst)
                        factors.append(f"SST: {sst:.1f} deg C (MET.no live)")
                    elif sea_temp_db is not None:
                        sst = sea_temp_db
                        factors.append(f"SST: {sst:.1f} deg C (BarentsWatch DB)")
                    else:
                        factors.append(f"SST: using default {DEFAULT_SST} deg C")
                elif sea_temp_db is not None:
                    sst = sea_temp_db
                    factors.append(f"SST: {sst:.1f} deg C (BarentsWatch DB)")
                else:
                    factors.append(f"SST: using default {DEFAULT_SST} deg C")
            elif sea_temp_db is not None:
                sst = sea_temp_db
                factors.append(f"SST: {sst:.1f} deg C (BarentsWatch DB)")
            else:
                factors.append(f"SST: using default {DEFAULT_SST} deg C")
        except Exception as e:
            if sea_temp_db is not None:
                sst = sea_temp_db
                factors.append(f"SST: {sst:.1f} deg C (BarentsWatch DB, MET.no failed)")
            else:
                factors.append(f"SST: using default {DEFAULT_SST} deg C (MET.no failed: {e})")

        # ── Fetch bloom risk ────────────────────────────────────────
        bloom_risk = DEFAULT_BLOOM_RISK
        try:
            from core.market.threshold_alerts import threshold_alert_engine
            alerts = await threshold_alert_engine.check_all()
            # Extract bloom-related alerts
            if isinstance(alerts, list):
                bloom_alerts = [a for a in alerts if "bloom" in str(a).lower()]
                if bloom_alerts:
                    bloom_risk = min(len(bloom_alerts) * 0.2, 1.0)
                    factors.append(f"Bloom risk: {bloom_risk:.1f} ({len(bloom_alerts)} alerts)")
                else:
                    factors.append("Bloom risk: low (no active bloom alerts)")
            else:
                factors.append(f"Bloom risk: using default {DEFAULT_BLOOM_RISK}")
        except Exception:
            factors.append(f"Bloom risk: using default {DEFAULT_BLOOM_RISK}")

        # ── Compute component scores ────────────────────────────────
        components = {
            "lice": round(self._lice_component(lice), 3),
            "thermal": round(self._thermal_component(sst), 3),
            "mortality": round(self._mortality_component(mortality_pct), 3),
            "environment": round(self._environment_component(sst, bloom_risk), 3),
            "treatment_stress": round(self._treatment_stress(weeks_since_treatment, treatments_90d), 3),
        }

        # ── Weighted total ──────────────────────────────────────────
        total = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)
        total_score = round(total * 100, 1)

        # ── Predict 7-day mortality ─────────────────────────────────
        predicted_mortality = self._predict_mortality_7d(
            lice, sst, weeks_since_treatment, mortality_pct,
        )

        # ── Build result ────────────────────────────────────────────
        return WelfareScore(
            total_score=total_score,
            grade=self._grade(total_score),
            components=components,
            predicted_mortality_7d=predicted_mortality,
            alert_reason=self._alert_reason(components),
            factors=factors,
            locality_no=locality_no,
            scored_at=dt.datetime.now(dt.UTC).isoformat(),
        )


# ── Singleton ───────────────────────────────────────────────────────
welfare_scorer = WelfareScorer()
