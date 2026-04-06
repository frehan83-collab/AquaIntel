"""
Subscription & Tier Management
================================
SaaS subscription tiers for the Aquaculture Predictability Platform.

Tiers:
  Free       — Dashboard access, weekly digest, 100 API calls/month
  Professional — Real-time alerts, farm-level forecasts, treatment recs, 5K API calls
  Enterprise — Full API, supply chain intelligence, custom reports, unlimited calls
  Investor   — All Enterprise + conditional trading signals, performance tracking

Pricing (NOK/month):
  Free: 0
  Professional: 2,990
  Enterprise: 14,900
  Investor: 24,900 + 20% performance fee
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TierConfig:
    name: str
    monthly_price_nok: float
    api_calls_limit: int
    features: list[str]
    roles: list[str]  # which user roles can subscribe


TIERS: dict[str, TierConfig] = {
    "free": TierConfig(
        name="Free",
        monthly_price_nok=0,
        api_calls_limit=100,
        features=[
            "Dashboard access",
            "Weekly lice digest",
            "National-level statistics",
            "Basic heatmap",
        ],
        roles=["farmer", "buyer", "processor", "investor"],
    ),
    "professional": TierConfig(
        name="Professional",
        monthly_price_nok=2990,
        api_calls_limit=5000,
        features=[
            "Real-time alerts (15-min polling)",
            "Farm-level lice forecasts (1-2 week)",
            "Treatment recommendations",
            "Harvest-timing optimizer",
            "Risk scoring per locality",
            "Email/SMS notifications",
            "API access (5K calls/month)",
        ],
        roles=["farmer", "buyer", "processor"],
    ),
    "enterprise": TierConfig(
        name="Enterprise",
        monthly_price_nok=14900,
        api_calls_limit=-1,  # unlimited
        features=[
            "Everything in Professional",
            "Medium-term forecasts (2-6 week)",
            "Regional supply volume predictions",
            "Quality/grade forecasts",
            "Contract risk alerts",
            "Custom PDF reports",
            "Unlimited API access",
            "Priority support",
            "Multi-user accounts",
        ],
        roles=["buyer", "processor", "farmer"],
    ),
    "investor": TierConfig(
        name="Investor",
        monthly_price_nok=24900,
        api_calls_limit=-1,
        features=[
            "Everything in Enterprise",
            "Conditional trading signals (MOWI, SALM, LSG, GSF)",
            "Harvest-impact → stock-price translation",
            "Monte Carlo profit simulations",
            "Performance tracking & 20% fee calculator",
            "Backtesting engine access",
            "Paper trading execution",
        ],
        roles=["investor"],
    ),
    "intelligence": TierConfig(
        name="Intelligence",
        monthly_price_nok=39900,
        api_calls_limit=-1,
        features=[
            "Everything in Investor",
            "AI Chat Assistant (ask anything about lice/markets)",
            "What-If Scenario Simulator",
            "Auto-generated narrative reports (farmer/buyer/investor)",
            "Autonomous insight alerts (LLM-powered)",
            "RAG knowledge queries over research papers",
            "Custom AI report generation",
            "LLM cost tracked and budgeted",
        ],
        roles=["farmer", "buyer", "processor", "investor", "admin"],
    ),
}


def check_feature_access(tier: str, feature: str) -> bool:
    """Check if a tier grants access to a specific feature."""
    tier_config = TIERS.get(tier)
    if not tier_config:
        return False

    # Hierarchical: higher tiers include lower tier features
    tier_hierarchy = ["free", "professional", "enterprise", "investor"]
    tier_idx = tier_hierarchy.index(tier) if tier in tier_hierarchy else 0

    for t_name in tier_hierarchy[: tier_idx + 1]:
        t_config = TIERS.get(t_name)
        if t_config and feature in t_config.features:
            return True

    return False


def check_api_limit(tier: str, current_calls: int) -> bool:
    """Check if user is within their API call limit."""
    tier_config = TIERS.get(tier)
    if not tier_config:
        return False
    if tier_config.api_calls_limit == -1:
        return True  # unlimited
    return current_calls < tier_config.api_calls_limit


def get_tier_for_role(role: str) -> list[str]:
    """Get available tiers for a user role."""
    return [
        name for name, config in TIERS.items()
        if role in config.roles
    ]
