"""Canonical entitlements — THE single source of truth for plans.

Before this module there were **two conflicting tier tables**:

  * ``core/auth.py``                — 4 tiers, per-DAY ``api_calls_per_day``
    (the figure the quota middleware actually enforced), plus route allow-lists.
  * ``core/valuechain/subscription.py`` — 5 tiers, per-MONTH ``api_calls_limit``
    (never enforced), plus feature lists.

``/api/tiers`` returned **both** to clients, so the API contradicted itself, and
``intelligence`` (present in one table only) silently fell back to the free
quota. ``CHANGELOG.md`` had already documented that the monthly figure was "NOT
what is enforced" — the honesty layer was papering over a product defect.

Both modules now *project* from this file, so the tables cannot drift again
(``tests/test_entitlements.py`` proves it).

Design decisions (see docs/ENTITLEMENTS.md):

* Keys stay backward compatible (``free``/``professional``/``enterprise``/
  ``investor``/``intelligence``) because issued JWTs and Stripe subscription
  metadata carry them; ``operator`` and ``data`` are added for commercial
  packaging (farm field tier, data-licensing tier).
* Per-day quota is the enforced unit; the monthly figure is *derived*.
* The paywall is enforced on the small curated ``PREMIUM_PREFIXES`` set — the
  crown-jewel outputs — never the whole route space. Anonymous visitors keep
  browsing (that is the funnel); an authenticated user whose plan does not cover
  a premium output gets a structured 402 with an upgrade path.
"""
from __future__ import annotations

from dataclasses import dataclass

# ── Premium prefixes: the curated, enforced paywall boundary ─────────────────
PREMIUM_PREFIXES: tuple[str, ...] = (
    "/api/market/price-outlook",
    "/api/market/price-forecast",
    "/api/market/prediction-history",
    "/api/market/hedger-signals",
    "/api/supply/demand-balance",
    "/api/supply-forecast",
    "/api/futures/",
    "/api/ais/",
    "/api/contracts/",
    "/api/investor/event-impact/",
    "/api/harvest/optimize",
    "/api/feed-supply-chain/",
    "/api/ml/ensemble/",
    "/api/scenarios/compound",
    "/api/indices/premium/",
)

# Never gated, whatever the plan (login, upgrade, infra, public indices).
NEVER_GATED: tuple[str, ...] = (
    "/api/auth/",
    "/api/billing/",
    "/api/health",
    "/api/entitlements",
    "/api/tiers",
    "/api/disclaimer",
)

# Alias strings seen in tokens, Stripe metadata and older docs.
LEGACY_ALIASES: dict[str, str] = {
    "premium": "professional",
    "pro": "professional",
    "desk": "professional",
    "basic": "free",
    "starter": "free",
    "trial": "free",
    "pilot": "professional",
    "growth": "operator",
    "farm": "operator",
    "licence": "data",
    "license": "data",
    "datapartner": "data",
    # legacy names for the paid tiers (from pre-SSOT tokens/docs)
    "market": "enterprise",
    "institutional": "investor",
}


@dataclass(frozen=True)
class Plan:
    """One commercial plan. Frozen so callers cannot mutate the SSOT."""

    key: str
    name: str
    audience: str
    price_nok_month: float
    api_calls_per_day: int              # <= 0 means unlimited
    seats: int                          # <= 0 means unlimited
    sites: int                          # <= 0 means unlimited
    features: tuple[str, ...]
    all_routes: bool = False            # True = every non-admin route
    premium: bool = False               # True = may call PREMIUM_PREFIXES
    upgrade_to: str | None = None       # suggested next plan for the 402 payload
    roles: tuple[str, ...] = ()

    @property
    def api_calls_per_month(self) -> int:
        """Derived — never stored separately (the old drift source)."""
        return -1 if self.api_calls_per_day <= 0 else self.api_calls_per_day * 30


