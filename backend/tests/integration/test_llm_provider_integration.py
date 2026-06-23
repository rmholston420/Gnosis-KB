"""
Integration tests for LLMProvider three-tier fallback logic.

These tests exercise the *real* initialize() logic but replace all external
network calls with httpx / openai mocks so no live Ollama/Groq/OpenAI is needed.

Coverage targets (llm_provider.py)
-----------------------------------
  41->52   Ollama HTTP probe succeeds → client created, "ollama" appended
  53-58    Groq key present            → Groq client created
  112      active_model branch: groq
  114      active_model branch: openai
  125      swap_model raises when Ollama not in _available
  181->179 complete() falls through to next provider on exception
  184-187  stream() provider exception fallback path
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from gnosis.services.llm_provider import LLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_ollama_response():
    """Minimal httpx.Response-like mock for /api/tags returning 200."""
    resp = MagicMock()
    resp.status_code = 200
    return resp


def _mock_chat_response(content: str = "hello"):
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _mock_stream_chunk(content: str):
    choice = MagicMock()
    choice.delta.content = content
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


async def _async_iter(items):
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# initialize() – Ollama probe succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_ollama_available():
    """When Ollama /api/tags returns 200 the provider adds 'ollama' to _available."""
    provider = LLMProvider()
    mock_resp = _mock_ollama_response()

    with patch("gnosis.services.llm_provider.settings") as mock_settings, \
         patch("gnosis.services.llm_provider.httpx.AsyncClient") as mock_http:
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_llm_model = "llama3"
        mock_settings.groq_api_key = ""
        mock_settings.openai_api_key = ""

        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=AsyncMock(get=AsyncMock(return_value=mock_resp)))
        mock_client_cm.__aexit__ = AsyncMock(return_value=False)
        mock_http.return_value = mock_client_cm

        await provider.initialize()

    assert "ollama" in provider._available
    assert provider.active_provider == "ollama"
    assert provider.active_model == "llama3"


# ---------------------------------------------------------------------------
# initialize() – Ollama unreachable, Groq key set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_ollama_unreachable_groq_fallback():
    """When Ollama is unreachable and groq_api_key is set, 'groq' is registered."""
    provider = LLMProvider()

    with patch("gnosis.services.llm_provider.settings") as mock_settings, \
         patch("gnosis.services.llm_provider.httpx.AsyncClient") as mock_http:
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_llm_model = "llama3"
        mock_settings.groq_api_key = "gsk_test_key"
        mock_settings.openai_api_key = ""

        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=AsyncMock(get=AsyncMock(side_effect=Exception("refused"))))
        mock_client_cm.__aexit__ = AsyncMock(return_value=False)
        mock_http.return_value = mock_client_cm

        await provider.initialize()

    assert "ollama" not in provider._available
    assert "groq" in provider._available
    assert provider.active_provider == "groq"
    assert provider.active_model == "llama-3.3-70b-versatile"  # line 112


# ---------------------------------------------------------------------------
# initialize() – OpenAI only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_openai_only():
    """When only openai_api_key is set, 'openai' is registered."""
    provider = LLMProvider()

    with patch("gnosis.services.llm_provider.settings") as mock_settings, \
         patch("gnosis.services.llm_provider.httpx.AsyncClient") as mock_http:
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_llm_model = "llama3"
        mock_settings.groq_api_key = ""
        mock_settings.openai_api_key = "sk-test"

        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=AsyncMock(get=AsyncMock(side_effect=Exception("refused"))))
        mock_client_cm.__aexit__ = AsyncMock(return_value=False)
        mock_http.return_value = mock_client_cm

        await provider.initialize()

    assert "openai" in provider._available
    assert provider.active_provider == "openai"
    assert provider.active_model == "gpt-4o-mini"  # line 114


# ---------------------------------------------------------------------------
# swap_model() – Ollama not available raises RuntimeError  (line 125)
# ---------------------------------------------------------------------------

def test_swap_model_raises_when_ollama_unavailable():
    provider = LLMProvider()
    # _available is empty by default
    with pytest.raises(RuntimeError, match="Ollama is not an available provider"):
        provider.swap_model("mistral")


# ---------------------------------------------------------------------------
# complete() – first provider fails, second succeeds  (lines 181->179)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_falls_back_on_provider_failure():
    """complete() should skip a failing provider and succeed on the next one."""
    provider = LLMProvider()
    provider._available = ["groq", "openai"]

    failing_client = AsyncMock()
    failing_client.chat.completions.create = AsyncMock(side_effect=Exception("groq down"))

    succeeding_client = AsyncMock()
    succeeding_client.chat.completions.create = AsyncMock(return_value=_mock_chat_response("fallback answer"))

    provider._groq_client = failing_client
    provider._openai_client = succeeding_client

    result = await provider.complete("tell me something")
    assert result == "fallback answer"


# ---------------------------------------------------------------------------
# complete() – all providers fail → RuntimeError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_raises_when_all_providers_fail():
    provider = LLMProvider()
    provider._available = ["openai"]

    failing_client = AsyncMock()
    failing_client.chat.completions.create = AsyncMock(side_effect=Exception("openai down"))
    provider._openai_client = failing_client

    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await provider.complete("test")


# ---------------------------------------------------------------------------
# stream() – provider exception falls back to next  (lines 184-187)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_falls_back_on_provider_failure():
    """stream() should skip a failing provider and stream from the next."""
    provider = LLMProvider()
    provider._available = ["groq", "openai"]

    failing_client = AsyncMock()
    failing_client.chat.completions.create = AsyncMock(side_effect=Exception("stream error"))
    provider._groq_client = failing_client

    # Build a real async generator for the openai stream
    chunks = [_mock_stream_chunk("token1"), _mock_stream_chunk("token2")]

    async def _fake_stream(*args, **kwargs):
        return _async_iter(chunks)

    succeeding_client = AsyncMock()
    succeeding_client.chat.completions.create = AsyncMock(side_effect=_fake_stream)
    provider._openai_client = succeeding_client

    tokens = []
    async for tok in provider.stream("hello"):
        tokens.append(tok)

    assert tokens == ["token1", "token2"]


@pytest.mark.asyncio
async def test_stream_raises_when_all_providers_fail():
    provider = LLMProvider()
    provider._available = ["openai"]

    failing_client = AsyncMock()
    failing_client.chat.completions.create = AsyncMock(side_effect=Exception("all down"))
    provider._openai_client = failing_client

    with pytest.raises(RuntimeError, match="All LLM stream providers failed"):
        async for _ in provider.stream("test"):
            pass
