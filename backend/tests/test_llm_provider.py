"""Tests for gnosis/services/llm_provider.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# get_completion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_completion_openai_returns_string():
    from gnosis.services.llm_provider import get_completion

    fake_choice = MagicMock()
    fake_choice.message.content = "Hello from GPT"
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)

    fake_openai = MagicMock()
    fake_openai.AsyncOpenAI.return_value = fake_client

    with patch.dict("sys.modules", {"openai": fake_openai}), \
         patch("gnosis.services.llm_provider.settings") as s:
        s.llm_provider = "openai"
        s.openai_api_key = "sk-test"
        s.llm_model = "gpt-4o-mini"
        result = await get_completion("Say hello")

    assert result == "Hello from GPT"


@pytest.mark.asyncio
async def test_get_completion_anthropic_returns_string():
    from gnosis.services.llm_provider import get_completion

    fake_content = MagicMock()
    fake_content.text = "Hello from Claude"
    fake_response = MagicMock()
    fake_response.content = [fake_content]

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_response)

    fake_anthropic = MagicMock()
    fake_anthropic.AsyncAnthropic.return_value = fake_client

    with patch.dict("sys.modules", {"anthropic": fake_anthropic}), \
         patch("gnosis.services.llm_provider.settings") as s:
        s.llm_provider = "anthropic"
        s.anthropic_api_key = "sk-test"
        s.llm_model = "claude-3-haiku-20240307"
        result = await get_completion("Say hello")

    assert result == "Hello from Claude"


@pytest.mark.asyncio
async def test_get_completion_ollama_returns_string():
    from gnosis.services.llm_provider import get_completion

    fake_response = MagicMock()
    fake_response.message.content = "Hello from Ollama"

    fake_ollama = MagicMock()
    fake_ollama.chat = AsyncMock(return_value=fake_response)

    with patch.dict("sys.modules", {"ollama": fake_ollama}), \
         patch("gnosis.services.llm_provider.settings") as s:
        s.llm_provider = "ollama"
        s.ollama_base_url = "http://localhost:11434"
        s.llm_model = "llama3"
        result = await get_completion("Say hello")

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_completion_unsupported_raises():
    from gnosis.services.llm_provider import get_completion

    with patch("gnosis.services.llm_provider.settings") as s:
        s.llm_provider = "nonexistent_provider_xyz"
        with pytest.raises(Exception):
            await get_completion("hello")


# ---------------------------------------------------------------------------
# stream_completion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_completion_openai_yields_chunks():
    from gnosis.services.llm_provider import stream_completion

    chunk1 = MagicMock(); chunk1.choices = [MagicMock()]; chunk1.choices[0].delta.content = "Hello"
    chunk2 = MagicMock(); chunk2.choices = [MagicMock()]; chunk2.choices[0].delta.content = " world"

    async def fake_stream():
        for c in [chunk1, chunk2]:
            yield c

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_stream())

    fake_openai = MagicMock()
    fake_openai.AsyncOpenAI.return_value = fake_client

    with patch.dict("sys.modules", {"openai": fake_openai}), \
         patch("gnosis.services.llm_provider.settings") as s:
        s.llm_provider = "openai"
        s.openai_api_key = "sk-test"
        s.llm_model = "gpt-4o-mini"
        chunks = [c async for c in stream_completion("Say hello")]

    assert len(chunks) > 0
