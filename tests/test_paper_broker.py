"""Tests for the paper broker."""
import pytest
from execution.paper_broker import PaperBroker


@pytest.fixture
def broker():
    return PaperBroker(initial_capital=100_000)


def test_buy_order(broker):
    result = broker.execute_order("MOWI", "BUY", 100, 200.0)
    assert result["status"] == "filled"
    assert broker.cash == 100_000 - (100 * 200)
    assert len(broker.open_positions) == 1


def test_sell_order(broker):
    result = broker.execute_order("SALM", "SELL", 50, 150.0)
    assert result["status"] == "filled"
    assert len(broker.open_positions) == 1


def test_insufficient_capital(broker):
    result = broker.execute_order("MOWI", "BUY", 10000, 200.0)
    assert result["status"] == "rejected"


def test_close_position(broker):
    broker.execute_order("MOWI", "BUY", 100, 200.0)
    result = broker.close_position(0, 220.0)
    assert result["status"] == "closed"
    assert result["pnl"] == 2000.0
    assert len(broker.open_positions) == 0


def test_portfolio_summary(broker):
    summary = broker.summary()
    assert summary["initial_capital"] == 100_000
    assert summary["open_positions"] == 0
