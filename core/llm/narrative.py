"""
Explainability & Narrative Generator
======================================
Produces stakeholder-specific plain-language reports:
  - Farmer treatment briefs
  - Buyer supply-risk memos
  - Investor thesis summaries
  - Regulatory summaries
"""
from __future__ import annotations

import json

from core.llm.client import llm_client
from core.llm.prompts import (
    SYSTEM_AQUACULTURE_EXPERT,
    NARRATIVE_FARMER_TEMPLATE,
    NARRATIVE_BUYER_TEMPLATE,
    NARRATIVE_INVESTOR_TEMPLATE,
)

import structlog

log = structlog.get_logger(__name__)


class NarrativeGenerator:
    """Generates stakeholder-specific narrative reports."""

    async def farmer_brief(self, farm_data: dict) -> str:
        """Generate a farmer treatment brief."""
        prompt = NARRATIVE_FARMER_TEMPLATE.format(
            farm_data=json.dumps(farm_data, indent=2, default=str)
        )
        resp = await llm_client.complete(
            prompt=prompt,
            system=SYSTEM_AQUACULTURE_EXPERT,
            max_tokens=1024,
        )
        return resp.content

    async def buyer_memo(self, supply_data: dict) -> str:
        """Generate a buyer supply-risk memo."""
        prompt = NARRATIVE_BUYER_TEMPLATE.format(
            supply_data=json.dumps(supply_data, indent=2, default=str)
        )
        resp = await llm_client.complete(
            prompt=prompt,
            system=SYSTEM_AQUACULTURE_EXPERT,
            max_tokens=1500,
        )
        return resp.content

    async def investor_thesis(self, market_data: dict) -> str:
        """Generate an investor thesis summary."""
        prompt = NARRATIVE_INVESTOR_TEMPLATE.format(
            market_data=json.dumps(market_data, indent=2, default=str)
        )
        resp = await llm_client.complete(
            prompt=prompt,
            system=SYSTEM_AQUACULTURE_EXPERT,
            max_tokens=1500,
        )
        return resp.content

    async def custom_report(
        self, data: dict, audience: str, focus: str = ""
    ) -> str:
        """Generate a custom report for any audience."""
        prompt = (
            f"Generate a {audience} report"
            f"{' focusing on ' + focus if focus else ''}.\n\n"
            f"DATA:\n{json.dumps(data, indent=2, default=str)}\n\n"
            f"Write a clear, structured report with specific numbers and actionable insights."
        )
        resp = await llm_client.complete(
            prompt=prompt,
            system=SYSTEM_AQUACULTURE_EXPERT,
            max_tokens=2000,
        )
        return resp.content


narrative_generator = NarrativeGenerator()