# Ordered free → highest (the hierarchy used for entitlement checks).
PLANS: dict[str, Plan] = {
    "free": Plan(
        key="free",
        name="Insight",
        audience="Analysts, journalists, evaluation",
        price_nok_month=0,
        api_calls_per_day=100,
        seats=1,
        sites=0,
        features=(
            "Public indices (AI-STI, AI-LPI) and Accuracy & Method",
            "National-level statistics",
            "Bio>Price Weekly digest",
            "30-day lag on market detail",
        ),
        roles=("farmer", "buyer", "processor", "investor", "analyst"),
        upgrade_to="operator",
    ),
    "operator": Plan(
        key="operator",
        name="Operator",
        audience="Farm operations, lice/welfare/quota managers",
        price_nok_month=4900,
        api_calls_per_day=5000,
        seats=3,
        sites=25,
        features=(
            "Everything in Insight",
            "Lice forecasting (1-4 weeks) and quota headroom",
            "Lice emission quota + ASC welfare compliance pack",
            "Treatment checklist and cost comparison",
            "Field/mobile experience with offline capture",
        ),
        roles=("farmer", "processor"),
        upgrade_to="professional",
    ),
    "professional": Plan(
        key="professional",
        name="Desk",
        audience="Trading desks, buyers, sales planners, analysts",
        price_nok_month=2990,
        api_calls_per_day=20000,
        seats=5,
        sites=0,
        premium=True,
        features=(
            "Everything in Operator",
            "Real-time supply tension (AI-STI) and harvest runway",
            "2-20 week price path with conformal bands",
            "Feed margin squeeze alerts",
            "Contract risk and hedge exposure",
            "API access (20k calls/day)",
        ),
        roles=("buyer", "processor", "investor", "farmer"),
        upgrade_to="enterprise",
    ),
    "enterprise": Plan(
        key="enterprise",
        name="Enterprise",
        audience="Integrated producers, large processors",
        price_nok_month=14900,
        api_calls_per_day=50000,
        seats=0,
        sites=0,
        all_routes=True,
        premium=True,
        features=(
            "Everything in Desk",
            "Multi-country supply balance and disruption alerts",
            "Harvest optimizer with NOK-value simulation",
            "Custom indices, embedded API, SSO, SLA",
            "Unlimited seats and locations",
        ),
        roles=("farmer", "processor", "buyer", "investor", "admin"),
    ),
    "investor": Plan(
        key="investor",
        name="Investor",
        audience="Investors and funds",
        price_nok_month=24900,
        api_calls_per_day=100000,
        seats=0,
        sites=0,
        all_routes=True,
        premium=True,
        features=(
            "Everything in Enterprise",
            "Monte Carlo profit simulations and backtesting",
            "Paper trading with audit trail",
        ),
        roles=("investor",),
    ),
    "intelligence": Plan(
        key="intelligence",
        name="Intelligence",
        audience="AI-first customers",
        price_nok_month=39900,
        api_calls_per_day=100000,
        seats=0,
        sites=0,
        all_routes=True,
        premium=True,
        features=(
            "Everything in Investor",
            "AI assistant and scenario sandbox",
            "Auto-generated narrative reports",
            "RAG queries over research literature",
        ),
        roles=("farmer", "buyer", "processor", "investor", "admin"),
    ),
    "data": Plan(
        key="data",
        name="Data & Assurance",
        audience="Insurers, banks, assurance providers",
        price_nok_month=0,  # licensed per contract (EUR 25k-150k/yr)
        api_calls_per_day=250000,
        seats=0,
        sites=0,
        all_routes=True,
        premium=True,
        features=(
            "Licensed trigger feeds (SST, lice, bloom) with SLA",
            "Historical archive access",
            "Accuracy & provenance attestations",
            "API/SFTP delivery, no UI required",
        ),
        roles=("partner",),
    ),
}

