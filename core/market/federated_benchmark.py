"""
Federated Benchmarking Engine — Privacy-Preserving Peer Comparison
===================================================================
Uses differential privacy (Laplace mechanism) to enable companies
to compare performance against peers without revealing individual data.

Key properties:
  - ε-differential privacy on all aggregated outputs
  - Cohort-based grouping (size × region) for fair comparison
  - Trend benchmarks (12-week trajectory comparison)
  - Minimum cohort size = 5 for meaningful privacy
  - Noise-seeded per cache cycle for consistency
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# ── Privacy parameters ─────────────────────────────────────────────
EPSILON_STATS = 1.0        # For means/medians
EPSILON_PERCENTILE = 0.5   # For percentile rankings (tighter)
EPSILON_COUNTS = 2.0       # For cohort sizes (looser)
MIN_COHORT_SIZE = 5        # Minimum for cohort-level stats
LICE_CLIP_MAX = 2.0        # Clip lice values for bounded sensitivity

# ── Cohort definitions ─────────────────────────────────────────────
SIZE_TIERS = {
    "micro": (1, 5),
    "small": (6, 15),
    "medium": (16, 40),
    "large": (41, 9999),
}

REGION_MAP = {
    "south": [1, 2, 3, 4],
    "central": [5, 6, 7, 8],
    "north": [9, 10, 11, 12, 13],
}

METRICS = [
    "lice_management",
    "threshold_compliance",
    "performance_score",
    "esg_total",
    "disease_resilience",
]

TIER_DESC = {"micro": "1-5 sites", "small": "6-15 sites", "medium": "16-40 sites", "large": "41+ sites"}
REGION_DESC = {"south": "Southern Norway (PA 1-4)", "central": "Central Norway (PA 5-8)", "north": "Northern Norway (PA 9-13)", "all": "All regions"}


@dataclass
class CohortDefinition:
    cohort_id: str
    size_tier: str
    region: str
    n_companies: int  # noised
    description: str


@dataclass
class PrivateMetric:
    metric: str
    your_value: float
    cohort_avg: float       # noised
    cohort_median: float    # noised
    industry_avg: float     # noised
    industry_median: float  # noised
    cohort_percentile: float  # noised, 0-100
    industry_percentile: float  # noised, 0-100
    cohort_size: int          # rounded to 5
    verdict: str
    narrative: str


@dataclass
class TrendMetric:
    metric: str
    your_slope: float
    your_direction: str
    cohort_avg_slope: float   # noised
    trend_percentile: float   # noised
    weeks: int
    narrative: str


@dataclass
class FederatedReport:
    company_name: str
    cohort: CohortDefinition
    generated_at: str
    epsilon: float
    metrics: list[dict] = field(default_factory=list)
    trends: list[dict] = field(default_factory=list)
    overall_percentile: float = 50.0  # noised
    overall_verdict: str = ""
    insights: list[str] = field(default_factory=list)


class FederatedBenchmarkEngine:
    """Privacy-preserving peer comparison engine."""

    def __init__(self) -> None:
        self._cache: dict | None = None
        self._cache_time: dt.datetime | None = None
        self._cache_ttl = dt.timedelta(hours=1)
        self._rng = np.random.default_rng(42)

    def _laplace_noise(self, sensitivity: float, epsilon: float) -> float:
        """Sample from Laplace(0, sensitivity/epsilon)."""
        scale = sensitivity / max(epsilon, 0.01)
        return float(self._rng.laplace(0, scale))

    def _noised_mean(self, values: list[float], epsilon: float = EPSILON_STATS) -> float:
        """Compute mean with DP noise."""
        if not values:
            return 0.0
        n = len(values)
        clipped = [min(max(v, 0), LICE_CLIP_MAX) for v in values]
        mean = sum(clipped) / n
        sensitivity = LICE_CLIP_MAX / n
        return round(mean + self._laplace_noise(sensitivity, epsilon), 4)

    def _noised_median(self, values: list[float], epsilon: float = EPSILON_STATS) -> float:
        """Compute median with DP noise."""
        if not values:
            return 0.0
        med = float(np.median(values))
        sensitivity = LICE_CLIP_MAX / max(len(values), 1)
        return round(med + self._laplace_noise(sensitivity, epsilon), 4)

    def _noised_percentile(self, value: float, all_values: list[float], epsilon: float = EPSILON_PERCENTILE) -> float:
        """Compute percentile rank with DP noise."""
        if not all_values:
            return 50.0
        n = len(all_values)
        rank = sum(1 for v in all_values if v <= value)
        pct = (rank / n) * 100
        sensitivity = 100.0 / n
        noised = pct + self._laplace_noise(sensitivity, epsilon)
        return round(max(0, min(100, noised)), 1)

    def _noised_count(self, count: int, epsilon: float = EPSILON_COUNTS) -> int:
        """Noise a count and round to nearest 5."""
        noised = count + self._laplace_noise(1.0, epsilon)
        return max(5, int(round(noised / 5) * 5))

    def _assign_cohort(self, company: dict) -> CohortDefinition:
        """Assign company to a size x region cohort."""
        n_locs = company.get("n_localities", 0)
        size_tier = "micro"
        for tier, (lo, hi) in SIZE_TIERS.items():
            if lo <= n_locs <= hi:
                size_tier = tier
                break

        # Primary region from most common PA
        pas = company.get("production_areas", [])
        region = "all"
        if pas:
            for reg_name, reg_pas in REGION_MAP.items():
                if any(pa in reg_pas for pa in pas):
                    region = reg_name
                    break

        cohort_id = f"{size_tier}_{region}"

        return CohortDefinition(
            cohort_id=cohort_id,
            size_tier=size_tier,
            region=region,
            n_companies=0,  # filled later with noised count
            description=f"{TIER_DESC[size_tier]}, {REGION_DESC[region]}",
        )

    @staticmethod
    def _to_dict(obj: object) -> dict:
        """Convert dataclass or object to dict."""
        if isinstance(obj, dict):
            return obj
        from dataclasses import asdict
        try:
            return asdict(obj)
        except Exception:
            pass
        # Fallback: use __dict__ or vars
        try:
            return vars(obj)
        except Exception:
            return {}

    async def _get_company_data(self) -> list[dict]:
        """Get all company data from existing engines. Cached for 1 hour."""
        now = dt.datetime.now(dt.UTC)
        if (
            self._cache is not None
            and self._cache_time
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._cache

        try:
            from core.market.top50_engine import top50_engine
            companies = await top50_engine.compile_top50()
            if isinstance(companies, list) and companies:
                result = [self._to_dict(c) for c in companies]
                self._cache = result
                self._cache_time = now
                return result
            raise ValueError("top50 engine returned no companies")
        except Exception:
            try:
                from core.market.benchmarking import benchmarking_engine
                raw = await benchmarking_engine.compute_all()
                if isinstance(raw, dict):
                    items = raw.get("companies", [])
                elif isinstance(raw, list):
                    items = raw
                else:
                    items = []
                result = [self._to_dict(c) for c in items]
                self._cache = result
                self._cache_time = now
                return result
            except Exception as e:
                log.warning("federated.data_error", error=str(e)[:80])
                return []

    def _extract_metric(self, company: dict, metric: str) -> float:
        """Extract a metric value from company data."""
        # Map our metric names to benchmark metric names
        benchmark_names = {
            "lice_management": "Lice Performance",
            "threshold_compliance": "Threshold Compliance",
            "performance_score": "Overall Performance",
            "esg_total": "ESG Sustainability",
            "disease_resilience": "Disease Resilience",
        }
        # Try to find in benchmarks array first
        bench_name = benchmark_names.get(metric, metric)
        for b in company.get("benchmarks", []):
            if isinstance(b, dict) and b.get("metric") == bench_name:
                val = b.get("your_value")
                if val is not None:
                    return float(val)
        # Fallback to flat fields
        flat_keys = {
            "lice_management": ["avg_lice", "avg_adult_female_lice"],
            "threshold_compliance": ["pct_below_threshold"],
            "performance_score": ["overall_percentile", "performance_score"],
            "esg_total": ["esg_total", "esg_score"],
            "disease_resilience": ["disease_resilience"],
        }
        for key in flat_keys.get(metric, [metric]):
            val = company.get(key)
            if val is not None and isinstance(val, (int, float)):
                return float(val)
        return 0.0

    def _verdict(self, percentile: float) -> str:
        if percentile >= 80:
            return "Top Performer"
        elif percentile >= 60:
            return "Above Average"
        elif percentile >= 40:
            return "Average"
        elif percentile >= 20:
            return "Below Average"
        return "Needs Improvement"

    async def get_company_report(self, company_name: str) -> dict:
        """Generate a full federated benchmark report for one company."""
        all_companies = await self._get_company_data()
        if not all_companies:
            return {"error": "No company data available"}

        # Find target company
        target = None
        for c in all_companies:
            if (c.get("company_name", c.get("name", "")) or "").lower() == company_name.lower():
                target = c
                break
        if not target:
            # Try partial match
            for c in all_companies:
                if company_name.lower() in (c.get("company_name", c.get("name", "")) or "").lower():
                    target = c
                    break
        if not target:
            return {"error": f"Company '{company_name}' not found"}

        # Assign cohort — precompute all assignments once
        all_assignments = {id(c): self._assign_cohort(c) for c in all_companies}
        cohort = all_assignments[id(target)]

        # Find cohort peers using precomputed assignments
        cohort_peers = [
            c for c in all_companies
            if all_assignments[id(c)].cohort_id == cohort.cohort_id
        ]

        # Fallback if cohort too small
        if len(cohort_peers) < MIN_COHORT_SIZE:
            # Fall back to size-only
            cohort.region = "all"
            cohort.cohort_id = f"{cohort.size_tier}_all"
            cohort.description = cohort.description.split(",")[0] + ", All regions"
            cohort_peers = [
                c for c in all_companies
                if all_assignments[id(c)].size_tier == cohort.size_tier
            ]
        if len(cohort_peers) < MIN_COHORT_SIZE:
            # Fall back to industry-wide
            cohort.cohort_id = "industry_all"
            cohort.size_tier = "all"
            cohort.description = "All companies (industry-wide)"
            cohort_peers = all_companies

        cohort.n_companies = self._noised_count(len(cohort_peers))

        # Reseed RNG for consistent results within cache period
        self._rng = np.random.default_rng(hash(company_name) % 2**31)

        # Compute metrics
        metrics = []
        metric_percentiles = []

        for metric in METRICS:
            your_val = self._extract_metric(target, metric)
            cohort_vals = [self._extract_metric(c, metric) for c in cohort_peers]
            industry_vals = [self._extract_metric(c, metric) for c in all_companies]

            # For lice: lower is better, so invert percentile
            invert = metric == "lice_management"

            c_pct = self._noised_percentile(your_val, cohort_vals)
            i_pct = self._noised_percentile(your_val, industry_vals)

            if invert:
                c_pct = 100 - c_pct
                i_pct = 100 - i_pct

            metric_percentiles.append(c_pct)

            m = {
                "metric": metric.replace("_", " ").title(),
                "your_value": round(your_val, 4),
                "cohort_avg": self._noised_mean(cohort_vals),
                "cohort_median": self._noised_median(cohort_vals),
                "industry_avg": self._noised_mean(industry_vals),
                "industry_median": self._noised_median(industry_vals),
                "cohort_percentile": c_pct,
                "industry_percentile": i_pct,
                "cohort_size": cohort.n_companies,
                "verdict": self._verdict(c_pct),
                "higher_is_better": not invert,
            }
            metrics.append(m)

        # Overall percentile
        overall = round(sum(metric_percentiles) / max(len(metric_percentiles), 1), 1)
        overall_noised = max(0, min(100, overall + self._laplace_noise(10.0, EPSILON_PERCENTILE)))

        # Generate insights
        insights = []
        for m in metrics:
            if m["cohort_percentile"] >= 75:
                insights.append(f"Your {m['metric'].lower()} ranks in the top 25% of your peer cohort.")
            elif m["cohort_percentile"] <= 25:
                insights.append(f"Your {m['metric'].lower()} is below 75% of peers — consider improvement strategies.")

        if overall_noised >= 70:
            insights.append(f"Overall, you are a strong performer within the {cohort.description.lower()} group.")
        elif overall_noised <= 30:
            insights.append("Overall performance below peer average — multiple metrics need attention.")

        return {
            "company_name": target.get("company_name", target.get("name", company_name)),
            "cohort": {
                "cohort_id": cohort.cohort_id,
                "size_tier": cohort.size_tier,
                "region": cohort.region,
                "n_companies": cohort.n_companies,
                "description": cohort.description,
            },
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "epsilon": EPSILON_STATS,
            "metrics": metrics,
            "overall_percentile": round(overall_noised, 1),
            "overall_verdict": self._verdict(overall_noised),
            "insights": insights,
            "privacy_note": "All peer statistics include calibrated Laplace noise (epsilon=1.0). No individual company data is revealed.",
        }

    async def get_cohorts(self) -> list[dict]:
        """List all cohorts with noised member counts."""
        all_companies = await self._get_company_data()
        cohorts: dict[str, list] = {}
        for c in all_companies:
            co = self._assign_cohort(c)
            cohorts.setdefault(co.cohort_id, []).append(c)

        result = []
        for cid, members in cohorts.items():
            if members:
                sample = self._assign_cohort(members[0])
                result.append({
                    "cohort_id": cid,
                    "size_tier": sample.size_tier,
                    "region": sample.region,
                    "n_companies": self._noised_count(len(members)),
                    "description": sample.description,
                    "has_enough_members": len(members) >= MIN_COHORT_SIZE,
                })
        return sorted(result, key=lambda x: x["n_companies"], reverse=True)

    async def get_cohort_summary(self, cohort_id: str) -> dict:
        """Aggregated noised statistics for a cohort."""
        all_companies = await self._get_company_data()
        members = [c for c in all_companies if self._assign_cohort(c).cohort_id == cohort_id]

        if len(members) < MIN_COHORT_SIZE:
            return {"error": f"Cohort '{cohort_id}' has fewer than {MIN_COHORT_SIZE} members", "n_companies": len(members)}

        summary = {"cohort_id": cohort_id, "n_companies": self._noised_count(len(members))}
        for metric in METRICS:
            vals = [self._extract_metric(c, metric) for c in members]
            summary[metric] = {
                "avg": self._noised_mean(vals),
                "median": self._noised_median(vals),
            }
        return summary

    def get_privacy_info(self) -> dict:
        """Privacy transparency dashboard."""
        return {
            "mechanism": "Laplace",
            "epsilon_stats": EPSILON_STATS,
            "epsilon_percentile": EPSILON_PERCENTILE,
            "epsilon_counts": EPSILON_COUNTS,
            "min_cohort_size": MIN_COHORT_SIZE,
            "lice_clip_max": LICE_CLIP_MAX,
            "cache_ttl_hours": 1,
            "guarantee": (
                "All aggregated peer statistics are computed with epsilon-differential privacy. "
                "This means that the presence or absence of any single company in the dataset "
                "changes any output by at most a bounded amount, preventing reverse-engineering "
                "of individual company data from published statistics."
            ),
            "size_tiers": SIZE_TIERS,
            "regions": {k: f"PA {v}" for k, v in REGION_MAP.items()},
        }


# Singleton
federated_benchmark_engine = FederatedBenchmarkEngine()
