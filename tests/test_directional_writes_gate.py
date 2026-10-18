"""WS-28: no agent may write a directional row on a listed security.

The surfaces were withdrawn on 2026-10-17 (WS-20) and ``GET /api/signals`` serves only
the notice — but four agents still *wrote* the rows (signal generator, market hedger,
prediction agent, bloom agent). They run only with the agents service, so the output
would have reappeared the moment it starts. The gate is one definition in
``core.legal.equity_signals``; these tests pin the gate, each writer's use of it, and
the fact that non-equity instruments are not affected.
"""
from __future__ import annotations

import inspect
import types

import pytest

from core.legal import equity_signals


class _FakeSession:
    """Captures ``add`` calls; enough for the two writers that persist directly."""

    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:  # noqa: ANN001 — mirrors Session.add
        self.added.append(obj)

    def add_all(self, objs) -> None:  # noqa: ANN001 — mirrors Session.add_all
        self.added.extend(objs)

    async def execute(self, *_args, **_kwargs):
        class _Empty:
            def scalars(self):
                return self

            def first(self):
                return None

            def all(self):
                return []

        return _Empty()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def fake_session(monkeypatch):
    session = _FakeSession()
    factory = lambda: session  # noqa: E731
    for module_name in (
        "agents.signal_generator",
        "agents.market_hedger_agent",
        "agents.bloom_agent",
        "agents.prediction_agent",
    ):
        module = __import__(module_name, fromlist=["get_async_session"])
        monkeypatch.setattr(module, "get_async_session", factory, raising=False)
    return session


# ── The gate itself ─────────────────────────────────────────────────────


def test_directional_writes_are_off():
    assert equity_signals.DIRECTIONAL_WRITES_ENABLED is False


def test_equity_is_withheld_and_other_instruments_are_not():
    assert equity_signals.may_persist_directional() is False
    assert equity_signals.may_persist_directional(instrument="equity") is False
    for instrument in ("spot", "futures", "physical", "fx"):
        assert equity_signals.may_persist_directional(instrument=instrument) is True


def test_the_reason_names_the_legal_basis():
    assert "MAR" in equity_signals.WRITE_GATE_REASON
    assert "WS-28" in equity_signals.WRITE_GATE_REASON


# ── Every writer checks it ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "module_name",
    [
        "agents.signal_generator",
        "agents.market_hedger_agent",
        "agents.bloom_agent",
        "agents.prediction_agent",
    ],
)
def test_writer_imports_the_shared_gate(module_name):
    module = __import__(module_name, fromlist=["may_persist_directional"])
    assert hasattr(module, "may_persist_directional"), module_name
    # ...and is the same object as the legal module's - one definition, no copies.
    assert module.may_persist_directional is equity_signals.may_persist_directional


@pytest.mark.asyncio
async def test_signal_generator_persists_no_directional_row_but_audits(fake_session):
    from agents.signal_generator import SignalGeneratorAgent
    from core.models import Signal

    signal = Signal(ticker="MOWI", direction="SHORT", strength=0.9, status="pending")
    await SignalGeneratorAgent._persist(signal)

    assert not [o for o in fake_session.added if isinstance(o, Signal)], (
        "a directional row on a listed share was persisted"
    )
    audit = [o for o in fake_session.added if type(o).__name__ == "AuditLog"]
    assert audit, "the skip must leave an audit trail"
    # AuditLog maps the agents' `detail=` kwarg onto the `details` column.
    assert "not persisted" in audit[0].details


@pytest.mark.asyncio
async def test_market_hedger_persists_no_equity_row(fake_session):
    from agents.market_hedger_agent import MarketHedgerAgent
    from core.models import Signal

    agent = MarketHedgerAgent()
    await agent._store_signals(
        [
            {"ticker": "MOWI", "direction": "bullish", "strength": 0.7,
             "entry_rationale": "backwardation"},
            {"ticker": "SALM", "direction": "bearish", "strength": 0.6,
             "entry_rationale": "cost pressure"},
        ]
    )
    assert not [o for o in fake_session.added if isinstance(o, Signal)]


@pytest.mark.asyncio
async def test_bloom_agent_withholds_the_short_call(fake_session):
    from agents.bloom_agent import BloomAgent
    from core.models import Signal

    agent = BloomAgent()
    await agent._inject_bloom_signals({"MOWI", "SALM"})
    assert not [o for o in fake_session.added if isinstance(o, Signal)]


@pytest.mark.asyncio
async def test_prediction_agent_withholds_the_arbitrage_row(fake_session):
    from agents.prediction_agent import PredictionAgent
    from core.models import Signal
    from core.predictors.impact_translator import ArbitrageSignal

    arb = ArbitrageSignal(
        ticker="MOWI",
        direction="LONG",
        strength=0.7,
        expected_move_pct=4.2,
        time_horizon_weeks=6,
        rationale="test",
        prob_exceed_threshold=0.6,
        harvest_impact=None,
    )
    await PredictionAgent._persist_signal(arb)
    assert not [o for o in fake_session.added if isinstance(o, Signal)]


def test_no_writer_defines_its_own_gate():
    """A second `DIRECTIONAL_WRITES_ENABLED` anywhere would defeat the withdrawal."""
    for module_name in (
        "agents.signal_generator",
        "agents.market_hedger_agent",
        "agents.bloom_agent",
        "agents.prediction_agent",
    ):
        module = __import__(module_name, fromlist=["x"])
        assert not hasattr(module, "DIRECTIONAL_WRITES_ENABLED"), module_name


def test_the_advice_boundary_still_lists_the_writers_under_review():
    entry = equity_signals.advice_boundary_entry()
    assert any("agents that write directional rows" in item for item in entry["under_review"])


def test_gate_module_is_pure(monkeypatch):
    """The gate must not need a DB, a network or an app to answer."""
    module = types.ModuleType("probe")
    module.__dict__["may_persist_directional"] = equity_signals.may_persist_directional
    assert module.may_persist_directional() is False
    source = inspect.getsource(equity_signals)
    assert "sqlalchemy" not in source and "httpx" not in source
