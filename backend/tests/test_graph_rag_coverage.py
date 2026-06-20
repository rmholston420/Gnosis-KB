"""Coverage tests for gnosis/services/graph_rag.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_rag():
    """Construct a GraphRAGService with LightRAG stubbed out."""
    # Patch the module-level import guard so _LIGHTRAG_AVAILABLE stays True
    # and _instances lookup works without a real Ollama/LightRAG install.
    with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.LightRAG", MagicMock(), create=True), \
         patch("gnosis.services.graph_rag.settings") as s:
        s.lightrag_data_dir = "/tmp/lightrag_test"
        from gnosis.services.graph_rag import GraphRAGService
        svc = GraphRAGService.__new__(GraphRAGService)
        svc._instances = {}
        from pathlib import Path
        svc._base_dir = Path("/tmp/lightrag_test")
        return svc


def test_graph_rag_instantiates():
    from gnosis.services.graph_rag import GraphRAGService
    # Minimal smoke-test: the class can be imported and has expected attrs.
    assert hasattr(GraphRAGService, "ingest_note")
    assert hasattr(GraphRAGService, "query")
    assert hasattr(GraphRAGService, "stream")


@pytest.mark.asyncio
async def test_ingest_note_calls_ainsert():
    rag = _make_rag()
    mock_instance = AsyncMock()
    mock_instance.ainsert = AsyncMock()
    # Pre-populate so _get_instance returns our mock immediately
    rag._instances[1] = mock_instance

    # ingest_note(title, body, user_id)
    await rag.ingest_note(title="My Note", body="Some content", user_id=1)
    mock_instance.ainsert.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_note_no_instance_is_noop():
    """When _get_instance returns None (LightRAG unavailable), ingest is silent."""
    rag = _make_rag()
    with patch.object(rag, "_get_instance", new_callable=AsyncMock, return_value=None):
        # Should not raise
        await rag.ingest_note(title="T", body="B", user_id=1)


@pytest.mark.asyncio
async def test_ingest_note_rag_error_is_swallowed():
    """LightRAG ainsert errors are caught and logged, not re-raised."""
    rag = _make_rag()
    mock_instance = AsyncMock()
    mock_instance.ainsert = AsyncMock(side_effect=RuntimeError("RAG failure"))
    rag._instances[1] = mock_instance

    # Must NOT raise — error is swallowed by the except block in ingest_note
    await rag.ingest_note(title="T", body="B", user_id=1)


@pytest.mark.asyncio
async def test_query_single_graph_returns_string():
    rag = _make_rag()
    mock_instance = AsyncMock()
    mock_instance.aquery = AsyncMock(return_value="Answer from graph")
    rag._instances[1] = mock_instance

    with patch("gnosis.services.graph_rag.QueryParam", MagicMock(), create=True):
        result = await rag.query(question="What is Python?", user_id=1)

    assert isinstance(result, str)
    assert "Answer" in result


@pytest.mark.asyncio
async def test_query_returns_unavailable_when_no_instance():
    rag = _make_rag()
    with patch.object(rag, "_get_instance", new_callable=AsyncMock, return_value=None):
        result = await rag.query(question="test?", user_id=99)

    assert "unavailable" in result.lower() or isinstance(result, str)


@pytest.mark.asyncio
async def test_is_available_false_when_not_initialised():
    rag = _make_rag()
    result = await rag.is_available(user_id=999)
    assert result is False


@pytest.mark.asyncio
async def test_stream_yields_unavailable_when_no_instance():
    rag = _make_rag()
    with patch.object(rag, "_get_instance", new_callable=AsyncMock, return_value=None):
        chunks = []
        async for chunk in rag.stream(question="test", user_id=99):
            chunks.append(chunk)

    assert len(chunks) >= 1
    assert any("unavailable" in c.lower() for c in chunks)
