"""
Market Engine Tests
=====================
Verifies core market engines produce valid output with real data.
Run with: pytest tests/test_market_engines.py -v
"""
import pytest


class TestSSBPriceClient:
    """SSB (Statistics Norway) price data integration."""

    @pytest.mark.asyncio
    async def test_ssb_fetch_prices(self):
        from core.market.ssb_price_client import ssb_price_client
        result = await ssb_price_client.fetch_prices(n_weeks=8)
        assert result is not None
        assert hasattr(result, "prices") or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_ssb_get_current_spot(self):
        from core.market.ssb_price_client import ssb_price_client
        spot = await ssb_price_client.get_current_spot()
        # Should be a positive number (NOK/kg) or 0 if unreachable
        assert isinstance(spot, (int, float))
        if spot > 0:
            assert 30 < spot < 200, f"Spot price {spot} NOK/kg seems unrealistic"


class TestDataProvenance:
    """Data provenance system."""

    def test_live_provenance(self):
        from core.market.data_provenance import DataProvenance
        p = DataProvenance.live("SSB Table 03024", confidence=0.95)
        d = p.to_dict()
        assert d["source"] == "SSB Table 03024"
        assert d["is_live"] is True
        assert d["confidence"] == 0.95
        assert d["fallback_reason"] is None

    def test_degraded_provenance(self):
        from core.market.data_provenance import DataProvenance
        p = DataProvenance.degraded("BarentsWatch", "API timeout", confidence=0.4)
        d = p.to_dict()
        assert d["is_live"] is False
        assert d["confidence"] == 0.4
        assert "timeout" in d["fallback_reason"]

    def test_simulated_provenance(self):
        from core.market.data_provenance import DataProvenance
        p = DataProvenance.simulated("No credentials")
        d = p.to_dict()
        assert d["source"] == "simulated"
        assert d["confidence"] == 0.0


class TestPriceML:
    """Price ML ensemble prediction engine."""

    def test_seasonal_pattern_coverage(self):
        from core.market.price_ml import SEASONAL_PATTERN
        assert len(SEASONAL_PATTERN) >= 52, "Should have pattern for all 52 weeks"
        values = list(SEASONAL_PATTERN.values())
        assert max(values) != min(values), "Pattern should vary across weeks"

    def test_ensemble_predict(self):
        from core.market.price_ml import price_ensemble
        fc = price_ensemble.predict(
            current_spot=80.0,
            horizon_weeks=4,
            national_avg_lice=0.15,
            pct_above_threshold=0.1,
            avg_mobile_lice=0.05,
            avg_sessile_lice=0.02,
            cleaner_fish_pct=0.3,
            export_volume_trend=0.0,
            futures_premium_pct=0.0,
            n_scenarios=100,
        )
        assert fc.predicted_nok > 0
        assert fc.price_lo95 <= fc.predicted_nok <= fc.price_hi95
        assert 0 < fc.confidence <= 1.0
        assert fc.horizon_weeks == 4


class TestDecisionEngine:
    """Farmer Decision Engine."""

    @pytest.mark.asyncio
    async def test_decision_valid_locality(self):
        from core.market.decision_engine import decision_engine
        from core.models import Session, LiceRecord
        from sqlalchemy import select

        with Session() as s:
            loc = s.execute(
                select(LiceRecord.locality_no)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            ).scalar()
        if not loc:
            pytest.skip("No lice data")

        result = await decision_engine.get_decision(loc)
        assert "error" not in result, f"Decision error: {result.get('error')}"
        assert result["action"] in ("TREAT_NOW", "SCHEDULE_TREATMENT", "MONITOR", "NO_ACTION")
        assert "data_provenance" in result
        assert result["data_provenance"]["confidence"] > 0

    @pytest.mark.asyncio
    async def test_decision_invalid_locality(self):
        from core.market.decision_engine import decision_engine
        result = await decision_engine.get_decision(99999999)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_portfolio_decisions(self):
        from core.market.decision_engine import decision_engine
        result = await decision_engine.portfolio_decisions("Mowi")
        assert "company" in result
        assert "decisions" in result
        assert isinstance(result["decisions"], list)


