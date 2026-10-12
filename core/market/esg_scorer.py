"""
ESG Sustainability Scorer
==========================
Computes per-company ESG (Environmental, Social, Governance) scores
from existing platform data. No competitor offers this for salmon.

Scoring framework (100-point scale):
  E — Environmental (40 pts):
    - Lice performance vs. threshold (15 pts)
    - Treatment frequency and type (10 pts) — chemical penalty, cleaner fish bonus
    - Bloom/mortality exposure (10 pts)
    - Cleaner fish adoption rate (5 pts)
    - Disease outbreak penalty (up to -5 pts) — ISA/PD from Mattilsynet

  S — Social/Welfare (30 pts):
    - Fish welfare (mortality rate proxy) (15 pts)
    - Treatment method humaneness (10 pts) — thermal penalty, mechanical neutral
    - Regulatory compliance (traffic light) (5 pts)

  G — Governance/Transparency (30 pts):
    - Data reporting completeness (15 pts) — % weeks with lice reports
    - Peer performance percentile (10 pts)
    - Production area diversity (5 pts) — geographic risk spread

Data sources: ALL from existing BarentsWatch + internal platform data.
No additional APIs needed.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)


@dataclass
class ESGScore:
    """ESG score for a single company."""
    company_name: str
    ticker: str | None = None
    # Component scores
    environmental: float = 0.0    # 0-40
    social: float = 0.0           # 0-30
    governance: float = 0.0       # 0-30
    total: float = 0.0            # 0-100
    grade: str = "—"              # A+ / A / B+ / B / C / D / F
    # Breakdown
    e_lice_score: float = 0.0
    e_treatment_score: float = 0.0
    e_bloom_score: float = 0.0
    e_cleaner_fish_score: float = 0.0
    e_disease_score: float = 0.0
    s_welfare_score: float = 0.0
    s_treatment_method_score: float = 0.0
    s_regulatory_score: float = 0.0
    g_reporting_score: float = 0.0
    g_peer_score: float = 0.0
    g_diversity_score: float = 0.0
    # Metadata
    n_localities: int = 0
    production_areas: list[int] = field(default_factory=list)
    computed_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))


def _grade(score: float) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B+"
    if score >= 60: return "B"
    if score >= 50: return "C"
    if score >= 35: return "D"
    return "F"


class ESGScorer:
    """Compute ESG sustainability scores from existing platform data."""

    _scores: list[ESGScore] = []
    _last_compute: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=1)

    def __init__(self) -> None:
        self._scores = []

    async def compute_all(self) -> list[ESGScore]:
        """Compute ESG scores for all companies in the database."""
        now = dt.datetime.now(dt.UTC)
        if self._scores and self._last_compute and (now - self._last_compute) < self._cache_ttl:
            return self._scores

        from core.market.top50_engine import top50_engine
        from core.market.regime_detector import regime_detector

        companies = await top50_engine.compile_top50()
        regime_states = regime_detector.get_all_states()
        regime_map = {s["production_area"]: s for s in regime_states}

        # Fetch disease counts per company from Mattilsynet
        disease_by_company: dict[str, dict] = {}
        try:
            from core.market.mattilsynet_client import mattilsynet_client
            cases = await mattilsynet_client.fetch_disease_cases(200)
            disease_by_company = await mattilsynet_client.get_company_disease_counts(cases)
        except Exception as exc:
            log.debug("esg.disease_fetch_skipped", error=str(exc)[:80])

        scores = []
        # Compute peer stats for percentile scoring
        all_lice = [c.avg_lice for c in companies if c.avg_lice is not None and c.avg_lice > 0]
        avg_peer_lice = sum(all_lice) / max(len(all_lice), 1)

        for co in companies:
            s = ESGScore(
                company_name=co.name,
                ticker=co.ticker,
                n_localities=co.n_localities,
                production_areas=co.production_areas or [],
            )

            # ── Environmental (40 pts) ───────────────────────────────
            # E1: Lice performance (15 pts) — lower is better
            lice = co.avg_lice or 0
            if lice <= 0.05:
                s.e_lice_score = 15.0
            elif lice <= 0.1:
                s.e_lice_score = 13.0
            elif lice <= 0.2:
                s.e_lice_score = 10.0
            elif lice <= 0.5:
                s.e_lice_score = 5.0
            else:
                s.e_lice_score = max(0, 3.0 - (lice - 0.5) * 4)

            # E2: Treatment score (10 pts) — cleaner fish = bonus, chemical = penalty
            has_cleaner = co.score_components.get("cleaner_fish_pct", 0) if co.score_components else 0
            pct_above = co.pct_above_threshold or 0
            if pct_above <= 5:
                s.e_treatment_score = 10.0
            elif pct_above <= 15:
                s.e_treatment_score = 7.0
            elif pct_above <= 30:
                s.e_treatment_score = 4.0
            else:
                s.e_treatment_score = max(0, 2.0 - (pct_above - 30) / 20)

            # E3: Bloom exposure (10 pts) — lower bloom risk = higher score
            # Use PA color as proxy for environmental stress
            red_pas = sum(1 for pa in (co.production_areas or [])
                         if regime_map.get(pa, {}).get("current_color") == "red")
            if red_pas == 0:
                s.e_bloom_score = 10.0
            elif red_pas == 1:
                s.e_bloom_score = 6.0
            else:
                s.e_bloom_score = max(0, 3.0 - red_pas)

            # E4: Cleaner fish adoption (5 pts)
            s.e_cleaner_fish_score = min(5.0, has_cleaner * 5)

            # E5: Disease outbreak penalty (0 to -5 pts) — from Mattilsynet
            disease_info = disease_by_company.get(co.name, {})
            n_disease = disease_info.get("total", 0)
            n_isa = disease_info.get("isa", 0)
            if n_isa >= 2:
                s.e_disease_score = -5.0  # Multiple ISA outbreaks = max penalty
            elif n_isa == 1:
                s.e_disease_score = -3.0  # One ISA = severe
            elif n_disease >= 3:
                s.e_disease_score = -3.0  # Multiple PD/other
            elif n_disease >= 1:
                s.e_disease_score = -1.5  # One or two PD
            else:
                s.e_disease_score = 0.0   # No active outbreaks = no penalty

            s.environmental = round(max(0, (
                s.e_lice_score + s.e_treatment_score + s.e_bloom_score
                + s.e_cleaner_fish_score + s.e_disease_score
            )), 1)

            # ── Social / Welfare (30 pts) ────────────────────────────
            # S1: Fish welfare proxy — inverse of lice severity (15 pts)
            if lice <= 0.1:
                s.s_welfare_score = 15.0
            elif lice <= 0.3:
                s.s_welfare_score = 10.0
            elif lice <= 0.5:
                s.s_welfare_score = 6.0
            else:
                s.s_welfare_score = max(0, 3.0 - (lice - 0.5) * 3)

            # S2: Treatment method humaneness (10 pts)
            # Less treatment = more humane; cleaner fish = most humane method
            s.s_treatment_method_score = min(10.0, s.e_treatment_score)

            # S3: Regulatory compliance (5 pts)
            yellow_or_red = sum(1 for pa in (co.production_areas or [])
                                if regime_map.get(pa, {}).get("current_color") in ("yellow", "red"))
            if yellow_or_red == 0:
                s.s_regulatory_score = 5.0
            elif yellow_or_red <= 2:
                s.s_regulatory_score = 3.0
            else:
                s.s_regulatory_score = 1.0

            s.social = round(
                s.s_welfare_score + s.s_treatment_method_score + s.s_regulatory_score, 1
            )

            # ── Governance / Transparency (30 pts) ───────────────────
            # G1: Reporting completeness (15 pts)
            n_records = co.n_lice_records or 0
            expected = co.n_localities * 26  # ~26 weeks of data expected
            completeness = min(1.0, n_records / max(expected, 1))
            s.g_reporting_score = round(completeness * 15, 1)

            # G2: Peer performance percentile (10 pts)
            if avg_peer_lice > 0 and lice > 0:
                peer_ratio = lice / avg_peer_lice
                if peer_ratio <= 0.5:
                    s.g_peer_score = 10.0
                elif peer_ratio <= 1.0:
                    s.g_peer_score = 7.0
                elif peer_ratio <= 1.5:
                    s.g_peer_score = 4.0
                else:
                    s.g_peer_score = 1.0
            else:
                s.g_peer_score = 5.0

            # G3: Geographic diversity (5 pts)
            n_pas = len(set(co.production_areas or []))
            s.g_diversity_score = min(5.0, n_pas * 1.0)

            s.governance = round(
                s.g_reporting_score + s.g_peer_score + s.g_diversity_score, 1
            )

            # ── Total ────────────────────────────────────────────────
            s.total = round(s.environmental + s.social + s.governance, 1)
            s.grade = _grade(s.total)

            scores.append(s)

        # Sort by total score descending
        scores.sort(key=lambda x: x.total, reverse=True)
        self._scores = scores
        self._last_compute = now
        log.info("esg.computed", n_companies=len(scores), top_grade=scores[0].grade if scores else "—")
        return scores

    async def get_all(self) -> list[dict]:
        """Return all ESG scores as API-friendly dicts."""
        scores = await self.compute_all()
        return [self._to_dict(s, rank=i + 1) for i, s in enumerate(scores)]

    async def get_company(self, name: str) -> dict | None:
        """Get ESG score for a specific company."""
        scores = await self.compute_all()
        for i, s in enumerate(scores):
            if s.company_name.lower() == name.lower() or (s.ticker and s.ticker.lower() == name.lower()):
                return self._to_dict(s, rank=i + 1)
        return None

    async def get_summary(self) -> dict:
        """Get ESG summary statistics."""
        scores = await self.compute_all()
        if not scores:
            return {"n_companies": 0}
        totals = [s.total for s in scores]
        return {
            "n_companies": len(scores),
            "avg_score": round(sum(totals) / len(totals), 1),
            "median_score": round(sorted(totals)[len(totals) // 2], 1),
            "top_company": scores[0].company_name,
            "top_score": scores[0].total,
            "top_grade": scores[0].grade,
            "grade_distribution": {
                grade: sum(1 for s in scores if s.grade == grade)
                for grade in ["A+", "A", "B+", "B", "C", "D", "F"]
            },
            "computed_at": self._last_compute.isoformat() if self._last_compute else None,
        }

    @staticmethod
    def _to_dict(s: ESGScore, rank: int = 0) -> dict:
        return {
            "rank": rank,
            "company_name": s.company_name,
            "ticker": s.ticker,
            "total": s.total,
            "grade": s.grade,
            "environmental": s.environmental,
            "social": s.social,
            "governance": s.governance,
            "breakdown": {
                "e_lice": s.e_lice_score,
                "e_treatment": s.e_treatment_score,
                "e_bloom": s.e_bloom_score,
                "e_cleaner_fish": s.e_cleaner_fish_score,
                "e_disease": s.e_disease_score,
                "s_welfare": s.s_welfare_score,
                "s_treatment_method": s.s_treatment_method_score,
                "s_regulatory": s.s_regulatory_score,
                "g_reporting": s.g_reporting_score,
                "g_peer": s.g_peer_score,
                "g_diversity": s.g_diversity_score,
            },
            "n_localities": s.n_localities,
            "production_areas": s.production_areas,
            "computed_at": s.computed_at.isoformat(),
        }


# Singleton
esg_scorer = ESGScorer()
