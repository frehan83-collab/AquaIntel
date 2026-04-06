"""
Unified LLM Client
====================
Abstracts Anthropic Claude and OpenAI behind a single interface.
Tracks token usage, cost, and logs all calls for compliance.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field

import structlog

from config.settings import settings
from core.models import AuditLog
from core.async_db import get_async_session

log = structlog.get_logger(__name__)

# ── Cost per 1M tokens (approximate, March 2026) ────────────────────
COST_TABLE = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    cached: bool = False


@dataclass
class UsageTracker:
    """Tracks monthly LLM spend."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0
    month: str = ""

    def add(self, resp: LLMResponse) -> None:
        current_month = dt.datetime.now(dt.UTC).strftime("%Y-%m")
        if self.month != current_month:
            # Reset for new month
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.total_cost_usd = 0.0
            self.call_count = 0
            self.month = current_month

        self.total_input_tokens += resp.input_tokens
        self.total_output_tokens += resp.output_tokens
        self.total_cost_usd += resp.cost_usd
        self.call_count += 1

    def within_budget(self) -> bool:
        return self.total_cost_usd < settings.llm_monthly_budget_usd


class LLMClient:
    """Unified LLM client supporting Anthropic and OpenAI."""

    def __init__(self) -> None:
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.usage = UsageTracker()
        self._anthropic = None
        self._openai = None

    def _get_anthropic(self):
        if self._anthropic is None:
            import anthropic
            self._anthropic = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._anthropic

    def _get_openai(self):
        if self._openai is None:
            import openai
            self._openai = openai.OpenAI(api_key=settings.openai_api_key)
        return self._openai

    def _get_openrouter(self):
        if not hasattr(self, "_openrouter") or self._openrouter is None:
            import openai
            self._openrouter = openai.OpenAI(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
            )
        return self._openrouter

    async def complete(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        user_id: str = "system",
    ) -> LLMResponse:
        """Send a completion request to the configured LLM provider."""
        model = model or self.model
        max_tokens = max_tokens or settings.llm_max_tokens
        temperature = temperature if temperature is not None else settings.llm_temperature

        # Budget check
        if not self.usage.within_budget():
            log.warning("llm.budget_exceeded", spent=self.usage.total_cost_usd)
            return LLMResponse(
                content="[LLM budget limit reached for this month. Contact admin.]",
                model=model,
            )

        start = dt.datetime.now(dt.UTC)

        try:
            if self.provider == "anthropic":
                resp = await self._call_anthropic(prompt, system, model, max_tokens, temperature)
            elif self.provider == "openai":
                resp = await self._call_openai(prompt, system, model, max_tokens, temperature)
            elif self.provider == "openrouter":
                resp = await self._call_openrouter(prompt, system, model, max_tokens, temperature)
            else:
                raise ValueError(f"Unknown LLM provider: {self.provider}")
        except Exception as exc:
            log.error("llm.call_failed", provider=self.provider, error=str(exc))
            return LLMResponse(content=f"[LLM error: {exc}]", model=model)

        elapsed = (dt.datetime.now(dt.UTC) - start).total_seconds() * 1000
        resp.latency_ms = elapsed

        # Calculate cost
        costs = COST_TABLE.get(model, {"input": 5.0, "output": 15.0})
        resp.cost_usd = (
            resp.input_tokens * costs["input"] / 1_000_000 +
            resp.output_tokens * costs["output"] / 1_000_000
        )

        # Track usage
        self.usage.add(resp)

        # Audit log
        await self._log_call(user_id, model, resp)

        log.info(
            "llm.complete",
            model=model,
            tokens_in=resp.input_tokens,
            tokens_out=resp.output_tokens,
            cost=f"${resp.cost_usd:.4f}",
            latency_ms=round(elapsed),
        )

        return resp

    async def _call_anthropic(
        self, prompt: str, system: str, model: str,
        max_tokens: int, temperature: float,
    ) -> LLMResponse:
        """Call Anthropic Claude API."""
        import asyncio

        client = self._get_anthropic()

        # Run sync client in thread pool
        def _sync_call():
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system

            return client.messages.create(**kwargs)

        result = await asyncio.get_event_loop().run_in_executor(None, _sync_call)

        content = ""
        for block in result.content:
            if hasattr(block, "text"):
                content += block.text

        return LLMResponse(
            content=content,
            model=model,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        )

    async def _call_openai(
        self, prompt: str, system: str, model: str,
        max_tokens: int, temperature: float,
    ) -> LLMResponse:
        """Call OpenAI API."""
        import asyncio

        client = self._get_openai()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        def _sync_call():
            return client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        result = await asyncio.get_event_loop().run_in_executor(None, _sync_call)

        return LLMResponse(
            content=result.choices[0].message.content or "",
            model=model,
            input_tokens=result.usage.prompt_tokens,
            output_tokens=result.usage.completion_tokens,
        )

    async def _call_openrouter(
        self, prompt: str, system: str, model: str,
        max_tokens: int, temperature: float,
    ) -> LLMResponse:
        """Call OpenRouter API (OpenAI-compatible, any model)."""
        import asyncio

        client = self._get_openrouter()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        def _sync_call():
            return client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                extra_headers={
                    "HTTP-Referer": "https://openclaw.no",
                    "X-Title": "OpenClaw Aquaculture Platform",
                },
            )

        result = await asyncio.get_event_loop().run_in_executor(None, _sync_call)

        return LLMResponse(
            content=result.choices[0].message.content or "",
            model=model,
            input_tokens=getattr(result.usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(result.usage, "completion_tokens", 0) or 0,
        )

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        user_id: str = "system",
    ) -> dict:
        """Send a multi-turn message list with tool definitions.

        Returns a dict with:
          - text: str — any text content in the response
          - tool_calls: list[dict] — tool_use blocks (name, id, input), empty if none
          - input_tokens / output_tokens: int
          - stop_reason: str
        Only the Anthropic provider supports native tool-use.
        OpenAI/OpenRouter will raise NotImplementedError.
        """
        model = model or self.model
        max_tokens = max_tokens or settings.llm_max_tokens
        temperature = temperature if temperature is not None else settings.llm_temperature

        if not self.usage.within_budget():
            log.warning("llm.budget_exceeded", spent=self.usage.total_cost_usd)
            return {"text": "[LLM budget limit reached for this month.]", "tool_calls": [], "input_tokens": 0, "output_tokens": 0, "stop_reason": "budget"}

        if self.provider != "anthropic":
            raise NotImplementedError(
                f"complete_with_tools not supported for provider '{self.provider}'. "
                "Use the keyword-based tool enrichment fallback instead."
            )

        import asyncio

        client = self._get_anthropic()

        # Format tools for Anthropic API
        api_tools = []
        for t in tools:
            api_tools.append({
                "name": t["name"],
                "description": t["description"],
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            })

        start = dt.datetime.now(dt.UTC)

        def _sync_call():
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
                "tools": api_tools,
            }
            if system:
                kwargs["system"] = system
            return client.messages.create(**kwargs)

        result = await asyncio.get_event_loop().run_in_executor(None, _sync_call)

        elapsed = (dt.datetime.now(dt.UTC) - start).total_seconds() * 1000

        # Parse response blocks
        text_parts = []
        tool_calls = []
        for block in result.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        resp = LLMResponse(
            content="".join(text_parts),
            model=model,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            latency_ms=elapsed,
        )
        # Calculate cost & track
        costs = COST_TABLE.get(model, {"input": 5.0, "output": 15.0})
        resp.cost_usd = (
            resp.input_tokens * costs["input"] / 1_000_000 +
            resp.output_tokens * costs["output"] / 1_000_000
        )
        self.usage.add(resp)
        await self._log_call(user_id, model, resp)

        log.info(
            "llm.complete_with_tools",
            model=model,
            tokens_in=resp.input_tokens,
            tokens_out=resp.output_tokens,
            cost=f"${resp.cost_usd:.4f}",
            latency_ms=round(elapsed),
            tool_calls=len(tool_calls),
            stop_reason=result.stop_reason,
        )

        return {
            "text": "".join(text_parts),
            "tool_calls": tool_calls,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "stop_reason": result.stop_reason,
        }

    @staticmethod
    async def _log_call(user_id: str, model: str, resp: LLMResponse) -> None:
        async with get_async_session() as s:
            s.add(AuditLog(
                event_type="llm_call",
                actor=user_id,
                detail=(
                    f"model={model} in={resp.input_tokens} out={resp.output_tokens} "
                    f"cost=${resp.cost_usd:.4f} latency={resp.latency_ms:.0f}ms"
                ),
            ))

    def get_usage_summary(self) -> dict:
        return {
            "month": self.usage.month,
            "total_calls": self.usage.call_count,
            "total_input_tokens": self.usage.total_input_tokens,
            "total_output_tokens": self.usage.total_output_tokens,
            "total_cost_usd": round(self.usage.total_cost_usd, 4),
            "budget_usd": settings.llm_monthly_budget_usd,
            "budget_remaining": round(
                settings.llm_monthly_budget_usd - self.usage.total_cost_usd, 4
            ),
        }


# Singleton
llm_client = LLMClient()
