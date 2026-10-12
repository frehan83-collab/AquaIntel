"""
Tests for sea-lice growth helpers added to biomass_predictor (Session 41).

These constants/functions were reconstructed when tests/test_module_imports.py
revealed that core/ml/harvest_optimizer imported nonexistent names.
"""
from core.market.biomass_predictor import (
    LICE_Q10,
    MAX_SGR_PCT,
    THERMAL_TOLERANCE,
    _temperature_growth_factor,
)


def test_temperature_growth_factor_normalised_at_10c():
    assert _temperature_growth_factor(10.0) == 1.0
    assert _temperature_growth_factor(15.0) > 1.0 > _temperature_growth_factor(5.0)


def test_temperature_growth_factor_clamped():
    assert _temperature_growth_factor(-50.0) == 0.5
    assert _temperature_growth_factor(50.0) == 2.0


def test_documented_constant_values():
    assert LICE_Q10 == 3.0
    assert THERMAL_TOLERANCE == 6.0
    assert MAX_SGR_PCT == 2.5