PLAN_HIERARCHY: tuple[str, ...] = (
    "free",
    "operator",
    "professional",
    "enterprise",
    "investor",
    "intelligence",
)

# Route allow-lists for the non-`all_routes` plans (used by the auth/misc tier
# surfaces and by `check_tier_access`). `all_routes` plans report "all".
_PLAN_ROUTE_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "free": (
        "/api/health", "/api/brief", "/api/lice/summary", "/api/signals",
        "/api/auth/", "/api/billing/", "/api/entitlements", "/api/tiers",
        "/api/indices/", "/api/accuracy", "/api/disclaimer",
    ),
    "operator": (
        "/api/health", "/api/brief", "/api/lice/", "/api/signals",
        "/api/auth/", "/api/billing/", "/api/entitlements", "/api/tiers",
        "/api/indices/", "/api/accuracy", "/api/disclaimer",
        "/api/farms/", "/api/farm-graph/", "/api/treatment/", "/api/disease/",
        "/api/regulatory/", "/api/compliance/", "/api/ocean/", "/api/climate/",
        "/api/alerts", "/api/notifications/", "/api/analytics/", "/api/anomaly/",
        "/api/ras/", "/api/twin/", "/api/efficacy/",
    ),
    "professional": (
        "/api/health", "/api/brief", "/api/lice/", "/api/signals",
        "/api/auth/", "/api/billing/", "/api/entitlements", "/api/tiers",
        "/api/indices/", "/api/accuracy", "/api/disclaimer",
        "/api/farms/", "/api/farm-graph/", "/api/treatment/", "/api/disease/",
        "/api/regulatory/", "/api/compliance/", "/api/ocean/", "/api/climate/",
        "/api/alerts", "/api/notifications/", "/api/analytics/", "/api/anomaly/",
        "/api/ras/", "/api/twin/", "/api/efficacy/",
        "/api/market/", "/api/supply", "/api/supply/", "/api/futures/",
        "/api/feed-cost/", "/api/feed-supply-chain/", "/api/global",
        "/api/sentiment/", "/api/ais/", "/api/biomass/", "/api/esg/",
        "/api/leaders/", "/api/regime/", "/api/pairs/", "/api/causal/",
        "/api/intelligence/", "/api/exposure/", "/api/production/",
        "/api/contracts/", "/api/investor/", "/api/parametric/", "/api/ml/",
        "/api/chat/", "/api/scenarios/", "/api/backtest/", "/api/traceability/",
        "/api/macro/", "/api/chile/", "/api/canada/", "/api/iceland/",
        "/api/faroes/", "/api/scotland/", "/api/harvest/", "/api/tiers",
    ),
}

_PLAN_PAGES: dict[str, object] = {
    "free": ("/", "/brief", "/settings", "/billing", "/accuracy", "/indices"),
    "operator": ("/", "/brief", "/settings", "/billing", "/disease", "/lice-quota",
                 "/farmer-daily", "/harvest", "/compliance", "/accuracy", "/indices"),
    "professional": "all",
}


# ── Lookup + policy ─────────────────────────────────────────────────────────

def normalize_plan(tier: str | None) -> str:
    """Map any tier string (canonical, alias, unknown) to a canonical key."""
    if not tier:
        return "free"
    key = str(tier).strip().lower()
    key = LEGACY_ALIASES.get(key, key)
    return key if key in PLANS else "free"


def get_plan(tier: str | None) -> Plan:
    return PLANS[normalize_plan(tier)]


def daily_quota(tier: str | None) -> int:
    """The enforced per-day allowance (<= 0 means unlimited)."""
    return get_plan(tier).api_calls_per_day


def feature_allowed(tier: str | None, feature: str) -> bool:
    """Feature check by substring across the plan hierarchy (inclusive)."""
    plan = get_plan(tier)
    idx = PLAN_HIERARCHY.index(plan.key) if plan.key in PLAN_HIERARCHY else -1
    for name in PLAN_HIERARCHY[: idx + 1] if idx >= 0 else [plan.key]:
        if feature in PLANS[name].features:
            return True
    return feature in plan.features