class TestMorningBrief:
    """Morning Brief engine."""

    @pytest.mark.asyncio
    async def test_brief_generates(self):
        from core.market.morning_brief import morning_brief_engine
        brief = await morning_brief_engine.generate()
        assert brief is not None
        result = morning_brief_engine.to_dict(brief)
        assert isinstance(result, dict)


class TestAnomalyEngine:
    """Anomaly detection engine."""

    @pytest.mark.asyncio
    async def test_anomaly_computes(self):
        from core.market.anomaly_engine import anomaly_engine
        report = await anomaly_engine.compute()
        assert report is not None
        result = anomaly_engine.to_dict(report)
        assert isinstance(result, dict)


class TestFeedCostEngine:
    """Feed cost / anchovy watch engine."""

    @pytest.mark.asyncio
    async def test_composite_index(self):
        from core.market.feed_cost_engine import feed_cost_engine
        result = await feed_cost_engine.compute_composite_index(2)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_peru_anchovy_watch(self):
        from core.market.feed_cost_engine import feed_cost_engine
        result = await feed_cost_engine.peru_anchovy_watch()
        assert isinstance(result, dict)


class TestMETOcean:
    """MET.no ocean forecast client."""

    @pytest.mark.asyncio
    async def test_ocean_forecast(self):
        from core.market.met_ocean import met_ocean_client
        forecasts = await met_ocean_client.get_ocean_forecast(65.0, 12.0)
        # May return empty if API is slow, but should not crash
        assert isinstance(forecasts, list)

    @pytest.mark.asyncio
    async def test_pa_forecast(self):
        from core.market.met_ocean import met_ocean_client
        result = await met_ocean_client.get_pa_forecast(3)
        assert result is not None
        assert "production_area" in result


class TestTop50Engine:
    """Company ranking engine.

    Scale guard: the ranking assertions require the production dataset
    (1000+ localities); CI / demo-seeded runners have ~22 localities and
    discover only 5 companies, so skip there.
    """

    @staticmethod
    def _full_dataset() -> bool:
        try:
            from core.models import Session, LiceRecord
            from sqlalchemy import select, func
            with Session() as s:
                n = s.execute(select(func.count(LiceRecord.id))).scalar() or 0
            return n >= 10_000
        except Exception:
            return False

    def test_compile_top50(self):
        if not self._full_dataset():
            import pytest
            pytest.skip("Requires production-scale dataset (10k+ lice records)")
        from core.market.top50_engine import top50_engine
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            companies = loop.run_until_complete(top50_engine.compile_top50())
        finally:
            loop.close()
        assert len(companies) >= 30, f"Only {len(companies)} companies"

    def test_companies_have_scores(self):
        if not self._full_dataset():
            import pytest
            pytest.skip("Requires production-scale dataset (10k+ lice records)")
        from core.market.top50_engine import top50_engine
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            companies = loop.run_until_complete(top50_engine.compile_top50())
        finally:
            loop.close()
        with_scores = sum(1 for c in companies if c.performance_score > 0)
        assert with_scores >= 20


class TestAuthModule:
    """Authentication module."""

    def test_hash_password_bcrypt(self):
        from core.auth import hash_password
        h = hash_password("testpassword123")
        assert h.startswith("$2b$"), f"Expected bcrypt hash, got: {h[:10]}"

    def test_verify_password_bcrypt(self):
        from core.auth import hash_password, verify_password
        h = hash_password("secret")
        assert verify_password("secret", h) is True
        assert verify_password("wrong", h) is False

    def test_legacy_sha256_verify(self):
        """Legacy SHA-256 hashes should still verify."""
        import hashlib
        from core.auth import verify_password, needs_rehash
        salt = "abc123"
        pw = "oldpassword"
        legacy = f"{salt}${hashlib.sha256(f'{salt}:{pw}'.encode()).hexdigest()}"
        assert verify_password(pw, legacy) is True
        assert needs_rehash(legacy) is True

    def test_bcrypt_no_rehash(self):
        from core.auth import hash_password, needs_rehash
        h = hash_password("test")
        assert needs_rehash(h) is False

    def test_create_decode_token(self):
        from core.auth import create_token, decode_token
        token = create_token(1, "test@test.com", "free")
        payload = decode_token(token)
        assert payload.user_id == 1
        assert payload.email == "test@test.com"
        assert payload.tier == "free"


