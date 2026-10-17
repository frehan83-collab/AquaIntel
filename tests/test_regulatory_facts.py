"""WS-21: regulatory facts are dated, sourced data, and every consumer uses them.

Before WS-21 the served traffic-light colours came from the frozen regime detector
(wrong for 6 of 13 areas against the 19 June 2026 decision, with a colour history
keyed on years that had no decision), the decision engine used a 0.5 lice limit all
year, the regulatory reporter applied the 0.2 spring limit only to PA 2-7 in weeks
16-21, a count equal to the limit was not a breach, the weekly lice report was due
"Wednesday", and the US tariffs predated the July 2026 Section 301 action.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from core import regulatory_facts as rf

DECISION_2026 = {
    "green": {1, 12, 13},
    "red": {3},
    "yellow": {2, 4, 5, 6, 7, 8, 9, 10, 11},
}


def _run(coro):
    return asyncio.run(coro)


class TestFactsAreSourced:
    def test_five_decisions_each_colouring_thirteen_areas(self):
        dates = [d.decided_on.isoformat() for d in rf.TRAFFIC_LIGHT_DECISIONS]
        assert dates == ["2017-10-30", "2020-02-04", "2022-06-07", "2024-03-06", "2026-06-19"]
        for d in rf.TRAFFIC_LIGHT_DECISIONS:
            assert sorted(d.colours) == list(range(1, 14))
            assert d.source_url.startswith("https://www.regjeringen.no/")
            assert d.regulation_url.startswith("https://lovdata.no/")

    def test_latest_decision_is_june_2026(self):
        d = rf.traffic_light_decision(dt.date(2026, 10, 17))
        assert d.decided_on == dt.date(2026, 6, 19)
        for colour, pas in DECISION_2026.items():
            assert {pa for pa, c in d.colours.items() if c == colour} == pas
        assert d.capacity_cut_to_pct == {3: 83.06, 4: 83.06, 5: 94.0}
        assert d.cuts_apply_from == dt.date(2027, 2, 20)

    def test_capacity_in_force_follows_the_cut_dates(self):
        # § 9: a cut applies 6 months after the cut regulation enters into force,
        # so the 2026 decision does not change PO3's capacity until 2027-02-20.
        assert rf.capacity_pct(3, dt.date(2026, 10, 17)) == 88.36
        assert rf.capacity_pct(3, dt.date(2027, 3, 1)) == 83.06
        assert rf.capacity_pct(4, dt.date(2026, 10, 17)) == 83.06
        assert rf.capacity_pct(5, dt.date(2026, 10, 17)) == 94.0
        assert rf.capacity_pct(1, dt.date(2026, 10, 17)) == 100.0
        assert rf.capacity_pct(4, dt.date(2020, 3, 1)) == 100.0       # before 2020-08-05
        assert rf.capacity_pct(4, dt.date(2020, 9, 1)) == 94.0
        pending = rf.scheduled_capacity(3, dt.date(2026, 10, 17))
        assert pending["capacity_pct"] == 83.06 and pending["applies_from"] == "2027-02-20"
        assert rf.scheduled_capacity(4, dt.date(2026, 10, 17)) is None
        # in March 2020 the 2022 decision did not exist yet
        assert rf.scheduled_capacity(3, dt.date(2020, 3, 1)) is None
        # decided on 2026-06-19, cut regulation adopted only on 2026-08-20
        july = rf.scheduled_capacity(3, dt.date(2026, 7, 1))
        assert july["capacity_pct"] == 83.06 and july["applies_from"] is None and july["regulation"] is None

    def test_decision_in_force_follows_the_date(self):
        assert rf.traffic_light_decision(dt.date(2025, 1, 1)).decided_on == dt.date(2024, 3, 6)
        assert rf.traffic_light_decision(dt.date(2026, 6, 18)).decided_on == dt.date(2024, 3, 6)
        with pytest.raises(LookupError):
            rf.traffic_light_decision(dt.date(2017, 1, 1))

    def test_history_has_only_real_decision_years(self):
        history = rf.traffic_light_history()
        assert set(history[3]) == {"2017", "2020", "2022", "2024", "2026"}
        assert history[3] == {"2017": "red", "2020": "yellow", "2022": "red", "2024": "red", "2026": "red"}

    def test_every_tariff_row_cites_a_source(self):
        for rows in rf.US_SALMON_TARIFFS.values():
            dates = [row.effective_from for row in rows]
            assert dates == sorted(set(dates)) and dates[0] >= dt.date(2026, 7, 24)
            for row in rows:
                assert row.source_url.startswith("https://")

    def test_tariff_lookup_is_dated(self):
        assert rf.us_salmon_tariff("Norway", dt.date(2026, 10, 17)).rate == 0.125
        with pytest.raises(LookupError):
            rf.us_salmon_tariff("Norway", dt.date(2026, 7, 1))  # no verified row before the 301 action


class TestTrafficLightConsumers:
    def test_simulator_serves_the_official_colours(self, monkeypatch):
        from core.market import traffic_light_simulator as tls

        monkeypatch.setattr(tls, "_now", lambda: dt.datetime(2026, 10, 17, 12, tzinfo=dt.UTC))
        traffic_light_simulator = tls.traffic_light_simulator
        result = _run(traffic_light_simulator.get_current_colors())
        served = {p["production_area"]: p["current_color"] for p in result["production_areas"]}
        assert served == rf.traffic_light_decision(dt.date(2026, 10, 17)).colours
        assert (result["green"], result["yellow"], result["red"]) == (3, 9, 1)
        assert result["decision"]["decided_on"] == "2026-06-19"
        assert result["decision"]["source_url"].startswith("https://www.regjeringen.no/")
        rows = {p["production_area"]: p for p in result["production_areas"]}
        # capacity in force on 2026-10-17, the decided cut separately, no offered growth counted
        assert rows[3]["capacity_pct_in_force"] == 88.36
        assert rows[3]["capacity_change_scheduled"]["capacity_pct"] == 83.06
        assert rows[3]["capacity_change_scheduled"]["applies_from"] == "2027-02-20"
        assert rows[3]["effective_mab_tonnes"] == round(rows[3]["base_mab_tonnes"] * 0.8836, 0)
        assert rows[1]["effective_mab_tonnes"] == rows[1]["base_mab_tonnes"]  # green: growth offered, not taken

        monkeypatch.setattr(tls, "_now", lambda: dt.datetime(2027, 3, 1, 12, tzinfo=dt.UTC))
        later = {p["production_area"]: p for p in _run(traffic_light_simulator.get_current_colors())["production_areas"]}
        assert later[3]["capacity_pct_in_force"] == 83.06 and later[3]["capacity_change_scheduled"] is None

    def test_simulations_cite_the_decision(self, monkeypatch):
        from core.market import traffic_light_simulator as tls

        monkeypatch.setattr(tls, "_now", lambda: dt.datetime(2026, 10, 17, 12, tzinfo=dt.UTC))
        traffic_light_simulator = tls.traffic_light_simulator

        one = _run(traffic_light_simulator.simulate_color_change(3, "yellow"))
        assert one["current_decision"]["decided_on"] == "2026-06-19"
        assert "Q2" not in one["effective_date"] and "§ 9" in one["effective_date"]
        allp = _run(traffic_light_simulator.simulate_all_pas())
        assert allp["current_decision"]["source_url"].startswith("https://www.regjeringen.no/")

    def test_route_cites_the_decision(self, monkeypatch):
        from fastapi.testclient import TestClient

        from core.api import app
        from core.market import traffic_light_simulator as tls

        monkeypatch.setattr(tls, "_now", lambda: dt.datetime(2026, 10, 17, 12, tzinfo=dt.UTC))

        body = TestClient(app).get("/api/regulatory/traffic-light/current").json()
        assert {p["production_area"]: p["current_color"] for p in body["production_areas"]}[3] == "red"
        prov = body["data_provenance"]
        assert "2026-06-19" in prov["source"] and "BarentsWatch" not in prov["source"]

    def test_frozen_regime_detector_reads_the_official_colours(self):
        # Maintenance fix only: the detector's tables now come from the facts.
        from core.market import regime_detector as rd

        assert rd.CURRENT_COLORS == rf.traffic_light_decision().colours
        assert rd.HISTORICAL_COLORS == rf.traffic_light_history()


class TestLiceLimit:
    @pytest.mark.parametrize(
        "pa, week, municipality, county, expected",
        [
            (3, 15, None, None, 0.5),
            (3, 16, None, None, 0.2),
            (1, 17, None, None, 0.2),      # PA 1 was missed by the old reporter rule
            (7, 21, None, None, 0.2),      # week 21 is spring everywhere
            (3, 22, None, None, 0.5),
            (9, 20, None, None, 0.5),
            (9, 21, None, None, 0.2),
            (9, 26, None, None, 0.2),      # the northern window was missing entirely
            (9, 27, None, None, 0.5),
            (7, 23, "Bindal", None, 0.2),  # Bindal is in Nordland
            (7, 23, "SØMNA", None, 0.2),   # so are Sømna and Brønnøy (PO7/PO8 line at Vennesundet)
            (7, 18, "SØMNA", None, 0.5),
            (7, 23, "BRØNNØY", None, 0.2),
            (7, 18, "Brønnøy", None, 0.5),
            (7, 23, None, None, 0.5),
            (6, 23, None, "Nordland", 0.2),  # county wins over the area
            (10, 24, None, "18", 0.2),       # county number 18 = Nordland
            (3, 18, None, "46", 0.2),        # 46 = Vestland
            (10, 24, None, "  ", 0.2),       # blank county falls through to the area
            (10, 24, None, "Ukjent", 0.2),   # unrecognised county falls through to the area
            (10, 24, None, "Romsa", 0.2),    # Sámi name for Troms
            (5, 18, None, "Møre og Romsdal", 0.2),
            (None, 18, None, None, 0.2),     # unknown region in a window: precautionary
            (None, 30, None, None, 0.5),
            (None, 23, None, "Vestland", 0.5),   # the county alone decides (no PA)
            (None, 18, None, "Nordland", 0.5),
            (None, 23, None, "46", 0.5),
            (7, 23, None, "18", 0.2),            # a Nordland county number moves a PO7 site north
        ],
    )
    def test_limit_by_area_week_and_county(self, pa, week, municipality, county, expected):
        assert rf.lice_limit(pa, week, municipality=municipality, county=county).limit == expected

    def test_unknown_region_is_flagged_not_established(self):
        assert rf.lice_limit(None, 23, county="Vestland").established is True
        assert rf.lice_limit(None, 18).established is False
        assert rf.lice_limit(None, 21).established is True   # week 21: both windows
        assert rf.lice_limit(3, 18).established is True
        as_dict = rf.lice_limit(3, 18).as_dict()
        assert as_dict["trigger_basis"].startswith("product rule")

    def test_equal_to_the_limit_is_a_breach(self):
        assert rf.breaches_limit(0.2, 0.2) is True
        assert rf.breaches_limit(0.19, 0.2) is False
        assert rf.breaches_limit(0.5, 0.5) is True


class TestDecisionEngine:
    def _engine(self):
        from core.market.decision_engine import DecisionEngine

        return DecisionEngine()

    def test_spring_limit_changes_the_action(self):
        spring = rf.lice_limit(3, 18)
        action, urgency, _ = self._engine()._compute_action(
            lice=0.25, trend="stable", temp=8.0, gnn_pred=None, limit=spring
        )
        assert (action, urgency) == ("TREAT_NOW", "immediate")

    def test_a_breach_is_never_monitor_only(self):
        # Above the legal limit the farm is in breach whatever the trend.
        action, _, reasoning = self._engine()._compute_action(
            lice=0.6, trend="declining", temp=10.0, gnn_pred=None
        )
        assert action == "TREAT_NOW"
        assert any("limit" in r for r in reasoning)

    def test_equal_to_the_limit_triggers(self):
        action, _, _ = self._engine()._compute_action(
            lice=0.5, trend="stable", temp=10.0, gnn_pred=None
        )
        assert action == "TREAT_NOW"

    def test_explanation_uses_the_limit_in_force(self):
        def lice_text(limit):
            expl = self._engine()._compute_feature_importance(
                0.31, "stable", 8.0, None, "TREAT_NOW", limit=limit
            )
            return {f["name"]: f["en"] for f in expl["factors"]}

        spring = lice_text(rf.lice_limit(3, 18))
        assert spring["lice_level"] == "Lice level 0.31 is at or above the legal limit (0.2)"
        assert spring["regulatory_distance"].startswith("Already exceeding regulatory limit by 0.11")
        autumn = lice_text(rf.lice_limit(3, 40))
        assert autumn["lice_level"] == "Lice level 0.31 exceeds warning threshold (0.3)"

    def test_precautionary_limit_is_worded_as_such(self):
        _, _, reasoning = self._engine()._compute_action(
            lice=0.3, trend="stable", temp=8.0, gnn_pred=None, limit=rf.lice_limit(None, 18)
        )
        assert reasoning[0].startswith("Lice 0.30 at or above the precautionary limit (0.2;")
        expl = self._engine()._compute_feature_importance(
            0.3, "stable", 8.0, None, "TREAT_NOW", limit=rf.lice_limit(None, 18)
        )
        texts = {f["name"]: f for f in expl["factors"]}
        assert "precautionary" in texts["regulatory_distance"]["en"]
        assert "føre-var-grensen" in texts["regulatory_distance"]["no"]
        assert "regulatorisk" not in texts["regulatory_distance"]["no"]

    @staticmethod
    def _card(monkeypatch, *, now, count_week, lice, place=(3, "KVINNHERAD", None)):
        from core.market import decision_engine as de

        engine = de.DecisionEngine()

        async def lice_data(_):
            return {"current": lice, "current_year": 2026, "current_week": count_week, "sea_temp_c": 8.0,
                    "trend": "stable", "history": [{"lice": lice, "week": count_week, "year": 2026}]}

        async def none(*_a, **_k):
            return None

        async def info(_):
            return place

        monkeypatch.setattr(engine, "_get_lice_data", lice_data)
        monkeypatch.setattr(engine, "_get_gnn_prediction", none)
        monkeypatch.setattr(engine, "_get_ocean_forecast", none)
        monkeypatch.setattr(engine, "_get_learned_profiles", none)
        monkeypatch.setattr(engine, "_locality_info", info)
        monkeypatch.setattr(de, "_now", lambda: now)
        return _run(engine.get_decision(12345))

    def test_window_opening_uses_this_weeks_limit(self, monkeypatch):
        # Monday of week 16 at 00:30 Oslo is still week 15 in UTC; the W15 count of
        # 0.25 is above the 0.2 limit now in force, so the advice is to treat.
        card = self._card(monkeypatch, now=dt.datetime(2026, 4, 12, 22, 30, tzinfo=dt.UTC), count_week=15, lice=0.25)
        assert card["action"] == "TREAT_NOW"
        lim = card["regulatory_limit"]
        assert lim["limit"] == 0.2 and lim["evaluated_for"] == "2026-W16"
        assert lim["count_week"] == "2026-W15" and lim["count_week_limit"] == 0.5
        assert lim["count_breached_its_week_limit"] is False
        assert lim["source_url"].startswith("https://lovdata.no/")

    def test_window_closing_reports_the_past_breach_without_urgency(self, monkeypatch):
        card = self._card(monkeypatch, now=dt.datetime(2026, 5, 25, 9, tzinfo=dt.UTC), count_week=21, lice=0.25)
        assert card["action"] == "NO_ACTION"           # 0.25 is below this week's 0.5 and trigger 0.3
        lim = card["regulatory_limit"]
        assert lim["limit"] == 0.5 and lim["count_week_limit"] == 0.2
        assert lim["count_breached_its_week_limit"] is True
        assert any("breached that week's limit (0.2)" in r for r in card["reasoning"])

    def test_somna_site_follows_the_northern_window(self, monkeypatch):
        card = self._card(monkeypatch, now=dt.datetime(2026, 6, 3, 9, tzinfo=dt.UTC), count_week=22,
                          lice=0.25, place=(7, "SØMNA", None))
        assert card["action"] == "TREAT_NOW"
        assert card["regulatory_limit"]["region"] == "north" and card["regulatory_limit"]["limit"] == 0.2
        early = self._card(monkeypatch, now=dt.datetime(2026, 4, 29, 9, tzinfo=dt.UTC), count_week=17,
                           lice=0.25, place=(7, "SØMNA", None))
        assert early["regulatory_limit"]["limit"] == 0.5 and early["action"] != "TREAT_NOW"

    def test_history_bars_carry_their_own_weeks_limit(self, monkeypatch):
        card = self._card(monkeypatch, now=dt.datetime(2026, 4, 12, 22, 30, tzinfo=dt.UTC), count_week=15, lice=0.25)
        assert card["lice_history"][0]["limit"] == 0.5   # W15, outside the window

    def test_card_seams_read_the_database(self, lice_store, monkeypatch):
        from core.market import decision_engine as de

        monkeypatch.setattr("core.market.decision_engine.get_async_session", lice_store)
        engine = de.DecisionEngine()
        assert _run(engine._locality_info(91003)) == (7, "SØMNA", None)
        data = _run(engine._get_lice_data(91003))
        assert (data["current_year"], data["current_week"]) == (2026, 23)


@pytest.fixture
def lice_store(tmp_path, monkeypatch):
    """A throwaway async database bound to the regulatory reporter."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base, LiceRecord, Locality

    engine = create_async_engine(f"sqlite+aiosqlite:///{Path(tmp_path) / 'lice.db'}")
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    sites = [
        (91001, "Nord site", 9, None, None, [(2026, 23, 0.21)]),
        (91002, "Vest site", 3, None, None, [(2026, 23, 0.21), (2026, 30, 0.5)]),
        (91003, "Somna site", 7, "SØMNA", None, [(2026, 23, 0.21), (2026, 18, 0.3)]),
        (91004, "No-PA site", None, None, None, [(2026, 18, 0.3), (2026, 19, 0.55)]),
        (91005, "County-only site", None, None, "Vestland", [(2026, 18, 0.3), (2026, 23, 0.3)]),
    ]

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as s:
            for no, name, pa, muni, county, counts in sites:
                s.add(Locality(locality_no=no, name=name, production_area=pa, municipality=muni, county=county))
                for year, week, af in counts:
                    s.add(LiceRecord(locality_no=no, year=year, week=week, avg_adult_female_lice=af,
                                     avg_mobile_lice=0.1, avg_stationary_lice=0.1))
            await s.commit()

    asyncio.run(setup())

    @asynccontextmanager
    async def session():
        async with factory() as s:
            yield s

    monkeypatch.setattr("core.market.regulatory_reporter.get_async_session", session)
    return session


