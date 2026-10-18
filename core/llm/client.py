"""
Unified LLM Client
====================
Abstracts Anthropic Claude and OpenAI behind a single interface.
Tracks token usage, cost, and logs all calls for compliance.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass

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
    "gemini-3.8-flash": {"input": 0.10, "output": 0.40},
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 5.00},
    "gemini-flash-latest": {"input": 0.10, "output": 0.40},
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
    #: Set when the provider call failed. `content` is empty in that case — an error
    #: message is never returned as an answer (WS-38b).
    error: str | None = None
    #: True when a free OpenRouter model wrote this, so the cost is zero and the label
    #: in the UI is honest (WS-42).
    is_free: bool = False
    #: The paid model that failed before the free chain answered, for the logs.
    fallback_from: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.content)


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

    @staticmethod
    def free_models() -> list[str]:
        """The configured free chain, in order, without empties or duplicates."""
        raw = str(getattr(settings, "llm_free_models", "") or "")
        seen: list[str] = []
        for part in raw.replace(";", ",").split(","):
            name = part.strip()
            if name and name not in seen:
                seen.append(name)
        return seen

    def _get_gemini_key(self) -> str:
        if getattr(settings, "gemini_api_key", ""):
            return settings.gemini_api_key
        import os
        from pathlib import Path
        if os.getenv("GEMINI_API_KEY"):
            return os.getenv("GEMINI_API_KEY")
        providers_file = Path.home() / ".cline" / "data" / "settings" / "providers.json"
        if providers_file.exists():
            try:
                with open(providers_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("providers", {}).get("gemini", {}).get("settings", {}).get("apiKey", "")
            except Exception:
                pass
        return ""

    def _get_gemini(self):
        if not hasattr(self, "_gemini") or self._gemini is None:
            import openai
            key = self._get_gemini_key()
            base_url = getattr(settings, "gemini_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")
            self._gemini = openai.OpenAI(
                api_key=key,
                base_url=base_url,
            )
        return self._gemini

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

        async def _attempt(target: str) -> LLMResponse:
            """One provider call for a specific model id."""
            if self.provider == "anthropic":
                return await self._call_anthropic(prompt, system, target, max_tokens, temperature)
            if self.provider == "openai":
                return await self._call_openai(prompt, system, target, max_tokens, temperature)
            if self.provider == "gemini":
                return await self._call_gemini(prompt, system, target, max_tokens, temperature)
            if self.provider == "openrouter":
                return await self._call_openrouter(prompt, system, target, max_tokens, temperature)
            raise ValueError(f"Unknown LLM provider: {self.provider}")

        free_models = self.free_models()
        prefer_free = bool(getattr(settings, "llm_prefer_free", False)) and self.provider == "openrouter"
        allow_free = bool(getattr(settings, "llm_free_fallback", True)) and self.provider == "openrouter"

        async def _free_answer(primary_failure: str | None) -> LLMResponse | None:
            """Walk the free chain; return the first answer, or None if every model failed."""
            for candidate in free_models:
                try:
                    free = await _attempt(candidate)
                except Exception as exc:  # noqa: BLE001 — a gone model is skipped
                    log.warning("llm.free_failed", model=candidate, error=str(exc)[:120])
                    primary_failure = primary_failure or str(exc)[:200]
                    continue
                if free.error or not free.content:
                    log.warning("llm.free_failed", model=candidate, error=(free.error or "empty")[:120])
                    primary_failure = primary_failure or (free.error or "empty content")
                    continue
                free.is_free = True
                free.fallback_from = primary_failure
                log.info(
                    "llm.free_used",
                    model=candidate,
                    fallback_from=primary_failure,
                    tokens_in=free.input_tokens,
                    tokens_out=free.output_tokens,
                )
                return free
            return None

        resp: LLMResponse | None = None
        try:
            if prefer_free:
                resp = await _free_answer(None)
            if resp is None:
                primary = await _attempt(model)
                if primary.error or not primary.content:
                    raise RuntimeError(primary.error or "empty completion")
                resp = primary
        except Exception as exc:
            log.error("llm.call_failed", provider=self.provider, error=str(exc)[:300])
            if allow_free:
                resp = await _free_answer(str(exc)[:200])
            if resp is None:
                return LLMResponse(content="", model=model, error=str(exc)[:400])

        elapsed = (dt.datetime.now(dt.UTC) - start).total_seconds() * 1000
        resp.latency_ms = elapsed

        if resp.is_free:
            # A free model costs nothing; pricing it from COST_TABLE would invent a charge.
            resp.cost_usd = 0.0
        else:
            costs = COST_TABLE.get(model, {"input": 5.0, "output": 15.0})
            resp.cost_usd = (
                resp.input_tokens * costs["input"] / 1_000_000 +
                resp.output_tokens * costs["output"] / 1_000_000
            )

        # Track usage
        self.usage.add(resp)

        # Audit log
        await self._log_call(user_id, resp.model or model, resp)

        log.info(
            "llm.complete",
            model=resp.model or model,
            free=resp.is_free,
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
                    "HTTP-Referer": "https://aquaintel.no",
                    "X-Title": "AquaIntel Aquaculture Platform",
                },
            )

        result = await asyncio.get_event_loop().run_in_executor(None, _sync_call)

        return LLMResponse(
            content=result.choices[0].message.content or "",
            model=model,
            input_tokens=getattr(result.usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(result.usage, "completion_tokens", 0) or 0,
        )

    async def _call_gemini(
        self, prompt: str, system: str, model: str,
        max_tokens: int, temperature: float,
    ) -> LLMResponse:
        """Call Google Gemini API via OpenAI-compatible endpoint."""
        import asyncio

        client = self._get_gemini()
        if not model or "gemini" not in model.lower():
            model = "gemini-3.8-flash"

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
        Supported by Anthropic (native messages API) and by OpenAI/OpenRouter
        (OpenAI-style function tools — OpenRouter proxies Claude tool-use too).
        Messages may be in Anthropic block format (the agentic loop's native
        format); they are converted internally for the OpenAI-style providers.
        """
        model = model or self.model
        max_tokens = max_tokens or settings.llm_max_tokens
        temperature = temperature if temperature is not None else settings.llm_temperature

        if not self.usage.within_budget():
            log.warning("llm.budget_exceeded", spent=self.usage.total_cost_usd)
            return {"text": "[LLM budget limit reached for this month.]", "tool_calls": [], "input_tokens": 0, "output_tokens": 0, "stop_reason": "budget"}

        if self.provider == "anthropic":
            return await self._tool_call_anthropic(messages, tools, system, model, max_tokens, temperature, user_id)
        if self.provider in ("openai", "openrouter", "gemini"):
            return await self._tool_call_openai_style(messages, tools, system, model, max_tokens, temperature, user_id)
        raise NotImplementedError(
            f"complete_with_tools not supported for provider '{self.provider}'."
        )

    async def _tool_call_anthropic(
        self, messages: list[dict], tools: list[dict], system: str,
        model: str, max_tokens: int, temperature: float, user_id: str = "system",
    ) -> dict:
        """Anthropic-native tool-use call."""
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

    async def _tool_call_openai_style(
        self, messages: list[dict], tools: list[dict], system: str,
        model: str, max_tokens: int, temperature: float, user_id: str = "system",
    ) -> dict:
        """OpenAI/OpenRouter tool-use call (OpenAI function-tool format).

        Accepts the agentic loop's Anthropic block-format messages and converts
        them: assistant tool_use blocks -> tool_calls, user tool_result blocks
        -> per-call role:"tool" messages. Response is normalised to the same
        shape as the Anthropic path.
        """
        import asyncio

        if self.provider == "gemini":
            client = self._get_gemini()
            if not model or "gemini" not in model.lower():
                model = "gemini-3.8-flash"
        elif self.provider == "openrouter":
            client = self._get_openrouter()
        else:
            client = self._get_openai()

        api_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]
        api_messages = self._to_openai_messages(messages, system)

        start = dt.datetime.now(dt.UTC)

        def _sync_call():
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": api_messages,
                "tools": api_tools,
                "tool_choice": "auto",
            }
            if self.provider == "openrouter":
                kwargs["extra_headers"] = {
                    "HTTP-Referer": "https://aquaintel.no",
                    "X-Title": "AquaIntel Aquaculture Platform",
                }
            return client.chat.completions.create(**kwargs)

        result = await asyncio.get_event_loop().run_in_executor(None, _sync_call)

        elapsed = (dt.datetime.now(dt.UTC) - start).total_seconds() * 1000
        choice = result.choices[0]
        message = choice.message

        text_parts = [message.content] if message.content else []
        tool_calls = []
        for tc in (getattr(message, "tool_calls", None) or []):
            try:
                import json as _json
                tool_input = _json.loads(tc.function.arguments or "{}")
            except Exception:
                tool_input = {}
            tool_calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "input": tool_input,
            })

        resp = LLMResponse(
            content="".join(text_parts),
            model=model,
            input_tokens=getattr(result.usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(result.usage, "completion_tokens", 0) or 0,
            latency_ms=elapsed,
        )
        costs = COST_TABLE.get(model, {"input": 5.0, "output": 15.0})
        resp.cost_usd = (
            resp.input_tokens * costs["input"] / 1_000_000 +
            resp.output_tokens * costs["output"] / 1_000_000
        )
        self.usage.add(resp)
        await self._log_call(user_id, model, resp)

        stop_reason = getattr(choice, "finish_reason", None) or getattr(result, "stop_reason", "stop")
        log.info(
            "llm.complete_with_tools",
            provider=self.provider,
            model=model,
            tool_calls=len(tool_calls),
            stop_reason=stop_reason,
        )

        return {
            "text": "".join(text_parts),
            "tool_calls": tool_calls,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "stop_reason": stop_reason,
        }

    @staticmethod
    def _to_openai_messages(messages: list[dict], system: str) -> list[dict]:
        """Convert Anthropic block-format messages to OpenAI chat format."""
        out: list[dict] = []
        if system:
            out.append({"role": "system", "content": system})
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                out.append({"role": msg["role"], "content": content})
                continue
            # Anthropic block content — split into OpenAI message semantics
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            tool_results = [b for b in content if b.get("type") == "tool_result"]
            if tool_uses:
                out.append({
                    "role": "assistant",
                    "content": text or None,
                    "tool_calls": [
                        {
                            "id": b["id"],
                            "type": "function",
                            "function": {
                                "name": b["name"],
                                "arguments": __import__("json").dumps(b.get("input", {})),
                            },
                        }
                        for b in tool_uses
                    ],
                })
            elif tool_results:
                # Tool results must directly follow their assistant tool_calls
                # message; any accompanying text is preserved as an assistant
                # message first (W1).
                if text:
                    out.append({"role": "assistant", "content": text})
                for b in tool_results:
                    content = b.get("content", "")
                    if not isinstance(content, str):
                        import json as _json
                        content = _json.dumps(content, default=str)  # W2
                    out.append({
                        "role": "tool",
                        "tool_call_id": b.get("tool_use_id", ""),
                        "content": content,
                    })
            else:
                out.append({"role": msg["role"], "content": text})
        return out

    @staticmethod
    async def _log_call(user_id: str, model: str, resp: LLMResponse) -> None:
        # AuditLog.user_id is an Integer column, but chat callers pass free-form
        # actor strings ("system", session ids) — store numeric ids when
        # parseable, otherwise keep the actor string in details.
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            uid = None
        async with get_async_session() as s:
            s.add(AuditLog(
                action="llm_call",
                user_id=uid,
                resource=f"model:{model}",
                details=(
                    f"actor={user_id} model={model} "
                    f"in={resp.input_tokens} out={resp.output_tokens} "
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
