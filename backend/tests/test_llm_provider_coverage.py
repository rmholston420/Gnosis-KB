"""Gap-filling tests for gnosis/services/llm_provider.py.

Covers:
- LLMProvider properties: is_available, active_provider, active_model
- swap_model: success and RuntimeError when ollama not available
- _get_client_and_model: each tier and RuntimeError when empty
- _get_client_for: each tier and ValueError for unknown provider
- complete(): success path, all-providers-fail RuntimeError
- stream(): success path, all-providers-fail RuntimeError
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gnosis.services.llm_provider import LLMProvider


def _provider_with(*available, **clients):
    """Construct a pre-configured LLMProvider without calling initialize()."""
    p = LLMProvider()
    p._available = list(available)
    if "ollama" in clients:
        p._ollama_client = clients["ollama"]
    if "groq" in clients:
        p._groq_client = clients["groq"]
    if "openai" in clients:
        p._openai_client = clients["openai"]
    return p


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

def test_is_available_true_when_providers_present():
    p = _provider_with("ollama")
    assert p.is_available is True


def test_is_available_false_when_no_providers():
    p = _provider_with()
    assert p.is_available is False


def test_active_provider_ollama_first():
    p = _provider_with("ollama", "openai")
    assert p.active_provider == "ollama"


def test_active_provider_groq_when_no_ollama():
    p = _provider_with("groq", "openai")
    assert p.active_provider == "groq"


def test_active_provider_openai_last():
    p = _provider_with("openai")
    assert p.active_provider == "openai"


def test_active_provider_none_when_empty():
    p = _provider_with()
    assert p.active_provider == "none"


def test_active_model_ollama():
    p = _provider_with("ollama")
    p._ollama_model = "llama3"
    assert p.active_model == "llama3"


def test_active_model_groq():
    p = _provider_with("groq")
    assert p.active_model == "llama-3.3-70b-versatile"


def test_active_model_openai():
    p = _provider_with("openai")
    assert p.active_model == "gpt-4o-mini"


def test_active_model_empty():
    p = _provider_with()
    assert p.active_model == ""


# ---------------------------------------------------------------------------
# swap_model
# ---------------------------------------------------------------------------

def test_swap_model_updates_ollama_model():
    p = _provider_with("ollama")
    p.swap_model("mistral")
    assert p._ollama_model == "mistral"


def test_swap_model_raises_when_no_ollama():
    p = _provider_with("openai")
    with pytest.raises(RuntimeError, match="not an available"):
        p.swap_model("anything")


# ---------------------------------------------------------------------------
# _get_client_and_model
# ---------------------------------------------------------------------------

def test_get_client_and_model_ollama():
    mock_client = MagicMock()
    p = _provider_with("ollama", ollama=mock_client)
    p._ollama_model = "llama3"
    client, model = p._get_client_and_model()
    assert client is mock_client
    assert model == "llama3"


def test_get_client_and_model_groq():
    mock_client = MagicMock()
    p = _provider_with("groq", groq=mock_client)
    client, model = p._get_client_and_model()
    assert client is mock_client
    assert model == "llama-3.3-70b-versatile"


def test_get_client_and_model_openai():
    mock_client = MagicMock()
    p = _provider_with("openai", openai=mock_client)
    client, model = p._get_client_and_model()
    assert client is mock_client
    assert model == "gpt-4o-mini"


def test_get_client_and_model_raises_when_empty():
    p = _provider_with()
    with pytest.raises(RuntimeError, match="No LLM provider"):
        p._get_client_and_model()


# ---------------------------------------------------------------------------
# _get_client_for
# ---------------------------------------------------------------------------

def test_get_client_for_ollama():
    mock_client = MagicMock()
    p = _provider_with("ollama", ollama=mock_client)
    c, m = p._get_client_for("ollama")
    assert c is mock_client


def test_get_client_for_groq():
    mock_client = MagicMock()
    p = _provider_with("groq", groq=mock_client)
    c, m = p._get_client_for("groq")
    assert m == "llama-3.3-70b-versatile"


def test_get_client_for_openai():
    mock_client = MagicMock()
    p = _provider_with("openai", openai=mock_client)
    c, m = p._get_client_for("openai")
    assert m == "gpt-4o-mini"


def test_get_client_for_unknown_raises():
    p = _provider_with()
    with pytest.raises(ValueError, match="Unknown"):
        p._get_client_for("anthropic")


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_success():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "The answer."
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    p = _provider_with("openai", openai=mock_client)
    result = await p.complete("What is 2+2?")
    assert result == "The answer."


@pytest.mark.asyncio
async def test_complete_all_fail_raises():
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError("timeout")
    )
    p = _provider_with("openai", openai=mock_client)
    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await p.complete("prompt")


@pytest.mark.asyncio
async def test_complete_falls_back_to_next_provider():
    """If ollama fails, groq is tried and succeeds."""
    ollama_client = AsyncMock()
    ollama_client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError("ollama down")
    )
    groq_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "groq answer"
    groq_client.chat.completions.create = AsyncMock(return_value=mock_response)

    p = _provider_with("ollama", "groq", ollama=ollama_client, groq=groq_client)
    result = await p.complete("hello")
    assert result == "groq answer"


# ---------------------------------------------------------------------------
# stream()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_success_yields_chunks():
    async def fake_chunks():
        for text in ["chunk1", "chunk2"]:
            chunk = MagicMock()
            chunk.choices[0].delta.content = text
            yield chunk

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake_chunks())

    p = _provider_with("openai", openai=mock_client)
    chunks = [c async for c in p.stream("prompt")]
    assert chunks == ["chunk1", "chunk2"]


@pytest.mark.asyncio
async def test_stream_all_fail_raises():
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError("stream fail")
    )
    p = _provider_with("openai", openai=mock_client)
    with pytest.raises(RuntimeError, match="All LLM stream providers failed"):
        async for _ in p.stream("prompt"):
            pass
