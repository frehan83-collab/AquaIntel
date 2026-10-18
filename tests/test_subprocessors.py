"""WS-51 — say what is actually in place, not what would be convenient.

The register is a factual list: `contracted` is False where no agreement exists, the AI-Act notes
now record the grounded assistant, and the guard can refuse an uncontracted provider when the
operator turns it on.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.legal.subprocessors import SUBPROCESSORS, disclosure, is_contracted


def test_the_register_states_what_is_missing():
    payload = disclosure("openrouter")
    assert payload["total_count"] == len(SUBPROCESSORS)
    assert payload["contracted_count"] == 0, "no DPA is signed on this deployment"
    assert "openrouter" in payload["missing_contracts"]
    assert "not a claim of compliance" in payload["statement"]


def test_a_free_endpoint_is_not_marked_contracted():
    entry = SUBPROCESSORS["openrouter_free"].to_dict()
    assert entry["contracted"] is False
    assert entry["zero_retention"] is False
    assert "retain" in entry["note"]
    assert is_contracted("openrouter_free") is False


def test_the_endpoint_serves_the_register():
    from core.api import app

    body = TestClient(app).get("/api/legal/sub-processors").json()
    keys = {item["key"] for item in body["sub_processors"]}
    assert {"openrouter", "openrouter_free", "stripe"} <= keys
    assert body["provider_in_use"]


def test_the_ai_act_notes_now_include_the_assistant_and_the_transfer():
    from core.api import app

    body = TestClient(app).get("/api/legal/ai-act").json()
    systems = " ".join(item["system"] for item in body["systems"])
    assert "Grounded assistant" in systems
    assert "AI system is answering" in " ".join(item["transparency"] for item in body["systems"])
    assert "sub-processors" in body["personal_data"]
    assert "hash, not the text" in body["personal_data"]


@pytest.mark.asyncio
async def test_the_guard_refuses_an_uncontracted_provider_when_enabled(monkeypatch):
    from core.llm.client import LLMClient

    monkeypatch.setattr("core.llm.client.settings.llm_contracted_provider_only", True)
    client = LLMClient()
    client.provider = "openrouter"

    response = await client.complete(prompt="q", system="s")
    assert response.content == ""
    assert "no signed instrument" in (response.error or "")


@pytest.mark.asyncio
async def test_the_guard_is_off_by_default(monkeypatch):
    from core.llm.client import LLMClient

    monkeypatch.setattr("core.llm.client.settings.llm_contracted_provider_only", False)
    client = LLMClient()
    client.provider = "openrouter"
    assert client._provider_blocked() is None
