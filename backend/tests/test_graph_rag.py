"""Tests for services/graph_rag.py — GraphRAGService."""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gnosis.services.graph_rag import GraphRAGService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service_with_lightrag() -> tuple[GraphRAGService, MagicMock]:
    """Return a GraphRAGService and a fake LightRAG instance pre-loaded."""
    service = GraphRAGService()
    mock_instance = MagicMock()
    mock_instance.ainsert = AsyncMock(return_value=None)
    mock_instance.aquery = AsyncMock(return_value="The answer")
    mock_instance.astream_query = None  # will be replaced per-test
    service._instances[1] = mock_instance
    return service, mock_instance


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_available_false_when_not_initialised():
    service = GraphRAGService()
    result = await service.is_available(user_id=1)
    assert result is False


@pytest.mark.asyncio
async def test_is_available_true_when_cached():
    service, _ = _make_service_with_lightrag()
    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", True):
        result = await service.is_available(user_id=1)
    assert result is True


# ---------------------------------------------------------------------------
# ingest_note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_note_calls_ainsert():
    service, mock_instance = _make_service_with_lightrag()
    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", True):
        await service.ingest_note(title="My Note", body="body text", user_id=1)
    mock_instance.ainsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_note_no_op_when_lightrag_unavailable():
    service = GraphRAGService()
    # _instances is empty — _get_instance returns None
    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", False):
        await service.ingest_note(title="T", body="b", user_id=1)  # must not raise


@pytest.mark.asyncio
async def test_ingest_note_swallows_exception():
    service, mock_instance = _make_service_with_lightrag()
    mock_instance.ainsert = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", True):
        await service.ingest_note(title="T", body="b", user_id=1)  # must not raise


# ---------------------------------------------------------------------------
# query — single graph
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_single_returns_answer():
    service, mock_instance = _make_service_with_lightrag()
    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.QueryParam", MagicMock()):
        result = await service.query("What is X?", user_id=1)
    assert result == "The answer"


@pytest.mark.asyncio
async def test_query_returns_unavailable_message_when_no_instance():
    service = GraphRAGService()
    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", False):
        result = await service.query("anything", user_id=99)
    assert "unavailable" in result.lower()


@pytest.mark.asyncio
async def test_query_swallows_exception_returns_error_string():
    service, mock_instance = _make_service_with_lightrag()
    mock_instance.aquery = AsyncMock(side_effect=RuntimeError("crash"))
    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.QueryParam", MagicMock()):
        result = await service.query("question", user_id=1)
    assert "failed" in result.lower() or "crash" in result.lower()


# ---------------------------------------------------------------------------
# query — multi-graph fan-out
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_multi_graph_merges_answers():
    service = GraphRAGService()
    # Pre-load two user instances
    for uid, answer in [(1, "Answer from vault 1"), (2, "Answer from vault 2")]:
        mock = MagicMock()
        mock.aquery = AsyncMock(return_value=answer)
        service._instances[uid] = mock

    mock_llm = MagicMock()
    mock_llm.is_available = True
    mock_llm.complete = AsyncMock(return_value="Synthesised answer")

    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.QueryParam", MagicMock()), \
         patch("gnosis.services.llm_provider.llm_provider", mock_llm):
        result = await service.query("question", user_id=1, owner_ids={1, 2})

    assert result  # some non-empty answer returned


# ---------------------------------------------------------------------------
# stream
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_yields_tokens_via_aquery_fallback():
    service, mock_instance = _make_service_with_lightrag()
    # No astream_query attribute — falls back to aquery
    del mock_instance.astream_query
    mock_instance.aquery = AsyncMock(return_value="token1 token2")

    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.QueryParam", MagicMock()):
        tokens = [t async for t in service.stream("question", user_id=1)]

    assert len(tokens) >= 1
    assert "token1" in tokens[0]


@pytest.mark.asyncio
async def test_stream_yields_unavailable_when_no_instance():
    service = GraphRAGService()
    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", False):
        tokens = [t async for t in service.stream("q", user_id=99)]
    assert any("unavailable" in t.lower() for t in tokens)


@pytest.mark.asyncio
async def test_stream_yields_error_on_exception():
    service, mock_instance = _make_service_with_lightrag()
    del mock_instance.astream_query
    mock_instance.aquery = AsyncMock(side_effect=RuntimeError("stream crash"))

    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.QueryParam", MagicMock()):
        tokens = [t async for t in service.stream("q", user_id=1)]

    assert any("error" in t.lower() or "crash" in t.lower() for t in tokens)


# ---------------------------------------------------------------------------
# _synthesise
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesise_calls_llm_provider():
    service = GraphRAGService()
    mock_llm = MagicMock()
    mock_llm.is_available = True
    mock_llm.complete = AsyncMock(return_value="Synthesised")

    with patch("gnosis.services.llm_provider.llm_provider", mock_llm):
        result = await service._synthesise("question", ["A", "B"])

    assert result  # non-empty


@pytest.mark.asyncio
async def test_synthesise_concatenates_when_llm_unavailable():
    service = GraphRAGService()
    mock_llm = MagicMock()
    mock_llm.is_available = False

    with patch("gnosis.services.llm_provider.llm_provider", mock_llm):
        result = await service._synthesise("q", ["Part A", "Part B"])

    assert "Part A" in result and "Part B" in result


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_no_op_when_lightrag_unavailable():
    service = GraphRAGService()
    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", False):
        await service.initialize(user_id=1)  # must not raise
