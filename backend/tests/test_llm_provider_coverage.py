"""Coverage tests for gnosis/services/llm_provider.py - LLMProvider class."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from gnosis.services.llm_provider import LLMProvider


def _p(available=None):
    p = LLMProvider()
    if available is not None:
        p._available = list(available)
    return p


@pytest.mark.asyncio
async def test_initialize_ollama_available():
    p = LLMProvider()
    mock_resp = MagicMock(); mock_resp.status_code = 200
    with patch("gnosis.services.llm_provider.httpx.AsyncClient") as mhx, \
         patch("gnosis.services.llm_provider.get_settings") as mc:
        mc.return_value = MagicMock(ollama_base_url="http://localhost:11434",
            ollama_llm_model="mistral", groq_api_key=None, openai_api_key=None)
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=mock_resp)
        mhx.return_value = client
        await p.initialize()
    assert "ollama" in p._available
    assert p.is_available is True
    assert p.active_provider == "ollama"


@pytest.mark.asyncio
async def test_initialize_ollama_down_openai_fallback():
    p = LLMProvider()
    with patch("gnosis.services.llm_provider.httpx.AsyncClient") as mhx, \
         patch("gnosis.services.llm_provider.get_settings") as mc:
        mc.return_value = MagicMock(ollama_base_url="http://localhost:11434",
            ollama_llm_model="mistral", groq_api_key=None, openai_api_key="sk-x")
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(side_effect=Exception("down"))
        mhx.return_value = client
        await p.initialize()
    assert "openai" in p._available
    assert p.active_provider == "openai"


@pytest.mark.asyncio
async def test_initialize_no_providers():
    p = LLMProvider()
    with patch("gnosis.services.llm_provider.httpx.AsyncClient") as mhx, \
         patch("gnosis.services.llm_provider.get_settings") as mc:
        mc.return_value = MagicMock(ollama_base_url="http://localhost:11434",
            ollama_llm_model="mistral", groq_api_key=None, openai_api_key=None)
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(side_effect=Exception("down"))
        mhx.return_value = client
        await p.initialize()
    assert p._available == []
    assert p.is_available is False
    assert p.active_provider == "none"


@pytest.mark.asyncio
async def test_complete_returns_string():
    p = _p(["openai"])
    mo = AsyncMock()
    mo.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="Answer"))]))
    p._openai_client = mo
    assert await p.complete("q") == "Answer"


@pytest.mark.asyncio
async def test_complete_falls_back_on_error():
    p = _p(["ollama", "openai"])
    mo_o = AsyncMock()
    mo_o.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
    p._ollama_client = mo_o; p._ollama_model = "mistral"
    mo_oa = AsyncMock()
    mo_oa.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="fallback"))]))
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
    p = _p([])
    with pytest.raises(RuntimeError):
        await p.complete("q")


@pytest.mark.asyncio
async def test_stream_yields_chunks():
    p = _p(["openai"])
    c1 = MagicMock(); c1.choices = [MagicMock(delta=MagicMock(content="Hello "))]
    c2 = MagicMock(); c2.choices = [MagicMock(delta=MagicMock(content="world"))]
    async def _fake(**kwargs):
        for c in [c1, c2]: yield c
    mo = AsyncMock()
    mo.chat.completions.create = AsyncMock(return_value=_fake())
    p._openai_client = mo
    chunks = [c async for c in p.stream("q")]
    assert chunks == ["Hello ", "world"]


def test_active_model_ollama():
    p = _p(["ollama"]); p._ollama_model = "llama3"
    assert p.active_model == "llama3"

def test_active_model_groq():
    assert _p(["groq"]).active_model == "llama-3.3-70b-versatile"

def test_active_model_openai():
    assert _p(["openai"]).active_model == "gpt-4o-mini"

def test_active_model_none():
    assert _p([]).active_model == "none"

def test_set_ollama_model():
    p = _p(["ollama"]); p._ollama_model = "old"
    p.set_ollama_model("llama3")
    assert p._ollama_model == "llama3"

def test_set_ollama_model_not_available_raises():
    p = _p(["openai"])
    with pytest.raises(RuntimeError, match="not an available provider"):
        p.set_ollama_model("llama3")
