"""Credit packs for deep analysis runs — priced per document, not per token.

A token markup on chat is a rounding error: a grounded answer costs USD 0.008, so even a
3x markup on 300 questions is a few dollars a month. The work where a credit makes sense is
the **document**: a margin dossier, an origin landed-cost comparison or a lice-pressure
review, each synthesising several engines into something a buyer would otherwise ask a
consultant for. Those cost USD 0.10-0.60 of model spend and save an hour of an analyst's
time, so a run price of NOK 120-150 is defensible in a way a per-question price never is.

One credit = one run. Packs expire after 12 months (stated below), because a prepaid
balance is a liability and an unstated expiry is a complaint waiting to happen.
"""
from __future__ import annotations

from dataclasses import dataclass

#: A rendered deep-analysis run with its model cost measured on 2026-10-18 (~USD 0.35
#: for a 3-engine dossier at ~18k input / 2.5k output tokens). Kept here so the margin is
#: stated rather than assumed.
MODEL_COST_PER_RUN_NOK = 3.30


@dataclass(frozen=True)
class CreditPack:
    key: str
    name: str
    runs: int
    price_nok: float
    audience: str
    note: str = ""

    @property
    def per_run_nok(self) -> float:
        return round(self.price_nok / self.runs, 2) if self.runs else 0.0

    @property
    def gross_margin_pct(self) -> float:
        if not self.price_nok:
            return 0.0
        return round((1 - (MODEL_COST_PER_RUN_NOK / self.per_run_nok)) * 100, 1) if self.per_run_nok else 0.0

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "runs": self.runs,
            "price_nok": self.price_nok,
            "per_run_nok": self.per_run_nok,
            "audience": self.audience,
            "note": self.note,
            "gross_margin_pct": self.gross_margin_pct,
        }


CREDIT_PACKS: dict[str, CreditPack] = {
    "review": CreditPack(
        key="review",
        name="Review",
        runs=10,
        price_nok=1490.0,
        audience="A single site or a first quarter of board packs",
        note="10 deep-analysis runs, one year validity",
    ),
    "desk": CreditPack(
        key="desk",
        name="Desk",
        runs=30,
        price_nok=3900.0,
        audience="A sales desk that writes a weekly origin or margin note",
        note="30 runs, one year validity; NOK 130 per document",
    ),
    "fleet": CreditPack(
        key="fleet",
        name="Fleet",
        runs=100,
        price_nok=11900.0,
        audience="Multi-site groups running monthly reviews across areas",
        note="100 runs, one year validity; NOK 119 per document",
    ),
}

#: Stated on every purchase surface; enforced by the ledger, not by a cron job.
CREDIT_VALIDITY_MONTHS = 12
CREDIT_VALIDITY_NOTE = (
    "Credits are valid for 12 months from purchase. Unused credits do not auto-renew."
)


def pack(key: str | None) -> CreditPack | None:
    return CREDIT_PACKS.get((key or "").strip().lower())


def catalog() -> list[dict]:
    return [pack_.to_dict() for pack_ in CREDIT_PACKS.values()]


def best_value_key() -> str:
    """The pack with the lowest price per run (used for the UI's 'best value' badge)."""
    return min(CREDIT_PACKS.values(), key=lambda p: p.per_run_nok).key
