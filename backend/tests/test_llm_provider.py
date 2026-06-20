"""Unit tests for gnosis/services/llm_provider.py.

LLMProvider uses AsyncOpenAI clients (openai SDK) — not httpx directly.
All tests mock the openai client's chat.completions.create coroutine.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_provider(provider_name="ollama"):
    """Return a pre-initialised LLMProvider with one fake client."""
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()
    fake_client = MagicMock()
    fake_client.chat = MagicMock()
    fake_client.chat.completions = MagicMock()
    p._available = [provider_name]
    if provider_name == "ollama":
        p._ollama_client = fake_client
        p._ollama_model = "mistral"
    elif provider_name == "groq":
        p._groq_client = fake_client
    elif provider_name == "openai":
        p._openai_client = fake_client
    return p, fake_client


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

def test_is_available_false_when_no_providers():
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()
    assert not p.is_available


def test_is_available_true_when_provider_set():
    p, _ = _make_provider("ollama")
    assert p.is_available


def test_active_provider_returns_highest_priority():
    p, _ = _make_provider("ollama")
    assert p.active_provider == "ollama"


def test_active_model_ollama():
    p, _ = _make_provider("ollama")
    assert p.active_model == "mistral"


def test_active_model_groq():
    p, _ = _make_provider("groq")
    assert p.active_model == "llama-3.3-70b-versatile"


def test_active_model_openai():
    p, _ = _make_provider("openai")
    assert p.active_model == "gpt-4o-mini"


def test_active_provider_none_when_empty():
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()
    assert p.active_provider == "none"
    assert p.active_model == ""


def test_swap_model_updates_ollama_model():
    p, _ = _make_provider("ollama")
    p.swap_model("llama3")
    assert p._ollama_model == "llama3"


def test_swap_model_raises_when_ollama_unavailable():
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()
    p._available = ["groq"]
    with pytest.raises(RuntimeError, match="Ollama"):
        p.swap_model("llama3")


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_returns_content():
    p, fake_client = _make_provider("ollama")
    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = "Answer text"
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)

    result = await p.complete("What is 2+2?")
    assert result == "Answer text"


@pytest.mark.asyncio
async def test_complete_falls_back_to_next_provider():
    """First provider raises, second succeeds."""
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()

    fake_ollama = MagicMock()
    fake_ollama.chat.completions.create = AsyncMock(side_effect=RuntimeError("timeout"))

    fake_groq = MagicMock()
    good_response = MagicMock()
    good_response.choices = [MagicMock()]
    good_response.choices[0].message.content = "Fallback answer"
    fake_groq.chat.completions.create = AsyncMock(return_value=good_response)

    p._available = ["ollama", "groq"]
    p._ollama_client = fake_ollama
    p._ollama_model = "mistral"
    p._groq_client = fake_groq

    result = await p.complete("hi")
    assert result == "Fallback answer"


@pytest.mark.asyncio
async def test_complete_raises_when_all_providers_fail():
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("fail"))
    p._available = ["ollama"]
    p._ollama_client = fake_client
    p._ollama_model = "mistral"

    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await p.complete("hi")


@pytest.mark.asyncio
async def test_complete_no_providers_raises():
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()
    with pytest.raises(RuntimeError):
        await p.complete("hi")


# ---------------------------------------------------------------------------
# initialize() — provider availability probing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_adds_ollama_when_reachable():
    from gnosis.services.llm_provider import LLMProvider
    import httpx
    p = LLMProvider()

    fake_resp = MagicMock()
    fake_resp.status_code = 200

    with patch("httpx.AsyncClient") as mock_ctx:
        instance = AsyncMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.get = AsyncMock(return_value=fake_resp)
        mock_ctx.return_value = instance
        with patch("gnosis.services.llm_provider.AsyncOpenAI"):
            await p.initialize()

    assert "ollama" in p._available


@pytest.mark.asyncio
async def test_initialize_skips_ollama_when_unreachable():
    from gnosis.services.llm_provider import LLMProvider
    import httpx
    p = LLMProvider()

    with patch("httpx.AsyncClient") as mock_ctx:
        instance = AsyncMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_ctx.return_value = instance
        await p.initialize()

    assert "ollama" not in p._available
