"""Full LLMProvider tests — rewritten to match the actual LLMProvider class.

The old file assumed get_completion / stream_completion / _client / _provider
attributes that don't exist. This replacement uses the real API:
  complete(prompt) -> str
  stream(prompt)   -> AsyncGenerator[str, None]
"""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from gnosis.services.llm_provider import LLMProvider


def _p(provider: str, client=None, model=None):
    """Build an LLMProvider with a single available provider pre-wired."""
    p = LLMProvider()
    p._available = [provider]
    if provider == "openai":
        p._openai_client = client
    elif provider == "groq":
        p._groq_client = client
    elif provider == "ollama":
        p._ollama_client = client
        p._ollama_model = model or "mistral"
    return p


def _make_client(content="response text"):
    """Build an AsyncOpenAI mock that returns content from chat.completions.create."""
    mo = AsyncMock()
    mo.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=content))]
        )
    )
    return mo


# ---------------------------------------------------------------------------
# complete() via each provider
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_completion_openai():
    """complete() via openai provider returns a string."""
    p = _p("openai", client=_make_client("Hello from OpenAI"))
    result = await p.complete("Say hello")
    assert isinstance(result, str)
    assert result == "Hello from OpenAI"


@pytest.mark.asyncio
async def test_get_completion_anthropic():
    """Groq is the Anthropic substitute in the 3-tier design; verify string return."""
    p = _p("groq", client=_make_client("Hello from Groq/Anthropic"))
    result = await p.complete("Say hello")
    assert isinstance(result, str)
    assert result == "Hello from Groq/Anthropic"


@pytest.mark.asyncio
async def test_get_completion_ollama():
    """complete() via ollama provider returns a string."""
    p = _p("ollama", client=_make_client("Ollama response"), model="llama3")
    result = await p.complete("Say hello")
    assert isinstance(result, str)
    assert result == "Ollama response"


# ---------------------------------------------------------------------------
# stream() test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_completion_yields_chunks():
    """stream() yields non-empty string chunks."""
    chunks_data = ["Hello", " ", "world", "!"]

    async def _fake_stream(**kwargs):
        for text in chunks_data:
            m = MagicMock()
            m.choices = [MagicMock(delta=MagicMock(content=text))]
            yield m

    mo = AsyncMock()
    mo.chat.completions.create = AsyncMock(return_value=_fake_stream())
    p = _p("openai", client=mo)

    collected = [chunk async for chunk in p.stream("test")]
    assert len(collected) > 0
    assert all(isinstance(c, str) for c in collected)
    assert "".join(collected) == "Hello world!"