class TestRegulatoryReporter:
    def test_threshold_uses_the_regulation(self):
        from core.market.regulatory_reporter import applicable_lice_limit

        assert applicable_lice_limit(1, 17).limit == 0.2
        assert applicable_lice_limit(9, 23).limit == 0.2
        assert applicable_lice_limit(3, 23).limit == 0.5

    @pytest.mark.parametrize(
        "locality, week, threshold, exceeds",
        [
            (91001, 23, 0.2, True),    # northern window
            (91002, 23, 0.5, False),   # southern, outside its window
            (91002, 30, 0.5, True),    # equal to the limit is a breach
            (91003, 23, 0.2, True),    # Sømna: Nordland, northern window
            (91003, 18, 0.5, False),   # Sømna is not in the southern window
            (91004, 18, 0.2, None),    # region unknown: 0.3 is a breach in one window only
            (91004, 19, 0.2, True),    # 0.55 is a breach in either window
            (91005, 18, 0.2, True),    # county Vestland: southern window, established
            (91005, 23, 0.5, False),
        ],
    )
    def test_weekly_report_judges_the_count(self, lice_store, locality, week, threshold, exceeds):
        from core.market.regulatory_reporter import regulatory_reporter

        report = _run(regulatory_reporter.generate_weekly_lice_report(locality, week, 2026))
        data = report.data
        assert data["threshold"] == threshold
        assert data["exceeds_threshold"] is exceeds
        assert data["threshold_source"].startswith("https://lovdata.no/")

    def test_weekly_report_due_tuesday(self):
        from core.market import regulatory_reporter as rr

        assert rr.LICE_REPORT_DUE_DAY == 1
        deadlines = _run(rr.regulatory_reporter.get_upcoming_deadlines(days_ahead=14))
        lice = [d for d in deadlines if d.report_type == "weekly_lice"]
        assert lice and all(dt.date.fromisoformat(d.due_date).weekday() == 1 for d in lice)


