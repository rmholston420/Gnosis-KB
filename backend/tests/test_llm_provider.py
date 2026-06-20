"""Tests for gnosis.services.llm_provider.LLMProvider.

All external I/O is mocked:
  - httpx.AsyncClient.get  — Ollama health probe
  - AsyncOpenAI            — replaced with a lightweight stub

No network, no Qdrant, no DB required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from gnosis.services.llm_provider import LLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completion(content: str) -> MagicMock:
    """Build a minimal openai ChatCompletion-shaped mock."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


async def _async_chunks(tokens: list[str]):
    """Async generator that yields streaming delta mocks."""
    for t in tokens:
        delta = MagicMock()
        delta.content = t
        choice = MagicMock()
        choice.delta = delta
        chunk = MagicMock()
        chunk.choices = [choice]
        yield chunk


def _mock_openai_client(completion_content: str = "ok") -> MagicMock:
    """Return a mock AsyncOpenAI client whose completions.create returns a canned response."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_make_completion(completion_content))
    return client


# ---------------------------------------------------------------------------
# initialize() — Ollama probe paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_ollama_available():
    """When Ollama responds 200, it is added as the active provider."""
    provider = LLMProvider()
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient") as mock_http_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls.return_value = mock_http

        with patch("gnosis.services.llm_provider.AsyncOpenAI", return_value=_mock_openai_client()):
            with patch("gnosis.services.llm_provider.settings") as s:
                s.ollama_base_url = "http://localhost:11434"
                s.ollama_llm_model = "llama3"
                s.groq_api_key = None
                s.openai_api_key = None
                await provider.initialize()

    assert "ollama" in provider._available
    assert provider.active_provider == "ollama"
    assert provider.active_model == "llama3"
    assert provider.is_available is True


@pytest.mark.asyncio
async def test_initialize_ollama_unreachable_falls_to_groq():
    """When Ollama raises a connection error, Groq is used instead."""
    provider = LLMProvider()

    with patch("httpx.AsyncClient") as mock_http_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls.return_value = mock_http

        with patch("gnosis.services.llm_provider.AsyncOpenAI", return_value=_mock_openai_client()):
            with patch("gnosis.services.llm_provider.settings") as s:
                s.ollama_base_url = "http://localhost:11434"
                s.ollama_llm_model = "llama3"
                s.groq_api_key = "gsk_test"
                s.openai_api_key = None
                await provider.initialize()

    assert "ollama" not in provider._available
    assert "groq" in provider._available
    assert provider.active_provider == "groq"
    assert provider.active_model == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_initialize_openai_only():
    """Only OpenAI key configured — no Ollama, no Groq."""
    provider = LLMProvider()

    with patch("httpx.AsyncClient") as mock_http_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls.return_value = mock_http

        with patch("gnosis.services.llm_provider.AsyncOpenAI", return_value=_mock_openai_client()):
            with patch("gnosis.services.llm_provider.settings") as s:
                s.ollama_base_url = "http://localhost:11434"
                s.ollama_llm_model = "llama3"
                s.groq_api_key = None
                s.openai_api_key = "sk-test"
                await provider.initialize()

    assert provider.active_provider == "openai"
    assert provider.active_model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_initialize_no_providers_available():
    """All providers absent — is_available is False, active_provider is 'none'."""
    provider = LLMProvider()

    with patch("httpx.AsyncClient") as mock_http_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls.return_value = mock_http

        with patch("gnosis.services.llm_provider.settings") as s:
            s.ollama_base_url = "http://localhost:11434"
            s.ollama_llm_model = "llama3"
            s.groq_api_key = None
            s.openai_api_key = None
            await provider.initialize()

    assert provider.is_available is False
    assert provider.active_provider == "none"
    assert provider.active_model == ""


@pytest.mark.asyncio
async def test_initialize_ollama_non_200_ignored():
    """Ollama returning non-200 is silently skipped."""
    provider = LLMProvider()
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 503

    with patch("httpx.AsyncClient") as mock_http_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls.return_value = mock_http

        with patch("gnosis.services.llm_provider.settings") as s:
            s.ollama_base_url = "http://localhost:11434"
            s.ollama_llm_model = "llama3"
            s.groq_api_key = None
            s.openai_api_key = None
            await provider.initialize()

    assert "ollama" not in provider._available


# ---------------------------------------------------------------------------
# complete() — single provider, fallback, all-fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_returns_content():
    """complete() returns the first choice's message content."""
    provider = LLMProvider()
    provider._available = ["ollama"]
    provider._ollama_client = _mock_openai_client("hello world")
    provider._ollama_model = "llama3"

    result = await provider.complete("say hello")
    assert result == "hello world"


@pytest.mark.asyncio
async def test_complete_falls_back_on_provider_failure():
    """When Ollama fails, complete() falls back to Groq."""
    provider = LLMProvider()
    provider._available = ["ollama", "groq"]

    failing_client = _mock_openai_client()
    failing_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("timeout"))
    provider._ollama_client = failing_client
    provider._ollama_model = "llama3"

    provider._groq_client = _mock_openai_client("groq response")

    result = await provider.complete("test")
    assert result == "groq response"


@pytest.mark.asyncio
async def test_complete_all_providers_fail_raises():
    """When every provider fails, complete() raises RuntimeError."""
    provider = LLMProvider()
    provider._available = ["ollama"]

    bad_client = _mock_openai_client()
    bad_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("down"))
    provider._ollama_client = bad_client
    provider._ollama_model = "llama3"

    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await provider.complete("test")


@pytest.mark.asyncio
async def test_complete_no_providers_raises():
    """complete() with empty _available raises RuntimeError immediately."""
    provider = LLMProvider()
    provider._available = []

    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await provider.complete("test")


