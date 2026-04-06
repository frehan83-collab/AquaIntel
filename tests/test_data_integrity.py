"""
Data Integrity Test Suite
===========================
Verifies that all platform data comes from real sources,
not hardcoded values. Run with: pytest tests/ -v
"""
import pytest
from core.models import Session, Locality, LiceRecord, SSBWeeklyPrice
from sqlalchemy import select, func


class TestDatabaseIntegrity:
    """Verify real data exists in the database."""

    def test_localities_exist(self):
        with Session() as s:
            count = s.execute(select(func.count(Locality.id))).scalar()
        assert count > 1000, f"Expected 1000+ localities, got {count}"

    def test_localities_have_owners(self):
        with Session() as s:
            with_owner = s.execute(
                select(func.count(Locality.id))
                .where(Locality.owner_company.isnot(None), Locality.owner_company != "")
            ).scalar()
            total = s.execute(select(func.count(Locality.id))).scalar()
        pct = with_owner / total * 100
        assert pct > 50, f"Only {pct:.0f}% of localities have company attribution"

    def test_localities_have_coordinates(self):
        with Session() as s:
            with_coords = s.execute(
                select(func.count(Locality.id))
                .where(Locality.latitude.isnot(None))
            ).scalar()
        assert with_coords > 1000, f"Only {with_coords} localities have coordinates"

    def test_lice_records_exist(self):
        with Session() as s:
            count = s.execute(select(func.count(LiceRecord.id))).scalar()
        assert count > 100000, f"Expected 100K+ lice records, got {count}"

    def test_lice_records_span_multiple_years(self):
        with Session() as s:
            years = s.execute(
                select(func.count(func.distinct(LiceRecord.year)))
            ).scalar()
        assert years >= 5, f"Expected 5+ years of lice data, got {years}"

    def test_companies_with_lice_data(self):
        """At least 100 companies should have real lice records."""
        with Session() as s:
            companies = s.execute(
                select(func.count(func.distinct(Locality.owner_company)))
                .join(LiceRecord, LiceRecord.locality_no == Locality.locality_no)
                .where(Locality.owner_company.isnot(None))
            ).scalar()
        assert companies >= 100, f"Only {companies} companies have lice data"

    def test_production_areas_assigned(self):
        with Session() as s:
            with_pa = s.execute(
                select(func.count(Locality.id))
                .where(Locality.production_area.isnot(None))
            ).scalar()
        assert with_pa > 500, f"Only {with_pa} localities have PA codes"


class TestTop100Engine:
    """Verify the Top 100 engine uses real data."""

    def test_discovers_companies_from_db(self):
        from core.market.top50_engine import top50_engine
        import asyncio; companies = asyncio.new_event_loop().run_until_complete(top50_engine.compile_top50(force_refresh=True))
        assert len(companies) >= 50, f"Only {len(companies)} companies discovered"

    def test_no_hardcoded_company_names(self):
        """Engine should NOT have a KNOWN_COMPANIES list."""
        import inspect
        from core.market import top50_engine as module
        source = inspect.getsource(module)
        assert "KNOWN_COMPANIES" not in source, "KNOWN_COMPANIES still exists — should be DB-driven"
        assert "est_volume" not in source, "est_volume still exists — should be DB-driven"

    def test_companies_have_real_lice_data(self):
        from core.market.top50_engine import top50_engine
        import asyncio; companies = asyncio.new_event_loop().run_until_complete(top50_engine.compile_top50())
        with_lice = sum(1 for c in companies if c.avg_lice > 0 or c.n_lice_records > 0)
        assert with_lice >= 50, f"Only {with_lice} companies have real lice data"

    def test_sparklines_are_real(self):
        from core.market.top50_engine import top50_engine
        import asyncio; companies = asyncio.new_event_loop().run_until_complete(top50_engine.compile_top50())
        with_spark = sum(1 for c in companies if len(c.lice_sparkline) >= 4)
        assert with_spark >= 30, f"Only {with_spark} companies have sparklines"

    def test_pa_leaderboard(self):
        from core.market.top50_engine import top50_engine
        import asyncio; lb = asyncio.new_event_loop().run_until_complete(top50_engine.get_pa_leaderboard())
        assert len(lb) >= 10, f"Only {len(lb)} PAs in leaderboard"


class TestSSBPriceData:
    """Verify SSB price integration uses real data."""

    def test_seasonal_pattern_not_all_same(self):
        """The seasonal pattern should vary across weeks."""
        from core.market.price_ml import SEASONAL_PATTERN
        values = list(SEASONAL_PATTERN.values())
        assert len(set(values)) > 10, "Seasonal pattern has too few distinct values"

    def test_salmon_price_uses_shared_seasonal(self):
        """salmon_price.py should use the same SEASONAL_PATTERN as price_ml.py."""
        from core.market.salmon_price import SEASONAL_PATTERN as sp
        from core.market.price_ml import SEASONAL_PATTERN as pm
        assert sp is pm, "salmon_price.py has its own SEASONAL_PATTERN — should share with price_ml.py"


class TestNoHardcodedData:
    """Verify no hardcoded sample/fake data remains."""

    def test_no_sample_data_in_dashboard(self):
        """Dashboard page should not contain SAMPLE_ arrays."""
        with open("frontend/src/app/page.tsx", "r") as f:
            content = f.read()
        assert "SAMPLE_LICE" not in content, "SAMPLE_LICE still in dashboard"
        assert "SAMPLE_SUPPLY" not in content, "SAMPLE_SUPPLY still in dashboard"

    def test_biomass_tracker_labeled_as_estimate(self):
        """Biomass data should be clearly labeled as estimated."""
        with open("frontend/src/app/market/page.tsx", "r", encoding="utf-8") as f:
            content = f.read()
        assert "estimated" in content.lower(), "Biomass section not labeled as estimated"

    def test_bloom_api_returns_company_names(self):
        """Bloom risk API should include owner_company field."""
        import glob
        found = False
        for path in ["core/api.py"] + glob.glob("core/routers/*.py"):
            with open(path, "r", encoding="utf-8") as f:
                if "owner_company" in f.read():
                    found = True
                    break
        assert found, "owner_company not found in any API route file"
