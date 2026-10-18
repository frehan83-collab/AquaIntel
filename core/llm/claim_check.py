"""Verify every number in an answer against the grounded facts — signed, bound and closed.

The research is blunt: a model asked to cite still produces numbers that are not in the
sources, and up to 57 % of model-generated citations are post-rationalised (arXiv 2412.18004);
citations show provenance, they do not enforce it (arXiv 2509.06902). Only a check on the
**digits** enforces anything.

A first version of this module matched values, and the council showed it was blind to three of
the most likely lies:

1. **Sign.** It compared absolute values, so a −1.69 NOK/kg margin reported as "+1.69 profit"
   verified.
2. **Binding.** The candidate pool was one flat set of every number in every fact, so swapping
   the spot price (72.55) with the modelled cost (74.24), or the § 8 limit (0.5) with the
   trigger (0.4), verified.
3. **Round numbers.** 0 and 100 were exempt as trivial, so "0 lice", "100 % mortality" and
   "3 production areas" were never claims at all.

This version fixes all three:

* comparison is **signed**; an unsigned match to a negative fact is allowed only when the
  sentence carries a loss cue ("loss", "below", "fell"), so "a loss of 1.69" still verifies;
* each candidate carries a **role** (spot, cost, margin, limit, trigger, tariff, feed,
  chlorophyll, lice, age, cited) derived from its fact key, and a claim must land on a role the
  sentence talks about — a swap fails;
* 0 and 100 are claims again (1–3 stay exempt as counts).

And it fails **closed**: `strip_unsupported()` removes the sentence carrying an unsupported
number and says how many went, because a caveat does not travel with a forwarded document.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Relative tolerance for a match: presentation rounding, not value drift.
RELATIVE_TOLERANCE = 0.01

#: Small counting integers that are never claims: "3 production areas", "2 events".
TRIVIAL = {1.0, 2.0, 3.0}

_NUMBER_RE = re.compile(r"-?\d[\d \u00a0]*(?:[.,]\d+)?")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

#: Dates and week labels are references, not claims: 2026-10-18, 2026-W41, 2026-07, ISO
#: timestamps, HTS codes, "Section 301", "24 July", "mg/m3". Masked before extraction.
_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?)?"
    r"|\b\d{4}-W\d{1,2}\b"
    r"|\b\d{4}-\d{2}\b"
    r"|\bW\d{2}\b"
    r"|Section \d+"
    r"|HTS [\d.]+"
    r"|\b9903[\d.]*"
    r"|\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}\b"
    r"|\bm3\b|\bm\u00b3\b"
)

#: Role hints a sentence can carry. The roles found decide which candidates are compatible.
_ROLE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("margin", ("margin", "marginen", "profit", "loss", "tap", "resultat")),
    ("trigger", ("trigger", "threshold", "terskel", "varselgrense")),
    ("limit", ("limit", "grense", "lakselusforskrift", "section 8")),
    ("spot", ("spot", "price", "pris", "export price", "notering")),
    ("cost", ("cost", "kostnad", "modelled cost", "production cost")),
    ("feed", ("feed", "fôr", "fcr", "fôrfaktor")),
    ("tariff", ("tariff", "duty", "avgift", "toll")),
    ("chlorophyll", ("chlorophyll", "klorofyll", "algae", "alge", "bloom")),
    ("lice", ("lice", "lus", "lakselus")),
)

#: Words that let an unsigned claim match a negative fact ("a loss of 1.69").
_NEGATIVE_CUES = (
    "loss", "losses", "negative", "below", "fell", "fall", "dropped", "down", "under",
    "tap", "negativ",
)


@dataclass
class Candidate:
    value: float
    role: str
    unit: str = ""

    @property
    def negative(self) -> bool:
        return self.value < 0


@dataclass
class NumberClaim:
    token: str
    value: float
    role: str | None = None

    def to_dict(self) -> dict:
        return {"token": self.token, "value": self.value, "role": self.role}


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
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_numbers(text: str) -> list[NumberClaim]:
    """Every numeric claim in the text, skipping dates, week labels and trivial counts."""
    claims: list[NumberClaim] = []
    masked = _DATE_RE.sub(" ", text or "")
    for match in _NUMBER_RE.finditer(masked):
        token = match.group(0).strip()
        if not token or _YEAR_RE.fullmatch(token):
            continue
        value = _parse(token)
        if value is None:
            continue
        claims.append(NumberClaim(token=token, value=value))
    return claims


def _unit_for(key: str) -> str:
    lowered = key.lower()
    if "pct" in lowered or "rate" in lowered:
        return "%"
    if "usd" in lowered:
        return "USD"
    if "mg_m3" in lowered or "chlorophyll" in lowered:
        return "mg/m3"
    if "per_fish" in lowered or "lice" in lowered:
        return "lice/fish"
    if "nok" in lowered:
        return "NOK"
    if "tonnes" in lowered:
        return "t"
    return ""


def _role_for(key: str) -> str:
    # Only the leaf key decides the role: the fact key prefix ("margin.bridge") must not
    # relabel a spot price that lives inside it.
    leaf = (key or "").split(".")[-1]
    lowered = leaf.lower().replace(" ", "_")
    for role, hints in _ROLE_HINTS:
        for hint in hints:
            if hint.replace(" ", "_") in lowered:
                return role
    return "other"


def _candidates_from(fact: dict) -> list[Candidate]:
    """Every number a fact exposes, carrying the role and unit its key implies."""
    out: list[Candidate] = []
    base_role = _role_for(fact.get("key") or "")

    def walk(value, key: str, inherited: str) -> None:
        # The nested key is more specific than the fact key: spot_nok_per_kg is a spot
        # number even when the fact itself is the margin bridge.
        specific = _role_for(key)
        role = specific if specific != "other" else inherited
        unit = _unit_for(key)
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            out.append(Candidate(float(value), role, unit))
            if 0 <= float(value) <= 1:
                out.append(Candidate(float(value) * 100.0, role, "%"))
            return
        if isinstance(value, dict):
            for nested_key, nested in value.items():
                walk(nested, f"{key}.{nested_key}", role)
            return
        if isinstance(value, (list, tuple)):
            for nested in value:
                walk(nested, key, role)

    walk(fact.get("value"), fact.get("key") or "", base_role)
    if fact.get("age_days") is not None:
        out.append(Candidate(float(fact["age_days"]), "age", "d"))
    # A number inside a cited string (an HTS code, "Section 301" in a source note) is
    # supported by the data even though it is not a field.
    for key in ("source", "note", "as_of"):
        raw = fact.get(key)
        if isinstance(raw, str):
            for token in _NUMBER_RE.findall(_DATE_RE.sub(" ", raw)):
                parsed = _parse(token)
                if parsed is not None:
                    out.append(Candidate(parsed, "cited", ""))
    return out


def _segment_bounds(text: str, index: int) -> tuple[int, int]:
    """The start and end of the sentence around a character index."""
    body = text or ""
    boundary = re.compile(r"[!?]|\.(?=\s)|\n")
    starts = [0] + [m.end() for m in boundary.finditer(body)]
    start = max([s for s in starts if s <= index], default=0)
    ends = [m.start() for m in boundary.finditer(body) if m.start() >= index]
    end = min(ends) if ends else len(body)
    return start, end


def _hinted_role(segment: str, offset: int) -> str | None:
    """The role the sentence attributes to the number at `offset`.

    A hint before the number wins (English and Norwegian both label first: "the spot was
    72.55", "limit is 0.5"); a later hint is a fallback. This is what makes a swap fail —
    "the spot was 74.24 and the cost 72.55" attributes each number to the wrong field.
    """
    lowered = segment.lower()
    best: tuple[int, str] | None = None
    for role, hints in _ROLE_HINTS:
        for hint in hints:
            for match in re.finditer(re.escape(hint), lowered):
                if match.end() <= offset:
                    distance = offset - match.end()
                else:
                    distance = 1000 + (match.start() - offset)
                if best is None or distance < best[0]:
                    best = (distance, role)
    return best[1] if best else None


def _has_negative_cue(segment: str) -> bool:
    lowered = segment.lower()
    return "-" in segment or "\u2212" in segment or any(cue in lowered for cue in _NEGATIVE_CUES)


def _within(claim: float, candidate: float) -> bool:
    if not candidate:
        return claim == candidate
    return abs(claim - candidate) / abs(candidate) <= RELATIVE_TOLERANCE


def _claim_matches(
    claim: NumberClaim,
    candidates: list[Candidate],
    segment: str,
    offset: int,
) -> Candidate | None:
    """The candidate that supports this claim, or None. Signed, bound and unit-aware."""
    hinted = _hinted_role(segment, offset)
    negative_cue = _has_negative_cue(segment)
    for candidate in candidates:
        if candidate.role == "cited":
            if abs(candidate.value) == abs(claim.value) or _within(
                abs(claim.value), abs(candidate.value)
            ):
                return candidate
            continue
        if hinted and candidate.role != hinted and candidate.role not in ("age", "other", "cited"):
            continue
        same_sign = (candidate.value >= 0) == (claim.value >= 0)
        if not same_sign and not (candidate.negative and negative_cue):
            continue
        if candidate.value == claim.value or _within(claim.value, candidate.value):
            return candidate
        if (
            candidate.negative
            and negative_cue
            and _within(abs(claim.value), abs(candidate.value))
        ):
            return candidate
    return None


def verify(answer: str, facts: list[dict]) -> Verification:
    """Split the answer's numbers into those the facts support and those they do not."""
    candidates: list[Candidate] = []
    for fact in facts:
        candidates.extend(_candidates_from(fact))

    result = Verification()
    body = answer or ""
    for match in _NUMBER_RE.finditer(body):
        token = match.group(0).strip()
        if not token or _YEAR_RE.fullmatch(token):
            continue
        if _DATE_RE.fullmatch(token) or _DATE_RE.match(token):
            continue
        value = _parse(token)
        if value is None or value in TRIVIAL:
            continue
        segment_start, segment_end = _segment_bounds(body, match.start())
        segment = body[segment_start:segment_end]
        # A token inside a date, week label or citation is a reference, not a claim.
        window_start = max(0, match.start() - 12)
        window = body[window_start : match.end() + 6]
        if _DATE_RE.search(window):
            continue
        claim = NumberClaim(token=token, value=value)
        support = _claim_matches(claim, candidates, segment, match.start() - segment_start)
        result.checked += 1
        if support is None:
            result.unverified.append(claim)
        else:
            claim.role = support.role
            result.verified.append(claim)
    return result


def caveat(verification: Verification, *, limit: int = 4) -> str | None:
    """One honest sentence naming what could not be supported."""
    if verification.clean or not verification.unverified:
        return None
    shown = ", ".join(claim.token for claim in verification.unverified[:limit])
    return (
        f"Note: {len(verification.unverified)} number(s) in this answer could not be matched "
        f"to the verified data ({shown}) and should be treated as context, not measurements."
    )


def strip_unsupported(answer: str, verification: Verification) -> tuple[str, int]:
    """Remove every sentence that carries an unsupported number; return (text, removed).

    Fail closed: a caveat beside an invented figure is adequate in a chat bubble and useless in
    a forwarded document, so the sentence goes and the rest of the answer stands.
    """
    if verification.clean or not verification.unverified:
        return answer, 0
    bad = {claim.token for claim in verification.unverified}
    kept: list[str] = []
    removed = 0
    for block in re.split(r"(?<=[.!?])\s+|\n+", answer or ""):
        if not block.strip():
            continue
        tokens = {claim.token for claim in extract_numbers(block)}
        if tokens & bad:
            removed += 1
            continue
        kept.append(block.strip())
    return " ".join(kept), removed
