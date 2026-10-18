"""WS-35 — a company volume is a reported harvest, not a locality count × 800 t.

`top50_engine` derived production as `n_localities * 800` and shipped it as a volume:
Mowi read **113 600 t** against roughly **332 000 t** harvested in Norway in 2025 — a 3×
understatement of the largest producer, on the analyst desk. The multiplier is retired;
volumes now come from dated, sourced facts, and a company without one reports `None`
rather than a number nobody measured.
"""
from __future__ import annotations

import inspect

import pytest

from core.market import company_facts
from core.market.top50_engine import CompanyProfile, Top50Engine


# ── 1. The facts ────────────────────────────────────────────────────────


def test_mowi_reports_its_reported_norway_harvest():
    assert company_facts.volume_or_none("MOWI ASA") == 332_000
    basis = company_facts.volume_basis("MOWI ASA")
    assert basis["basis"] == "reported"
    assert basis["year"] == 2025
    assert basis["scope"] == "Norway", "a Norway figure must not be read as a group figure"
    assert basis["source_url"].startswith("https://")
    assert basis["entity"] == "Mowi ASA"


def test_an_unknown_company_is_none_and_says_why():
    assert company_facts.volume_or_none("Some Fjord Salmon AS") is None
    basis = company_facts.volume_basis("Some Fjord Salmon AS")
    assert basis["basis"] == "unknown"
    assert "not estimated from locality counts" in basis["source"]
    assert str(int(company_facts.RETIRED_PER_SITE_MULTIPLIER_TONNES)) in basis["source"]


def test_a_sub_entity_does_not_repeat_the_group_volume():
    """MOWI FEED AS is not a farming entity; repeating the harvest would double-count."""
    assert company_facts.volume_or_none("MOWI FEED AS") is None
    basis = company_facts.volume_basis("MOWI FEED AS")
    assert basis["basis"] == "sub_entity"
    assert basis["entity"] == "Mowi ASA"


def test_the_retired_multiplier_is_not_used_in_the_compute_path():
    from core.market import top50_engine

    source = inspect.getsource(top50_engine)
    # The old expression was `production_volume_tonnes=n_locs * 800`; only the comment
    # that explains the retirement may mention the multiplier.
    compute_lines = [
        line for line in source.splitlines()
        if "800" in line and not line.strip().startswith("#")
    ]
    assert compute_lines == [], compute_lines
    assert "volume_or_none(name)" in source
    assert "volume_basis(name)" in source


# ── 2. The payload ─────────────────────────────────────────────────────


def test_an_unknown_volume_serialises_as_null_not_zero():
    engine = Top50Engine()
    profile = CompanyProfile(name="Unknown AS", n_localities=12)
    row = engine.to_api_response([profile])[0]
    assert row["production_volume_tonnes"] is None, (
        "an unknown volume must not render as 0 t — that is a measurement"
    )


def test_a_reported_volume_serialises_with_its_basis():
    engine = Top50Engine()
    profile = CompanyProfile(
        name="MOWI ASA",
        n_localities=142,
        production_volume_tonnes=company_facts.volume_or_none("MOWI ASA"),
        volume_basis=company_facts.volume_basis("MOWI ASA"),
    )
    row = engine.to_api_response([profile])[0]
    assert row["production_volume_tonnes"] == 332_000
    assert row["volume_basis"]["scope"] == "Norway"


def test_sorting_puts_unknown_volumes_last():
    unknown = CompanyProfile(name="Unknown AS", production_volume_tonnes=None)
    small = CompanyProfile(name="Small AS", production_volume_tonnes=1_000.0)
    big = CompanyProfile(name="MOWI ASA", production_volume_tonnes=332_000.0)
    ordered = sorted(
        [unknown, small, big],
        key=lambda c: (
            c.production_volume_tonnes is not None,
            c.production_volume_tonnes or 0.0,
        ),
        reverse=True,
    )
    assert [c.name for c in ordered] == ["MOWI ASA", "Small AS", "Unknown AS"]


@pytest.mark.parametrize("name", ["MOWI ASA", "MOWI", "mowi asa", " Mowi ASA "])
def test_the_reporting_entity_is_recognised_whatever_the_spelling(name):
    assert company_facts.volume_or_none(name) == 332_000
