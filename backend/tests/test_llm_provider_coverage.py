"""Coverage tests for gnosis/services/llm_provider.py.

Key facts from the source:
  - complete() iterates self._available; if empty the for-loop never runs,
    last_exc stays None, and it raises:
      RuntimeError("All LLM providers failed. Last error: None")
    NOT "No LLM provider available" (that comes from _get_client_and_model,
    which is NOT called by complete()).
  - swap_model raises: RuntimeError("Ollama is not an available provider")
    (exact message from source)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gnosis.services.llm_provider import LLMProvider


def _p(available=None, ollama_model="mistral"):
    p = LLMProvider()
    p._available = list(available or [])
    p._ollama_model = ollama_model
    return p


# ---------------------------------------------------------------------------
# initialize() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_ollama_available():
    p = LLMProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=mock_resp)
    with (
        patch("gnosis.services.llm_provider.httpx.AsyncClient", return_value=client),
        patch("gnosis.services.llm_provider.settings") as ms,
        patch("gnosis.services.llm_provider.AsyncOpenAI"),
    ):
        ms.ollama_base_url = "http://localhost:11434"
        ms.ollama_llm_model = "mistral"
        ms.groq_api_key = None
        ms.openai_api_key = None
        await p.initialize()
    assert "ollama" in p._available
    assert p.is_available is True
    assert p.active_provider == "ollama"


@pytest.mark.asyncio
async def test_initialize_ollama_down_openai_fallback():
    p = LLMProvider()
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(side_effect=Exception("down"))
    with (
        patch("gnosis.services.llm_provider.httpx.AsyncClient", return_value=client),
        patch("gnosis.services.llm_provider.settings") as ms,
        patch("gnosis.services.llm_provider.AsyncOpenAI"),
    ):
        ms.ollama_base_url = "http://localhost:11434"
        ms.ollama_llm_model = "mistral"
        ms.groq_api_key = None
        ms.openai_api_key = "sk-x"
        await p.initialize()
    assert "openai" in p._available
    assert p.active_provider == "openai"


@pytest.mark.asyncio
async def test_initialize_no_providers():
    """Ollama down + no API keys → _available is empty."""
    p = LLMProvider()
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(side_effect=Exception("down"))
    with (
        patch("gnosis.services.llm_provider.httpx.AsyncClient", return_value=client),
        patch("gnosis.services.llm_provider.settings") as ms,
    ):
        ms.ollama_base_url = "http://localhost:11434"
        ms.ollama_llm_model = "mistral"
        ms.groq_api_key = None
        ms.openai_api_key = None
        await p.initialize()
    assert p._available == []
    assert p.is_available is False
    assert p.active_provider == "none"


# ---------------------------------------------------------------------------
# complete() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_returns_string():
    p = _p(["openai"])
    mo = AsyncMock()
    mo.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="Answer"))])
    )
    p._openai_client = mo
    assert await p.complete("q") == "Answer"


@pytest.mark.asyncio
async def test_complete_falls_back_on_error():
    p = _p(["ollama", "openai"])
    mo_o = AsyncMock()
    mo_o.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
    p._ollama_client = mo_o
    mo_oa = AsyncMock()
    mo_oa.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="fallback"))])
    )
    p._openai_client = mo_oa
    assert await p.complete("q") == "fallback"


@pytest.mark.asyncio
async def test_complete_all_fail_raises():
    p = _p(["openai"])
    mo = AsyncMock()
    mo.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
    p._openai_client = mo
    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await p.complete("q")


@pytest.mark.asyncio
async def test_complete_no_providers_raises():
    """_available == [] → for-loop never runs → raises with last_exc=None.

    Exact message: 'All LLM providers failed. Last error: None'
    """
    p = _p([])
    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await p.complete("q")


# ---------------------------------------------------------------------------
# stream() test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_yields_chunks():
    p = _p(["openai"])
    c1 = MagicMock()
    c1.choices = [MagicMock(delta=MagicMock(content="Hello "))]
    c2 = MagicMock()
    c2.choices = [MagicMock(delta=MagicMock(content="world"))]

    async def _fake(**kwargs):
        for c in [c1, c2]:
            yield c

    mo = AsyncMock()
    mo.chat.completions.create = AsyncMock(return_value=_fake())
    p._openai_client = mo
    chunks = [c async for c in p.stream("q")]
    assert chunks == ["Hello ", "world"]


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


def test_active_model_ollama():
    p = _p(["ollama"], ollama_model="llama3")
    assert p.active_model == "llama3"


def test_active_model_groq():
    assert _p(["groq"]).active_model == "llama-3.3-70b-versatile"


def test_active_model_openai():
    assert _p(["openai"]).active_model == "gpt-4o-mini"


def test_active_model_none():
    assert _p([]).active_model == ""


# ---------------------------------------------------------------------------
# swap_model() tests
# ---------------------------------------------------------------------------


def test_swap_model_updates_ollama_model():
    p = _p(["ollama"], ollama_model="old")
    p.swap_model("llama3")
    assert p._ollama_model == "llama3"


def test_swap_model_not_available_raises():
    """Exact message from source: 'Ollama is not an available provider'"""
    p = _p(["openai"])
    with pytest.raises(RuntimeError, match="not an available provider"):
        p.swap_model("llama3")
