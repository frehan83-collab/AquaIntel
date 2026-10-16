"""GTM 101 — the ROI calculator.

Honest by construction: it **invents no market value**. Every number either comes
from the caller (their volumes, prices, costs) or is a documented default marked
``assumption: true`` in the response, together with the formula that produced it. A
salesperson can therefore show the arithmetic, and a customer can replace any input
with their own reality.

Usage: ``POST /api/gtm/roi {"icp": "producer", "inputs": {"annual_tonnes": 12000}}``
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Defaults are documented ASSUMPTIONS, not measurements. They exist so a
# conversation can start; they are never presented as market facts.
PRODUCER_DEFAULTS = {
    "annual_tonnes": 10000.0,
    "price_nok_kg": 85.0,
    "lice_treatments_per_year": 18,
    "cost_per_treatment_nok": 250000.0,
    "treatments_avoidable_pct": 15.0,
    "harvest_timing_gain_pct": 1.5,
    "plan_price_nok_month": 4900.0,
}
PROCESSOR_DEFAULTS = {
    "annual_tonnes": 20000.0,
    "margin_nok_kg": 6.0,
    "contract_risk_avoided_nok": 750000.0,
    "plan_price_nok_month": 2990.0,
}
DESK_DEFAULTS = {
    "annual_tonnes": 50000.0,
    "basis_improvement_nok_kg": 0.35,
    "decisions_per_month": 20,
    "minutes_saved_per_decision": 25,
    "analyst_cost_nok_hour": 1200.0,
    "plan_price_nok_month": 2990.0,
}
INSURER_DEFAULTS = {
    "portfolio_sum_nok": 500_000_000.0,
    "loss_ratio_improvement_pct": 0.5,
    "admin_hours_saved": 400.0,
    "analyst_cost_nok_hour": 1200.0,
    "plan_price_nok_month": 25000.0,
}

ICP_DEFAULTS = {
    "producer": PRODUCER_DEFAULTS,
    "processor": PROCESSOR_DEFAULTS,
    "desk": DESK_DEFAULTS,
    "insurer": INSURER_DEFAULTS,
}

ICP_LABELS = {
    "producer": "Salmon producer (farm operations / lice / quotas)",
    "processor": "Processor / secondary processing",
    "desk": "Trading desk / buyer / sales planner",
    "insurer": "Insurer / bank / assurance provider",
}


@dataclass
class RoiLine:
    name: str
    formula: str
    value_nok: float
    inputs_used: dict = field(default_factory=dict)
    assumption: bool = False
    note: str | None = None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "formula": self.formula,
            "value_nok": round(self.value_nok, 0),
            "inputs_used": self.inputs_used,
            "assumption": self.assumption,
            "note": self.note,
        }


def _producer(inputs: dict) -> list[RoiLine]:
    return [
        RoiLine(
            name="Avoided lice treatment cost",
            formula=(
                "lice_treatments_per_year x cost_per_treatment_nok x "
                "treatments_avoidable_pct / 100"
            ),
            value_nok=(
                inputs["lice_treatments_per_year"]
                * inputs["cost_per_treatment_nok"]
                * inputs["treatments_avoidable_pct"]
                / 100.0
            ),
            inputs_used={
                "lice_treatments_per_year": inputs["lice_treatments_per_year"],
                "cost_per_treatment_nok": inputs["cost_per_treatment_nok"],
                "treatments_avoidable_pct": inputs["treatments_avoidable_pct"],
            },
            assumption=True,
            note=(
                "Treatment cost is farm-specific; the avoidable share must be "
                "validated with the customer."
            ),
        ),
        RoiLine(
            name="Harvest-timing uplift",
            formula="annual_tonnes x 1000 x price_nok_kg x harvest_timing_gain_pct / 100",
            value_nok=(
                inputs["annual_tonnes"] * 1000.0 * inputs["price_nok_kg"]
                * inputs["harvest_timing_gain_pct"] / 100.0
            ),
            inputs_used={
                "annual_tonnes": inputs["annual_tonnes"],
                "price_nok_kg": inputs["price_nok_kg"],
                "harvest_timing_gain_pct": inputs["harvest_timing_gain_pct"],
            },
            assumption=True,
            note="Depends on the price path realised; the AI-STI horizon is the basis.",
        ),
    ]


def _processor(inputs: dict) -> list[RoiLine]:
    return [
        RoiLine(
            name="Contract-risk cost avoided",
            formula="contract_risk_avoided_nok",
            value_nok=inputs["contract_risk_avoided_nok"],
            inputs_used={"contract_risk_avoided_nok": inputs["contract_risk_avoided_nok"]},
            assumption=True,
            note="Customer-supplied; we do not estimate their exposure for them.",
        ),
        RoiLine(
            name="Margin protected by earlier sourcing signal",
            formula="annual_tonnes x 1000 x margin_nok_kg x 0.5",
            value_nok=inputs["annual_tonnes"] * 1000.0 * inputs["margin_nok_kg"] * 0.5,
            inputs_used={
                "annual_tonnes": inputs["annual_tonnes"],
                "margin_nok_kg": inputs["margin_nok_kg"],
            },
            assumption=True,
            note="The 0.5 factor is a placeholder for the share of volume a signal can affect.",
        ),
    ]


def _desk(inputs: dict) -> list[RoiLine]:
    return [
        RoiLine(
            name="Basis improvement on hedged volume",
            formula="annual_tonnes x 1000 x basis_improvement_nok_kg",
            value_nok=inputs["annual_tonnes"] * 1000.0 * inputs["basis_improvement_nok_kg"],
            inputs_used={
                "annual_tonnes": inputs["annual_tonnes"],
                "basis_improvement_nok_kg": inputs["basis_improvement_nok_kg"],
            },
            assumption=True,
            note="Requires the desk to confirm the basis improvement they can capture.",
        ),
        RoiLine(
            name="Analyst time saved",
            formula=(
                "decisions_per_month x 12 x minutes_saved_per_decision / 60 x "
                "analyst_cost_nok_hour"
            ),
            value_nok=(
                inputs["decisions_per_month"] * 12
                * inputs["minutes_saved_per_decision"] / 60.0
                * inputs["analyst_cost_nok_hour"]
            ),
            inputs_used={
                "decisions_per_month": inputs["decisions_per_month"],
                "minutes_saved_per_decision": inputs["minutes_saved_per_decision"],
                "analyst_cost_nok_hour": inputs["analyst_cost_nok_hour"],
            },
            assumption=True,
        ),
    ]


def _insurer(inputs: dict) -> list[RoiLine]:
    return [
        RoiLine(
            name="Expected loss-ratio improvement",
            formula="portfolio_sum_nok x loss_ratio_improvement_pct / 100",
            value_nok=(
                inputs["portfolio_sum_nok"] * inputs["loss_ratio_improvement_pct"] / 100.0
            ),
            inputs_used={
                "portfolio_sum_nok": inputs["portfolio_sum_nok"],
                "loss_ratio_improvement_pct": inputs["loss_ratio_improvement_pct"],
            },
            assumption=True,
            note="Expectation, not a quote — parametric pricing needs validated triggers.",
        ),
        RoiLine(
            name="Underwriting time saved",
            formula="admin_hours_saved x analyst_cost_nok_hour",
            value_nok=inputs["admin_hours_saved"] * inputs["analyst_cost_nok_hour"],
            inputs_used={"admin_hours_saved": inputs["admin_hours_saved"]},
            assumption=True,
        ),
    ]


CALCULATORS = {
    "producer": _producer,
    "processor": _processor,
    "desk": _desk,
    "insurer": _insurer,
}


def calculate(icp: str, inputs: dict | None = None, *, months: int = 12) -> dict:
    """Compute ROI for an ICP. Unknown inputs fall back to labelled assumptions."""
    key = (icp or "").strip().lower()
    if key not in CALCULATORS:
        raise ValueError(f"unknown icp '{icp}' (expected one of {sorted(CALCULATORS)})")

    defaults = ICP_DEFAULTS[key]
    supplied = {k: v for k, v in (inputs or {}).items() if v is not None}
    unknown = sorted(set(supplied) - set(defaults))
    if unknown:
        raise ValueError(f"unknown input(s) for '{key}': {unknown}")

    merged = {**defaults, **supplied}
    lines = CALCULATORS[key](merged)
    benefit = sum(line.value_nok for line in lines)
    cost = merged["plan_price_nok_month"] * months
    net = benefit - cost
    return {
        "icp": key,
        "icp_label": ICP_LABELS[key],
        "months": months,
        "benefit_nok": round(benefit, 0),
        "cost_nok": round(cost, 0),
        "net_nok": round(net, 0),
        "roi_multiple": round(benefit / cost, 2) if cost else None,
        "lines": [line.as_dict() for line in lines],
        "assumptions_used": {
            name: merged[name] for name in sorted(defaults) if name not in supplied
        },
        "inputs_supplied": supplied,
        "disclosure": (
            "Every figure above is either an input the customer supplied or a clearly "
            "labelled assumption; the platform asserts no market value. Change any "
            "input to the customer's own numbers and re-run."
        ),
        "not_included": (
            "Integration effort, change management and any revenue the customer has "
            "not verified. This is a discussion tool, not a forecast and not advice."
        ),
    }
