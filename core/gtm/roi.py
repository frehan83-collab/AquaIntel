"""GTM 101 — the ROI calculator.

Honest by construction: it **invents no market value**. Every number either comes
from the caller (their volumes, prices, costs) or is a documented default marked
``assumption: true`` in the response, together with the formula that produced it. A
salesperson can therefore show the arithmetic, and a customer can replace any input
with their own reality.

**Claim-like inputs default to zero (WS-30, 2026-10-18).** The avoidable share, the
harvest-timing gain, the basis improvement, the affected share of volume and the
loss-ratio improvement are *claims about what our product achieves for this customer*.
Shipping a default for them produced a 228x-1,693x multiple that a finance buyer reads
as a red flag, so they now start at 0 and the calculator answers a better question:
**what would have to be true for this to pay for itself?** (``break_even``).

Scale inputs (tonnes, price, treatment cost, analyst rate, plan price) keep documented
defaults: they describe the customer's world, not our effect on it.

Usage: ``POST /api/gtm/roi {"icp": "producer", "inputs": {"annual_tonnes": 12000}}``
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Defaults are documented ASSUMPTIONS, not measurements. They exist so a
# conversation can start; they are never presented as market facts.
# Claim-like inputs (what the product achieves) start at ZERO — see the module docstring.
PRODUCER_DEFAULTS = {
    "annual_tonnes": 10000.0,
    "price_nok_kg": 85.0,
    "lice_treatments_per_year": 18,
    "cost_per_treatment_nok": 250000.0,
    "treatments_avoidable_pct": 0.0,     # claim: zero until the customer supplies it
    "harvest_timing_gain_pct": 0.0,      # claim: zero until the customer supplies it
    "plan_price_nok_month": 4900.0,
}
PROCESSOR_DEFAULTS = {
    "annual_tonnes": 20000.0,
    "margin_nok_kg": 6.0,
    "contract_risk_avoided_nok": 0.0,    # claim: zero until the customer supplies it
    "share_of_volume_affected": 0.0,     # claim: the old hard-coded 0.5, now an input
    "plan_price_nok_month": 2990.0,
}
DESK_DEFAULTS = {
    "annual_tonnes": 50000.0,
    "basis_improvement_nok_kg": 0.0,     # claim: zero until the customer supplies it
    "decisions_per_month": 20,
    "minutes_saved_per_decision": 0,  # claim: zero until the customer supplies it
    "analyst_cost_nok_hour": 1200.0,
    "plan_price_nok_month": 2990.0,
}
INSURER_DEFAULTS = {
    "portfolio_sum_nok": 500_000_000.0,
    "loss_ratio_improvement_pct": 0.0,   # claim: zero until the customer supplies it
    "admin_hours_saved": 0.0,         # claim: zero until the customer supplies it
    "analyst_cost_nok_hour": 1200.0,
    "plan_price_nok_month": 25000.0,
}

ICP_DEFAULTS = {
    "producer": PRODUCER_DEFAULTS,
    "processor": PROCESSOR_DEFAULTS,
    "desk": DESK_DEFAULTS,
    "insurer": INSURER_DEFAULTS,
}

#: The one input per ICP that is a *claim about our effect*, and therefore the input the
#: break-even is computed against. Everything else is the customer's scale.
PRIMARY_DRIVER = {
    "producer": "treatments_avoidable_pct",
    "processor": "share_of_volume_affected",
    "desk": "basis_improvement_nok_kg",
    "insurer": "loss_ratio_improvement_pct",
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
            formula="annual_tonnes x 1000 x margin_nok_kg x share_of_volume_affected",
            value_nok=(
                inputs["annual_tonnes"] * 1000.0 * inputs["margin_nok_kg"]
                * inputs["share_of_volume_affected"]
            ),
            inputs_used={
                "annual_tonnes": inputs["annual_tonnes"],
                "margin_nok_kg": inputs["margin_nok_kg"],
                "share_of_volume_affected": inputs["share_of_volume_affected"],
            },
            assumption=True,
            note=(
                "share_of_volume_affected is the customer's estimate of the volume the "
                "signal can move; it used to be a hard-coded 0.5 and now starts at 0."
            ),
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


def _break_even(key: str, inputs: dict, cost: float) -> dict:
    """The value of the primary driver at which benefit equals cost (WS-30).

    This is the honest replacement for a default uplift: instead of asserting that the
    customer avoids 15 % of treatments, the calculator says what share would be needed
    for the plan to pay for itself at their scale. ``feasible`` is False when no
    value inside the input's natural range reaches break-even.
    """
    driver = PRIMARY_DRIVER[key]
    # Branches are if/elif on purpose: a dict literal would evaluate every branch and
    # read an input another ICP does not have.
    if key == "producer":
        unit = "% of lice treatments avoided"
        per_unit = inputs["lice_treatments_per_year"] * inputs["cost_per_treatment_nok"] / 100.0
        other_benefit = (
            inputs["annual_tonnes"] * 1000.0 * inputs["price_nok_kg"]
            * inputs["harvest_timing_gain_pct"] / 100.0
        )
        upper = 100.0
        formula = (
            "annual_cost / (lice_treatments_per_year x cost_per_treatment_nok) x 100, "
            "with the harvest-timing line held at the supplied value"
        )
    elif key == "processor":
        unit = "share of volume the signal moves (0-1)"
        per_unit = inputs["annual_tonnes"] * 1000.0 * inputs["margin_nok_kg"]
        other_benefit = inputs["contract_risk_avoided_nok"]
        upper = 1.0
        formula = (
            "annual_cost / (annual_tonnes x 1000 x margin_nok_kg), with contract risk "
            "held at the supplied value"
        )
    elif key == "desk":
        unit = "NOK/kg basis improvement"
        per_unit = inputs["annual_tonnes"] * 1000.0
        other_benefit = (
            inputs["decisions_per_month"] * 12
            * inputs["minutes_saved_per_decision"] / 60.0
            * inputs["analyst_cost_nok_hour"]
        )
        upper = None
        formula = (
            "annual_cost / (annual_tonnes x 1000), with the analyst-time line held at the "
            "supplied value"
        )
    else:  # insurer
        unit = "% loss-ratio improvement"
        per_unit = inputs["portfolio_sum_nok"] / 100.0
        other_benefit = inputs["admin_hours_saved"] * inputs["analyst_cost_nok_hour"]
        upper = 100.0
        formula = (
            "annual_cost / portfolio_sum_nok x 100, with underwriting time held at the "
            "supplied value"
        )

    value = None
    feasible = None
    if per_unit > 0:
        value = max(0.0, (cost - other_benefit) / per_unit)
        feasible = value <= upper if upper is not None else value > 0
        # Six decimals: a share-of-volume driver can legitimately be 3e-4, and rounding\n        # it to 4dp would miss payback by thousands of kroner.\n        value = round(value, 6)
    return {
        "input": driver,
        "unit": unit,
        "value": value,
        "feasible": feasible,
        "annual_cost_nok": round(cost, 0),
        # The plainest statement of the same fact, for a sales conversation:
        # "you need this product to create NOK X a year to pay for itself".
        "benefit_needed_nok": round(max(0.0, cost - other_benefit), 0),
        "formula": formula,
        "note": (
            "What this input would have to reach for the plan to pay for itself at the "
            "current scale; supply your own value and re-run to see the result. It is not "
            "a claim that the value is achievable."
        ),
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
    # A zero benefit is not a 0x multiple: it means the customer has not yet said what
    # the product would do for them. Say that, and give them the break-even instead.
    status = "computed" if benefit > 0 else "awaiting_customer_inputs"
    return {
        "icp": key,
        "icp_label": ICP_LABELS[key],
        "months": months,
        "status": status,
        "benefit_nok": round(benefit, 0),
        "cost_nok": round(cost, 0),
        "net_nok": round(net, 0),
        "roi_multiple": round(benefit / cost, 2) if cost else None,
        "paid_back": benefit >= cost if status == "computed" else None,
        "break_even": _break_even(key, merged, cost),
        "lines": [line.as_dict() for line in lines],
        "assumptions_used": {
            name: merged[name] for name in sorted(defaults) if name not in supplied
        },
        "inputs_supplied": supplied,
        "disclosure": (
            "Every figure above is either an input the customer supplied or a clearly "
            "labelled assumption; the platform asserts no market value. Claim-like inputs "
            "(what the product achieves) start at zero, so the default answer is 'tell us "
            "what you would change' with the break-even value named — not a multiple. "
            "Change any input to the customer's own numbers and re-run."
        ),
        "not_included": (
            "Integration effort, change management and any revenue the customer has "
            "not verified. This is a discussion tool, not a forecast and not advice."
        ),
    }
