"""WS-42 — the free OpenRouter chain: answers when the paid model cannot, and says so.

OpenRouter's free tier is 20 requests/minute and 50/day without a lifetime top-up (up to
1,000/day after $10) at zero marginal cost, which is exactly what a deployment with an
exhausted balance needs. The catalogue rotates, so this is a chain: a model that has gone is
skipped, and the next one answers.

These tests pin the three behaviours that matter: the fallback fires only when the paid model
fails, a free answer is labelled and costs nothing, and every model failing still returns an
error rather than an empty "answer".
"""
from __future__ import annotations

import pytest

from core.llm.client import COST_TABLE, LLMClient, LLMResponse


def _client(monkeypatch, *, chain="free-a:free,free-b:free", prefer=False, fallback=True):
    monkeypatch.setattr("core.llm.client.settings.llm_free_models", chain)
    monkeypatch.setattr("core.llm.client.settings.llm_prefer_free", prefer)
    monkeypatch.setattr("core.llm.client.settings.llm_free_fallback", fallback)
    client = LLMClient()
    client.provider = "openrouter"
    client.model = "paid/model"
    return client


@pytest.mark.asyncio
async def test_the_paid_model_is_used_when_it_works(monkeypatch):
    client = _client(monkeypatch)

    async def attempt(prompt, system, target, max_tokens, temperature):
        return LLMResponse(content="paid answer", model=target, input_tokens=10, output_tokens=5)

    monkeypatch.setattr(client, "_call_openrouter", attempt)
    response = await client.complete(prompt="q", system="s")

    assert response.content == "paid answer"
    assert response.is_free is False
    assert response.cost_usd > 0


@pytest.mark.asyncio
async def test_an_exhausted_paid_model_falls_back_to_the_free_chain(monkeypatch):
    client = _client(monkeypatch)

    async def attempt(prompt, system, target, max_tokens, temperature):
        if target == "paid/model":
            raise RuntimeError("402 insufficient credits")
        return LLMResponse(content=f"answer from {target}", model=target,
                           input_tokens=1000, output_tokens=100)

    monkeypatch.setattr(client, "_call_openrouter", attempt)
    response = await client.complete(prompt="q", system="s")

    assert response.content == "answer from free-a:free"
    assert response.is_free is True
    assert response.cost_usd == 0.0, "a free answer must not be priced from COST_TABLE"
    assert "402" in (response.fallback_from or "")


@pytest.mark.asyncio
async def test_a_gone_model_in_the_chain_is_skipped(monkeypatch):
    client = _client(monkeypatch)

    async def attempt(prompt, system, target, max_tokens, temperature):
        if target == "paid/model":
            raise RuntimeError("429 upstream")
        if target == "free-a:free":
            raise RuntimeError("404 model not found")
        return LLMResponse(content="second free model", model=target)

    monkeypatch.setattr(client, "_call_openrouter", attempt)
    response = await client.complete(prompt="q", system="s")

    assert response.content == "second free model"
    assert response.model == "free-b:free"


@pytest.mark.asyncio
async def test_an_empty_free_answer_moves_to_the_next_model(monkeypatch):
    client = _client(monkeypatch)

    async def attempt(prompt, system, target, max_tokens, temperature):
        if target == "paid/model":
            raise RuntimeError("402")
        if target == "free-a:free":
            return LLMResponse(content="", model=target, error="empty content")
        return LLMResponse(content="real answer", model=target)

    monkeypatch.setattr(client, "_call_openrouter", attempt)
    response = await client.complete(prompt="q", system="s")
    assert response.content == "real answer"


@pytest.mark.asyncio
async def test_every_model_failing_returns_an_error_not_an_answer(monkeypatch):
    client = _client(monkeypatch)

    async def attempt(prompt, system, target, max_tokens, temperature):
        raise RuntimeError("everything is down")

    monkeypatch.setattr(client, "_call_openrouter", attempt)
    response = await client.complete(prompt="q", system="s")

    assert response.content == ""
    assert response.error
    assert response.ok is False


@pytest.mark.asyncio
async def test_prefer_free_tries_the_chain_first(monkeypatch):
    client = _client(monkeypatch, prefer=True)
    seen: list[str] = []

    async def attempt(prompt, system, target, max_tokens, temperature):
        seen.append(target)
        return LLMResponse(content="free first", model=target)

    monkeypatch.setattr(client, "_call_openrouter", attempt)
    response = await client.complete(prompt="q", system="s")

    assert response.is_free is True
    assert seen[0] == "free-a:free"
    assert "paid/model" not in seen


@pytest.mark.asyncio
async def test_the_fallback_can_be_disabled(monkeypatch):
    client = _client(monkeypatch, fallback=False)

    async def attempt(prompt, system, target, max_tokens, temperature):
        raise RuntimeError("402")

    monkeypatch.setattr(client, "_call_openrouter", attempt)
    response = await client.complete(prompt="q", system="s")

    assert response.content == ""
    assert "402" in (response.error or "")


def test_the_chain_is_parsed_and_deduplicated(monkeypatch):
    client = _client(monkeypatch, chain=" a:free , b:free ;;a:free,, ")
    assert client.free_models() == ["a:free", "b:free"]


def test_the_default_chain_is_a_real_free_catalogue_subset():
    """The shipped chain must name free variants, or the fallback would cost money."""
    from config.settings import settings

    chain = [part.strip() for part in settings.llm_free_models.split(",") if part.strip()]
    assert chain, "a default chain must ship"
    for model in chain:
        assert model.endswith(":free"), model
    assert "claude-sonnet-4-20250514" in COST_TABLE
