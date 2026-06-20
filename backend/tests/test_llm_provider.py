"""Unit tests for gnosis/services/llm_provider.py.

Covers: is_available, active_provider, active_model, swap_model,
_get_client_and_model, complete (happy + all-fail fallback),
stream (happy + all-fail), initialize tiers.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _fresh_provider():
    """Return a new LLMProvider instance with a clean state."""
    from gnosis.services.llm_provider import LLMProvider
    return LLMProvider()


# ---------------------------------------------------------------------------
# Introspection properties
# ---------------------------------------------------------------------------

def test_is_available_false_when_no_providers():
    p = _fresh_provider()
    assert p.is_available is False


def test_active_provider_none_when_empty():
    p = _fresh_provider()
    assert p.active_provider == "none"


def test_active_model_empty_when_no_provider():
    p = _fresh_provider()
    assert p.active_model == ""


def test_is_available_true_with_ollama():
    p = _fresh_provider()
    p._available = ["ollama"]
    p._ollama_client = MagicMock()
    assert p.is_available is True
    assert p.active_provider == "ollama"


def test_active_model_for_ollama():
    p = _fresh_provider()
    p._available = ["ollama"]
    p._ollama_model = "llama3"
    assert p.active_model == "llama3"


def test_active_model_for_groq():
    p = _fresh_provider()
    p._available = ["groq"]
    assert p.active_model == "llama-3.3-70b-versatile"


def test_active_model_for_openai():
    p = _fresh_provider()
    p._available = ["openai"]
    assert p.active_model == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# swap_model
# ---------------------------------------------------------------------------

def test_swap_model_updates_ollama_model():
    p = _fresh_provider()
    p._available = ["ollama"]
    p._ollama_client = MagicMock()
    p.swap_model("mistral")
    assert p._ollama_model == "mistral"


def test_swap_model_raises_when_ollama_unavailable():
    p = _fresh_provider()
    p._available = ["groq"]
    with pytest.raises(RuntimeError, match="Ollama is not"):
        p.swap_model("mistral")


# ---------------------------------------------------------------------------
# _get_client_and_model
# ---------------------------------------------------------------------------

def test_get_client_and_model_raises_when_empty():
    p = _fresh_provider()
    with pytest.raises(RuntimeError, match="No LLM provider"):
        p._get_client_and_model()


def test_get_client_and_model_returns_groq_client():
    p = _fresh_provider()
    groq = MagicMock()
    p._available = ["groq"]
    p._groq_client = groq
    client, model = p._get_client_and_model()
    assert client is groq
    assert model == "llama-3.3-70b-versatile"


# ---------------------------------------------------------------------------
# complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_returns_text_from_first_provider():
    p = _fresh_provider()
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "Hello!"
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    p._available = ["ollama"]
    p._ollama_client = mock_client

    result = await p.complete("Tell me something")
    assert result == "Hello!"


@pytest.mark.asyncio
async def test_complete_falls_back_to_groq_on_ollama_failure():
    p = _fresh_provider()

    ollama_client = AsyncMock()
    ollama_client.chat.completions.create = AsyncMock(side_effect=Exception("timeout"))

    groq_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "Groq answer"
    groq_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    p._available = ["ollama", "groq"]
    p._ollama_client = ollama_client
    p._groq_client = groq_client

    result = await p.complete("hello")
    assert result == "Groq answer"


@pytest.mark.asyncio
async def test_complete_raises_when_all_providers_fail():
    p = _fresh_provider()
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
    p._available = ["groq"]
    p._groq_client = client

    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await p.complete("hi")


# ---------------------------------------------------------------------------
# stream
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_yields_tokens():
    p = _fresh_provider()

    async def _fake_stream(**kwargs):
        for t in ["Hello", " world"]:
            chunk = MagicMock()
            chunk.choices[0].delta.content = t
            yield chunk

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_fake_stream())

    p._available = ["groq"]
    p._groq_client = client

    tokens = []
    async for t in p.stream("say hello"):
        tokens.append(t)
    assert tokens == ["Hello", " world"]


@pytest.mark.asyncio
async def test_stream_raises_when_all_providers_fail():
    p = _fresh_provider()
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
    p._available = ["openai"]
    p._openai_client = client

    with pytest.raises(RuntimeError, match="All LLM stream providers failed"):
        async for _ in p.stream("hi"):
            pass


# ---------------------------------------------------------------------------
# initialize — Ollama + Groq + OpenAI tier probes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_adds_ollama_when_reachable():
    p = _fresh_provider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("gnosis.services.llm_provider.httpx.AsyncClient") as mock_ctx:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=mock_resp)
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=instance)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("gnosis.services.llm_provider.settings") as mock_settings:
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_llm_model = "llama3"
            mock_settings.groq_api_key = None
            mock_settings.openai_api_key = None
            await p.initialize()

    assert "ollama" in p._available


@pytest.mark.asyncio
async def test_initialize_adds_groq_when_key_present():
    p = _fresh_provider()

    with patch("gnosis.services.llm_provider.httpx.AsyncClient") as mock_ctx:
        instance = AsyncMock()
        instance.get = AsyncMock(side_effect=Exception("no ollama"))
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=instance)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("gnosis.services.llm_provider.settings") as mock_settings:
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_llm_model = "llama3"
            mock_settings.groq_api_key = "gsk_abc123"
            mock_settings.openai_api_key = None
            await p.initialize()

    assert "groq" in p._available
    assert "ollama" not in p._available
