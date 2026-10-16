"""Performance-fee decision point — deliberately DEFERRED and enforced as such.

The Investor tier historically advertised a "+20% performance fee". Charging a
success fee tied to trading signals moves the platform toward regulated investment
advice, needs a different legal footing (possibly a licence) and changes the tax
treatment. Until that decision is taken by a human, the platform must not charge it
**and must not advertise it**.

This module makes the deferral explicit and machine-readable: `is_enabled()` reads
``FISHINTEL_PERFORMANCE_FEE_ENABLED`` (default off), and `status()` states the
conditions that must be met before it may be turned on.
"""
from __future__ import annotations

import os

STATUS = "deferred"
DECISION_OWNER = "founder + external counsel (NOT an engineering decision)"
DECISION_REQUIRED_BY = "before the first Investor contract is signed"

CONDITIONS = (
    "Legal opinion that a success fee on informational signals is not regulated "
    "investment advice in the target jurisdictions (NO/EU at minimum).",
    "Terms of service updated to describe the fee basis, the measurement window "
    "and the clawback rules.",
    "An auditable, reproducible performance calculation (the accuracy registry's "
    "versioned artifacts are the intended basis).",
    "Client reporting that separates the fee calculation from any advice framing.",
    "Billing support for a variable fee (the current catalog is fixed monthly "
    "subscription only).",
)

PROHIBITED_WHILE_DEFERRED = (
    "Advertising a performance fee on the pricing page, in sales decks or in the "
    "API catalog.",
    "Recording a performance fee as revenue in any projection that is shown to a "
    "customer or investor as current.",
    "Presenting signals as personalised recommendations in order to justify a fee.",
)


def is_enabled() -> bool:
    """True only when a human has explicitly enabled the fee."""
    return os.environ.get("FISHINTEL_PERFORMANCE_FEE_ENABLED", "0").lower() in (
        "1",
        "true",
        "yes",
    )


def status() -> dict:
    enabled = is_enabled()
    return {
        "enabled": enabled,
        "status": "enabled" if enabled else STATUS,
        "decision_owner": DECISION_OWNER,
        "decision_required_by": DECISION_REQUIRED_BY,
        "conditions_to_enable": list(CONDITIONS),
        "prohibited_while_deferred": list(PROHIBITED_WHILE_DEFERRED),
        "switch": "FISHINTEL_PERFORMANCE_FEE_ENABLED",
        "note": (
            "While deferred, the platform must not charge or advertise a performance "
            "fee. The Investor plan is priced as a fixed monthly subscription."
        ),
    }
