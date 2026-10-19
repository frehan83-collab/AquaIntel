"""WS-58 — the navigation is the product's claim about itself, and it must stay true.

Every nav link is a promise that something behind it is worth a click. These tests keep the promise
small and checkable: no link to a withdrawn or dead surface, every link resolves to a page that
exists, and the count stays inside the trimmed budget.
"""
from __future__ import annotations

import re
from pathlib import Path

SIDEBAR = Path("frontend/src/components/Sidebar.tsx")
APP = Path("frontend/src/app")

#: Surfaces deliberately hidden by WS-58, each for a stated reason (docs/COMMERCIAL_TRIM.md).
HIDDEN = {
    "/signals": "withdrawn equity signals (WS-20) — a link to a notice is a liability",
    "/investor": "headline features withdrawn; the plan must be repointed before it is sold",
    "/trader": "paper trading with no licensed edge and no directional calls",
    "/twin": "farm digital twin — the farmer's own vendors model this better",
    "/scenarios": "duplicate of /scenarios-lab; its API returns 404",
    "/scenarios-lab": "scenario sandbox with no buyer",
    "/china-demand": "endpoint returns 404",
    "/causal": "academic causality view, no buyer",
    "/ras": "RAS is a niche with demo-only data",
    "/command-centre": "operations demo, no buyer",
    "/design-system": "internal",
    "/ml-baselines": "model museum; /accuracy carries the honest number",
    "/benchmark": "endpoint returns 404; /compare covers the need",
    "/farmer": "duplicate of /farmer-daily",
    "/welfare": "modelled welfare score, no paying audience of its own",
    "/efficacy": "marketplace seeded with demo outcomes",
    "/climate": "overlaps /bio-risk and /satellite",
    "/canada": "country monitor with thin data; /global-supply aggregates",
    "/scotland": "country monitor with thin data; /global-supply aggregates",
    "/faroe": "country monitor with thin data; /global-supply aggregates",
    "/iceland": "country monitor with thin data; /global-supply aggregates",
}

#: The trimmed budget. A product with one differentiated asset does not need 56 links.
MAX_LINKS = 36


def _nav_hrefs() -> list[str]:
    text = SIDEBAR.read_text(encoding="utf-8")
    block = text.split("const NAV_SECTIONS", 1)[1].split("];", 1)[0]
    return re.findall(r'href: "([^"]+)"', block)


def test_every_nav_link_resolves_to_a_page():
    missing = []
    for href in _nav_hrefs():
        relative = href.strip("/")
        candidate = APP / relative / "page.tsx" if relative else APP / "page.tsx"
        if not candidate.exists():
            missing.append(href)
    assert missing == [], f"nav links without a page: {missing}"


def test_no_hidden_surface_is_linked():
    linked = set(_nav_hrefs())
    offenders = sorted(linked & set(HIDDEN))
    assert offenders == [], f"hidden surfaces still in the nav: {offenders}"


def test_the_nav_stays_inside_its_budget():
    hrefs = _nav_hrefs()
    assert len(hrefs) <= MAX_LINKS, f"{len(hrefs)} links; the trimmed budget is {MAX_LINKS}"
    assert len(set(hrefs)) == len(hrefs), "a link appears twice"


def test_every_hidden_surface_has_a_written_reason():
    assert all(reason.strip() for reason in HIDDEN.values())


def test_the_commercial_trim_document_exists_and_names_the_reasons():
    doc = Path("docs/COMMERCIAL_TRIM.md")
    assert doc.exists(), "the trim decision must be written down, not implied"
    text = doc.read_text(encoding="utf-8")
    for surface in ("/signals", "/investor", "/trader", "/twin"):
        assert surface in text, surface
