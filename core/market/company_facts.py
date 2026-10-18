"""Reported company harvest — dated, sourced facts instead of a per-site multiplier.

WS-35 (2026-10-18). ``top50_engine`` derived a company's annual production as
``n_localities * 800`` and presented it as a volume. That made Mowi 113 600 t against
roughly 332 000 t harvested in Norway in 2025 — a 3x understatement on the analyst desk,
and one of the numbers a buyer checks first.

A volume is a *reported fact*, so it lives here like the regulatory facts do: one row per
company per year with the scope (Norway or group), the figure, and a source. A company
without a row reports ``None`` and says so — it is never estimated from site counts,
because the multiplier is not a measurement and companies differ by an order of
magnitude in output per site.

Scope matters: "Mowi 332 000 t" is Norway, not group. Never compare a Norway row with a
group row without saying so.
"""
from __future__ import annotations

#: Reported harvest volumes. ``scope`` is explicit because a Norway figure and a group
#: figure are different quantities. Only figures with a citation are listed.
COMPANY_HARVEST_FACTS: dict[str, dict] = {
    "MOWI": {
        "company": "Mowi ASA",
        "year": 2025,
        "volume_tonnes_gwt": 332_000.0,
        "scope": "Norway",
        "source": "Mowi Q4 2025 trading update (reported harvest, Norway)",
        "source_url": (
            "https://weareaquaculture.com/news/aquaculture/financial-results-did-not-"
            "match-mowis-record-volumes-in-q4-2025"
        ),
        "confidence": "reported",
    },
}

#: Exact owner-company strings that are the reporting entity for a fact. Deliberately
#: exact: a substring match caught "MOWI FEED AS" (a feed company) and put the farming
#: harvest on it, and would silently attach one group figure to several rows.
_ALIASES = {
    "MOWI": "MOWI",
    "MOWI ASA": "MOWI",
}

#: The rule this module exists to replace, kept as a named constant so a reader can see
#: what is no longer used (and so a test can assert it is not in the compute path).
RETIRED_PER_SITE_MULTIPLIER_TONNES = 800.0


def ticker_for(company_name: str | None) -> str | None:
    """Map an exact owner-company name to a ticker we hold facts for, or None."""
    if not company_name:
        return None
    return _ALIASES.get(company_name.strip().upper())


def harvest_for(company_name: str | None) -> dict | None:
    """The reported harvest fact for the *reporting entity*, or None.

    A row for another entity in the same group (a subsidiary, a feed arm) returns None:
    the figure belongs to the reporting entity, and repeating it on several rows would
    look like several harvests.
    """
    ticker = ticker_for(company_name)
    if ticker is None:
        return None
    fact = COMPANY_HARVEST_FACTS.get(ticker)
    return dict(fact) if fact else None


def volume_or_none(company_name: str | None) -> float | None:
    """Reported harvest in tonnes for the reporting entity, else None.

    Never an estimate from site counts: the retired multiplier is not a measurement.
    """
    fact = harvest_for(company_name)
    return fact["volume_tonnes_gwt"] if fact else None


def volume_basis(company_name: str | None) -> dict:
    """What the volume is (and is not), for the payload beside the number."""
    fact = harvest_for(company_name)
    if fact:
        return {
            "basis": "reported",
            "year": fact["year"],
            "scope": fact["scope"],
            "source": fact["source"],
            "source_url": fact["source_url"],
            "entity": fact["company"],
        }
    near_miss = _group_entity(company_name)
    if near_miss:
        return {
            "basis": "sub_entity",
            "year": None,
            "scope": None,
            "source": (
                f"this row is another entity in the {near_miss['company']} group; the "
                "reported harvest is attached to that entity's own row, not repeated here"
            ),
            "source_url": near_miss["source_url"],
            "entity": near_miss["company"],
        }
    return {
        "basis": "unknown",
        "year": None,
        "scope": None,
        "source": (
            "no reported harvest is registered for this company; the volume is not "
            "estimated from locality counts (the retired per-site multiplier was "
            f"{RETIRED_PER_SITE_MULTIPLIER_TONNES:.0f} t, which understated the largest "
            "producers several-fold)"
        ),
        "source_url": None,
        "entity": None,
    }


def _group_entity(company_name: str | None) -> dict | None:
    """The registered group fact whose brand token appears in this row, if any."""
    if not company_name:
        return None
    key = company_name.strip().upper()
    for fact in COMPANY_HARVEST_FACTS.values():
        brand = fact["company"].split()[0].upper()
        if len(brand) > 2 and brand in key:
            return fact
    return None
