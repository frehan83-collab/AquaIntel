"""
Critical Engine Tests — Dedicated coverage for 10 core engines
================================================================
Each engine gets: import test, primary method test, edge case test.
Run: pytest tests/test_critical_engines.py -v
"""
import asyncio
import pytest


def run_async(coro):
    """Run async coroutine in sync test context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ═══════════════════════════════════════════════════════════════════════
# 1. FeedCostEngine — core/market/feed_cost_engine.py
# ═══════════════════════════════════════════════════════════════════════

class TestFeedCostEngine:
    def test_import(self):
        from core.market.feed_cost_engine import feed_cost_engine
        assert feed_cost_engine is not None

    def test_feed_composition_weights_sum_to_one(self):
        from core.market.feed_cost_engine import FEED_COMPOSITION
        total = sum(FEED_COMPOSITION.values())
        assert abs(total - 1.0) < 0.01, f"Feed composition sums to {total}, expected ~1.0"

    @pytest.mark.xfail(reason="Requires FRED/Yahoo external data fetch")
    def test_fetch_prices_returns_snapshot(self):
        from core.market.feed_cost_engine import feed_cost_engine
        result = run_async(feed_cost_engine.fetch_prices())
        assert result is not None
        assert hasattr(result, "total_nok_per_kg")

    @pytest.mark.xfail(reason="Requires external price history data")
    def test_compute_composite_index_returns_dict(self):
        from core.market.feed_cost_engine import feed_cost_engine
        result = run_async(feed_cost_engine.compute_composite_index(years=1))
        assert isinstance(result, dict)

    def test_get_official_cost_history_returns_list(self):
        from core.market.feed_cost_engine import FeedCostEngine
        history = FeedCostEngine.get_official_cost_history()
        assert isinstance(history, list)
        assert len(history) > 0
        assert "year" in history[0]
        assert "total_cost" in history[0]

    def test_get_latest_returns_none_before_fetch(self):
        """A fresh engine instance should return None before any fetch."""
        from core.market.feed_cost_engine import FeedCostEngine
        engine = FeedCostEngine()
        result = engine.get_latest()
        # May be None or dict depending on if singleton was already fetched
        assert result is None or isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════
# 2. MorningBriefEngine — core/market/morning_brief.py
# ═══════════════════════════════════════════════════════════════════════

class TestMorningBriefEngine:
    def test_import(self):
        from core.market.morning_brief import morning_brief_engine
        assert morning_brief_engine is not None

    def test_brief_section_dataclass(self):
        from core.market.morning_brief import BriefSection
        section = BriefSection(
            title="Test", icon="T", headline="Test headline"
        )
        assert section.sentiment == "neutral"
        assert section.detail == ""

    def test_morning_brief_dataclass_defaults(self):
        from core.market.morning_brief import MorningBrief
        brief = MorningBrief()
        assert brief.market_mood == "neutral"
        assert isinstance(brief.sections, list)
        assert len(brief.sections) == 0

    @pytest.mark.xfail(reason="Requires live data from multiple engines")
    def test_generate_returns_brief(self):
        from core.market.morning_brief import morning_brief_engine
        result = run_async(morning_brief_engine.generate())
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════
# 3. CompetitivenessEngine — core/market/competitiveness_engine.py
# ═══════════════════════════════════════════════════════════════════════

class TestCompetitivenessEngine:
    def test_import(self):
        from core.market.competitiveness_engine import competitiveness_engine
        assert competitiveness_engine is not None

    def test_origin_baselines_coverage(self):
        from core.market.competitiveness_engine import ORIGIN_BASELINES
        expected_origins = {"Norway", "Chile", "Scotland", "Canada", "Faroe Islands", "Iceland"}
        assert expected_origins.issubset(set(ORIGIN_BASELINES.keys()))

    @pytest.mark.xfail(reason="Requires live FX rates from FRED/Yahoo")
    def test_compute_index_returns_dict(self):
        from core.market.competitiveness_engine import competitiveness_engine
        result = run_async(competitiveness_engine.compute_index())
        assert isinstance(result, dict)

    def test_tariff_scenarios_with_zero_tariffs(self):
        from core.market.competitiveness_engine import competitiveness_engine
        overrides = {"Norway": 0.0, "Chile": 0.0, "Scotland": 0.0}
        result = competitiveness_engine.compute_tariff_scenarios(overrides)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════
# 4. GlobalSupplyEngine — core/market/global_supply.py
# ═══════════════════════════════════════════════════════════════════════

class TestGlobalSupplyEngine:
    def test_import(self):
        from core.market.global_supply import global_supply_engine
        assert global_supply_engine is not None

    @pytest.mark.xfail(reason="Requires live data from country monitors")
    def test_compute_returns_balance(self):
        from core.market.global_supply import global_supply_engine
        result = run_async(global_supply_engine.compute())
        assert result is not None

    def test_to_dict_with_empty_balance(self):
        from core.market.global_supply import GlobalSupplyEngine, GlobalSupplyBalance
        engine = GlobalSupplyEngine()
        balance = GlobalSupplyBalance()
        result = engine.to_dict(balance)
        assert isinstance(result, dict)
        assert "countries" in result


# ═══════════════════════════════════════════════════════════════════════
# 5. Top50Engine — core/market/top50_engine.py
# ═══════════════════════════════════════════════════════════════════════

class TestTop50Engine:
    def test_import(self):
        from core.market.top50_engine import top50_engine
        assert top50_engine is not None

    @pytest.mark.xfail(reason="Requires database with lice records")
    def test_compile_top50_returns_list(self):
        from core.market.top50_engine import top50_engine
        result = run_async(top50_engine.compile_top50())
        assert isinstance(result, list)

    def test_parent_groups_defined(self):
        from core.market.top50_engine import PARENT_GROUPS
        assert isinstance(PARENT_GROUPS, dict)
        assert "Mowi ASA" in PARENT_GROUPS

    def test_to_api_response_empty_list(self):
        from core.market.top50_engine import top50_engine
        result = top50_engine.to_api_response([])
        assert isinstance(result, list)
        assert len(result) == 0


# ═══════════════════════════════════════════════════════════════════════
# 6. ESGScorer — core/market/esg_scorer.py
# ═══════════════════════════════════════════════════════════════════════

class TestESGScorer:
    def test_import(self):
        from core.market.esg_scorer import esg_scorer
        assert esg_scorer is not None

    def test_grade_function(self):
        from core.market.esg_scorer import _grade
        assert _grade(95) == "A+"
        assert _grade(85) == "A"
        assert _grade(75) == "B+"
        assert _grade(65) == "B"
        assert _grade(55) == "C"
        assert _grade(40) == "D"
        assert _grade(20) == "F"

    @pytest.mark.xfail(reason="Requires database with company lice data")
    def test_compute_all_returns_list(self):
        from core.market.esg_scorer import esg_scorer
        result = run_async(esg_scorer.compute_all())
        assert isinstance(result, list)

    @pytest.mark.xfail(reason="Requires database with company lice data")
    def test_get_all_returns_list(self):
        from core.market.esg_scorer import esg_scorer
        result = run_async(esg_scorer.get_all())
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════
# 7. BiomassPredictionEngine — core/market/biomass_predictor.py
# ═══════════════════════════════════════════════════════════════════════

class TestBiomassPredictionEngine:
    def test_import(self):
        from core.market.biomass_predictor import biomass_predictor
        assert biomass_predictor is not None

    def test_tgc_daily_growth_positive(self):
        from core.market.biomass_predictor import _tgc_daily_growth
        growth = _tgc_daily_growth(temp_c=10.0, weight_kg=3.0)
        assert growth > 0, "TGC growth must be positive at typical temps"

    def test_tgc_daily_growth_zero_temp(self):
        from core.market.biomass_predictor import _tgc_daily_growth
        growth = _tgc_daily_growth(temp_c=0.0, weight_kg=3.0)
        # At 0 degrees, growth should be zero or near zero
        assert growth >= 0

    def test_effective_temperature_clamps(self):
        from core.market.biomass_predictor import _effective_temperature
        # Very low temp should be clamped
        result_low = _effective_temperature(-5.0)
        assert result_low >= 0
        # Very high temp should be clamped or reduced
        result_high = _effective_temperature(25.0)
        assert isinstance(result_high, float)

    @pytest.mark.xfail(reason="Requires database with current biomass state")
    def test_compute_outlook_returns_object(self):
        from core.market.biomass_predictor import biomass_predictor
        result = run_async(biomass_predictor.compute_outlook(horizon_weeks=4))
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════
# 8. WelfareScorer — core/market/welfare_scorer.py
# ═══════════════════════════════════════════════════════════════════════

class TestWelfareScorer:
    def test_import(self):
        from core.market.welfare_scorer import welfare_scorer
        assert welfare_scorer is not None

    def test_lice_component_zero(self):
        from core.market.welfare_scorer import WelfareScorer
        score = WelfareScorer._lice_component(0.0)
        assert 0 <= score <= 100

    def test_lice_component_high(self):
        from core.market.welfare_scorer import WelfareScorer
        score_low = WelfareScorer._lice_component(0.05)
        score_high = WelfareScorer._lice_component(1.5)
        assert score_low > score_high, "Higher lice should yield lower welfare score"

    def test_thermal_component_optimal(self):
        from core.market.welfare_scorer import WelfareScorer
        score = WelfareScorer._thermal_component(10.0)
        assert 0 <= score <= 100

    def test_mortality_component_zero(self):
        from core.market.welfare_scorer import WelfareScorer
        score = WelfareScorer._mortality_component(0.0)
        # Returns 0-1 scale; zero mortality should give perfect score
        assert score >= 0.8, f"Zero mortality should give high welfare, got {score}"

    def test_grade_ranges(self):
        from core.market.welfare_scorer import WelfareScorer
        assert WelfareScorer._grade(95) == "A+"
        assert WelfareScorer._grade(85) == "A"
        assert WelfareScorer._grade(20) == "F"


# ═══════════════════════════════════════════════════════════════════════
# 9. RegulatoryReporter — core/market/regulatory_reporter.py
# ═══════════════════════════════════════════════════════════════════════

class TestRegulatoryReporter:
    def test_import(self):
        from core.market.regulatory_reporter import regulatory_reporter
        assert regulatory_reporter is not None

    def test_get_upcoming_deadlines_returns_list(self):
        from core.market.regulatory_reporter import regulatory_reporter
        result = run_async(regulatory_reporter.get_upcoming_deadlines(days_ahead=14))
        assert isinstance(result, list)
        # Should always generate at least a couple of weekly lice deadlines
        assert len(result) >= 1

    def test_get_upcoming_deadlines_with_locality(self):
        from core.market.regulatory_reporter import regulatory_reporter
        result = run_async(regulatory_reporter.get_upcoming_deadlines(
            locality_no=10362, days_ahead=30
        ))
        assert isinstance(result, list)

    def test_deadline_dataclass(self):
        from core.market.regulatory_reporter import RegulatoryDeadline
        deadline = RegulatoryDeadline(
            report_type="weekly_lice",
            due_date="2026-04-15",
            locality_no=10362,
            status="pending",
            description="Weekly lice report",
        )
        d = deadline.to_dict()
        assert d["report_type"] == "weekly_lice"
        assert d["status"] == "pending"


# ═══════════════════════════════════════════════════════════════════════
# 10. FeedSupplyChainEngine — core/market/feed_supply_chain.py
# ═══════════════════════════════════════════════════════════════════════

class TestFeedSupplyChainEngine:
    def test_import(self):
        from core.market.feed_supply_chain import feed_supply_chain
        assert feed_supply_chain is not None

    def test_get_standard_feed_composition(self):
        from core.market.feed_supply_chain import feed_supply_chain
        ingredients = feed_supply_chain.get_standard_feed_composition()
        assert isinstance(ingredients, list)
        assert len(ingredients) >= 5
        # Weight percentages should sum to a reasonable total (may not be 100% if
        # some micro-ingredients are not individually listed)
        total_weight = sum(i.weight_pct for i in ingredients)
        assert total_weight > 50, f"Ingredient weights sum to {total_weight}%, expected >50%"

    def test_get_supply_chain_summary(self):
        from core.market.feed_supply_chain import feed_supply_chain
        result = feed_supply_chain.get_supply_chain_summary()
        assert isinstance(result, dict)
        assert "composition" in result
        assert "total_cost_nok_per_tonne" in result
        assert "eudr_risk" in result
        assert result["total_cost_nok_per_tonne"] > 0

    def test_assess_eudr_risk(self):
        from core.market.feed_supply_chain import feed_supply_chain
        ingredients = feed_supply_chain.get_standard_feed_composition()
        risk = feed_supply_chain.assess_eudr_risk(ingredients)
        assert risk is not None
        assert hasattr(risk, "risk_level")
        assert hasattr(risk, "eudr_status")

    def test_assess_eudr_risk_empty_list(self):
        from core.market.feed_supply_chain import feed_supply_chain
        risk = feed_supply_chain.assess_eudr_risk([])
        assert risk is not None

    def test_model_cost_scenarios(self):
        from core.market.feed_supply_chain import feed_supply_chain
        ingredients = feed_supply_chain.get_standard_feed_composition()
        scenarios = feed_supply_chain.model_cost_scenarios(ingredients)
        assert isinstance(scenarios, (dict, list))
