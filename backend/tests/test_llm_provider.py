"""Tests for gnosis/services/llm_provider.py.

LLMProvider imports httpx and openai at MODULE LEVEL, so they must be
patched as module-level attributes (patch('gnosis.services.llm_provider.httpx', ...)).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(available: list[str] | None = None):
    """Return an LLMProvider with _available pre-set (skips async initialize())."""
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()
    if available is not None:
        p._available = list(available)
    return p


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

def test_is_available_false_when_no_providers():
    p = _make_provider([])
    assert p.is_available is False


def test_is_available_true_when_ollama():
    p = _make_provider(["ollama"])
    assert p.is_available is True


def test_active_provider_prefers_ollama():
    p = _make_provider(["ollama", "openai"])
    assert p.active_provider == "ollama"


def test_active_provider_falls_back_to_groq():
    p = _make_provider(["groq", "openai"])
    assert p.active_provider == "groq"


def test_active_provider_openai_last():
    p = _make_provider(["openai"])
    assert p.active_provider == "openai"


def test_active_provider_none_when_empty():
    p = _make_provider([])
    assert p.active_provider == "none"


def test_active_model_ollama():
    p = _make_provider(["ollama"])
    p._ollama_model = "llama3.2"
    assert p.active_model == "llama3.2"


def test_active_model_groq():
    p = _make_provider(["groq"])
    assert p.active_model == "llama-3.3-70b-versatile"


def test_active_model_openai():
    p = _make_provider(["openai"])
    assert p.active_model == "gpt-4o-mini"


def test_active_model_none_when_empty():
    p = _make_provider([])
    assert p.active_model == ""


# ---------------------------------------------------------------------------
# swap_model
# ---------------------------------------------------------------------------

def test_swap_model_updates_model_name():
    p = _make_provider(["ollama"])
    p.swap_model("mistral:7b")
    assert p._ollama_model == "mistral:7b"


def test_swap_model_raises_when_not_ollama():
    p = _make_provider(["openai"])
    with pytest.raises(RuntimeError, match="Ollama"):
        p.swap_model("any-model")


# ---------------------------------------------------------------------------
# _get_client_and_model
# ---------------------------------------------------------------------------

def test_get_client_and_model_raises_when_empty():
    p = _make_provider([])
    with pytest.raises(RuntimeError):
        p._get_client_and_model()


def test_get_client_and_model_returns_ollama_first():
    p = _make_provider(["ollama", "openai"])
    p._ollama_client = MagicMock()
    p._openai_client = MagicMock()
    client, model = p._get_client_and_model()
    assert client is p._ollama_client


# ---------------------------------------------------------------------------
# initialize() — patches httpx so no real network calls
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_detects_ollama_when_available():
    from gnosis.services.llm_provider import LLMProvider
    from gnosis.config import get_settings

    fake_resp = MagicMock()
    fake_resp.status_code = 200

    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    fake_httpx = MagicMock()
    fake_httpx.AsyncClient.return_value = fake_client

    p = LLMProvider()
    with patch("gnosis.services.llm_provider.httpx", fake_httpx), \
         patch("gnosis.services.llm_provider.AsyncOpenAI", MagicMock()):
        await p.initialize()

    assert "ollama" in p._available


@pytest.mark.asyncio
async def test_initialize_skips_ollama_when_unreachable():
    from gnosis.services.llm_provider import LLMProvider

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=Exception("refused"))
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    fake_httpx = MagicMock()
    fake_httpx.AsyncClient.return_value = fake_client

    p = LLMProvider()
    with patch("gnosis.services.llm_provider.httpx", fake_httpx), \
         patch("gnosis.services.llm_provider.AsyncOpenAI", MagicMock()):
        await p.initialize()

    assert "ollama" not in p._available


# ---------------------------------------------------------------------------
# complete() — end-to-end with a mocked AsyncOpenAI client
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_returns_string():
    from gnosis.services.llm_provider import LLMProvider

    fake_msg = MagicMock()
    fake_msg.content = "Hello from LLM."
    fake_choice = MagicMock()
    fake_choice.message = fake_msg
    fake_completion = MagicMock()
    fake_completion.choices = [fake_choice]

    fake_client = MagicMock()
    fake_client.chat = MagicMock()
    fake_client.chat.completions = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_completion)

    p = _make_provider(["ollama"])
    p._ollama_client = fake_client
    p._ollama_model = "llama3.2"

    result = await p.complete("Say hello")
    assert result == "Hello from LLM."


@pytest.mark.asyncio
async def test_complete_raises_when_no_provider():
    from gnosis.services.llm_provider import LLMProvider
    p = _make_provider([])
    with pytest.raises(RuntimeError):
        await p.complete("hello")
