"""WS-22: claims that outran the data.

Four buyer-visible defects, one regression test per fix:
  1. competitiveness reported `data_quality: live` while FX had fallen back to
     the hardcoded NOK/USD 0.093;
  2. `foundation_models_available` was "does `torch` import";
  3. `/api/disease/norway` sliced the first 20 upstream rows, hiding the newest;
  4. `/api/disease/alerts` named Mattilsynet in its provenance but never
     queried it, so it could say "no outbreaks" while ISA cases were active.
"""
from __future__ import annotations

import asyncio

import pytest

from core.market.competitiveness_engine import (
    FALLBACK_FX,
    CompetitivenessEngine,
    CompetitivenessSnapshot,
)


def run_async(coro):
    """Run async coroutine in sync test context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _engine(fx_fallbacks=(), norway_fallback=False) -> CompetitivenessEngine:
    engine = CompetitivenessEngine()
    engine._fx_fallbacks = list(fx_fallbacks)
    engine._norway_cost_is_fallback = norway_fallback
    return engine


class TestCompetitivenessFxHonesty:
    def test_fx_fallback_is_named_and_not_live(self):
        out = _engine(["NOK"])._to_dict(CompetitivenessSnapshot())

        assert out["data_quality"] == "partial_fallback"
        assert out["fx_fallbacks"] == ["NOK"]
        assert out["fx_fallback_values"]["NOK"] == FALLBACK_FX["NOK"]
        assert "NOK" in out["fallback_reason"]
        assert out["data_provenance"]["is_live"] is False

    def test_live_only_when_no_quote_fell_back(self):
        out = _engine([])._to_dict(CompetitivenessSnapshot())

        assert out["data_quality"] == "live"
        assert out["fx_fallbacks"] == []
        assert out["fallback_reason"] is None
        assert out["data_provenance"]["is_live"] is True

    def test_cost_fallback_is_reported_alongside_fx(self):
        out = _engine(["NOK"], norway_fallback=True)._to_dict(CompetitivenessSnapshot())

        assert out["data_quality"] == "stale_fallback"
        assert out["fallback_value"] is True
        assert "2024" in out["fallback_reason"]
        assert "NOK" in out["fallback_reason"]

    def test_fetch_records_every_currency_that_fell_back(self, monkeypatch):
        from core.market.macro_intelligence import macro_intelligence

        async def macro_down():
            raise RuntimeError("macro down")

        class _BoomClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                raise RuntimeError("yahoo down")

            async def __aexit__(self, *exc):
                return False

        monkeypatch.setattr(macro_intelligence, "fetch", macro_down)
        monkeypatch.setattr(
            "core.market.competitiveness_engine.httpx.AsyncClient", _BoomClient
        )

        engine = CompetitivenessEngine()
        rates = run_async(engine._fetch_fx_rates())

        assert set(engine._fx_fallbacks) == set(FALLBACK_FX)
        assert rates["NOK"] == FALLBACK_FX["NOK"]
        assert engine._to_dict(CompetitivenessSnapshot())["data_quality"] == "partial_fallback"


class TestFoundationModelAvailability:
    def _probe(self, modules):
        return lambda name: name if name in modules else None

    def test_torch_alone_is_not_availability(self):
        from core.routers.accuracy_routes import _foundation_model_availability

        out = _foundation_model_availability(probe=self._probe({"torch"}))

        assert out["foundation_models_available"] is False
        assert out["foundation_models_installed"] == []
        assert "none of chronos-forecasting" in out["foundation_models_note"]

    def test_missing_torch_is_named(self):
        from core.routers.accuracy_routes import _foundation_model_availability

        out = _foundation_model_availability(probe=self._probe(set()))

        assert out["foundation_models_available"] is False
        assert "torch is not installed" in out["foundation_models_note"]

    def test_one_model_library_makes_it_available(self):
        from core.routers.accuracy_routes import _foundation_model_availability

        out = _foundation_model_availability(probe=self._probe({"torch", "timesfm"}))

        assert out["foundation_models_available"] is True
        assert out["foundation_models_installed"] == ["timesfm"]
        assert out["foundation_models"]["timesfm"]["installed"] is True
        assert out["foundation_models"]["chronos"]["installed"] is False
        assert "not proof that a forecast was real" in out["foundation_models_note"]

    def test_each_model_requires_its_own_library(self):
        from core.routers.accuracy_routes import _foundation_model_availability

        out = _foundation_model_availability(probe=self._probe({"torch", "uni2ts"}))

        assert out["foundation_models_installed"] == ["moirai"]
        assert out["foundation_models"]["moirai"]["requires"] == "uni2ts"
        assert all(
            isinstance(v["loaded"], bool) for v in out["foundation_models"].values()
        )
class TestFoundationModelDisclosure:
    def test_disclosure_wires_the_helper(self):
        from core.routers import accuracy_routes

        disclosure = run_async(accuracy_routes._fallback_disclosure())

        assert disclosure["foundation_models_available"] == (
            accuracy_routes._foundation_model_availability()["foundation_models_available"]
        )
        assert set(disclosure["foundation_models"]) == {"chronos", "timesfm", "moirai"}
        assert disclosure["foundation_models_note"]


class TestCompetitivenessLivePath:
    def test_live_nok_rate_is_used_when_macro_answers(self, monkeypatch):
        """The macro import name was wrong, so NOK always fell back."""
        from core.market.macro_intelligence import macro_intelligence

        class _Snapshot:
            series = {"nok_usd": 9.57, "global_salmon": 9.1}

        async def fake_fetch():
            return _Snapshot()

        class _BoomClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                raise RuntimeError("yahoo down")

            async def __aexit__(self, *exc):
                return False

        monkeypatch.setattr(macro_intelligence, "fetch", fake_fetch)
        monkeypatch.setattr(
            "core.market.competitiveness_engine.httpx.AsyncClient", _BoomClient
        )

        engine = CompetitivenessEngine()
        rates = run_async(engine._fetch_fx_rates())

        assert rates["NOK"] == pytest.approx(1.0 / 9.57)
        assert "NOK" not in engine._fx_fallbacks
        assert set(engine._fx_fallbacks) == set(FALLBACK_FX) - {"NOK"}

    def test_untracked_spot_fallback_degrades_quality(self, monkeypatch):
        from core.market.macro_intelligence import macro_intelligence

        async def macro_down():
            raise RuntimeError("macro down")

        monkeypatch.setattr(macro_intelligence, "fetch", macro_down)

        engine = CompetitivenessEngine()
        assert run_async(engine._get_us_spot()) == 8.50
        assert engine._us_spot_is_fallback is True

        out = engine._to_dict(CompetitivenessSnapshot())
        assert out["us_spot_fallback"] is True
        assert out["data_quality"] == "partial_fallback"
        assert "8.50" in out["fallback_reason"]
        assert out["data_provenance"]["is_live"] is False


class TestMattilsynetFetchStatus:
    def test_status_survives_a_cache_hit(self, monkeypatch):
        from core.market import mattilsynet_client as mod

        class _Response:
            status_code = 200

            @staticmethod
            def json():
                return [{
                    "id": "1",
                    "lokalitetsnummer": 12345,
                    "lokalitetsnavn": "Test",
                    "sykdomstype": "ILA",
                    "sykdomssubtype": "ILA_HPR0",
                    "arter": [{"artskode": "SAL"}],
                }]

        class _Client:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, *args, **kwargs):
                return _Response()

        monkeypatch.setattr(mod.httpx, "AsyncClient", _Client)

        client = mod.MattilsynetClient()
        assert len(run_async(client.fetch_disease_cases())) == 1
        assert client.last_fetch_ok is True

        # Second call is served from cache; it must not reset the status to
        # "failed" (it used to, so an answered source looked silent).
        assert len(run_async(client.fetch_disease_cases())) == 1
        assert client.last_fetch_ok is True


class TestMattilsynetProvenance:
    def test_live_only_when_rows_were_returned(self):
        from core.routers.disease_routes import _mattilsynet_provenance

        live = _mattilsynet_provenance(True, 3, "none returned")
        assert live.is_live is True
        assert "WOAH" not in live.source
        assert live.source.startswith("Mattilsynet")

        empty = _mattilsynet_provenance(True, 0, "no active cases returned")
        assert empty.is_live is False
        assert empty.fallback_reason == "no active cases returned"

        silent = _mattilsynet_provenance(False, 0, "no active cases returned")
        assert silent.is_live is False
        assert silent.fallback_reason == "Mattilsynet did not answer"


class TestDiseaseListOrdering:
    @staticmethod
    def _case(i: int, diagnosis: str | None = None, suspicion: str | None = None):
        from core.market.mattilsynet_client import DiseaseCase

        return DiseaseCase(
            id=str(i),
            locality_no=i,
            locality_name=f"Locality {i}",
            disease_type="ILA",
            disease_subtype="ILA_HPR0",
            species="SAL",
            suspicion_date=suspicion,
            diagnosis_date=diagnosis,
        )

    def test_newest_first_not_upstream_order(self):
        from core.market.mattilsynet_client import newest_first_cases

        # Upstream order is oldest-first; the old slice showed exactly these.
        cases = [self._case(i, diagnosis=f"2026-06-{i:02d}") for i in range(1, 26)]
        shown = newest_first_cases(cases, limit=20)

        assert len(shown) == 20
        assert shown[0].diagnosis_date == max(c.diagnosis_date for c in cases)
        assert "2026-06-01" not in {c.diagnosis_date for c in shown}

    def test_undated_cases_sort_last(self):
        from core.market.mattilsynet_client import newest_first_cases

        cases = [
            self._case(1),
            self._case(2, diagnosis="2026-09-22"),
            self._case(3, suspicion="2026-08-01"),
        ]
        shown = newest_first_cases(cases, limit=3)

        assert [c.diagnosis_date for c in shown] == ["2026-09-22", None, None]
        assert shown[1].suspicion_date == "2026-08-01"

    def test_summary_labels_shown_against_total(self, monkeypatch):
        from core.market import mattilsynet_client as mod

        class _NoHTTP:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def get(self, *args, **kwargs):
                raise RuntimeError("no network in tests")

        monkeypatch.setattr(mod.httpx, "Client", _NoHTTP)
        monkeypatch.setattr(mod.mattilsynet_client, "_lice_company_cache", {})

        cases = [self._case(i, diagnosis=f"2026-06-{i:02d}") for i in range(1, 26)]
        summary = run_async(mod.mattilsynet_client.get_disease_summary(cases))

        assert summary["active_outbreaks_total"] == 25
        assert summary["active_outbreaks_shown"] == 20
        assert len(summary["active_outbreaks"]) == 20
        assert summary["active_outbreaks"][0]["diagnosis_date"] == "2026-06-25"


class TestDiseaseAlertSources:
    @staticmethod
    def _isa_case():
        from core.market.mattilsynet_client import DiseaseCase

        return DiseaseCase(
            id="1",
            locality_no=12345,
            locality_name="Test Locality",
            disease_type="ILA",
            disease_subtype="ILA_HPR0",
            species="SAL",
            suspicion_date="2026-09-01",
            diagnosis_date="2026-09-22",
        )

    def test_mattilsynet_cases_become_active_alerts(self, monkeypatch):
        from core.market import disease_alerts as mod
        from core.market.mattilsynet_client import mattilsynet_client
        from core.market.regime_detector import regime_detector

        async def fake_cases(limit=200):
            return [self._isa_case()]

        monkeypatch.setattr(mattilsynet_client, "fetch_disease_cases", fake_cases)
        monkeypatch.setattr(mattilsynet_client, "last_fetch_ok", True)
        monkeypatch.setattr(regime_detector, "get_alerts", lambda: [])

        engine = mod.DiseaseAlertEngine()
        alerts = run_async(engine._fetch_norway_alerts())

        assert [a.source for a in alerts] == ["mattilsynet"]
        assert alerts[0].status == "ongoing"
        assert alerts[0].severity == "high"
        assert alerts[0].trade_impact is True
        assert alerts[0].report_date == "2026-09-22"
        assert engine._source_status["mattilsynet"] == "ok"

    def test_silent_upstream_is_reported_as_failed(self, monkeypatch):
        from core.market import disease_alerts as mod
        from core.market.mattilsynet_client import mattilsynet_client
        from core.market.regime_detector import regime_detector

        async def silent(limit=200):
            return []

        monkeypatch.setattr(mattilsynet_client, "fetch_disease_cases", silent)
        monkeypatch.setattr(mattilsynet_client, "last_fetch_ok", False)
        monkeypatch.setattr(regime_detector, "get_alerts", lambda: [])

        engine = mod.DiseaseAlertEngine()
        alerts = run_async(engine._fetch_norway_alerts())

        assert alerts == []
        assert engine._source_status["mattilsynet"] == "failed"

    def test_provenance_names_only_sources_that_answered(self):
        from core.routers.disease_routes import _alerts_provenance

        live = _alerts_provenance({"woah_wahis": "ok", "mattilsynet": "ok"}, alerts=2)
        assert live.is_live is True
        assert live.source == "mattilsynet + woah_wahis"

        partial = _alerts_provenance({"woah_wahis": "ok", "mattilsynet": "failed"}, alerts=2)
        assert partial.is_live is False
        assert "mattilsynet" in (partial.fallback_reason or "")
        assert "mattilsynet" not in partial.source

        empty = _alerts_provenance({"woah_wahis": "ok", "mattilsynet": "ok"}, alerts=0)
        assert empty.is_live is False
        assert "no outbreaks" in (empty.fallback_reason or "")

        nothing = _alerts_provenance({"woah_wahis": "failed"})
        assert nothing.is_live is False
        assert "no upstream disease source answered" in (nothing.fallback_reason or "")

    def test_locality_rows_collapse_to_one_alert_per_disease(self, monkeypatch):
        from core.market import disease_alerts as mod
        from core.market.mattilsynet_client import DiseaseCase, mattilsynet_client
        from core.market.regime_detector import regime_detector

        async def twelve_pd_localities(limit=200):
            return [
                DiseaseCase(
                    id=str(i),
                    locality_no=i,
                    locality_name=f"L{i}",
                    disease_type="PANKREASSYKDOM",
                    disease_subtype="PD_SAV2",
                    species="SAL",
                    diagnosis_date="2026-09-01",
                )
                for i in range(12)
            ]

        monkeypatch.setattr(mattilsynet_client, "fetch_disease_cases", twelve_pd_localities)
        monkeypatch.setattr(mattilsynet_client, "last_fetch_ok", True)
        monkeypatch.setattr(regime_detector, "get_alerts", lambda: [])

        alerts = run_async(mod.DiseaseAlertEngine()._fetch_norway_alerts())

        # One alert per disease type: 12 localities must not read as 12 outbreaks.
        assert len(alerts) == 1
        assert alerts[0].cases == 12
        assert alerts[0].severity == "moderate"
        assert alerts[0].report_date == "2026-09-01"

    def test_payload_carries_sources_and_failures(self):
        from core.market.disease_alerts import DiseaseIntelligence, disease_alert_engine

        payload = disease_alert_engine.to_dict(
            DiseaseIntelligence(sources={"woah_wahis": "failed", "mattilsynet": "ok"})
        )

        assert payload["sources"] == {"woah_wahis": "failed", "mattilsynet": "ok"}
        assert payload["sources_failed"] == ["woah_wahis"]