# ---------------------------------------------------------------------------
# Session 22-25: New Engine Integration Tests
# ---------------------------------------------------------------------------
class TestEuronextFuturesEngine:
    """Euronext salmon futures data."""

    @pytest.mark.asyncio
    async def test_get_forward_curve(self):
        from core.market.euronext_futures import euronext_futures_engine
        result = await euronext_futures_engine.get_forward_curve()
        assert isinstance(result, dict)
        assert "data_provenance" in result

    @pytest.mark.asyncio
    async def test_get_basis_analysis(self):
        from core.market.euronext_futures import euronext_futures_engine
        result = await euronext_futures_engine.get_basis_analysis()
        assert isinstance(result, dict)


class TestEUMOFAClient:
    """European seafood market data."""

    @pytest.mark.asyncio
    async def test_get_salmon_prices(self):
        from core.market.eumofa_client import eumofa_client
        result = await eumofa_client.get_salmon_prices()
        assert isinstance(result, dict)
        assert "data_provenance" in result

    @pytest.mark.asyncio
    async def test_get_trade_flows(self):
        from core.market.eumofa_client import eumofa_client
        result = await eumofa_client.get_trade_flows()
        assert isinstance(result, dict)


class TestFiskeridirBiomass:
    """Fiskeridirektoratet biomass API."""

    @pytest.mark.asyncio
    async def test_get_national_summary(self):
        from core.market.fiskeridir_biomass import fiskeridir_biomass
        result = await fiskeridir_biomass.get_national_summary()
        assert isinstance(result, dict)
        assert "data_provenance" in result

    @pytest.mark.asyncio
    async def test_get_by_production_area(self):
        from core.market.fiskeridir_biomass import fiskeridir_biomass
        result = await fiskeridir_biomass.get_by_production_area(3)
        assert isinstance(result, dict)


class TestResistanceTracker:
    """Treatment resistance tracking."""

    @pytest.mark.asyncio
    async def test_build_resistance_matrix(self):
        from core.market.resistance_tracker import resistance_tracker
        result = await resistance_tracker.build_resistance_matrix()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_pa_resistance(self):
        from core.market.resistance_tracker import resistance_tracker
        result = await resistance_tracker.get_pa_resistance(3)
        assert isinstance(result, dict)


class TestASCCompliance:
    """ASC Farm Standard compliance checking."""

    @pytest.mark.asyncio
    async def test_audit_readiness(self):
        from core.market.asc_compliance import asc_compliance
        result = await asc_compliance.audit_readiness(10001)
        assert isinstance(result, dict)
        # Should have a readiness score
        assert "readiness_score" in result or "score" in result or "checks" in result

    def test_get_checklist(self):
        from core.market.asc_compliance import asc_compliance
        result = asc_compliance.get_checklist()
        assert isinstance(result, dict)


