"""Equity direction signals — withdrawn (WS-20, 2026-10-17).

The signal generator wrote directional calls on listed salmon shares (Grieg, Lerøy,
Mowi, SalMar and others), each with a per-share impact estimate such as "Expected
stock impact: -17.2% (NOK -28/share)", and anonymous ``GET /api/signals`` served
them to /trader, /signals, the dashboard and the chat. The project's own advice
boundary says AquaIntel is not licensed to give investment advice
(``/api/legal/advice-boundary``); information that proposes an investment decision
in a financial instrument may be an investment recommendation under the EU Market
Abuse Regulation, Art. 3(1)(34), which applies in Norway through the EEA.

This module is the one definition of the withdrawal: the signals routes, the
rule-based chat answer, the LLM chat context and the advice boundary read it.
Nothing is deleted — the ``signals`` table keeps its rows; they are no longer served.
The withdrawal stands until a legal opinion says what, if anything, may return.
"""
from __future__ import annotations

WITHDRAWN_SINCE = "2026-10-17"
ADVICE_BOUNDARY_URL = "/api/legal/advice-boundary"

# Worded without trade directions on purpose: the notice itself is served where the
# calls used to be.
REASON = (
    "The signal generator's directional calls on listed salmon shares, with "
    "per-share impact estimates, were withdrawn on 2026-10-17 pending a legal "
    "opinion. Information that proposes an investment decision in a financial "
    "instrument may count as an investment recommendation under the EU Market Abuse "
    "Regulation (Art. 3(1)(34)); AquaIntel is not an investment adviser and is not "
    "licensed to give investment advice."
)

#: The surfaces taken down, for the advice boundary and the docs.
SURFACES = (
    "GET /api/signals (serves no signal)",
    "POST /api/signals/confirm and /reject (410)",
    "rule-based chat answer and LLM chat context (no pending signals)",
    "/trader signals panel, /signals trading and order sections, dashboard signals widget",
)


#: Outputs of the same kind that are still served, pending the legal opinion
#: (docs/HANDOVER.md WS-28) — published so the boundary states its own gaps.
UNDER_REVIEW = (
    "GET /api/pairs/signals and the pairs cards: paired positions on listed shares",
    "GET /api/sentiment/signals: per-ticker news sentiment on listed shares",
    "GET /api/orders: the paper order history (no longer shown on /signals)",
    "the /trader Event Impact Simulator: per-company revenue and stock-move estimates",
    "GET /api/market/hedger-signals: now serves only the salmon-price (SALMON_SPOT) rows",
    "agents that write directional rows (signal generator, market hedger, prediction, "
    "bloom) — they run only with the agents service",
)


def notice() -> dict:
    """The withdrawal notice, in the shape ``GET /api/signals`` serves."""
    return {
        "signals": [],
        "withdrawn": True,
        "since": WITHDRAWN_SINCE,
        "reason": REASON,
        "advice_boundary": ADVICE_BOUNDARY_URL,
    }


def chat_answer() -> str:
    """What the chat says when asked for trading signals."""
    return (
        "**Equity signals withdrawn**\n\n"
        f"{REASON}\n\nThe advice boundary is published at {ADVICE_BOUNDARY_URL}."
    )


def advice_boundary_entry() -> dict:
    """The entry the published advice boundary carries for this withdrawal."""
    return {
        "output": "equity direction signals on listed salmon shares",
        "since": WITHDRAWN_SINCE,
        "reason": REASON,
        "surfaces": list(SURFACES),
        "under_review": list(UNDER_REVIEW),
    }


# ── The write gate (WS-28, 2026-10-18) ───────────────────────────────────────────
# The surfaces were taken down, but four agents still *wrote* directional rows on
# listed shares: the signal generator (SHORT/LONG), the market hedger (any equity
# ticker), the prediction agent (arbitrage direction) and the bloom agent (SHORT on a
# CRITICAL bloom). They only run with the agents service, so the rows would reappear
# the moment it starts — a withdrawal that only hides the output is not a withdrawal.
# One definition, checked by every writer, so there is no fifth place to remember.

#: Whether new directional rows on listed securities may be written at all. Off until a
#: legal opinion says what may return (docs/HANDOVER.md WS-28); existing rows are kept.
DIRECTIONAL_WRITES_ENABLED = False

WRITE_GATE_REASON = (
    "Writing new directional calls on listed securities is disabled while the "
    "withdrawal stands (WS-20/WS-28): the output may count as an investment "
    "recommendation under EU MAR Art. 3(1)(34)."
)

#: Instrument classes that are NOT listed securities and stay allowed.
NON_EQUITY_INSTRUMENTS: frozenset[str] = frozenset({"spot", "futures", "physical", "fx"})


def may_persist_directional(*, instrument: str = "equity") -> bool:
    """May a new directional signal row be written for this instrument class?

    ``instrument="equity"`` is the withdrawal's subject and returns False. Salmon spot
    and futures rows are not shares and are not affected — the gate only governs the
    listed-equity direction output.
    """
    if instrument in NON_EQUITY_INSTRUMENTS:
        return True
    return DIRECTIONAL_WRITES_ENABLED
