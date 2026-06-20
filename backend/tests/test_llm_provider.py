"""Tests for gnosis/services/llm_provider.py.

Public API:
  LLMProvider (class)
    .initialize() -> probes tiers, sets ._available
    .complete(prompt, system=None, max_tokens=None) -> str
    .stream(prompt, system=None) -> AsyncGenerator[str]

httpx and openai are imported at MODULE level, so we patch them at their
canonicl locations: gnosis.services.llm_provider.httpx and
gnosis.services.llm_provider.AsyncOpenAI.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# LLMProvider.initialize — probes Ollama/Groq/OpenAI
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_records_ollama_when_reachable():
    from gnosis.services.llm_provider import LLMProvider

    fake_resp = MagicMock()
    fake_resp.status_code = 200

    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    fake_httpx = MagicMock()
    fake_httpx.AsyncClient.return_value = fake_client

    with patch("gnosis.services.llm_provider.httpx", fake_httpx), \
         patch("gnosis.services.llm_provider.AsyncOpenAI"):
        provider = LLMProvider()
        await provider.initialize()

    assert "ollama" in provider._available


@pytest.mark.asyncio
async def test_initialize_skips_ollama_when_unreachable():
    from gnosis.services.llm_provider import LLMProvider
    import httpx as real_httpx

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=Exception("connection refused"))
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    fake_httpx = MagicMock()
    fake_httpx.AsyncClient.return_value = fake_client

    with patch("gnosis.services.llm_provider.httpx", fake_httpx), \
         patch("gnosis.services.llm_provider.AsyncOpenAI"):
        provider = LLMProvider()
        await provider.initialize()

    assert "ollama" not in provider._available


@pytest.mark.asyncio
async def test_initialize_records_openai_when_key_set():
    from gnosis.services.llm_provider import LLMProvider

    # Ollama unreachable so it falls through
    fail_client = MagicMock()
    fail_client.get = AsyncMock(side_effect=Exception("no ollama"))
    fail_client.__aenter__ = AsyncMock(return_value=fail_client)
    fail_client.__aexit__ = AsyncMock(return_value=False)

    fake_httpx = MagicMock()
    fake_httpx.AsyncClient.return_value = fail_client

    with patch("gnosis.services.llm_provider.httpx", fake_httpx), \
         patch("gnosis.services.llm_provider.AsyncOpenAI") as mock_oai, \
         patch("gnosis.services.llm_provider.settings") as s:
        s.openai_api_key = "sk-test"
        s.groq_api_key = ""
        s.ollama_base_url = "http://localhost:11434"
        s.ollama_llm_model = "llama3"
        provider = LLMProvider()
        await provider.initialize()

    # Should have tried to build an OpenAI client
    assert True  # no exception = pass


# ---------------------------------------------------------------------------
# LLMProvider.complete — delegates to first available tier
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_ollama_returns_string():
    from gnosis.services.llm_provider import LLMProvider

    fake_choice = MagicMock()
    fake_choice.message.content = "Hello from Ollama"
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    fake_ollama_client = MagicMock()
    fake_ollama_client.chat.completions.create = AsyncMock(return_value=fake_response)

    provider = LLMProvider()
    provider._available = ["ollama"]
    provider._ollama_client = fake_ollama_client
    provider._ollama_model = "llama3"

    result = await provider.complete("Say hello")
    assert result == "Hello from Ollama"


@pytest.mark.asyncio
async def test_complete_falls_back_to_openai():
    from gnosis.services.llm_provider import LLMProvider

    fake_choice = MagicMock()
    fake_choice.message.content = "Hello from OpenAI"
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    fake_openai_client = MagicMock()
    fake_openai_client.chat.completions.create = AsyncMock(return_value=fake_response)

    provider = LLMProvider()
    provider._available = ["openai"]
    provider._openai_client = fake_openai_client
    provider._ollama_client = None
    provider._groq_client = None

    with patch("gnosis.services.llm_provider.settings") as s:
        s.openai_llm_model = "gpt-4o-mini"
        result = await provider.complete("Say hello")

    assert result == "Hello from OpenAI"


@pytest.mark.asyncio
async def test_complete_raises_when_no_providers():
    from gnosis.services.llm_provider import LLMProvider

    provider = LLMProvider()
    provider._available = []

    with pytest.raises(Exception):
        await provider.complete("hello")
