"""
CI ratchet — API route typing coverage must never decrease (arch report §4.3).

When you add an endpoint, add a response_model and bump TYPED_ROUTE_FLOOR.
The floor only ever moves UP — removing typing from a route fails CI.
"""
from core.api import app

TYPED_ROUTE_FLOOR = 12  # Session 40: 8 pre-existing + 4 wave-1 (price-outlook, brief, biomass, causal)


def _typed_routes():
    return [r for r in app.routes if getattr(r, "response_model", None) is not None]


def test_typed_route_floor():
    typed = _typed_routes()
    assert len(typed) >= TYPED_ROUTE_FLOOR, (
        f"Typed-route count dropped to {len(typed)} (floor {TYPED_ROUTE_FLOOR}). "
        "New endpoints must ship with a response_model; do not remove typing from existing routes."
    )


def test_wave1_high_traffic_endpoints_typed():
    """The four wave-1 high-traffic endpoints must stay typed."""
    paths = {r.path for r in _typed_routes()}
    expected = (
        "/api/market/price-outlook",
        "/api/brief",
        "/api/biomass/outlook",
        "/api/causal/summary",
    )
    for path in expected:
        assert path in paths, f"{path} lost its response_model"
