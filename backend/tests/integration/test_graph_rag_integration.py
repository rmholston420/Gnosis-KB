"""
Integration tests for GraphRAGService.

These tests exercise the *real* service methods but replace LightRAG and
llm_provider with fakes so no Ollama or on-disk LightRAG store is needed.

Coverage targets (graph_rag.py)
--------------------------------
  50-52    import-time try/except when lightrag is NOT installed
  187      _synthesise: llm_provider.is_available False → concatenation fallback
  288->286 stream() _get_instance returns None → yields unavailability message
  291->exit stream() instance.astream_query raises → yields "Stream error: ..."
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helper: build a GraphRAGService with a fake LightRAG instance
# ---------------------------------------------------------------------------

def _make_service_with_instance(user_id: int = 1):
    """Return a GraphRAGService whose _instances[user_id] is a MagicMock."""
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()
    fake_instance = MagicMock()
    fake_instance.aquery = AsyncMock(return_value="query answer")
    # Simulate that astream_query is NOT present by default
    if hasattr(fake_instance, "astream_query"):
        del fake_instance.astream_query
    svc._instances[user_id] = fake_instance
    return svc, fake_instance


# ---------------------------------------------------------------------------
# _synthesise: llm_provider not available → concatenate  (line 187)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesise_without_llm_falls_back_to_concat():
    """When llm_provider.is_available is False, _synthesise concatenates answers."""
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()

    with patch("gnosis.services.graph_rag.graph_rag") as _:
        # Patch llm_provider inside the service module
        mock_llm = MagicMock()
        mock_llm.is_available = False

        with patch("gnosis.services.llm_provider.llm_provider", mock_llm):
            result = await svc._synthesise(
                question="What is impermanence?",
                answers=["[Vault 1]\nAnswer one.", "[Vault 2]\nAnswer two."],
            )

    assert "Answer one." in result
    assert "Answer two." in result


# ---------------------------------------------------------------------------
# _synthesise: llm_provider.complete raises → concatenation fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesise_llm_exception_falls_back_to_concat():
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()

    mock_llm = MagicMock()
    mock_llm.is_available = True
    mock_llm.complete = AsyncMock(side_effect=Exception("LLM down"))

    with patch("gnosis.services.llm_provider.llm_provider", mock_llm):
        result = await svc._synthesise(
            question="anything",
            answers=["first", "second"],
        )

    assert "first" in result
    assert "second" in result


# ---------------------------------------------------------------------------
# stream() – _get_instance returns None → unavailability yield  (line 288->286)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_yields_unavailable_when_instance_is_none():
    """When LightRAG is not installed (_get_instance returns None), stream
    must yield a single human-readable error string and return."""
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()

    with patch.object(svc, "_get_instance", new=AsyncMock(return_value=None)):
        tokens = []
        async for tok in svc.stream("any question", user_id=99):
            tokens.append(tok)

    assert len(tokens) == 1
    assert "unavailable" in tokens[0].lower() or "not initialised" in tokens[0].lower()


# ---------------------------------------------------------------------------
# stream() – astream_query raises → yields "Stream error: ..."  (line 291->exit)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_yields_error_on_astream_query_exception():
    """When the LightRAG instance's astream_query raises, the service should
    yield a single 'Stream error: ...' token and return."""
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()

    fake_instance = MagicMock()
    # Make hasattr(instance, "astream_query") True
    async def _exploding_stream(*args, **kwargs):
        raise RuntimeError("astream blew up")
        yield  # make it an async generator

    fake_instance.astream_query = _exploding_stream

    with patch.object(svc, "_get_instance", new=AsyncMock(return_value=fake_instance)):
        tokens = []
        async for tok in svc.stream("question", user_id=42):
            tokens.append(tok)

    assert any("Stream error" in t for t in tokens)


# ---------------------------------------------------------------------------
# stream() – instance has no astream_query → falls back to aquery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_falls_back_to_aquery_when_no_astream():
    """When instance lacks astream_query, stream() calls aquery and yields result."""
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()

    fake_instance = MagicMock(spec=["aquery"])  # spec excludes astream_query
    fake_instance.aquery = AsyncMock(return_value="single answer token")

    with patch.object(svc, "_get_instance", new=AsyncMock(return_value=fake_instance)):
        tokens = []
        async for tok in svc.stream("question", user_id=7):
            tokens.append(tok)

    assert tokens == ["single answer token"]


# ---------------------------------------------------------------------------
# _get_instance – LightRAG init raises → returns None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_instance_returns_none_on_lightrag_init_failure():
    """When LightRAG() constructor raises, _get_instance logs and returns None."""
    from gnosis.services import graph_rag as _mod

    if not _mod._LIGHTRAG_AVAILABLE:
        pytest.skip("lightrag not installed — import-path already covered")

    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()

    with patch("gnosis.services.graph_rag.LightRAG", side_effect=RuntimeError("CUDA OOM")):
        result = await svc._get_instance(user_id=999)

    assert result is None
    assert 999 not in svc._instances


# ---------------------------------------------------------------------------
# multi-graph query: empty answers → unavailability string
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_multi_graph_all_fail_returns_unavailable_message():
    """query() with multiple owner_ids that all fail returns the fallback string."""
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()

    async def _failing_query_single(uid, question, mode):
        return "Graph-RAG is unavailable (LightRAG not initialised). Ensure Ollama is running and lightrag-hku is installed."

    with patch.object(svc, "_query_single", side_effect=_failing_query_single):
        result = await svc.query("question", user_id=1, owner_ids={1, 2})

    assert "unavailable" in result.lower()
