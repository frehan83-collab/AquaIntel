"""The inference sub-processors this deployment can send customer content to (WS-51).

One list, read by the disclosure endpoint and by the provider guard. It states what is **known**
about each transfer mechanism rather than what would be convenient: `contracted` is False for a
provider with no signed DPA, and `zero_retention` is False unless an agreement says so. A
customer's lawyer can read this and see exactly what is and is not in place.

The register is deliberately conservative. The free OpenRouter models are the weakest link: a free
endpoint commonly reserves the right to retain and use inputs, which would make the provider a
controller rather than a processor.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubProcessor:
    key: str
    name: str
    purpose: str
    data_categories: tuple[str, ...]
    location: str
    transfer_mechanism: str
    contracted: bool
    zero_retention: bool
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "purpose": self.purpose,
            "data_categories": list(self.data_categories),
            "location": self.location,
            "transfer_mechanism": self.transfer_mechanism,
            "contracted": self.contracted,
            "zero_retention": self.zero_retention,
            "note": self.note,
        }


SUBPROCESSORS: dict[str, SubProcessor] = {
    "openrouter": SubProcessor(
        key="openrouter",
        name="OpenRouter (routing and inference)",
        purpose="Model inference for grounded chat answers and paid analysis documents.",
        data_categories=("question text", "assembled market facts (no farm identifiers beyond "
                         "the locality number the user supplies)", "account key"),
        location="United States",
        transfer_mechanism="none on file — standard contractual clauses not signed",
        contracted=False,
        zero_retention=False,
        note=(
            "Every model-backed answer and document passes through this provider. The DPA and "
            "SCCs are the blocking item recorded in docs/ADVICE_BOUNDARY.md."
        ),
    ),
    "openrouter_free": SubProcessor(
        key="openrouter_free",
        name="OpenRouter free-tier model endpoints",
        purpose="Degraded fallback when the paid model is unavailable (LLM_FREE_FALLBACK).",
        data_categories=("question text", "assembled market facts"),
        location="Provider-dependent (often United States)",
        transfer_mechanism="none on file",
        contracted=False,
        zero_retention=False,
        note=(
            "Free endpoints frequently reserve the right to retain and use inputs; a free answer "
            "is labelled `model_is_free` in the payload for that reason. Disable with "
            "LLM_FREE_FALLBACK=false."
        ),
    ),
    "stripe": SubProcessor(
        key="stripe",
        name="Stripe",
        purpose="Subscription and credit-pack payments.",
        data_categories=("name", "email", "billing address", "payment metadata"),
        location="Ireland (EU) / United States",
        transfer_mechanism="DPA available on acceptance — status to be recorded here",
        contracted=False,
        zero_retention=False,
        note="No card data reaches this platform.",
    ),
}


def disclosure(provider: str | None = None) -> dict:
    """The public register, with an explicit statement of what is missing."""
    items = [sp.to_dict() for sp in SUBPROCESSORS.values()]
    missing = [sp.key for sp in SUBPROCESSORS.values() if not sp.contracted]
    return {
        "sub_processors": items,
        "provider_in_use": provider or "not configured",
        "contracted_count": sum(1 for sp in SUBPROCESSORS.values() if sp.contracted),
        "total_count": len(SUBPROCESSORS),
        "missing_contracts": missing,
        "statement": (
            "This register is a factual list of the processors this deployment can use and the "
            "status of each transfer mechanism. It is not a claim of compliance: entries marked "
            "contracted=false have no signed data-processing agreement, so sending customer "
            "content to them is not covered by Article 28."
        ),
    }


def is_contracted(key: str) -> bool:
    entry = SUBPROCESSORS.get(key)
    return bool(entry and entry.contracted)
