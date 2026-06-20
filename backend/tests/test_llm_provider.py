"""Tests for gnosis/services/llm_provider.py.

Public API:
  LLMProvider (class)
    .initialize() -> probes Ollama/Groq/OpenAI tiers, populates ._available
    .complete(prompt, system, temperature, max_tokens) -> str
    .stream(prompt, system, temperature, max_tokens) -> AsyncGenerator[str]
    .swap_ollama_model(model) -> None
    ._get_client_and_model() -> (client, model_name)

httpx and AsyncOpenAI are imported at module level; patch them at
gnosis.services.llm_provider.httpx and gnosis.services.llm_provider.AsyncOpenAI.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def _make_httpx(status=200, raises=None):
    """Return a fake httpx module."""
    fake_resp = MagicMock()
    fake_resp.status_code = status
    fake_client = MagicMock()
    if raises:
        fake_client.get = AsyncMock(side_effect=raises)
    else:
        fake_client.get = AsyncMock(return_value=fake_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_httpx = MagicMock()
    fake_httpx.AsyncClient.return_value = fake_client
    return fake_httpx


def _make_completion_response(content):
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_records_ollama_when_reachable():
    from gnosis.services.llm_provider import LLMProvider
    with patch("gnosis.services.llm_provider.httpx", _make_httpx(200)), \
         patch("gnosis.services.llm_provider.AsyncOpenAI"):
        provider = LLMProvider()
        await provider.initialize()
    assert "ollama" in provider._available


@pytest.mark.asyncio
async def test_initialize_skips_ollama_when_unreachable():
    from gnosis.services.llm_provider import LLMProvider
    with patch("gnosis.services.llm_provider.httpx", _make_httpx(raises=Exception("refused"))), \
         patch("gnosis.services.llm_provider.AsyncOpenAI"):
        provider = LLMProvider()
        await provider.initialize()
    assert "ollama" not in provider._available


@pytest.mark.asyncio
async def test_initialize_skips_ollama_on_non_200():
    from gnosis.services.llm_provider import LLMProvider
    with patch("gnosis.services.llm_provider.httpx", _make_httpx(500)), \
         patch("gnosis.services.llm_provider.AsyncOpenAI"):
        provider = LLMProvider()
        await provider.initialize()
    assert "ollama" not in provider._available


@pytest.mark.asyncio
async def test_initialize_records_groq_when_key_set():
    from gnosis.services.llm_provider import LLMProvider
    with patch("gnosis.services.llm_provider.httpx", _make_httpx(raises=Exception("no ollama"))), \
         patch("gnosis.services.llm_provider.AsyncOpenAI"), \
         patch("gnosis.services.llm_provider.settings") as s:
        s.ollama_base_url = "http://localhost:11434"
        s.ollama_llm_model = "llama3"
        s.groq_api_key = "gsk_test_key"
        s.openai_api_key = ""
        provider = LLMProvider()
        await provider.initialize()
    assert "groq" in provider._available


@pytest.mark.asyncio
async def test_initialize_records_openai_when_key_set():
    from gnosis.services.llm_provider import LLMProvider
    with patch("gnosis.services.llm_provider.httpx", _make_httpx(raises=Exception("no ollama"))), \
         patch("gnosis.services.llm_provider.AsyncOpenAI"), \
         patch("gnosis.services.llm_provider.settings") as s:
        s.ollama_base_url = "http://localhost:11434"
        s.ollama_llm_model = "llama3"
        s.groq_api_key = ""
        s.openai_api_key = "sk-test"
        provider = LLMProvider()
        await provider.initialize()
    assert "openai" in provider._available


# ---------------------------------------------------------------------------
# complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_ollama_returns_string():
    from gnosis.services.llm_provider import LLMProvider
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        return_value=_make_completion_response("Hello from Ollama")
    )
    provider = LLMProvider()
    provider._available = ["ollama"]
    provider._ollama_client = fake_client
    provider._ollama_model = "llama3"
    result = await provider.complete("Say hello")
    assert result == "Hello from Ollama"


@pytest.mark.asyncio
async def test_complete_groq_returns_string():
    from gnosis.services.llm_provider import LLMProvider
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        return_value=_make_completion_response("Hello from Groq")
    )
    provider = LLMProvider()
    provider._available = ["groq"]
    provider._groq_client = fake_client
    result = await provider.complete("Say hello")
    assert result == "Hello from Groq"


@pytest.mark.asyncio
async def test_complete_openai_returns_string():
    from gnosis.services.llm_provider import LLMProvider
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        return_value=_make_completion_response("Hello from OpenAI")
    )
    provider = LLMProvider()
    provider._available = ["openai"]
    provider._openai_client = fake_client
    result = await provider.complete("Say hello")
    assert result == "Hello from OpenAI"


@pytest.mark.asyncio
async def test_complete_falls_back_to_second_provider():
    from gnosis.services.llm_provider import LLMProvider
    failing = MagicMock()
    failing.chat.completions.create = AsyncMock(side_effect=Exception("tier 1 failed"))
    working = MagicMock()
    working.chat.completions.create = AsyncMock(
        return_value=_make_completion_response("fallback response")
    )
    provider = LLMProvider()
    provider._available = ["ollama", "openai"]
    provider._ollama_client = failing
    provider._ollama_model = "llama3"
    provider._openai_client = working
    result = await provider.complete("hello")
    assert result == "fallback response"


@pytest.mark.asyncio
async def test_complete_raises_when_all_providers_fail():
    from gnosis.services.llm_provider import LLMProvider
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(side_effect=Exception("failed"))
    provider = LLMProvider()
    provider._available = ["ollama"]
    provider._ollama_client = fake_client
    provider._ollama_model = "llama3"
    with pytest.raises(RuntimeError):
        await provider.complete("hello")


@pytest.mark.asyncio
async def test_complete_raises_when_no_providers():
    from gnosis.services.llm_provider import LLMProvider
    provider = LLMProvider()
    provider._available = []
    with pytest.raises(RuntimeError):
        await provider.complete("hello")


# ---------------------------------------------------------------------------
# stream
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_yields_chunks():
    from gnosis.services.llm_provider import LLMProvider

    async def fake_stream():
        for word in ["Hello", " ", "world"]:
            chunk = MagicMock()
            chunk.choices[0].delta.content = word
            yield chunk

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_stream())

    provider = LLMProvider()
    provider._available = ["ollama"]
    provider._ollama_client = fake_client
    provider._ollama_model = "llama3"

    chunks = []
    async for chunk in provider.stream("Say hello"):
        chunks.append(chunk)

    assert "".join(chunks) == "Hello world"


@pytest.mark.asyncio
async def test_stream_raises_when_no_providers():
    from gnosis.services.llm_provider import LLMProvider
    provider = LLMProvider()
    provider._available = []
    with pytest.raises(RuntimeError):
        async for _ in provider.stream("hello"):
            pass


# ---------------------------------------------------------------------------
# swap_ollama_model
# ---------------------------------------------------------------------------

def test_swap_ollama_model_updates_model_name():
    from gnosis.services.llm_provider import LLMProvider
    provider = LLMProvider()
    provider._available = ["ollama"]
    provider._ollama_client = MagicMock()
    provider._ollama_model = "llama3"
    provider.swap_ollama_model("mistral")
    assert provider._ollama_model == "mistral"


def test_swap_ollama_model_raises_when_not_available():
    from gnosis.services.llm_provider import LLMProvider
    provider = LLMProvider()
    provider._available = []
    with pytest.raises(RuntimeError):
        provider.swap_ollama_model("mistral")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

def test_module_level_singleton_exists():
    from gnosis.services.llm_provider import llm_provider, LLMProvider
    assert isinstance(llm_provider, LLMProvider)
