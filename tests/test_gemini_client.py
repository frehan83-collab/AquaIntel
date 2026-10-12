"""
Tests for Gemini integration in LLMClient:
- Provider routing
- OpenAI-compatible chat completion and function calling
- Key fallback resolution
- Cost calculation for Gemini models
"""
import pytest
from unittest import mock
from types import SimpleNamespace

from core.llm.client import LLMClient, COST_TABLE


class TestGeminiClientIntegration:
    def test_gemini_cost_table_entries(self):
        assert "gemini-3.8-flash" in COST_TABLE
        assert "gemini-3.1-pro-preview" in COST_TABLE
        assert COST_TABLE["gemini-3.8-flash"]["input"] == 0.10
        assert COST_TABLE["gemini-3.8-flash"]["output"] == 0.40

    @pytest.mark.asyncio
    async def test_call_gemini_mocked(self):
        client = LLMClient()
        client.provider = "gemini"

        fake_choice = SimpleNamespace(
            message=SimpleNamespace(content="SalMar and Mowi lead PA 3.")
        )
        fake_usage = SimpleNamespace(prompt_tokens=25, completion_tokens=15)
        fake_response = SimpleNamespace(
            choices=[fake_choice],
            usage=fake_usage,
        )

        mock_openai_client = mock.MagicMock()
        mock_openai_client.chat.completions.create.return_value = fake_response

        with mock.patch.object(client, "_get_gemini", return_value=mock_openai_client):
            resp = await client.complete(
                prompt="Who leads PA 3?",
                system="You are an aquaculture analyst.",
                model="gemini-3.8-flash",
            )

            assert resp.content == "SalMar and Mowi lead PA 3."
            assert resp.model == "gemini-3.8-flash"
            assert resp.input_tokens == 25
            assert resp.output_tokens == 15
            assert resp.cost_usd > 0

    @pytest.mark.asyncio
    async def test_tool_call_gemini_mocked(self):
        client = LLMClient()
        client.provider = "gemini"

        fake_fn = SimpleNamespace(
            name="get_price_outlook",
            arguments='{"horizon_weeks": 4}',
        )
        fake_tc = SimpleNamespace(
            id="call_gemini_001",
            type="function",
            function=fake_fn,
        )
        fake_choice = SimpleNamespace(
            message=SimpleNamespace(content="", tool_calls=[fake_tc]),
            stop_reason="tool_use",
        )
        fake_usage = SimpleNamespace(prompt_tokens=40, completion_tokens=20)
        fake_response = SimpleNamespace(
            choices=[fake_choice],
            usage=fake_usage,
            stop_reason="tool_use",
        )

        mock_openai_client = mock.MagicMock()
        mock_openai_client.chat.completions.create.return_value = fake_response

        with mock.patch.object(client, "_get_gemini", return_value=mock_openai_client):
            tools = [
                {
                    "name": "get_price_outlook",
                    "description": "Fetch salmon spot price outlook",
                    "parameters": {
                        "type": "object",
                        "properties": {"horizon_weeks": {"type": "integer"}},
                    },
                }
            ]
            result = await client.complete_with_tools(
                messages=[{"role": "user", "content": "What is the 4-week price outlook?"}],
                tools=tools,
                model="gemini-3.8-flash",
            )

            assert len(result["tool_calls"]) == 1
            tc = result["tool_calls"][0]
            assert tc["name"] == "get_price_outlook"
            assert tc["input"] == {"horizon_weeks": 4}
            assert tc["id"] == "call_gemini_001"
