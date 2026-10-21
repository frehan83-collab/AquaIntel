"""WS-58 hid 21 dead surfaces; WS-59 deleted them.

Hiding was a half-measure. A hidden page is still a URL, still built into the bundle, and still
a promise the product makes to whoever finds it — and every one of the 21 was either withdrawn
for legal reasons (WS-20: the equity surfaces) or backed by an endpoint that answers 404
(`/api/scenarios`, `/api/china-demand/snapshot`, `/api/benchmarking/companies`). The nav is the
product's claim about itself; this file keeps the claim small, true, and enforced.
"""
from __future__ import annotations

import re
from pathlib import Path

SIDEBAR = Path("frontend/src/components/Sidebar.tsx")
APP = Path("frontend/src/app")
FRONTEND = Path("frontend/src")

#: Surfaces deleted by WS-59, each with the reason it could not stay.
DELETED = {
    "/signals": "withdrawn equity signals (WS-20) — a page selling a legal notice is a liability",
    "/investor": "paper trading and Monte Carlo profit simulation are withdrawn (WS-20)",
    "/trader": "paper trading with no licensed edge and no directional calls",
    "/twin": "farm digital twin — the farmer's own vendors model this better",
    "/scenarios": "/api/scenarios returns 404; duplicate of /scenarios-lab",
    "/scenarios-lab": "scenario sandbox with no buyer",
    "/china-demand": "/api/china-demand/snapshot returns 404",
    "/causal": "academic causality view, no buyer",
    "/ras": "RAS is a niche with demo-only data",
    "/command-centre": "operations demo, no buyer",
    "/design-system": "internal",
    "/ml-baselines": "model museum; /accuracy carries the honest number",
    "/benchmark": "/api/benchmarking/companies returns 404; /compare covers the need",
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


def test_no_deleted_surface_is_linked():
    linked = set(_nav_hrefs())
    offenders = sorted(linked & set(DELETED))
    assert offenders == [], f"deleted surfaces still in the nav: {offenders}"


def test_the_nav_stays_inside_its_budget():
    hrefs = _nav_hrefs()
    assert len(hrefs) <= MAX_LINKS, f"{len(hrefs)} links; the trimmed budget is {MAX_LINKS}"
    assert len(set(hrefs)) == len(hrefs), "a link appears twice"


def test_deleted_surfaces_no_longer_ship_a_page():
    """The point of WS-59: they are gone, not merely unlinked."""
    shipped = sorted(s for s in DELETED if (APP / s.strip("/")).exists())
    assert shipped == [], f"surfaces that should be deleted still ship: {shipped}"


def test_nothing_in_the_frontend_references_a_deleted_surface():
    """A stale link (keyboard shortcut, tour step, dashboard card) resurrects a dead route."""
    offenders = []
    for path in FRONTEND.rglob("*"):
        if path.suffix not in (".ts", ".tsx"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for surface in DELETED:
            pattern = re.compile(r'["\'`]' + re.escape(surface) + r'(?:["\'`/?#])')
            for match in pattern.finditer(text):
                line = text[: match.start()].count("\n") + 1
                offenders.append(f"{path.as_posix()}:{line}: {surface}")
    assert offenders == [], f"references to deleted surfaces: {offenders}"


def test_the_sales_documents_do_not_send_a_rep_to_a_deleted_page():
    """A demo script is a promise made in front of a customer.

    `DEMO_GUIDE.md` used to route a salesperson through `/causal`, `/ml-baselines` and the four
    country pages, and to promise Oslo equity quotes that WS-20 had withdrawn.
    """
    sales_docs = (
        Path("DEMO_GUIDE.md"),
        Path("README.md"),
        Path("docs/GTM_DEMO_SCRIPT.md"),
        Path("docs/GTM_SECURITY_ONE_PAGER.md"),
    )
    offenders = []
    for doc in sales_docs:
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8", errors="ignore")
        for surface in DELETED:
            for pattern in (f"({surface})", f"`{surface}`", f"]({surface})"):
                if pattern in text:
                    offenders.append(f"{doc.as_posix()}: {pattern}")
    assert offenders == [], offenders


def test_every_deleted_surface_has_a_written_reason():
    assert all(reason.strip() for reason in DELETED.values())


def test_the_commercial_trim_document_exists_and_names_the_reasons():
    doc = Path("docs/COMMERCIAL_TRIM.md")
    assert doc.exists(), "the trim decision must be written down, not implied"
    text = doc.read_text(encoding="utf-8")
    for surface in ("/signals", "/investor", "/trader", "/twin"):
        assert surface in text, surface
    assert "WS-59" in text, "the document must record that hiding became deletion"