class TestCompetitivenessTariffs:
    def test_engine_tariffs_come_from_the_facts(self, monkeypatch):
        from core.market import competitiveness_engine as ce

        engine = ce.CompetitivenessEngine()

        async def fx():
            return {"NOK": 0.094, "CLP": 0.00105, "GBP": 1.27, "CAD": 0.73, "DKK": 0.145, "ISK": 0.0072}

        async def cost():
            return 74.0

        async def spot():
            return 11.0

        monkeypatch.setattr(ce, "_now", lambda: dt.datetime(2026, 10, 17, 12, tzinfo=dt.UTC))
        monkeypatch.setattr(engine, "_fetch_fx_rates", fx)
        monkeypatch.setattr(engine, "_get_norway_cost_nok", cost)
        monkeypatch.setattr(engine, "_get_us_spot", spot)
        out = _run(engine.compute_index())
        origins = {o["country"]: o for o in out["origins"]}
        for country, o in origins.items():
            assert o["tariff"]["rate_pct"] == round(o["tariff_pct"] * 100, 2), country
            assert o["tariff_pct"] == rf.us_salmon_tariff(country, dt.date(2026, 10, 17)).rate
        assert origins["Norway"]["tariff_pct"] == 0.125 and origins["Chile"]["tariff_pct"] == 0.125
        assert origins["Scotland"]["tariff_pct"] == 0.10
        assert "tariff_us_pct" not in ce.ORIGIN_BASELINES["Norway"]  # one source: the facts module
        assert not any("12% " in line or "12% tariff" in line for line in out["insights"])  # 12.5 never rounds to 12

    def test_notes_carry_no_stale_tariff_text(self):
        from core.market.competitiveness_engine import ORIGIN_BASELINES

        stale = ("15% US tariff", "US-Chile FTA)", "2.5% MFN", "Same as Norway", "US-Iceland trade agreement")
        for origin, cfg in ORIGIN_BASELINES.items():
            assert not any(s in cfg["notes"] for s in stale), (origin, cfg["notes"])

    def test_origin_rows_cite_their_tariff(self):
        from core.market.competitiveness_engine import (
            CompetitivenessSnapshot,
            OriginCost,
            competitiveness_engine,
        )

        row = competitiveness_engine.tariff_row("Norway")
        assert row["rate_pct"] == 12.5 and row["source_url"].startswith("https://www.federalregister.gov/")
        snap = CompetitivenessSnapshot(origins=[OriginCost(
            country="Norway", flag="", currency="NOK", local_cost_per_kg=74.0, fx_rate_to_usd=0.1,
            production_cost_usd=7.4, tariff_pct=0.125, tariff_cost_usd=0.93, freight_usd=0.45,
            total_delivered_usd=8.78, margin_usd=0.0, margin_pct=0.0,
            tariff_row=row,
        )])
        origin = competitiveness_engine._to_dict(snap)["origins"][0]
        assert origin["tariff"]["rate_pct"] == origin["tariff_pct"] * 100

    def test_scenario_rows_do_not_carry_the_official_citation(self, monkeypatch):
        from core.market.competitiveness_engine import (
            CompetitivenessSnapshot,
            OriginCost,
            competitiveness_engine,
        )

        def origin(country, pct):
            return OriginCost(
                country=country, flag="", currency="X", local_cost_per_kg=1.0, fx_rate_to_usd=1.0,
                production_cost_usd=7.0, tariff_pct=pct, tariff_cost_usd=7.0 * pct, freight_usd=0.4,
                total_delivered_usd=7.4 + 7.0 * pct, margin_usd=0.0, margin_pct=0.0,
                tariff_row=competitiveness_engine.tariff_row(country, dt.datetime(2026, 10, 17, tzinfo=dt.UTC)),
            )

        snap = CompetitivenessSnapshot(origins=[origin("Norway", 0.125), origin("Chile", 0.125)])
        monkeypatch.setattr(competitiveness_engine, "_cache", snap)
        result = competitiveness_engine.compute_tariff_scenarios({"Norway": 0})
        rows = {o["country"]: o for o in result["scenario_origins"]}
        assert rows["Norway"]["tariff_scenario_override"] is True and rows["Norway"]["tariff"] is None
        assert rows["Chile"]["tariff"]["source_url"].startswith("https://www.federalregister.gov/")


class TestFrontendCarriesNoRetiredFacts:
    PAGES = ("competitiveness", "global-supply", "traffic-light", "exposure", "lice-quota")
    STALE = (
        r">\s*15\s*%\s*<", r"\b15\s?%\s*(tariff|\(|toll|p\u00e5|på)", r"Since Apr 2025", r"apr\. 2025",
        r"UK deal", r">\s*2\.5%\s*<", r"FTA 0%", r"0% FTA", r"FTA / USMCA", r"2027-2029",
        r"Q4, effective Q2", r'source="BarentsWatch" quality="live"', r"targeted 2026-2028",
        r"biannual reviews \(2017",
    )

    @pytest.mark.parametrize("page", PAGES)
    def test_no_retired_tariff_or_framework_text(self, page):
        import re

        src = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "app" / page / "page.tsx").read_text(encoding="utf-8")
        hits = [pat for pat in self.STALE if re.search(pat, src)]
        assert not hits, (page, hits)

    def test_backend_quota_note_matches_the_facts(self):
        src = (Path(__file__).resolve().parents[1] / "core" / "market" / "lice_quota_tracker.py").read_text(encoding="utf-8")
        assert "targeted 2026-2028" not in src and "Meld. St. 24" in src
