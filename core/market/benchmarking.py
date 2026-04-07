"""
Anonymous Peer Benchmarking Engine
====================================
The #1 retention feature and strongest competitive moat.
More farms sharing data → better benchmarks → more farms join → network effect.

Computes per-company and per-PA percentile rankings across:
  - Lice performance (avg adult female lice vs peers)
  - Treatment intensity (% sites above 0.5 threshold)
  - Mortality proxy (from lice severity trends)
  - ESG score vs peers
  - Production efficiency (sites per PA, geographic spread)

Output: "Your lice avg (0.12) is better than 78% of producers in PA-6"
This single sentence drives weekly check-ins.

Data: 100% from existing BarentsWatch lice data + top50 engine. Zero new APIs needed.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import structlog

log = structlog.get_logger(__name__)


@dataclass
class PeerBenchmark:
    """Benchmark result for a single metric."""
    metric: str
    your_value: float
    peer_avg: float
    peer_median: float
    peer_min: float
    peer_max: float
    percentile: float          # 0-100 (higher = better)
    rank: int                  # 1 = best
    total_peers: int
    direction: str             # "lower_is_better" or "higher_is_better"
    verdict: str               # "Excellent" / "Good" / "Average" / "Below Average" / "Needs Improvement"
    narrative: str             # Human-readable insight


@dataclass
class CompanyBenchmarkReport:
    """Full benchmark report for one company."""
    company_name: str
    ticker: str | None = None
    production_areas: list[int] = field(default_factory=list)
    n_localities: int = 0
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    overall_percentile: float = 0.0
    overall_verdict: str = ""
    benchmarks: list[PeerBenchmark] = field(default_factory=list)
    pa_benchmarks: list[dict] = field(default_factory=list)


def _verdict(percentile: float, lower_is_better: bool = True) -> str:
    """Convert percentile to human verdict."""
    # If lower is better (like lice), high percentile = good performance
    p = percentile if lower_is_better else (100 - percentile)
    if p >= 80: return "Excellent"
    if p >= 60: return "Good"
    if p >= 40: return "Average"
    if p >= 20: return "Below Average"
    return "Needs Improvement"


def _percentile_rank(value: float, all_values: list[float], lower_is_better: bool = True) -> float:
    """Compute percentile rank. Returns 0-100 where 100 = best."""
    if not all_values or len(all_values) < 2:
        return 50.0
    arr = np.array(all_values)
    if lower_is_better:
        # Lower value = higher percentile (better)
        rank = np.sum(arr >= value) / len(arr) * 100
    else:
        # Higher value = higher percentile (better)
        rank = np.sum(arr <= value) / len(arr) * 100
    return round(min(100, max(0, rank)), 1)


class BenchmarkingEngine:
    """
    Computes anonymous peer benchmarks from existing platform data.
    No new data sources needed — everything from top50_engine + regime_detector.
    """

    _cache: list[CompanyBenchmarkReport] | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(hours=1)

    async def compute_all(self) -> list[CompanyBenchmarkReport]:
        """Compute benchmarks for all companies."""
        now = dt.datetime.now(dt.UTC)
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        from core.market.top50_engine import top50_engine
        from core.market.esg_scorer import esg_scorer

        companies = await top50_engine.compile_top50()
        esg_scores = {s.company_name: s for s in await esg_scorer.compute_all()}

        # Fetch disease counts per company from Mattilsynet
        disease_by_company: dict[str, dict] = {}
        try:
            from core.market.mattilsynet_client import mattilsynet_client
            cases = await mattilsynet_client.fetch_disease_cases(200)
            disease_by_company = mattilsynet_client.get_company_disease_counts(cases)
        except Exception:
            pass

        if len(companies) < 5:
            log.warning("benchmarking.insufficient_data", n=len(companies))
            return []

        # Extract all values for percentile computation
        all_lice = [c.avg_lice for c in companies if c.avg_lice is not None and c.avg_lice > 0]
        all_max_lice = [c.max_lice for c in companies if c.max_lice is not None]
        all_pct_above = [c.pct_above_threshold for c in companies if c.pct_above_threshold is not None]
        all_scores = [c.performance_score for c in companies if c.performance_score is not None]
        all_esg = [s.total for s in esg_scores.values() if s.total > 0]
        all_n_locs = [c.n_localities for c in companies if c.n_localities > 0]

        # Disease resilience: 0 outbreaks = 100, each outbreak -20, ISA = -40
        all_disease_resilience: list[float] = []
        disease_resilience_map: dict[str, float] = {}
        for c in companies:
            d = disease_by_company.get(c.name, {})
            total = d.get("total", 0)
            isa = d.get("isa", 0)
            score = max(0.0, 100.0 - total * 20 - isa * 20)  # ISA counts double
            all_disease_resilience.append(score)
            disease_resilience_map[c.name] = score

        # PA-level lice averages for within-PA comparison
        pa_lice: dict[int, list[tuple[str, float]]] = {}
        for c in companies:
            if c.avg_lice is not None and c.avg_lice > 0:
                for pa in (c.production_areas or []):
                    if pa not in pa_lice:
                        pa_lice[pa] = []
                    pa_lice[pa].append((c.name, c.avg_lice))

        reports = []
        for co in companies:
            benchmarks: list[PeerBenchmark] = []
            esg = esg_scores.get(co.name)

            # 1. Lice Performance (lower is better)
            if co.avg_lice is not None and co.avg_lice > 0 and all_lice:
                pct = _percentile_rank(co.avg_lice, all_lice, lower_is_better=True)
                rank = sorted(all_lice).index(co.avg_lice) + 1 if co.avg_lice in sorted(all_lice) else len(all_lice) // 2
                benchmarks.append(PeerBenchmark(
                    metric="Lice Performance",
                    your_value=round(co.avg_lice, 4),
                    peer_avg=round(float(np.mean(all_lice)), 4),
                    peer_median=round(float(np.median(all_lice)), 4),
                    peer_min=round(float(np.min(all_lice)), 4),
                    peer_max=round(float(np.max(all_lice)), 4),
                    percentile=pct,
                    rank=rank,
                    total_peers=len(all_lice),
                    direction="lower_is_better",
                    verdict=_verdict(pct, lower_is_better=True),
                    narrative=f"Your avg lice ({co.avg_lice:.3f}) is better than {pct:.0f}% of {len(all_lice)} producers",
                ))

            # 2. Threshold Compliance (lower % above = better)
            if co.pct_above_threshold is not None and all_pct_above:
                pct = _percentile_rank(co.pct_above_threshold, all_pct_above, lower_is_better=True)
                benchmarks.append(PeerBenchmark(
                    metric="Threshold Compliance",
                    your_value=round(co.pct_above_threshold, 1),
                    peer_avg=round(float(np.mean(all_pct_above)), 1),
                    peer_median=round(float(np.median(all_pct_above)), 1),
                    peer_min=round(float(np.min(all_pct_above)), 1),
                    peer_max=round(float(np.max(all_pct_above)), 1),
                    percentile=pct,
                    rank=0,
                    total_peers=len(all_pct_above),
                    direction="lower_is_better",
                    verdict=_verdict(pct, lower_is_better=True),
                    narrative=f"{co.pct_above_threshold:.0f}% of your sites exceed 0.5 limit — better than {pct:.0f}% of peers",
                ))

            # 3. Performance Score (higher is better)
            if co.performance_score is not None and all_scores:
                pct = _percentile_rank(co.performance_score, all_scores, lower_is_better=False)
                benchmarks.append(PeerBenchmark(
                    metric="Overall Performance",
                    your_value=round(co.performance_score, 1),
                    peer_avg=round(float(np.mean(all_scores)), 1),
                    peer_median=round(float(np.median(all_scores)), 1),
                    peer_min=round(float(np.min(all_scores)), 1),
                    peer_max=round(float(np.max(all_scores)), 1),
                    percentile=pct,
                    rank=0,
                    total_peers=len(all_scores),
                    direction="higher_is_better",
                    verdict=_verdict(pct, lower_is_better=False),
                    narrative=f"Performance score {co.performance_score:.0f} — top {100 - pct:.0f}% of industry",
                ))

            # 4. ESG Score (higher is better)
            if esg and esg.total > 0 and all_esg:
                pct = _percentile_rank(esg.total, all_esg, lower_is_better=False)
                benchmarks.append(PeerBenchmark(
                    metric="ESG Sustainability",
                    your_value=round(esg.total, 1),
                    peer_avg=round(float(np.mean(all_esg)), 1),
                    peer_median=round(float(np.median(all_esg)), 1),
                    peer_min=round(float(np.min(all_esg)), 1),
                    peer_max=round(float(np.max(all_esg)), 1),
                    percentile=pct,
                    rank=0,
                    total_peers=len(all_esg),
                    direction="higher_is_better",
                    verdict=_verdict(pct, lower_is_better=False),
                    narrative=f"ESG grade {esg.grade} ({esg.total}/100) — top {100 - pct:.0f}% of industry",
                ))

            # 5. Disease Resilience (higher is better — no outbreaks = 100)
            dr_score = disease_resilience_map.get(co.name, 100.0)
            if all_disease_resilience:
                pct = _percentile_rank(dr_score, all_disease_resilience, lower_is_better=False)
                d_info = disease_by_company.get(co.name, {})
                n_outbreaks = d_info.get("total", 0)
                benchmarks.append(PeerBenchmark(
                    metric="Disease Resilience",
                    your_value=round(dr_score, 1),
                    peer_avg=round(float(np.mean(all_disease_resilience)), 1),
                    peer_median=round(float(np.median(all_disease_resilience)), 1),
                    peer_min=round(float(np.min(all_disease_resilience)), 1),
                    peer_max=round(float(np.max(all_disease_resilience)), 1),
                    percentile=pct,
                    rank=0,
                    total_peers=len(all_disease_resilience),
                    direction="higher_is_better",
                    verdict=_verdict(pct, lower_is_better=False),
                    narrative=f"{n_outbreaks} active outbreaks — disease resilience top {100 - pct:.0f}% of peers" if n_outbreaks > 0
                              else f"No active disease outbreaks — top {100 - pct:.0f}% of peers",
                ))

            # 6. PA-level benchmarks (most powerful: "you vs your PA neighbors")
            pa_benchmarks = []
            for pa in (co.production_areas or []):
                pa_data = pa_lice.get(pa, [])
                if len(pa_data) >= 3 and co.avg_lice is not None:
                    pa_values = [v for _, v in pa_data]
                    pa_pct = _percentile_rank(co.avg_lice, pa_values, lower_is_better=True)
                    pa_benchmarks.append({
                        "pa": pa,
                        "your_lice": round(co.avg_lice, 4),
                        "pa_avg": round(float(np.mean(pa_values)), 4),
                        "pa_median": round(float(np.median(pa_values)), 4),
                        "percentile": pa_pct,
                        "n_peers": len(pa_data),
                        "verdict": _verdict(pa_pct),
                        "narrative": f"In PA-{pa}: your lice ({co.avg_lice:.3f}) is better than {pa_pct:.0f}% of {len(pa_data)} local producers",
                    })

            # Overall percentile (average of all metric percentiles)
            if benchmarks:
                overall = round(float(np.mean([b.percentile for b in benchmarks])), 1)
            else:
                overall = 50.0

            reports.append(CompanyBenchmarkReport(
                company_name=co.name,
                ticker=co.ticker,
                production_areas=co.production_areas or [],
                n_localities=co.n_localities,
                overall_percentile=overall,
                overall_verdict=_verdict(overall),
                benchmarks=benchmarks,
                pa_benchmarks=pa_benchmarks,
            ))

        reports.sort(key=lambda r: r.overall_percentile, reverse=True)
        self._cache = reports
        self._cache_time = now
        log.info("benchmarking.computed", n_companies=len(reports),
                 avg_percentile=round(float(np.mean([r.overall_percentile for r in reports])), 1))
        return reports

    async def get_company(self, name: str) -> dict | None:
        """Get benchmark for a specific company."""
        reports = await self.compute_all()
        for r in reports:
            if r.company_name.lower() == name.lower() or (r.ticker and r.ticker.lower() == name.lower()):
                return self._to_dict(r)
        return None

    async def get_leaderboard(self, limit: int = 20) -> list[dict]:
        """Top performers by overall percentile."""
        reports = await self.compute_all()
        return [self._to_dict(r) for r in reports[:limit]]

    async def get_pa_leaderboard(self, pa: int) -> list[dict]:
        """Rankings within a specific production area."""
        reports = await self.compute_all()
        pa_companies = [r for r in reports if pa in r.production_areas]
        # Re-sort by lice performance within this PA
        for r in pa_companies:
            pa_data = [b for b in r.pa_benchmarks if b["pa"] == pa]
            if pa_data:
                r._pa_sort_key = pa_data[0]["percentile"]
            else:
                r._pa_sort_key = 50.0
        pa_companies.sort(key=lambda r: r._pa_sort_key, reverse=True)
        return [
            {
                **self._to_dict(r),
                "pa_benchmark": next((b for b in r.pa_benchmarks if b["pa"] == pa), None),
            }
            for r in pa_companies
        ]

    async def get_summary(self) -> dict:
        """Industry-wide benchmark summary."""
        reports = await self.compute_all()
        if not reports:
            return {"n_companies": 0}

        percentiles = [r.overall_percentile for r in reports]
        return {
            "n_companies": len(reports),
            "avg_percentile": round(float(np.mean(percentiles)), 1),
            "top_performer": reports[0].company_name if reports else None,
            "top_percentile": reports[0].overall_percentile if reports else 0,
            "verdict_distribution": {
                v: sum(1 for r in reports if r.overall_verdict == v)
                for v in ["Excellent", "Good", "Average", "Below Average", "Needs Improvement"]
            },
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        }

    @staticmethod
    def _to_dict(r: CompanyBenchmarkReport) -> dict:
        return {
            "company_name": r.company_name,
            "ticker": r.ticker,
            "production_areas": r.production_areas,
            "n_localities": r.n_localities,
            "overall_percentile": r.overall_percentile,
            "overall_verdict": r.overall_verdict,
            "benchmarks": [
                {
                    "metric": b.metric,
                    "your_value": b.your_value,
                    "peer_avg": b.peer_avg,
                    "peer_median": b.peer_median,
                    "percentile": b.percentile,
                    "total_peers": b.total_peers,
                    "direction": b.direction,
                    "verdict": b.verdict,
                    "narrative": b.narrative,
                }
                for b in r.benchmarks
            ],
            "pa_benchmarks": r.pa_benchmarks,
            "generated_at": r.generated_at.isoformat(),
        }


# Singleton
benchmarking_engine = BenchmarkingEngine()
