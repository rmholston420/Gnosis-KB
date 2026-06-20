"""Tests for gnosis/services/graph_rag.py.

LightRAG is an optional dependency. All tests either mock it or test
the fallback behaviour when it's unavailable.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(lightrag_available=False):
    """Return a GraphRAGService with lightrag availability set."""
    import gnosis.services.graph_rag as gr_mod
    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", lightrag_available):
        from gnosis.services.graph_rag import GraphRAGService
        svc = GraphRAGService()
    return svc


# ---------------------------------------------------------------------------
# _working_dir
# ---------------------------------------------------------------------------

def test_working_dir_legacy_user_is_base_dir(tmp_path):
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()
    svc._base_dir = tmp_path
    assert svc._working_dir(0) == tmp_path


def test_working_dir_non_zero_user_is_subdir(tmp_path):
    from gnosis.services.graph_rag import GraphRAGService
    svc = GraphRAGService()
    svc._base_dir = tmp_path
    assert svc._working_dir(42) == tmp_path / "42"


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_available_false_when_no_instance():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod
    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", True):
        svc = GraphRAGService()
    assert await svc.is_available(1) is False


@pytest.mark.asyncio
async def test_is_available_false_when_lightrag_not_installed():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod
    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", False):
        svc = GraphRAGService()
    assert await svc.is_available(0) is False


# ---------------------------------------------------------------------------
# _get_instance — returns None when lightrag unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_instance_returns_none_when_unavailable():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod
    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", False):
        svc = GraphRAGService()
        instance = await svc._get_instance(1)
    assert instance is None


# ---------------------------------------------------------------------------
# ingest_note — graceful no-op when lightrag unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_note_noop_when_unavailable():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod
    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", False):
        svc = GraphRAGService()
    # Must not raise
    await svc.ingest_note("Title", "Body", user_id=1)


# ---------------------------------------------------------------------------
# query — fallback message when lightrag unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_returns_fallback_message_when_unavailable():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod
    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", False):
        svc = GraphRAGService()
    result = await svc.query("What is consciousness?", user_id=1)
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# query — single-graph fast path with mocked LightRAG
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_single_user_returns_instance_answer():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod

    fake_instance = MagicMock()
    fake_instance.aquery = AsyncMock(return_value="Deep answer here.")

    svc = GraphRAGService()
    svc._instances[1] = fake_instance

    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.QueryParam", MagicMock()):
        result = await svc.query("question", user_id=1)

    assert result == "Deep answer here."


# ---------------------------------------------------------------------------
# query — multi-vault fan-out
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_multi_vault_merges_answers():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod

    fake_inst_1 = MagicMock()
    fake_inst_1.aquery = AsyncMock(return_value="Answer from vault 1.")
    fake_inst_2 = MagicMock()
    fake_inst_2.aquery = AsyncMock(return_value="Answer from vault 2.")

    svc = GraphRAGService()
    svc._instances[1] = fake_inst_1
    svc._instances[2] = fake_inst_2

    fake_llm = MagicMock()
    fake_llm.is_available = False  # triggers concatenation fallback

    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.QueryParam", MagicMock()), \
         patch("gnosis.services.graph_rag.llm_provider", fake_llm, create=True):
        result = await svc.query("question", user_id=1, owner_ids={1, 2})

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# stream — yields strings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_yields_fallback_when_unavailable():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod
    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", False):
        svc = GraphRAGService()
    chunks = []
    async for chunk in svc.stream("question", user_id=1):
        chunks.append(chunk)
    assert all(isinstance(c, str) for c in chunks)


@pytest.mark.asyncio
async def test_stream_yields_from_instance():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod

    async def _fake_astream(*args, **kwargs):
        for token in ["token1", " token2", " token3"]:
            yield token

    fake_instance = MagicMock()
    fake_instance.astream = _fake_astream

    svc = GraphRAGService()
    svc._instances[1] = fake_instance

    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.QueryParam", MagicMock()):
        chunks = []
        async for chunk in svc.stream("question", user_id=1):
            chunks.append(chunk)

    assert len(chunks) > 0
