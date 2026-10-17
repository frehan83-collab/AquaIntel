"""WS-20 (first takedown): no buy/sell/short direction on a listed security.

Anonymous ``GET /api/signals`` served the signal generator's rows — on the dev box
1,238 of them, every one SHORT, on Grieg (GSF), Lerøy (LSG), Mowi (MOWI) and
SalMar (SALM) among others, each with a per-share impact such as "Expected stock
impact: -17.2% (NOK -28/share)" — and /trader, /signals and the dashboard showed
them. The project's own advice boundary says AquaIntel is not licensed to give
investment advice (``/api/legal/advice-boundary``), and information that proposes
an investment decision in a financial instrument may be an investment
recommendation under the EU Market Abuse Regulation, Art. 3(1)(34).

These tests seed SHORT and LONG rows into a throwaway database the route would
read, so they prove the route serves none of them whatever the table holds.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.api import app

REPO_ROOT = Path(__file__).resolve().parent.parent
LISTED = ("GSF", "LSG", "MOWI", "SALM")
DIRECTION = re.compile(r"\b(SHORT|LONG|BUY|SELL)\b", re.IGNORECASE)


@pytest.fixture
def seeded_signal_store(tmp_path, monkeypatch):
    """Signals the generator writes (SHORT and LONG on listed tickers), in a
    throwaway database bound to every reader and writer of the signals table."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base, Signal

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'signals.db'}")
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            # every table: the chat paths read the lice and locality tables too
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as s:
            for i, ticker in enumerate(LISTED):
                s.add(
                    Signal(
                        ticker=ticker,
                        direction="SHORT" if i % 2 == 0 else "LONG",
                        strength=0.68,
                        status="pending",
                        rationale=(
                            f"Predicted 26.5% harvest reduction for {ticker}. Expected stock "
                            "impact: -17.2% (NOK -28/share)."
                        ),
                        created_at=dt.datetime(2026, 10, 12, 10, 43),
                    )
                )
            await s.commit()

    asyncio.run(setup())

    @asynccontextmanager
    async def session():
        async with factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    monkeypatch.setattr("core.routers.signals_routes.get_async_session", session)
    monkeypatch.setattr("execution.execution_agent.get_async_session", session)
    monkeypatch.setattr("core.routers.market_routes.get_async_session", session)  # hedger
    monkeypatch.setattr("core.async_db.get_async_session", session)  # the rule-based chat
    monkeypatch.setattr("core.llm.chat_agent.get_async_session", session)

    def rows():
        async def read():
            from sqlalchemy import select

            async with factory() as s:
                return (await s.execute(select(Signal).order_by(Signal.id))).scalars().all()

        return asyncio.run(read())

    try:
        yield rows
    finally:
        asyncio.run(engine.dispose())


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestSignalsTakedown:
    @pytest.mark.parametrize(
        "query", ["", "?status=pending", "?status=executed", "?limit=1000"]
    )
    def test_route_serves_no_direction_on_a_listed_security(
        self, client, seeded_signal_store, query
    ):
        assert any(r.direction == "SHORT" for r in seeded_signal_store()), "fixture seeds SHORT rows"
        r = client.get(f"/api/signals{query}")
        assert r.status_code == 200, r.text
        body = r.json()
        text = json.dumps(body)
        assert not DIRECTION.search(text), text[:400]
        for ticker in LISTED:
            assert ticker not in text, (ticker, text[:400])
        assert "/share" not in text and "stock impact" not in text
        assert body["signals"] == []
        assert body["withdrawn"] is True
        assert "advice" in body["reason"].lower()
        assert body["advice_boundary"] == "/api/legal/advice-boundary"

    def test_the_limit_bound_still_applies(self, client):
        # the frozen contract keeps the query parameters; an unbounded limit is still refused
        assert client.get("/api/signals?limit=999999").status_code == 422

    @pytest.mark.parametrize("action", ["confirm", "reject"])
    def test_a_withdrawn_signal_cannot_be_confirmed_or_rejected(
        self, client, seeded_signal_store, action
    ):
        target = seeded_signal_store()[0]
        r = client.post(f"/api/signals/{action}", json={"signal_id": target.id})
        assert r.status_code == 410, r.text
        assert "withdrawn" in json.dumps(r.json()).lower()
        after = seeded_signal_store()[0]
        assert after.status == "pending" and not after.confirmed_by_user

    def test_hedger_route_serves_no_direction_on_a_listed_security(self, client, seeded_signal_store):
        """The market hedger writes [HEDGER] rows on listed shares too; the route
        serves only the salmon-price rows."""
        from core.models import Signal

        async def add_hedger_rows():
            from core.routers import market_routes

            async with market_routes.get_async_session() as s:
                for ticker, direction in (("MOWI", "LONG"), ("GSF", "SHORT"), ("SALMON_SPOT", "SHORT")):
                    s.add(Signal(
                        ticker=ticker, direction=direction, strength=0.6, status="pending",
                        rationale="[HEDGER] Futures curve in backwardation (-20.4%)",
                        created_at=dt.datetime(2026, 10, 12, 11, 0),
                    ))

        asyncio.run(add_hedger_rows())
        rows = client.get("/api/market/hedger-signals").json()
        assert [row["ticker"] for row in rows] == ["SALMON_SPOT"], rows

    def test_the_advice_boundary_publishes_the_withdrawal_and_its_gaps(self, client):
        body = client.get("/api/legal/advice-boundary").json()
        entries = body["withdrawn_outputs"]
        assert entries and entries[0]["since"] == "2026-10-17"
        assert "/api/signals" in json.dumps(entries[0]["surfaces"])
        assert entries[0]["under_review"], "what is still served must be named"
        assert any("withdrawn_outputs" in line for line in body["safeguards"])

    def test_the_chat_never_lists_the_signals(self, seeded_signal_store, monkeypatch):
        """The rule-based chat answer and the LLM context read the same table."""
        import core.api as api_module
        from core.llm.chat_agent import ChatAgent

        out = asyncio.run(api_module._rule_based_chat_response("show me the trading signals"))
        text = json.dumps(out)
        assert not DIRECTION.search(text), text[:400]
        assert not any(ticker in text for ticker in LISTED), text[:400]
        assert "withdrawn" in text.lower()

        context = asyncio.run(ChatAgent._build_context("which signals are pending for MOWI?"))
        assert not re.search(r"\b(SHORT|LONG)\b", context), context[-400:]
        assert "Pending signals" not in context
        assert "Equity direction signals: withdrawn" in context

    @pytest.mark.parametrize(
        "page",
        [
            "frontend/src/app/trader/page.tsx",
            "frontend/src/app/signals/page.tsx",
            "frontend/src/app/page.tsx",
            "frontend/src/app/chat/page.tsx",
            "frontend/src/components/useDashboardData.ts",
        ],
    )
    def test_no_page_fetches_shows_or_acts_on_the_signals(self, page):
        source = (REPO_ROOT / page).read_text(encoding="utf-8")
        for call in ("api.signals(", "api.confirmSignal(", "api.rejectSignal(", "api.orders("):
            assert call not in source, f"{page} still calls {call}"
        assert "sig.direction" not in source, f"{page} still renders a signal direction"
