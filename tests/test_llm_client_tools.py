"""Tests for LLM tool wiring: message conversion + OpenAI-style tool calls.

Regression coverage for the QUANT #3 fixes (dead chat tools + provider-agnostic
tool-use) and the B1 response-parsing bug found in pre-commit review.
"""
import asyncio
import json
from types import SimpleNamespace
from unittest import mock

import pytest


class TestToOpenaiMessages:
    def test_plain_messages_pass_through(self):
        from core.llm.client import LLMClient

        msgs = [{"role": "user", "content": "hello"}]
        out = LLMClient._to_openai_messages(msgs, system="sys")
        assert out[0] == {"role": "system", "content": "sys"}
        assert out[1] == {"role": "user", "content": "hello"}

    def test_tool_use_becomes_assistant_tool_calls(self):
        from core.llm.client import LLMClient

        msgs = [{
            "role": "assistant",
            "content": [
                {"type": "text", "text": "checking"},
                {"type": "tool_use", "id": "t1", "name": "get_lice_data", "input": {"pa": 3}},
            ],
        }]
        out = LLMClient._to_openai_messages(msgs, system="")
        assert out[0]["role"] == "assistant"
        assert out[0]["content"] == "checking"
        tc = out[0]["tool_calls"][0]
        assert tc["id"] == "t1"
        assert tc["function"]["name"] == "get_lice_data"
        assert json.loads(tc["function"]["arguments"]) == {"pa": 3}

    def test_tool_result_pairing_and_ordering(self):
        from core.llm.client import LLMClient

        msgs = [
            {"role": "user", "content": "question"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "search_knowledge_base", "input": {"query": "x"}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "note"},
                    {"type": "tool_result", "tool_use_id": "t1", "content": "{\"context\": \"...\"}"},
                ],
            },
        ]
        out = LLMClient._to_openai_messages(msgs, system="")
        roles = [m["role"] for m in out]
        # tool result must follow the assistant tool_calls message
        assert roles == ["user", "assistant", "assistant", "tool"]
        assert out[3]["tool_call_id"] == "t1"
        assert out[2]["content"] == "note"  # accompanying text preserved (W1)

    def test_non_string_tool_result_content_serialised(self):
        from core.llm.client import LLMClient

        msgs = [{
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t9", "content": {"nested": 1}},
            ],
        }]
        out = LLMClient._to_openai_messages(msgs, system="")
        assert json.loads(out[0]["content"]) == {"nested": 1}


class TestOpenaiStyleToolCall:
    def test_response_parsing_and_usage_tracking(self, monkeypatch):
        """Regression for review blocker B1: LLMResponse construction must
        include content, and tool_calls must be normalised."""
        from core.llm import client as client_mod
        from core.llm.client import LLMClient

        fake_response = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    content="thinking",
                    tool_calls=[SimpleNamespace(
                        id="call-1",
                        function=SimpleNamespace(name="get_lice_data", arguments='{"pa": 5}'),
                    )],
                ),
                finish_reason="tool_calls",
            )],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )
        fake_openai = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=mock.MagicMock(return_value=fake_response)
                )
            )
        )

        lc = LLMClient.__new__(LLMClient)  # skip __init__ (no DB/budget state)
        lc.provider = "openai"
        lc.model = "gpt-4o"
        lc.usage = client_mod.UsageTracker()
        monkeypatch.setattr(lc, "_get_openai", lambda: fake_openai, raising=False)
        monkeypatch.setattr(client_mod.LLMClient, "_log_call",
                            staticmethod(lambda *a, **k: asyncio.sleep(0)))

        result = asyncio.run(lc._tool_call_openai_style(
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"name": "get_lice_data", "description": "d", "parameters": {}}],
            system="", model="gpt-4o", max_tokens=100, temperature=0.0,
        ))

        assert result["text"] == "thinking"
        assert result["stop_reason"] == "tool_calls"
        assert result["tool_calls"] == [
            {"id": "call-1", "name": "get_lice_data", "input": {"pa": 5}}
        ]
        assert result["input_tokens"] == 10
        assert result["output_tokens"] == 5


class TestChatToolHandlers:
    def test_get_price_outlook_returns_forecast(self):
        """Regression for the dead price_predictor import (QUANT #3)."""
        result = asyncio.run(
            __import__("core.llm.tools", fromlist=["get_price_outlook"]).get_price_outlook(horizon=4)
        )
        assert "error" not in result, result
        assert "predicted_nok" in result
        assert result["model_version"].startswith("ensemble_")

    def test_search_knowledge_base_returns_context(self):
        """Regression for the dead rag_retriever import (QUANT #3)."""
        result = asyncio.run(
            __import__("core.llm.tools", fromlist=["search_knowledge_base"]).search_knowledge_base("sea lice")
        )
        assert "error" not in result, result
        assert "context" in result