def is_premium_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in PREMIUM_PREFIXES)


def route_allowed(tier: str | None, path: str) -> bool:
    """May this plan call `path`?

    Policy (one place, one meaning — this is what the middleware enforces):

    * Anonymous visitors are **not an account**: the public site stays browsable
      (the funnel). The paywall applies to authenticated plans.
    * NEVER_GATED paths are always allowed (login/upgrade/infra).
    * Non-premium paths are always allowed, whatever the plan.
    * Only the curated PREMIUM_PREFIXES outputs require a premium-capable plan.
    """
    if tier is None or str(tier).strip() == "":
        return True  # anonymous: ungated public browsing
    if any(path.startswith(p) for p in NEVER_GATED):
        return True
    plan = get_plan(tier)
    if plan.all_routes or plan.premium:
        return True
    return not is_premium_path(path)


def upgrade_hint(
    tier: str | None,
    *,
    error: str,
    reason: str,
    path: str | None = None,
) -> dict:
    """Structured, actionable upgrade payload for 402/429 responses.

    One shape for both quota exhaustion and missing entitlement so clients can
    render the same "upgrade" affordance.
    """
    plan = get_plan(tier)
    suggested = plan.upgrade_to or "professional"
    return {
        "error": error,
        "message": reason,
        "current_plan": plan.key,
        "current_plan_name": plan.name,
        "tier": plan.key,  # backward-compatible alias for existing clients
        "current_api_calls_per_day": plan.api_calls_per_day,
        "requested_path": path,
        "suggested_plan": suggested,
        "suggested_plan_name": PLANS[suggested].name,
        "upgrade_url": f"/billing?plan={suggested}",
        "plans_url": "/api/entitlements/plans",
    }


# ── Compatibility projections (the wiring that removes the drift) ───────────

def auth_tiers() -> dict[str, dict]:
    """Projection for ``core.auth.TIERS`` (historical shape, ONE source now)."""
    out: dict[str, dict] = {}
    for key, plan in PLANS.items():
        if key == "data":
            continue  # licensed tier is not part of the self-serve hierarchy
        routes = "all" if plan.all_routes else list(_PLAN_ROUTE_ALLOWLIST.get(key, ()))
        pages = "all" if plan.all_routes else list(_PLAN_PAGES.get(key, ("/",)))
        out[key] = {
            "name": plan.name,
            "price_nok": plan.price_nok_month,
            "routes": routes,
            "pages": pages,
            "api_calls_per_day": plan.api_calls_per_day,
            "features": list(plan.features),
        }
    return out


def catalog_tiers() -> dict[str, dict]:
    """Projection for ``core.valuechain.subscription.TIERS`` (historical shape)."""
    return {
        key: {
            "name": plan.name,
            "monthly_price_nok": plan.price_nok_month,
            "api_calls_limit": plan.api_calls_per_month,
            "features": list(plan.features),
            "roles": list(plan.roles),
            "seats": plan.seats,
            "sites": plan.sites,
            "audience": plan.audience,
        }
        for key, plan in PLANS.items()
    }


def plan_catalog() -> list[dict]:
    """Pricing-page model: canonical plans in hierarchy order + licensing tier."""
    ordered = [PLANS[k] for k in PLAN_HIERARCHY] + [PLANS["data"]]
    return [
        {
            "key": p.key,
            "name": p.name,
            "audience": p.audience,
            "price_nok_month": p.price_nok_month,
            "price_eur_month": round(p.price_nok_month / 11.5, -1) if p.price_nok_month else 0,
            "api_calls_per_day": p.api_calls_per_day,
            "seats": p.seats,
            "sites": p.sites,
            "features": list(p.features),
            "upgrade_to": p.upgrade_to,
        }
        for p in ordered
    ]




