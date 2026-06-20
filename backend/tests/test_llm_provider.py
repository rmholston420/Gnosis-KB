"""Tests for gnosis/services/llm_provider.py."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def _make_httpx(status=200, raises=None):
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


def _resp(content):
    choice = MagicMock()
    choice.message.content = content
    r = MagicMock()
    r.choices = [choice]
    return r


@pytest.mark.asyncio
async def test_initialize_records_ollama_when_reachable():
    from gnosis.services.llm_provider import LLMProvider
    with patch("gnosis.services.llm_provider.httpx", _make_httpx(200)), \
         patch("gnosis.services.llm_provider.AsyncOpenAI"):
        p = LLMProvider()
        await p.initialize()
    assert "ollama" in p._available


@pytest.mark.asyncio
async def test_initialize_skips_ollama_when_unreachable():
    from gnosis.services.llm_provider import LLMProvider
    with patch("gnosis.services.llm_provider.httpx", _make_httpx(raises=Exception("refused"))), \
         patch("gnosis.services.llm_provider.AsyncOpenAI"):
        p = LLMProvider()
        await p.initialize()
    assert "ollama" not in p._available


@pytest.mark.asyncio
async def test_initialize_skips_ollama_on_non_200():
    from gnosis.services.llm_provider import LLMProvider
    with patch("gnosis.services.llm_provider.httpx", _make_httpx(500)), \
         patch("gnosis.services.llm_provider.AsyncOpenAI"):
        p = LLMProvider()
        await p.initialize()
    assert "ollama" not in p._available


@pytest.mark.asyncio
async def test_initialize_records_groq_when_key_set():
    from gnosis.services.llm_provider import LLMProvider
    with patch("gnosis.services.llm_provider.httpx", _make_httpx(raises=Exception("no ollama"))), \
         patch("gnosis.services.llm_provider.AsyncOpenAI"), \
         patch("gnosis.services.llm_provider.settings") as s:
        s.ollama_base_url = "http://localhost:11434"
        s.ollama_llm_model = "llama3"
        s.groq_api_key = "gsk_test"
        s.openai_api_key = ""
        p = LLMProvider()
        await p.initialize()
    assert "groq" in p._available


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
        p = LLMProvider()
        await p.initialize()
    assert "openai" in p._available


@pytest.mark.asyncio
async def test_complete_ollama_returns_string():
    from gnosis.services.llm_provider import LLMProvider
    fc = MagicMock()
    fc.chat.completions.create = AsyncMock(return_value=_resp("Hello from Ollama"))
    p = LLMProvider()
    p._available = ["ollama"]
    p._ollama_client = fc
    p._ollama_model = "llama3"
    assert await p.complete("Say hello") == "Hello from Ollama"


@pytest.mark.asyncio
async def test_complete_groq_returns_string():
    from gnosis.services.llm_provider import LLMProvider
    fc = MagicMock()
    fc.chat.completions.create = AsyncMock(return_value=_resp("Hello from Groq"))
    p = LLMProvider()
    p._available = ["groq"]
    p._groq_client = fc
    assert await p.complete("Say hello") == "Hello from Groq"


@pytest.mark.asyncio
async def test_complete_openai_returns_string():
    from gnosis.services.llm_provider import LLMProvider
    fc = MagicMock()
    fc.chat.completions.create = AsyncMock(return_value=_resp("Hello from OpenAI"))
    p = LLMProvider()
    p._available = ["openai"]
    p._openai_client = fc
    assert await p.complete("Say hello") == "Hello from OpenAI"


@pytest.mark.asyncio
async def test_complete_falls_back_to_second_provider():
    from gnosis.services.llm_provider import LLMProvider
    failing = MagicMock()
    failing.chat.completions.create = AsyncMock(side_effect=Exception("failed"))
    working = MagicMock()
    working.chat.completions.create = AsyncMock(return_value=_resp("fallback"))
    p = LLMProvider()
    p._available = ["ollama", "openai"]
    p._ollama_client = failing
    p._ollama_model = "llama3"
    p._openai_client = working
    assert await p.complete("hello") == "fallback"


@pytest.mark.asyncio
async def test_complete_raises_when_all_fail():
    from gnosis.services.llm_provider import LLMProvider
    fc = MagicMock()
    fc.chat.completions.create = AsyncMock(side_effect=Exception("failed"))
    p = LLMProvider()
    p._available = ["ollama"]
    p._ollama_client = fc
    p._ollama_model = "llama3"
    with pytest.raises(RuntimeError):
        await p.complete("hello")


@pytest.mark.asyncio
async def test_complete_raises_when_no_providers():
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()
    p._available = []
    with pytest.raises(RuntimeError):
        await p.complete("hello")


@pytest.mark.asyncio
async def test_stream_yields_chunks():
    from gnosis.services.llm_provider import LLMProvider

    async def fake_stream():
        for word in ["Hello", " ", "world"]:
            chunk = MagicMock()
            chunk.choices[0].delta.content = word
            yield chunk

    fc = MagicMock()
    fc.chat.completions.create = AsyncMock(return_value=fake_stream())
    p = LLMProvider()
    p._available = ["ollama"]
    p._ollama_client = fc
    p._ollama_model = "llama3"
    chunks = [c async for c in p.stream("Say hello")]
    assert "".join(chunks) == "Hello world"


@pytest.mark.asyncio
async def test_stream_raises_when_no_providers():
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()
    p._available = []
    with pytest.raises(RuntimeError):
        async for _ in p.stream("hello"):
            pass


# Real method name is swap_model, not swap_ollama_model
def test_swap_model_updates_model_name():
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()
    p._available = ["ollama"]
    p._ollama_client = MagicMock()
    p._ollama_model = "llama3"
    p.swap_model("mistral")
    assert p._ollama_model == "mistral"


def test_swap_model_raises_when_not_available():
    from gnosis.services.llm_provider import LLMProvider
    p = LLMProvider()
    p._available = []
    with pytest.raises(RuntimeError):
        p.swap_model("mistral")


def test_module_level_singleton_exists():
    from gnosis.services.llm_provider import llm_provider, LLMProvider
    assert isinstance(llm_provider, LLMProvider)
