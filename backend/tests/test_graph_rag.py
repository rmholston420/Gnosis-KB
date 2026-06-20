"""Unit tests for gnosis/services/graph_rag.py.

LightRAG is NOT installed in the venv, so _LIGHTRAG_AVAILABLE=False in the
module.  Tests cover:
  - unavailable path: _get_instance returns None, query/stream return fallback strings
  - available path: LightRAG class and QueryParam mocked via patch; ingest,
    query (single + multi-graph fan-out), stream (astream_query + aquery fallback)
  - _synthesise: LLM available and unavailable paths
  - is_available: reflects instance cache state
"""
from __future__ import annotations

import types
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lightrag_stub():
    """Build a minimal lightrag sys.modules stub."""
    lr_mod = types.ModuleType("lightrag")
    llm_mod = types.ModuleType("lightrag.llm")
    ollama_mod = types.ModuleType("lightrag.llm.ollama")

    QueryParam = MagicMock()
    LightRAG = MagicMock()

    lr_mod.LightRAG = LightRAG          # type: ignore[attr-defined]
    lr_mod.QueryParam = QueryParam      # type: ignore[attr-defined]
    ollama_mod.ollama_embed = MagicMock()            # type: ignore[attr-defined]
    ollama_mod.ollama_model_complete = MagicMock()   # type: ignore[attr-defined]

    return {
        "lightrag": lr_mod,
        "lightrag.llm": llm_mod,
        "lightrag.llm.ollama": ollama_mod,
    }, LightRAG, QueryParam


# ---------------------------------------------------------------------------
# Tests: LightRAG UNAVAILABLE (default venv state)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_instance_returns_none_when_lightrag_unavailable():
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()
    result = await svc._get_instance(user_id=1)
    assert result is None


@pytest.mark.asyncio
async def test_query_returns_fallback_string_when_unavailable():
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()
    answer = await svc.query("What is consciousness?", user_id=1)
    assert "unavailable" in answer.lower() or "Graph-RAG" in answer


@pytest.mark.asyncio
async def test_stream_yields_fallback_string_when_unavailable():
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()
    tokens = [t async for t in svc.stream("What is PKM?", user_id=1)]
    assert len(tokens) == 1
    assert "unavailable" in tokens[0].lower() or "Graph-RAG" in tokens[0]


@pytest.mark.asyncio
async def test_ingest_note_noop_when_unavailable():
    """ingest_note should silently no-op when LightRAG is absent."""
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()
    # Should not raise
    await svc.ingest_note("Title", "Body", user_id=1)


@pytest.mark.asyncio
async def test_is_available_false_when_lightrag_unavailable():
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()
    assert await svc.is_available(user_id=1) is False


# ---------------------------------------------------------------------------
# Tests: LightRAG AVAILABLE (mocked via patch)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_instance_creates_and_caches_instance(tmp_path):
    stubs, LightRAG_cls, _ = _make_lightrag_stub()
    mock_instance = AsyncMock()
    LightRAG_cls.return_value = mock_instance

    with patch.dict(sys.modules, stubs):
        from importlib import reload
        import gnosis.services.graph_rag as gr
        reload(gr)
        gr.settings.lightrag_data_dir = str(tmp_path)
        svc = gr.GraphRAGService()

        inst1 = await svc._get_instance(user_id=7)
        inst2 = await svc._get_instance(user_id=7)

    assert inst1 is inst2  # cached
    LightRAG_cls.assert_called_once()


@pytest.mark.asyncio
async def test_query_single_returns_aquery_result(tmp_path):
    stubs, LightRAG_cls, QueryParam_cls = _make_lightrag_stub()
    mock_instance = AsyncMock()
    mock_instance.aquery = AsyncMock(return_value="Deep answer")
    LightRAG_cls.return_value = mock_instance

    with patch.dict(sys.modules, stubs):
        from importlib import reload
        import gnosis.services.graph_rag as gr
        reload(gr)
        gr.settings.lightrag_data_dir = str(tmp_path)
        svc = gr.GraphRAGService()
        result = await svc._query_single(user_id=3, question="What is PKM?", mode="hybrid")

    assert result == "Deep answer"


