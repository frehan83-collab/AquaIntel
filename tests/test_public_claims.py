"""Public-surface honesty (WS-20).

The landing page, the API docs page, the billing and pricing pages and the plan
catalog are what a prospect reads before anything else. docs/VALUE_ANALYSIS.md
(section 3) found invented testimonials, stale vanity counts, unproven capability
claims, hard-coded price tables that disagree with the plan catalog, a waitlist form
that confirmed sign-ups it never stored, and an API reference that documented
endpoints which do not exist (one with invented accuracy figures). These tests read
the page sources AND the catalog text the pages render, so the claims cannot come
back unnoticed in either place.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.entitlements import PLANS

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend" / "src" / "app"
LANDING = APP / "landing" / "page.tsx"
API_DOCS = APP / "api-docs" / "page.tsx"
BILLING = APP / "billing" / "page.tsx"
PRICING = APP / "pricing" / "page.tsx"
PRIVACY = APP / "privacy" / "page.tsx"
PUBLIC_PAGES = (LANDING, API_DOCS, BILLING, PRICING, PRIVACY)

# Counts go stale (229 routes vs 360 measured) and capability claims must match
# what is served: the price tier is a rule ensemble, not a TFT; lice data and the
# indices are weekly; the AIS and causal figures have no current evidence; there is
# no "Institutional" plan and the API is not v2.1.0.
FORBIDDEN = (
    r"\b229\b",
    r"Market Engines",
    r"1,815",
    r"(?i)real-time",
    r"\bTFT\b",
    r"Temporal Fusion",
    r"z=3\.26",
    r"418 vessels",
    r"Nothing your competitors have",
    r"v2\.1\.0",
    r"\bInstitutional\b",
)

# A typed count of things ("360 endpoints", "1,800+ farms") goes stale the day it
# is written; counts must be computed or left out.
TYPED_COUNT = re.compile(r"\d[\d,.]*\+?\s*(?:REST |API )?(?:endpoints|routes|engines|farms|vessels)\b", re.I)


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _catalog_strings() -> list[str]:
    out: list[str] = []
    for plan in PLANS.values():
        out.extend([plan.name, plan.audience, *plan.features])
    return out


class TestNoInventedSocialProof:
    def test_landing_has_no_testimonials(self):
        src = _src(LANDING)
        for marker in ("TESTIMONIALS", "Trusted by", "Nordic Investment Bank", "Hedge Fund", "author:"):
            assert marker not in src, f"invented social proof is back on the landing page: {marker!r}"
        assert not re.search(r"\bQuote\b", src), "a quote block is back on the landing page"

    def test_landing_never_confirms_a_signup_it_did_not_store(self):
        # The old waitlist set local state and said "You're on the list" without
        # sending the address anywhere.
        src = _src(LANDING)
        assert "on the list" not in src
        assert "Join Waitlist" not in src
        assert 'type="email"' not in src, "an email capture needs a real endpoint first"


class TestNoStaleOrUnprovenClaims:
    @pytest.mark.parametrize("page", PUBLIC_PAGES, ids=lambda p: p.parent.name)
    def test_no_forbidden_claim(self, page: Path):
        src = _src(page)
        hits = [pat for pat in FORBIDDEN if re.search(pat, src)]
        assert not hits, f"{page.parent.name}/{page.name} still carries: {hits}"

    def test_rendered_catalog_text_has_no_forbidden_claim(self):
        # /pricing, /billing and /landing render these strings verbatim.
        hits = [(s, pat) for s in _catalog_strings() for pat in FORBIDDEN if re.search(pat, s)]
        assert not hits, f"core/entitlements.py plan text carries: {hits}"

    @pytest.mark.parametrize("page", (LANDING, API_DOCS), ids=lambda p: p.parent.name)
    def test_no_typed_counts(self, page: Path):
        hits = [m.group(0) for m in TYPED_COUNT.finditer(_src(page))]
        assert not hits, f"{page.parent.name} types a count that will go stale: {hits}"

    def test_landing_does_not_claim_the_outlook_is_scored(self):
        # The registry holds only the seasonal-naive fallback; the outlook has no
        # artifact of its own (WS-23). Claim a score only once one exists.
        artifacts = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in (ROOT / "artifacts" / "accuracy").glob("*.json")
        ]
        has_model_artifact = any(not a.get("fallback_used", True) for a in artifacts)
        if not has_model_artifact:
            assert not re.search(r"scored against", _src(LANDING), re.I)


class TestPricesComeFromTheCatalog:
    def test_landing_and_billing_render_the_catalog(self):
        for page in (LANDING, BILLING):
            assert "api.billingCatalog(" in _src(page), f"{page.parent.name} must read /api/billing/catalog"

    def test_no_hardcoded_tier_tables(self):
        assert "TIER_DETAILS" not in _src(BILLING)
        assert "const TIERS" not in _src(LANDING)

    @pytest.mark.parametrize("page", (LANDING, BILLING, PRICING), ids=lambda p: p.parent.name)
    def test_no_hardcoded_plan_prices(self, page: Path):
        # Every catalog price, in any common separator style (2990, 2,990, 2 990,
        # 2.990), plus the old landing table's amounts.
        amounts = {int(p.price_nok_month) for p in PLANS.values() if p.price_nok_month > 0}
        amounts |= {2500, 5000, 15000}

        def pattern(n: int) -> str:
            digits = str(n)
            if len(digits) <= 3:
                return rf"\b{digits}\b"
            head, tail = digits[:-3], digits[-3:]
            return rf"\b{head}[\s,.  ]?{tail}\b"

        src = _src(page)
        hits = [n for n in sorted(amounts) if re.search(pattern(n), src)]
        assert not hits, f"{page.parent.name} hard-codes plan prices: {hits}"


class TestApiReferenceMatchesTheContract:
    @staticmethod
    def _known() -> dict[str, set[str]]:
        spec = json.loads((ROOT / "docs" / "openapi.frozen.json").read_text(encoding="utf-8"))
        known: dict[str, set[str]] = {}
        for path, ops in spec["paths"].items():
            known.setdefault(_norm(path), set()).update(m.upper() for m in ops)
        return known

    def test_every_documented_endpoint_exists(self):
        documented = re.findall(
            r'method:\s*"(GET|POST|PUT|DELETE|PATCH)",\s*path:\s*"([^"]+)"', _src(API_DOCS)
        )
        assert len(documented) >= 30, "the API reference parser found too few endpoints"
        known = self._known()
        missing = [(m, p) for m, p in documented if m not in known.get(_norm(p), set())]
        assert not missing, f"documented endpoints missing from docs/openapi.frozen.json: {missing}"

    def test_code_examples_call_real_endpoints(self):
        src = _src(API_DOCS)
        start, end = src.index("const CODE_EXAMPLES"), src.index("const METHOD_COLORS")
        paths = set(re.findall(r"/api/[A-Za-z0-9_\-/{}]+", src[start:end]))
        assert paths, "no paths found in CODE_EXAMPLES"
        known = self._known()
        missing = [p for p in sorted(paths) if _norm(p) not in known]
        # concrete ids (/api/decision/12345) match their templated route
        missing = [p for p in missing if _norm(re.sub(r"/\d+(?=/|$)", "/{}", p)) not in known]
        assert not missing, f"code examples call endpoints that do not exist: {missing}"

    def test_samples_carry_no_accuracy_figures(self):
        # Accuracy figures come only from artifacts in /api/accuracy; a docs sample
        # must not print an MAPE/RMSE that no artifact backs.
        samples = re.findall(r"sample:\s*'([^']*)'", _src(API_DOCS))
        assert samples, "the API reference parser found no samples"
        bad = [s for s in samples if re.search(r'"(mape|rmse|coverage_80)"\s*:\s*[0-9]', s)]
        assert not bad, f"samples print accuracy figures: {bad}"

    def test_endpoint_count_is_computed_not_typed(self):
        assert not re.search(r"\d+ endpoints across", _src(API_DOCS))


def _norm(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path.split("?")[0])
