"""Coverage tests for gnosis/services/llm_provider.py."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_provider(provider="openai", model="gpt-4o-mini", api_key="test-key"):
    with patch("gnosis.services.llm_provider.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = provider
        mock_settings.OPENAI_API_KEY = api_key
        mock_settings.ANTHROPIC_API_KEY = api_key
        mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
        mock_settings.LLM_MODEL = model
        from gnosis.services.llm_provider import LLMProvider
        return LLMProvider()


def test_llm_provider_instantiates():
    from gnosis.services.llm_provider import LLMProvider
    with patch("gnosis.services.llm_provider.settings") as s:
        s.LLM_PROVIDER = "openai"
        s.OPENAI_API_KEY = "k"
        s.ANTHROPIC_API_KEY = "k"
        s.OLLAMA_BASE_URL = "http://localhost:11434"
        s.LLM_MODEL = "gpt-4o-mini"
        p = LLMProvider()
        assert p is not None


@pytest.mark.asyncio
async def test_get_completion_openai():
    from gnosis.services.llm_provider import LLMProvider
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello from OpenAI"

    with patch("gnosis.services.llm_provider.settings") as s, \
         patch("gnosis.services.llm_provider.AsyncOpenAI") as mock_oai:
        s.LLM_PROVIDER = "openai"
        s.OPENAI_API_KEY = "k"
        s.ANTHROPIC_API_KEY = "k"
        s.OLLAMA_BASE_URL = "http://localhost:11434"
        s.LLM_MODEL = "gpt-4o-mini"
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_oai.return_value = mock_client

        provider = LLMProvider()
        provider._client = mock_client
        result = await provider.get_completion("Say hello")
        assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_completion_anthropic():
    from gnosis.services.llm_provider import LLMProvider
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = "Hello from Anthropic"

    with patch("gnosis.services.llm_provider.settings") as s, \
         patch("gnosis.services.llm_provider.anthropic") as mock_anthropic:
        s.LLM_PROVIDER = "anthropic"
        s.OPENAI_API_KEY = "k"
        s.ANTHROPIC_API_KEY = "k"
        s.OLLAMA_BASE_URL = "http://localhost:11434"
        s.LLM_MODEL = "claude-3-5-sonnet-20241022"
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        provider = LLMProvider()
        provider._client = mock_client
        provider._provider = "anthropic"
        result = await provider.get_completion("Say hello")
        assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_completion_ollama():
    from gnosis.services.llm_provider import LLMProvider
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Ollama response"

    with patch("gnosis.services.llm_provider.settings") as s, \
         patch("gnosis.services.llm_provider.AsyncOpenAI") as mock_oai:
        s.LLM_PROVIDER = "ollama"
        s.OPENAI_API_KEY = "k"
        s.ANTHROPIC_API_KEY = "k"
        s.OLLAMA_BASE_URL = "http://localhost:11434"
        s.LLM_MODEL = "llama3"
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_oai.return_value = mock_client

        provider = LLMProvider()
        provider._client = mock_client
        provider._provider = "ollama"
        result = await provider.get_completion("Say hello")
        assert isinstance(result, str)


@pytest.mark.asyncio
async def test_stream_completion_yields_chunks():
    from gnosis.services.llm_provider import LLMProvider

    async def _fake_stream(*args, **kwargs):
        chunks = ["Hello", " world", "!"]
        for c in chunks:
            m = MagicMock()
            m.choices = [MagicMock()]
            m.choices[0].delta.content = c
            yield m

    with patch("gnosis.services.llm_provider.settings") as s, \
         patch("gnosis.services.llm_provider.AsyncOpenAI") as mock_oai:
        s.LLM_PROVIDER = "openai"
        s.OPENAI_API_KEY = "k"
        s.ANTHROPIC_API_KEY = "k"
        s.OLLAMA_BASE_URL = "http://localhost:11434"
        s.LLM_MODEL = "gpt-4o-mini"
        mock_client = MagicMock()
        mock_client.chat.completions.create = _fake_stream
        mock_oai.return_value = mock_client

        provider = LLMProvider()
        provider._client = mock_client
        chunks = []
        async for chunk in provider.stream_completion("test"):
            chunks.append(chunk)
        assert len(chunks) > 0
