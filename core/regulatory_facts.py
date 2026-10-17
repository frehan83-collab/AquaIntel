"""Dated, sourced regulatory facts (WS-21).

One place for the official facts the product computes with: Norway's
traffic-light colour decisions and the capacity cuts they impose, the legal
adult-female lice limit in lakselusforskriften § 8, and the US import tariff on
fresh Atlantic salmon by origin. Every fact carries its official source; colour
decisions, capacity cuts, the § 8 wording and tariff rows also carry the date
they were decided or apply from, so a payload can cite them and a reviewer can
check them.

Rules:
* Facts are data, never computed. A model may *predict* the next colour
  decision; the *current* colour is the latest official decision.
* When a fact changes, ADD a row with its new date; never edit history.
* Researched and cross-checked against primary sources on 2026-10-17
  (regjeringen.no, lovdata.no, federalregister.gov, hts.usitc.gov); the
  verification note is in docs/HANDOVER.md (WS-21) and CHANGELOG.md.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Literal

Colour = Literal["green", "yellow", "red"]

# ── Traffic-light decisions (produksjonsområdeforskriften, FOR-2017-01-16-61) ──

PRODUCTION_AREA_REGULATION_URL = "https://lovdata.no/dokument/SF/forskrift/2017-01-16-61"
# § 9: a cut applies from 6 months after the cut regulation enters into force.
CUT_LAG_NOTE = "a capacity cut applies 6 months after the cut regulation enters into force (produksjonsområdeforskriften § 9)"


@dataclass(frozen=True)
class TrafficLightDecision:
    """One official colour decision for the 13 production areas."""

    decided_on: dt.date
    source_url: str                      # the ministry's announcement
    regulation: str                      # the capacity-adjustment regulation
    regulation_url: str
    regulation_adopted_on: dt.date
    colours: dict[int, Colour]
    # Usable capacity (% of the original) for every area cut so far, as stated in
    # the regulation; areas not listed are uncut. It applies from cuts_apply_from.
    # Green areas are OFFERED growth; uptake is not known and is not counted.
    capacity_cut_to_pct: dict[int, float] = field(default_factory=dict)
    cuts_apply_from: dt.date | None = None
    cuts_apply_from_basis: str = ""
    basis: str = "lice-induced mortality on wild salmon"

    def as_dict(self) -> dict:
        return {
            "decided_on": self.decided_on.isoformat(),
            "source_url": self.source_url,
            "regulation": self.regulation,
            "regulation_url": self.regulation_url,
            "regulation_adopted_on": self.regulation_adopted_on.isoformat(),
            "capacity_after_cuts_pct": {str(k): v for k, v in sorted(self.capacity_cut_to_pct.items())},
            "cuts_apply_from": self.cuts_apply_from.isoformat() if self.cuts_apply_from else None,
            "cuts_apply_from_basis": self.cuts_apply_from_basis,
            "basis": self.basis,
        }


def _colours(green: tuple[int, ...], yellow: tuple[int, ...], red: tuple[int, ...]) -> dict[int, Colour]:
    out: dict[int, Colour] = {}
    for pa in green:
        out[pa] = "green"
    for pa in yellow:
        out[pa] = "yellow"
    for pa in red:
        out[pa] = "red"
    assert sorted(out) == list(range(1, 14)), "a decision must colour all 13 areas exactly once"
    return out


_APPROX_LAG = "regulation in force + 6 months (§ 9); approximate, not stated in the regulation"

# The five decisions since the system started (no other colour decision exists;
# 2019 was postponed to 2020-02-04, and no colour was changed after a decision).
TRAFFIC_LIGHT_DECISIONS: tuple[TrafficLightDecision, ...] = (
    TrafficLightDecision(
        decided_on=dt.date(2017, 10, 30),
        source_url="https://www.regjeringen.no/no/aktuelt/regjeringen-skrur-pa-trafikklyset/id2577032/",
        regulation="FOR-2017-12-20-2397",
        regulation_url="https://lovdata.no/dokument/SF/forskrift/2017-12-20-2397",
        regulation_adopted_on=dt.date(2017, 12, 20),
        colours=_colours(green=(1, 7, 8, 9, 10, 11, 12, 13), yellow=(2, 5, 6), red=(3, 4)),
        cuts_apply_from_basis="no cuts in the first round",
    ),
    TrafficLightDecision(
        decided_on=dt.date(2020, 2, 4),
        source_url="https://www.regjeringen.no/no/aktuelt/regjeringen-skrur-pa-trafikklyset-i-havbruksnaringen/id2688939/",
        regulation="FOR-2020-02-04-105",
        regulation_url="https://lovdata.no/dokument/SF/forskrift/2020-02-04-105",
        regulation_adopted_on=dt.date(2020, 2, 4),
        colours=_colours(green=(1, 2, 6, 7, 8, 9, 11, 12, 13), yellow=(3, 10), red=(4, 5)),
        capacity_cut_to_pct={4: 94.0, 5: 94.0},
        cuts_apply_from=dt.date(2020, 8, 5),
        cuts_apply_from_basis="Gulating lagmannsrett LG-2021-80234",
    ),
    TrafficLightDecision(
        decided_on=dt.date(2022, 6, 7),
        source_url="https://www.regjeringen.no/no/aktuelt/fargelegging-i-trafikklyssystemet-i-havbruk/id2917698/",
        regulation="FOR-2022-06-07-972",
        regulation_url="https://lovdata.no/dokument/LTI/forskrift/2022-06-07-972",
        regulation_adopted_on=dt.date(2022, 6, 7),
        colours=_colours(green=(1, 6, 8, 9, 10, 11, 12, 13), yellow=(2, 5, 7), red=(3, 4)),
        capacity_cut_to_pct={3: 94.0, 4: 88.36, 5: 94.0},
        cuts_apply_from=dt.date(2022, 12, 7),
        cuts_apply_from_basis=_APPROX_LAG,
    ),
    TrafficLightDecision(
        decided_on=dt.date(2024, 3, 6),
        source_url="https://www.regjeringen.no/no/aktuelt/ny-fargelegging-i-trafikklyssystemet-for-havbruk/id3028522/",
        regulation="FOR-2024-03-22-515",
        regulation_url="https://lovdata.no/dokument/SF/forskrift/2024-03-22-515",
        regulation_adopted_on=dt.date(2024, 3, 22),
        colours=_colours(green=(1, 9, 10, 11, 12, 13), yellow=(2, 5, 6, 7, 8), red=(3, 4)),
        capacity_cut_to_pct={3: 88.36, 4: 83.06, 5: 94.0},
        cuts_apply_from=dt.date(2024, 9, 22),
        cuts_apply_from_basis=_APPROX_LAG,
    ),
    TrafficLightDecision(
        decided_on=dt.date(2026, 6, 19),
        source_url="https://www.regjeringen.no/no/aktuelt/ny-fargelegging-i-trafikklyssystemet-for-havbruk/id3167021/",
        regulation="FOR-2026-08-20-1764",
        regulation_url="https://lovdata.no/dokument/LTI/forskrift/2026-08-20-1764",
        regulation_adopted_on=dt.date(2026, 8, 20),
        colours=_colours(green=(1, 12, 13), yellow=(2, 4, 5, 6, 7, 8, 9, 10, 11), red=(3,)),
        capacity_cut_to_pct={3: 83.06, 4: 83.06, 5: 94.0},
        cuts_apply_from=dt.date(2027, 2, 20),
        cuts_apply_from_basis=_APPROX_LAG,
    ),
)


def traffic_light_decision(as_of: dt.date | dt.datetime | None = None) -> TrafficLightDecision:
    """The latest official colour decision on `as_of` (today by default)."""
    day = _as_date(as_of)
    past = [d for d in TRAFFIC_LIGHT_DECISIONS if d.decided_on <= day]
    if not past:
        raise LookupError(f"no traffic-light decision on or before {day.isoformat()}")
    return max(past, key=lambda d: d.decided_on)


def traffic_light_history() -> dict[int, dict[str, Colour]]:
    """Colour per production area per decision year (e.g. {3: {"2017": "red", ...}})."""
    out: dict[int, dict[str, Colour]] = {pa: {} for pa in range(1, 14)}
    for d in TRAFFIC_LIGHT_DECISIONS:
        for pa, colour in d.colours.items():
            out[pa][str(d.decided_on.year)] = colour
    return out


def capacity_pct(pa: int, as_of: dt.date | dt.datetime | None = None) -> float:
    """Usable capacity (% of the original) in force for an area on `as_of`."""
    day = _as_date(as_of)
    applied = [d for d in TRAFFIC_LIGHT_DECISIONS if d.cuts_apply_from and d.cuts_apply_from <= day]
    if not applied:
        return 100.0
    latest = max(applied, key=lambda d: d.cuts_apply_from)
    return latest.capacity_cut_to_pct.get(int(pa), 100.0)


def scheduled_capacity(pa: int, as_of: dt.date | dt.datetime | None = None) -> dict | None:
    """A decided cut that has not applied yet on `as_of`, or None."""
    day = _as_date(as_of)
    now = capacity_pct(pa, day)
    pending = sorted(
        (
            d for d in TRAFFIC_LIGHT_DECISIONS
            if d.decided_on <= day and d.cuts_apply_from and d.cuts_apply_from > day
        ),
        key=lambda d: d.cuts_apply_from,
    )
    for d in pending:
        future = d.capacity_cut_to_pct.get(int(pa), 100.0)
        if future != now:
            if d.regulation_adopted_on > day:
                # Decided, but the cut regulation (and so its start date) does not exist yet.
                return {
                    "capacity_pct": future,
                    "applies_from": None,
                    "applies_from_basis": "cut regulation not yet adopted",
                    "regulation": None,
                    "regulation_url": None,
                }
            return {
                "capacity_pct": future,
                "applies_from": d.cuts_apply_from.isoformat(),
                "applies_from_basis": d.cuts_apply_from_basis,
                "regulation": d.regulation,
                "regulation_url": d.regulation_url,
            }
    return None


# ── Lice limit (lakselusforskriften FOR-2012-12-05-1140 § 8) ──────────────────

LICE_REGULATION = "FOR-2012-12-05-1140 § 8 (as amended by FOR-2017-03-06-275)"
LICE_REGULATION_URL = "https://lovdata.no/dokument/SF/forskrift/2012-12-05-1140"
LICE_RULE_IN_FORCE_FROM = dt.date(2017, 3, 6)   # the two-window § 8 (FOR-2017-03-06-275)
LICE_LIMIT_DEFAULT = 0.5      # "færre enn 0,5 voksne hunnlus i gjennomsnitt per fisk"
LICE_LIMIT_SPRING = 0.2       # in the spring window below
# "fra og med mandag i uke X til og med søndag i uke Y"
SPRING_WEEKS = {
    "south": (16, 21),        # "Nord-Trøndelag og sørover"
    "north": (21, 26),        # "Nordland, Troms og Finnmark"
}
# § 10: the weekly count is reported no later than Tuesday of the following week.
LICE_REPORT_DUE_WEEKDAY = 1   # 0 = Monday
# The warning level before the legal limit, kept in the same proportion as the
# long-standing 0.3 trigger against the 0.5 limit (a product rule, not law).
TRIGGER_FRACTION_OF_LIMIT = 0.6
TRIGGER_BASIS = "product rule: 0.6 x the legal limit (not in § 8)"

# Counties the regulation names, in any spelling the data carries (Norwegian,
# ASCII, Northern Sámi), and county numbers (Nordland 18; Troms 19/55; Finnmark
# 20/56; Troms og Finnmark 54 in 2020-2023).
_NORTHERN_COUNTIES = ("nordland", "troms", "finnmark", "nordlannda", "romsa", "finnmarku")
_SOUTHERN_COUNTIES = (
    "trondelag", "more og romsdal", "romsdal", "vestland", "hordaland", "sogn og fjordane",
    "rogaland", "agder", "vest-agder", "aust-agder", "telemark", "vestfold", "buskerud",
    "viken", "ostfold", "akershus", "oslo", "innlandet", "troondelage",
)
_NORTHERN_COUNTY_NUMBERS = {"18", "19", "20", "54", "55", "56"}
# Nordland municipalities lying (wholly or partly) in PO7 "Nord-Trøndelag med
# Bindal": the PO7/PO8 line runs at Vennesundet in Sømna. SSB: 1811-1813.
NORDLAND_MUNICIPALITIES_IN_PO7 = ("bindal", "somna", "bronnoy")


def _fold(text: str) -> str:
    t = text.strip().casefold()
    for a, b in (("ø", "o"), ("æ", "ae"), ("å", "a"), ("á", "a"), ("ö", "o")):
        t = t.replace(a, b)
    return " ".join(t.split())


@dataclass(frozen=True)
class LiceLimit:
    limit: float
    region: str | None        # "south" | "north" | None (unknown)
    in_spring_window: bool
    window: tuple[int, int] | None
    rule: str
    established: bool = True  # False: region unknown, so the limit is precautionary
    region_basis: str | None = None
    source_url: str = LICE_REGULATION_URL

    @property
    def trigger(self) -> float:
        return round(self.limit * TRIGGER_FRACTION_OF_LIMIT, 3)

    def as_dict(self) -> dict:
        return {
            "limit": self.limit,
            "established": self.established,
            "trigger": self.trigger,
            "trigger_basis": TRIGGER_BASIS,
            "region": self.region,
            "region_basis": self.region_basis,
            "in_spring_window": self.in_spring_window,
            "window_weeks": list(self.window) if self.window else None,
            "rule": self.rule,
            "regulation": LICE_REGULATION,
            "rule_in_force_from": LICE_RULE_IN_FORCE_FROM.isoformat(),
            "source_url": self.source_url,
        }


def _region_from_county(county: str | None) -> str | None:
    if not county or not county.strip():
        return None
    c = _fold(county)
    number = c[:2]
    if number.isdigit():
        return "north" if number in _NORTHERN_COUNTY_NUMBERS else "south"
    if any(name in c for name in _NORTHERN_COUNTIES):
        return "north"
    if any(name in c for name in _SOUTHERN_COUNTIES):
        return "south"
    return None  # unrecognised: fall through to the municipality / area


def lice_region_with_basis(
    pa: int | None, municipality: str | None = None, county: str | None = None
) -> tuple[str | None, str | None]:
    """Which spring window a site falls in, and how that was decided.

    The regulation speaks of counties. A recognised county decides; else a
    Nordland municipality inside PO7 (Bindal, Sømna, Brønnøy) is northern; else the
    production area decides: PO1-PO7 southern, PO8-PO13 northern.
    """
    by_county = _region_from_county(county)
    if by_county:
        return by_county, "county"
    if municipality and _fold(municipality) in NORDLAND_MUNICIPALITIES_IN_PO7:
        return "north", "municipality (Nordland)"
    if pa is None:
        return None, None
    if 1 <= int(pa) <= 7:
        return "south", "production area"
    if 8 <= int(pa) <= 13:
        return "north", "production area"
    return None, None


def lice_region(pa: int | None, municipality: str | None = None, county: str | None = None) -> str | None:
    return lice_region_with_basis(pa, municipality, county)[0]


def lice_limit(
    pa: int | None = None,
    iso_week: int | None = None,
    *,
    municipality: str | None = None,
    county: str | None = None,
) -> LiceLimit:
    """The limit for a site in an ISO week."""
    region, basis = lice_region_with_basis(pa, municipality, county)
    if iso_week is None:
        return LiceLimit(LICE_LIMIT_DEFAULT, region, False, None,
                         "no week given: limit outside the spring window", True, basis)
    if region is None:
        in_any = any(lo <= iso_week <= hi for lo, hi in SPRING_WEEKS.values())
        if in_any:
            both = all(lo <= iso_week <= hi for lo, hi in SPRING_WEEKS.values())
            if both:  # week 21 is spring in both windows: the limit is known
                return LiceLimit(LICE_LIMIT_SPRING, None, True, None, "week 21 is in both spring windows", True)
            return LiceLimit(
                LICE_LIMIT_SPRING, None, True, None,
                "region unknown: precautionary 0.2 applied; the legal limit is 0.2 or 0.5 depending on the county",
                False,
            )
        return LiceLimit(LICE_LIMIT_DEFAULT, None, False, None, "outside both spring windows", True)
    lo, hi = SPRING_WEEKS[region]
    if lo <= iso_week <= hi:
        return LiceLimit(LICE_LIMIT_SPRING, region, True, (lo, hi),
                         f"spring window weeks {lo}-{hi} ({region})", True, basis)
    return LiceLimit(LICE_LIMIT_DEFAULT, region, False, (lo, hi),
                     f"outside the spring window weeks {lo}-{hi} ({region})", True, basis)


def breaches_limit(avg_adult_female_lice: float, limit: float) -> bool:
    """§ 8 requires FEWER than the limit, so a count equal to the limit is a breach."""
    return avg_adult_female_lice >= limit


# ── US import tariff on fresh/chilled Atlantic salmon (HTS 0302.14, 0304.41) ───

SECTION_301_NOTICE_URL = (
    "https://www.federalregister.gov/documents/2026/07/28/2026-15181/"
    "notice-of-actions-in-section-301-investigations-of-acts-policies-and-practices-of-various-economies"
)
HTS_SALMON_URL = "https://hts.usitc.gov/search?query=0302.14.00"


@dataclass(frozen=True)
class UsSalmonTariff:
    origin: str
    rate: float                       # total ad valorem, as a fraction
    basis: str
    effective_from: dt.date
    source_url: str
    confidence: Literal["high", "medium"]
    caveat: str = ""

    def as_dict(self) -> dict:
        return {
            "origin": self.origin,
            "rate_pct": round(self.rate * 100, 2),
            "basis": self.basis,
            "effective_from": self.effective_from.isoformat(),
            "source_url": self.source_url,
            "confidence": self.confidence,
            "caveat": self.caveat,
        }


_LITIGATION = (
    "Section 301 forced-labor duties are under challenge at the US Court of "
    "International Trade (argued 2026-09-30); a ruling could change the rate."
)
_SECTION_301_START = dt.date(2026, 7, 24)

# Rows per origin, oldest first. Add a row when a rate changes; never edit one.
US_SALMON_TARIFFS: dict[str, tuple[UsSalmonTariff, ...]] = {
    "Norway": (UsSalmonTariff(
        "Norway", 0.125, "MFN free + Section 301 forced-labor duty 12.5% (HTS 9903.05.60)",
        _SECTION_301_START, SECTION_301_NOTICE_URL, "high", _LITIGATION,
    ),),
    "Chile": (UsSalmonTariff(
        "Chile", 0.125, "MFN free + Section 301 duty 12.5% (HTS 9903.05.30); the US-Chile FTA does not exempt it",
        _SECTION_301_START, SECTION_301_NOTICE_URL, "high", _LITIGATION,
    ),),
    "Scotland": (UsSalmonTariff(
        "Scotland", 0.10, "United Kingdom: MFN free + Section 301 duty 10% (HTS 9903.05.81); salmon not on the UK exemption list",
        _SECTION_301_START, SECTION_301_NOTICE_URL, "high", _LITIGATION,
    ),),
    "Canada": (UsSalmonTariff(
        "Canada", 0.0, "USMCA-originating farmed salmon is exempt from the Section 301 duty (HTS 9903.05.93); 10% (9903.05.29) applies only without a USMCA claim",
        _SECTION_301_START, SECTION_301_NOTICE_URL, "high",
        "0% assumes the importer claims USMCA treatment.",
    ),),
    "Faroe Islands": (UsSalmonTariff(
        "Faroe Islands", 0.0, "MFN column 1 free; not among the economies under the Section 301 action",
        _SECTION_301_START, HTS_SALMON_URL, "medium",
        "Assumes US Customs treats the Faroes as their own country of origin, not Denmark (EU 10%).",
    ),),
    "Iceland": (UsSalmonTariff(
        "Iceland", 0.0, "MFN column 1 free; not among the economies under the Section 301 action",
        _SECTION_301_START, HTS_SALMON_URL, "high",
    ),),
}


def us_salmon_tariff(origin: str, as_of: dt.date | dt.datetime | None = None) -> UsSalmonTariff:
    """The verified rate for an origin on `as_of` (today by default)."""
    day = _as_date(as_of)
    rows = [r for r in US_SALMON_TARIFFS.get(origin, ()) if r.effective_from <= day]
    if not rows:
        raise LookupError(f"no verified US salmon tariff for origin {origin!r} on {day.isoformat()}")
    return max(rows, key=lambda r: r.effective_from)


def _as_date(value: dt.date | dt.datetime | None) -> dt.date:
    if value is None:
        return dt.datetime.now(dt.UTC).date()
    if isinstance(value, dt.datetime):
        return value.date()
    return value