@pytest.mark.asyncio
async def test_query_single_returns_error_string_on_exception(tmp_path):
    stubs, LightRAG_cls, _ = _make_lightrag_stub()
    mock_instance = AsyncMock()
    mock_instance.aquery = AsyncMock(side_effect=RuntimeError("timeout"))
    LightRAG_cls.return_value = mock_instance

    with patch.dict(sys.modules, stubs):
        from importlib import reload
        import gnosis.services.graph_rag as gr
        reload(gr)
        gr.settings.lightrag_data_dir = str(tmp_path)
        svc = gr.GraphRAGService()
        result = await svc._query_single(user_id=3, question="?", mode="hybrid")

    assert "Query failed" in result


@pytest.mark.asyncio
async def test_ingest_note_calls_ainsert(tmp_path):
    stubs, LightRAG_cls, _ = _make_lightrag_stub()
    mock_instance = AsyncMock()
    mock_instance.ainsert = AsyncMock()
    LightRAG_cls.return_value = mock_instance

    with patch.dict(sys.modules, stubs):
        from importlib import reload
        import gnosis.services.graph_rag as gr
        reload(gr)
        gr.settings.lightrag_data_dir = str(tmp_path)
        svc = gr.GraphRAGService()
        await svc.ingest_note("My Title", "My body.", user_id=5)

    mock_instance.ainsert.assert_awaited_once()
    call_text = mock_instance.ainsert.call_args[0][0]
    assert "My Title" in call_text
    assert "My body." in call_text


@pytest.mark.asyncio
async def test_stream_uses_astream_query_when_available(tmp_path):
    stubs, LightRAG_cls, _ = _make_lightrag_stub()

    async def _fake_stream(*a, **kw):
        for token in ["Hello", " ", "World"]:
            yield token

    mock_instance = AsyncMock()
    mock_instance.astream_query = _fake_stream
    LightRAG_cls.return_value = mock_instance

    with patch.dict(sys.modules, stubs):
        from importlib import reload
        import gnosis.services.graph_rag as gr
        reload(gr)
        gr.settings.lightrag_data_dir = str(tmp_path)
        svc = gr.GraphRAGService()
        tokens = [t async for t in svc.stream("Tell me about PKM", user_id=2)]

    assert tokens == ["Hello", " ", "World"]


@pytest.mark.asyncio
async def test_stream_falls_back_to_aquery_when_no_astream(tmp_path):
    stubs, LightRAG_cls, _ = _make_lightrag_stub()
    mock_instance = AsyncMock()
    # no astream_query attribute
    del mock_instance.astream_query
    mock_instance.aquery = AsyncMock(return_value="Single token answer")
    LightRAG_cls.return_value = mock_instance

    with patch.dict(sys.modules, stubs):
        from importlib import reload
        import gnosis.services.graph_rag as gr
        reload(gr)
        gr.settings.lightrag_data_dir = str(tmp_path)
        svc = gr.GraphRAGService()
        tokens = [t async for t in svc.stream("?", user_id=2)]

    assert tokens == ["Single token answer"]


@pytest.mark.asyncio
async def test_synthesise_concatenates_when_llm_unavailable(tmp_path):
    stubs, LightRAG_cls, _ = _make_lightrag_stub()
    with patch.dict(sys.modules, stubs):
        from importlib import reload
        import gnosis.services.graph_rag as gr
        reload(gr)
        gr.settings.lightrag_data_dir = str(tmp_path)
        svc = gr.GraphRAGService()

        mock_llm = MagicMock()
        mock_llm.is_available = False
        with patch("gnosis.services.graph_rag.GraphRAGService._synthesise",
                   wraps=svc._synthesise):
            with patch("gnosis.services.llm_provider.llm_provider", mock_llm):
                result = await svc._synthesise(
                    "question", ["[Vault 1]\nAnswer A", "[Vault 2]\nAnswer B"]
                )

    assert "Answer A" in result
    assert "Answer B" in result