@pytest.mark.asyncio
async def test_complete_custom_system_prompt():
    """system param is forwarded to the client."""
    provider = LLMProvider()
    provider._available = ["ollama"]
    mock_client = _mock_openai_client("answer")
    provider._ollama_client = mock_client
    provider._ollama_model = "llama3"

    result = await provider.complete("q", system="You are a bot.", temperature=0.1, max_tokens=100)
    assert result == "answer"
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0.1
    assert call_kwargs["max_tokens"] == 100
    assert call_kwargs["messages"][0]["content"] == "You are a bot."


# ---------------------------------------------------------------------------
# stream() — yields tokens, fallback, all-fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_yields_tokens():
    """stream() yields delta content strings."""
    provider = LLMProvider()
    provider._available = ["ollama"]

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_async_chunks(["Hello", " ", "world"])
    )
    provider._ollama_client = mock_client
    provider._ollama_model = "llama3"

    tokens = []
    async for tok in provider.stream("hi"):
        tokens.append(tok)

    assert tokens == ["Hello", " ", "world"]


@pytest.mark.asyncio
async def test_stream_falls_back_on_failure():
    """stream() falls back to next provider when first raises."""
    provider = LLMProvider()
    provider._available = ["ollama", "groq"]

    bad_client = MagicMock()
    bad_client.chat = MagicMock()
    bad_client.chat.completions = MagicMock()
    bad_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("stream fail"))
    provider._ollama_client = bad_client
    provider._ollama_model = "llama3"

    good_client = MagicMock()
    good_client.chat = MagicMock()
    good_client.chat.completions = MagicMock()
    good_client.chat.completions.create = AsyncMock(
        return_value=_async_chunks(["ok"])
    )
    provider._groq_client = good_client

    tokens = []
    async for tok in provider.stream("test"):
        tokens.append(tok)

    assert tokens == ["ok"]


@pytest.mark.asyncio
async def test_stream_all_fail_raises():
    provider = LLMProvider()
    provider._available = ["ollama"]

    bad_client = MagicMock()
    bad_client.chat = MagicMock()
    bad_client.chat.completions = MagicMock()
    bad_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("dead"))
    provider._ollama_client = bad_client
    provider._ollama_model = "llama3"

    with pytest.raises(RuntimeError, match="All LLM stream providers failed"):
        async for _ in provider.stream("test"):
            pass


# ---------------------------------------------------------------------------
# swap_model()
# ---------------------------------------------------------------------------

def test_swap_model_updates_ollama_model():
    provider = LLMProvider()
    provider._available = ["ollama"]
    provider._ollama_model = "llama3"

    provider.swap_model("mistral")
    assert provider._ollama_model == "mistral"
    assert provider.active_model == "mistral"


def test_swap_model_raises_when_ollama_not_available():
    provider = LLMProvider()
    provider._available = ["groq"]

    with pytest.raises(RuntimeError, match="Ollama is not an available provider"):
        provider.swap_model("mistral")


# ---------------------------------------------------------------------------
# _get_client_and_model() — priority resolution
# ---------------------------------------------------------------------------

def test_get_client_and_model_prefers_ollama():
    provider = LLMProvider()
    provider._available = ["ollama", "groq", "openai"]
    mock_c = _mock_openai_client()
    provider._ollama_client = mock_c
    provider._ollama_model = "llama3"

    client, model = provider._get_client_and_model()
    assert client is mock_c
    assert model == "llama3"


def test_get_client_and_model_falls_to_groq():
    provider = LLMProvider()
    provider._available = ["groq"]
    mock_c = _mock_openai_client()
    provider._groq_client = mock_c

    client, model = provider._get_client_and_model()
    assert client is mock_c
    assert model == "llama-3.3-70b-versatile"


def test_get_client_and_model_falls_to_openai():
    provider = LLMProvider()
    provider._available = ["openai"]
    mock_c = _mock_openai_client()
    provider._openai_client = mock_c

    client, model = provider._get_client_and_model()
    assert client is mock_c
    assert model == "gpt-4o-mini"


def test_get_client_and_model_raises_when_none():
    provider = LLMProvider()
    provider._available = []

    with pytest.raises(RuntimeError, match="No LLM provider available"):
        provider._get_client_and_model()


# ---------------------------------------------------------------------------
# _get_client_for() — named provider lookup
# ---------------------------------------------------------------------------

def test_get_client_for_ollama():
    provider = LLMProvider()
    mock_c = _mock_openai_client()
    provider._ollama_client = mock_c
    provider._ollama_model = "llama3"

    client, model = provider._get_client_for("ollama")
    assert client is mock_c
    assert model == "llama3"


def test_get_client_for_groq():
    provider = LLMProvider()
    mock_c = _mock_openai_client()
    provider._groq_client = mock_c

    client, model = provider._get_client_for("groq")
    assert client is mock_c
    assert model == "llama-3.3-70b-versatile"


def test_get_client_for_openai():
    provider = LLMProvider()
    mock_c = _mock_openai_client()
    provider._openai_client = mock_c

    client, model = provider._get_client_for("openai")
    assert client is mock_c
    assert model == "gpt-4o-mini"


def test_get_client_for_unknown_raises():
    provider = LLMProvider()

    with pytest.raises(ValueError, match="Unknown or unconfigured provider"):
        provider._get_client_for("anthropic")


def test_get_client_for_unconfigured_raises():
    """Known provider name but client is None — raises ValueError."""
    provider = LLMProvider()
    provider._ollama_client = None

    with pytest.raises(ValueError, match="Unknown or unconfigured provider"):
        provider._get_client_for("ollama")
