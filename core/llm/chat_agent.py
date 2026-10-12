"""
Conversational Decision Intelligence Agent
============================================
Natural-language chat interface that performs chain-of-thought reasoning
over real-time predictions, historical data, and regulatory context.

Supports multi-turn tool-use: the LLM can call platform tools (lice data,
price forecasts, disease status, etc.) in a loop, building up context
before delivering a final answer.  Falls back to keyword-based tool
enrichment when the LLM provider does not support native tool-use.

Users ask questions like:
  "Should we treat now or delay harvest in PA 3?"
  "What's the lice outlook for Mowi this month?"
  "Compare treatment options for locality 13035"
"""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import select, func

from core.llm.client import llm_client
from core.llm.prompts import (
    SYSTEM_AQUACULTURE_EXPERT,
    DECISION_INTELLIGENCE_PROMPT,
    HORIZON_CONTEXT_TEMPLATE,
)
from core.predictors.medium_term import HORIZON_ACCURACY, uncertainty_scale
from core.models import LiceRecord, Locality, CompanyExposure, Signal
from core.async_db import get_async_session

import structlog

log = structlog.get_logger(__name__)

MAX_TOOL_ITERATIONS = 5


class ChatAgent:
    """Conversational decision intelligence over platform data."""

    # Bounded history (arch report §3.2/#10): prevents unbounded memory creep
    # in long-lived worker processes. Multi-turn context only uses the last 6.
    MAX_HISTORY_ENTRIES = 200

    def __init__(self) -> None:
        self.conversation_history: list[dict] = []

    def _append_history(self, role: str, content: str, **extra) -> None:
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
            **extra,
        })
        if len(self.conversation_history) > self.MAX_HISTORY_ENTRIES:
            del self.conversation_history[:-self.MAX_HISTORY_ENTRIES]

    # ── public entry point ──────────────────────────────────────────
    async def ask(self, question: str, user_id: str = "user", horizon: int = 4) -> str:
        """Process a natural-language question with full data context.

        Uses multi-turn tool-use when the Anthropic provider is active.
        Falls back to keyword-based tool enrichment for OpenAI/OpenRouter.
        """
        # Build data context from current DB state
        context = await self._build_context(question)

        # Build horizon-aware accuracy context
        acc = HORIZON_ACCURACY.get(horizon, HORIZON_ACCURACY[4])
        horizon_context = HORIZON_CONTEXT_TEMPLATE.format(
            horizon=horizon,
            accuracy_band=acc["band"].upper(),
            uncertainty_multiplier=f"{uncertainty_scale(horizon):.1f}",
        )

        # Try native multi-turn tool-use first (all providers — OpenAI and
        # OpenRouter support function tools; OpenRouter proxies Claude
        # tool-use). Falls back to keyword enrichment on any failure.
        try:
            answer = await self._agentic_ask(
                question, context, horizon_context, user_id,
            )
            return answer
        except NotImplementedError:
            log.info("chat.tool_use_not_supported, falling back to enrichment")
        except Exception as exc:
            log.warning("chat.agentic_ask_failed", error=str(exc)[:120])

        # Fallback: enrich context with keyword-matched tool calls, then
        # do a single-turn completion.
        return await self._enriched_ask(question, context, horizon_context, user_id)

    # ── multi-turn agentic loop (Anthropic native tool-use) ─────────
    async def _agentic_ask(
        self,
        question: str,
        data_context: str,
        horizon_context: str,
        user_id: str,
    ) -> str:
        """Run a multi-turn conversation where the LLM can call tools."""
        from core.llm.tools import TOOLS, TOOL_MAP

        system_prompt = (
            SYSTEM_AQUACULTURE_EXPERT
            + "\n\nYou have access to live data tools. Use them to fetch the latest "
            "lice counts, price forecasts, disease outbreaks, supply data, and farm "
            "network risk before answering.  Call multiple tools if the question "
            "spans several topics.  After gathering data, synthesize a clear, "
            "actionable answer with confidence levels."
        )

        # Seed the conversation with data context + user question
        user_content = (
            f"CURRENT DATA SNAPSHOT:\n{data_context}\n\n"
            f"FORECAST HORIZON CONTEXT:\n{horizon_context}\n\n"
            f"USER QUESTION: {question}\n\n"
            "Provide your analysis with:\n"
            "1. Key observations from the data\n"
            "2. Step-by-step reasoning\n"
            "3. Specific recommendation with confidence level (low/medium/high)\n"
            "4. Risk factors to consider\n"
            "5. Suggested next actions"
        )

        messages: list[dict] = []
        # Include recent conversation history for multi-turn context
        for entry in self.conversation_history[-6:]:
            if entry["role"] in ("user", "assistant"):
                messages.append({"role": entry["role"], "content": entry["content"]})
        messages.append({"role": "user", "content": user_content})

        final_text = ""
        for iteration in range(MAX_TOOL_ITERATIONS):
            response = await llm_client.complete_with_tools(
                messages=messages,
                tools=TOOLS,
                system=system_prompt,
                user_id=user_id,
            )

            tool_calls = response.get("tool_calls", [])
            text = response.get("text", "")

            if not tool_calls:
                # No more tool calls — this is the final answer
                final_text = text
                break

            # Append assistant turn with both text + tool_use blocks
            assistant_content = []
            if text:
                assistant_content.append({"type": "text", "text": text})
            for tc in tool_calls:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["input"],
                })
            messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool and collect results
            tool_results = []
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_input = tc.get("input", {})
                tool_id = tc["id"]

                handler = TOOL_MAP.get(tool_name, {}).get("handler")
                if handler:
                    try:
                        result = await handler(**tool_input)
                        result_str = json.dumps(result, default=str) if not isinstance(result, str) else result
                    except Exception as e:
                        result_str = json.dumps({"error": str(e)[:200]})
                        log.warning("chat.tool_error", tool=tool_name, error=str(e)[:100])
                else:
                    result_str = json.dumps({"error": f"Unknown tool: {tool_name}"})

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result_str,
                })

                log.info("chat.tool_called", tool=tool_name, iteration=iteration)

            messages.append({"role": "user", "content": tool_results})
            final_text = text  # keep latest text in case we hit max iterations
        else:
            # Exhausted iterations — use whatever text we have
            if not final_text:
                final_text = (
                    "I reached the maximum number of analysis steps. "
                    "Here is what I found so far based on the data retrieved."
                )

        # Persist to conversation history (bounded)
        self._append_history("user", question)
        self._append_history("assistant", final_text)

        return final_text

    # ── keyword-based tool enrichment fallback ──────────────────────
    async def _enrich_context_with_tools(self, message: str) -> str:
        """Call relevant tools based on message keywords to enrich context."""
        from core.llm.tools import TOOL_MAP

        enrichments: list[str] = []
        msg_lower = message.lower()

        keyword_tool_map = [
            (
                ["lice", "louse", "threshold", "pa-", "production area", "adult female"],
                "get_lice_data",
                {},
                "LIVE LICE DATA",
            ),
            (
                ["price", "forecast", "outlook", "cost", "nok", "spot", "salmon price"],
                "get_price_outlook",
                {},
                "LIVE PRICE OUTLOOK",
            ),
            (
                ["disease", "isa", " pd", "outbreak", "mattilsynet", "infection"],
                "get_disease_status",
                {},
                "LIVE DISEASE STATUS",
            ),
            (
                ["supply", "demand", "harvest", "smolt", "biomass", "production volume"],
                "get_supply_forecast",
                {},
                "LIVE SUPPLY FORECAST",
            ),
            (
                ["network", "cluster", "spread", "cascade", "farm graph", "dispersal"],
                "get_farm_network_risk",
                {},
                "LIVE FARM NETWORK RISK",
            ),
        ]

        for keywords, tool_name, kwargs, label in keyword_tool_map:
            if any(w in msg_lower for w in keywords):
                entry = TOOL_MAP.get(tool_name)
                if entry and entry.get("handler"):
                    try:
                        result = await entry["handler"](**kwargs)
                        enrichments.append(
                            f"[{label}]\n{json.dumps(result, default=str)[:500]}"
                        )
                        log.info("chat.tool_enrichment", tool=tool_name)
                    except Exception as e:
                        log.warning("chat.tool_enrichment_error", tool=tool_name, error=str(e)[:80])

        return "\n\n".join(enrichments)

    async def _enriched_ask(
        self,
        question: str,
        data_context: str,
        horizon_context: str,
        user_id: str,
    ) -> str:
        """Single-turn completion enriched with keyword-matched tool data."""
        tool_context = await self._enrich_context_with_tools(question)
        if tool_context:
            data_context = (
                data_context
                + "\n\n--- LIVE DATA (fetched just now) ---\n"
                + tool_context
            )

        prompt = DECISION_INTELLIGENCE_PROMPT.format(
            data_context=data_context,
            horizon_context=horizon_context,
            question=question,
        )

        resp = await llm_client.complete(
            prompt=prompt,
            system=SYSTEM_AQUACULTURE_EXPERT,
            user_id=user_id,
        )

        # Track conversation (bounded)
        self._append_history("user", question)
        self._append_history(
            "assistant", resp.content,
            tokens=resp.input_tokens + resp.output_tokens,
            cost=resp.cost_usd,
        )

        return resp.content

    @staticmethod
    async def _build_context(question: str) -> str:
        """Build a rich data context from the database for the LLM."""
        parts = []
        q_lower = question.lower()

        async with get_async_session() as s:
            # Latest week info
            result = await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )
            latest = result.first()

            if latest:
                year, week = latest
                parts.append(f"Current data: {year}-W{week:02d}")

                # Overall lice stats
                result = await s.execute(
                    select(
                        func.avg(LiceRecord.avg_adult_female_lice),
                        func.max(LiceRecord.avg_adult_female_lice),
                        func.count(LiceRecord.id),
                        func.avg(LiceRecord.sea_temp_c),
                    ).where(
                        LiceRecord.year == year,
                        LiceRecord.week == week,
                        LiceRecord.avg_adult_female_lice.isnot(None),
                    )
                )
                stats = result.one()

                parts.append(
                    f"National lice stats: avg={stats[0]:.3f}, max={stats[1]:.3f}, "
                    f"records={stats[2]}, avg_temp={stats[3]:.1f}°C"
                )

                # Company-level breakdown
                for ticker in ["MOWI", "SALM", "LSG", "GSF"]:
                    result = await s.execute(
                        select(CompanyExposure.locality_no)
                        .where(CompanyExposure.ticker == ticker)
                    )
                    locs = result.scalars().all()

                    if locs:
                        result = await s.execute(
                            select(
                                func.avg(LiceRecord.avg_adult_female_lice),
                                func.max(LiceRecord.avg_adult_female_lice),
                                func.count(LiceRecord.id),
                            ).where(
                                LiceRecord.year == year,
                                LiceRecord.week == week,
                                LiceRecord.locality_no.in_(list(locs)),
                                LiceRecord.avg_adult_female_lice.isnot(None),
                            )
                        )
                        company_stats = result.one()

                        if company_stats[2] > 0:
                            result = await s.execute(
                                select(func.count(LiceRecord.id)).where(
                                    LiceRecord.year == year,
                                    LiceRecord.week == week,
                                    LiceRecord.locality_no.in_(list(locs)),
                                    LiceRecord.avg_adult_female_lice > 0.5,
                                )
                            )
                            above = result.scalar() or 0

                            parts.append(
                                f"{ticker}: avg_lice={company_stats[0]:.3f}, "
                                f"max={company_stats[1]:.3f}, sites={company_stats[2]}, "
                                f"above_limit={above}"
                            )

                # If question mentions specific locality
                import re
                loc_match = re.findall(r'\b(\d{4,6})\b', question)
                for loc_no_str in loc_match[:3]:
                    loc_no = int(loc_no_str)
                    result = await s.execute(
                        select(LiceRecord)
                        .where(LiceRecord.locality_no == loc_no)
                        .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                        .limit(4)
                    )
                    loc_data = result.scalars().all()

                    if loc_data:
                        result = await s.execute(
                            select(Locality).where(Locality.locality_no == loc_no)
                        )
                        loc_info = result.scalar_one_or_none()

                        name = loc_info.name if loc_info else "Unknown"
                        parts.append(f"\nLocality {loc_no} ({name}) recent data:")
                        for r in loc_data:
                            parts.append(
                                f"  W{r.week}: adult={r.avg_adult_female_lice:.3f}, "
                                f"temp={r.sea_temp_c}°C"
                            )

                # PA-specific data if mentioned
                for pa in range(1, 14):
                    if f"pa {pa}" in q_lower or f"pa-{pa}" in q_lower or f"area {pa}" in q_lower:
                        result = await s.execute(
                            select(Locality.locality_no)
                            .where(Locality.production_area == pa)
                        )
                        pa_locs = result.scalars().all()

                        if pa_locs:
                            result = await s.execute(
                                select(
                                    func.avg(LiceRecord.avg_adult_female_lice),
                                    func.max(LiceRecord.avg_adult_female_lice),
                                    func.count(LiceRecord.id),
                                ).where(
                                    LiceRecord.year == year,
                                    LiceRecord.week == week,
                                    LiceRecord.locality_no.in_(list(pa_locs)),
                                    LiceRecord.avg_adult_female_lice.isnot(None),
                                )
                            )
                            pa_stats = result.one()

                            parts.append(
                                f"PA-{pa}: avg_lice={pa_stats[0]:.3f}, "
                                f"max={pa_stats[1]:.3f}, active_sites={pa_stats[2]}"
                            )

            # Pending signals
            result = await s.execute(
                select(Signal)
                .where(Signal.status == "pending")
                .order_by(Signal.created_at.desc())
                .limit(5)
            )
            signals = result.scalars().all()

            if signals:
                parts.append("\nPending signals:")
                for sig in signals:
                    parts.append(
                        f"  {sig.ticker} {sig.direction} strength={sig.strength:.2f}"
                    )

        return "\n".join(parts)

    def clear_history(self) -> None:
        self.conversation_history = []


# Singleton
chat_agent = ChatAgent()