class TestLiceQuotaTracker:
    """Lice emission quota estimation."""

    @pytest.mark.asyncio
    async def test_national_overview(self):
        from core.market.lice_quota_tracker import lice_quota_tracker
        result = await lice_quota_tracker.national_emission_overview()
        assert isinstance(result, dict)
        assert "data_provenance" in result

    @pytest.mark.asyncio
    async def test_pa_quota_status(self):
        from core.market.lice_quota_tracker import lice_quota_tracker
        result = await lice_quota_tracker.pa_quota_status(3)
        assert isinstance(result, dict)
        assert "lineage" in result  # WS-1

    @pytest.mark.asyncio
    async def test_national_overview_exposes_lineage(self):
        """WS-1: the overview carries the lineage of the rows it aggregated, and its
        provenance follows that lineage (never an unconditional live stamp)."""
        from core.market.lice_quota_tracker import lice_quota_tracker

        result = await lice_quota_tracker.national_emission_overview()
        lineage = result["lineage"]
        assert {"year", "rows_used", "by_class", "sources", "pas", "is_live", "source", "note"} <= set(lineage)
        assert lineage["rows_used"] == sum(lineage["by_class"].values())
        assert len(lineage["pas"]) == 13
        assert result["data_provenance"]["is_live"] == lineage["is_live"]
        assert lineage["is_live"] == (lineage["note"] is None)
        assert lice_quota_tracker.last_lineage == lineage
        assert lice_quota_tracker.last_is_live == lineage["is_live"]

    @pytest.mark.asyncio
    async def test_failed_pa_degrades_national_lineage(self, monkeypatch):
        """A production area whose lice fetch failed must degrade the national
        lineage — a missing input never passes as live."""
        from core import source_lineage as sl
        from core.cache import engine_cache
        from core.market.lice_quota_tracker import lice_quota_tracker as tracker

        original = tracker._get_pa_lice_data

        async def stub(pa):
            if pa == 7:
                lineage = sl.summarise_lineage(
                    {}, year=None, pas=[{"pa": 7, "rows_used": 0, "fetch_failed": True}]
                )
                return [], lineage
            return await original(pa)

        engine_cache.invalidate("lice_quota")
        monkeypatch.setattr(tracker, "_get_pa_lice_data", stub)
        try:
            result = await tracker.national_emission_overview()
            assert result["lineage"]["is_live"] is False
            assert "PA 7" in result["lineage"]["note"]
            assert result["data_provenance"]["is_live"] is False
            assert tracker.last_is_live is False
        finally:
            engine_cache.invalidate("lice_quota")
            tracker._mirror_lineage(None)  # do not leave the stub verdict behind

    def test_cached_lineage_is_re_evaluated_against_now(self):
        """A cached payload built while fresh must not keep serving is_live:true
        after its rows cross the cadence (review finding)."""
        import datetime as dt

        from core import source_lineage as sl
        from core.market import lice_quota_tracker as m

        then = dt.datetime.now(dt.UTC) - dt.timedelta(hours=400)
        iso = then.isocalendar()
        lineage = sl.summarise_lineage(
            {"barentswatch": 5}, year=iso[0], latest_fetched_at=then,
            latest_week=(iso[0], iso[1]),
            pas=[{"pa": 1, "rows_used": 5, "fetch_failed": False}], now=then,
        )
        assert lineage["is_live"] is True
        cached = {"lineage": lineage, "data_provenance": m._provenance_for(lineage, "x", 0.5)}
        assert cached["data_provenance"]["is_live"] is True

        m._refresh_cached_lineage(cached, "x", 0.5)
        assert cached["lineage"]["is_live"] is False
        assert cached["data_provenance"]["is_live"] is False
        assert "fetched" in cached["lineage"]["note"] or "weeks old" in cached["lineage"]["note"]

    @pytest.mark.asyncio
    async def test_locality_emission_provenance_follows_row_lineage(self, monkeypatch):
        """The single-locality path classifies the row it used, too."""
        import datetime as dt

        from core.cache import engine_cache
        from core.market.lice_quota_tracker import lice_quota_tracker as tracker

        now = dt.datetime.now(dt.UTC)
        iso = now.isocalendar()

        def stub_for(source):
            async def _get(locality_no):
                return {
                    "locality_no": locality_no,
                    "locality_name": "stub",
                    "production_area": 3,
                    "company": "X",
                    "avg_adult_female_lice": 0.4,
                    "sea_temp_c": 9.0,
                    "year": iso[0],
                    "week": iso[1],
                    "source": source,
                    "fetched_at": now,
                }
            return _get

        engine_cache.invalidate("lice_emission")
        try:
            monkeypatch.setattr(tracker, "_get_lice_data_for_locality", stub_for("demo_seed"))
            demo = await tracker.estimate_emission(999101)
            assert demo["data_provenance"]["is_live"] is False
            assert "synthetic" in demo["data_provenance"]["fallback_reason"]
            assert demo["lineage"]["by_class"]["synthetic"] == 1

            monkeypatch.setattr(tracker, "_get_lice_data_for_locality", stub_for("barentswatch"))
            real = await tracker.estimate_emission(999102)
            assert real["data_provenance"]["is_live"] is True
            assert real["lineage"]["is_live"] is True
        finally:
            engine_cache.invalidate("lice_emission")
