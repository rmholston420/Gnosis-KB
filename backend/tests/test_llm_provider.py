"""Unit tests for gnosis/services/llm_provider.py.

Patches httpx so no real Ollama server is required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provider():
    from gnosis.services.llm_provider import LLMProvider
    return LLMProvider()


# ---------------------------------------------------------------------------
# LLMProvider.list_models
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_models_returns_names():
    from gnosis.services.llm_provider import LLMProvider
    provider = LLMProvider()
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {"models": [{"name": "mistral"}, {"name": "llama3"}]}

    with patch.object(provider._client, "get", new=AsyncMock(return_value=fake_resp)):
        models = await provider.list_models()
    assert "mistral" in models
    assert "llama3" in models


@pytest.mark.asyncio
async def test_list_models_empty_on_error():
    from gnosis.services.llm_provider import LLMProvider
    import httpx
    provider = LLMProvider()

    with patch.object(provider._client, "get", new=AsyncMock(side_effect=httpx.ConnectError("refused"))):
        models = await provider.list_models()
    assert models == []


# ---------------------------------------------------------------------------
# LLMProvider.chat
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_returns_content():
    from gnosis.services.llm_provider import LLMProvider
    provider = LLMProvider()
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {"message": {"content": "Hello!"}}

    with patch.object(provider._client, "post", new=AsyncMock(return_value=fake_resp)):
        result = await provider.chat("mistral", [{"role": "user", "content": "Hi"}])
    assert result == "Hello!"


@pytest.mark.asyncio
async def test_chat_raises_on_http_error():
    from gnosis.services.llm_provider import LLMProvider
    import httpx
    provider = LLMProvider()

    error_resp = MagicMock()
    error_resp.status_code = 500
    error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=error_resp
    )
    with patch.object(provider._client, "post", new=AsyncMock(return_value=error_resp)):
        with pytest.raises(httpx.HTTPStatusError):
            await provider.chat("mistral", [{"role": "user", "content": "Hi"}])


# ---------------------------------------------------------------------------
# LLMProvider.generate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_returns_response():
    from gnosis.services.llm_provider import LLMProvider
    provider = LLMProvider()
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {"response": "Generated text."}

    with patch.object(provider._client, "post", new=AsyncMock(return_value=fake_resp)):
        result = await provider.generate("mistral", "Write a poem.")
    assert result == "Generated text."
