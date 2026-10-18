"""Verify every number in a generated answer against the grounded facts.

The research is blunt about this: a model asked to "cite sources" still produces numbers
that do not appear in them, and up to 57 % of model-generated citations are
post-rationalised (arXiv 2412.18004). Citations show provenance; they do not enforce it
(arXiv 2509.06902). The only thing that enforces it is a check on the **digits**.

So after the model writes, every numeric token in the answer is matched against the values in
the verified block. A number that appears in no fact is *unverified*: the answer keeps it (a
model may legitimately derive "12.5 %" from a rate or say "3.5 months") but the payload names
it, the UI badges it, and the metric that matters — the silent-wrong-number rate — becomes
visible instead of invisible.

Matching is deliberately forgiving about presentation (rounding, percent vs decimal, unit
suffixes, thousands separators) and strict about value: a number is verified when it equals a
fact value (or that value as a percentage) within a small relative tolerance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Relative tolerance for a match: presentation rounding, not value drift.
RELATIVE_TOLERANCE = 0.01

#: Numbers that are never claims: list indices, years in a date, "PA 3", section numbers.
TRIVIAL = {0.0, 1.0, 2.0, 3.0, 100.0, 1000.0}

_NUMBER_RE = re.compile(r"-?\d[\d \u00a0]*(?:[.,]\d+)?")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass
class NumberClaim:
    token: str
    value: float

    def to_dict(self) -> dict:
        return {"token": self.token, "value": self.value}


@dataclass
class Verification:
    verified: list[NumberClaim] = field(default_factory=list)
    unverified: list[NumberClaim] = field(default_factory=list)
    checked: int = 0

    @property
    def rate(self) -> float | None:
        return round(len(self.verified) / self.checked, 3) if self.checked else None

    @property
    def clean(self) -> bool:
        return not self.unverified

    def to_dict(self) -> dict:
        return {
            "checked": self.checked,
            "verified": [claim.to_dict() for claim in self.verified],
            "unverified": [claim.to_dict() for claim in self.unverified],
            "verified_rate": self.rate,
            "clean": self.clean,
        }


def _parse(token: str) -> float | None:
    cleaned = token.replace("\u00a0", "").replace(" ", "")
    # A Norwegian decimal comma: "-1,69" -> "-1.69"; "72,55" -> "72.55".
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_numbers(text: str) -> list[NumberClaim]:
    """Every numeric claim in the text, skipping years and trivial integers."""
    claims: list[NumberClaim] = []
    for match in _NUMBER_RE.finditer(text or ""):
        token = match.group(0).strip()
        if not token:
            continue
        if _YEAR_RE.fullmatch(token):
            continue
        value = _parse(token)
        if value is None:
            continue
        claims.append(NumberClaim(token=token, value=value))
    return claims


def _fact_values(facts: list[dict]) -> list[float]:
    """Every number a fact exposes, including percentages of rates."""
    values: list[float] = []

    def collect(value) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            values.append(float(value))
            # A rate stored as 0.125 is often spoken as 12.5 %.
            if 0 <= float(value) <= 1:
                values.append(float(value) * 100.0)
            return
        if isinstance(value, dict):
            for nested in value.values():
                collect(nested)
            return
        if isinstance(value, (list, tuple)):
            for nested in value:
                collect(nested)

    for fact in facts:
        collect(fact.get("value"))
    return values


def _matches(value: float, candidates: list[float]) -> bool:
    for candidate in candidates:
        if candidate == value:
            return True
        if candidate == 0:
            continue
        if abs(value - candidate) / abs(candidate) <= RELATIVE_TOLERANCE:
            return True
        # Integer presentation of a decimal fact (72.55 -> "72" in prose is not a claim
        # of 72.00, so only accept when the fact itself is an integer).
        if float(candidate).is_integer() and value == candidate:
            return True
    return False


def verify(answer: str, facts: list[dict]) -> Verification:
    """Split the answer's numbers into those the facts support and those they do not."""
    candidates = _fact_values(facts)
    result = Verification()
    for claim in extract_numbers(answer):
        if claim.value in TRIVIAL:
            continue
        result.checked += 1
        if _matches(claim.value, candidates):
            result.verified.append(claim)
        else:
            result.unverified.append(claim)
    return result


def caveat(verification: Verification, *, limit: int = 4) -> str | None:
    """One honest sentence to append when the answer carries unsupported numbers."""
    if verification.clean or not verification.unverified:
        return None
    shown = ", ".join(claim.token for claim in verification.unverified[:limit])
    return (
        f"Note: {len(verification.unverified)} number(s) in this answer could not be matched "
        f"to the verified data ({shown}). Treat them as context rather than measurements."
    )
