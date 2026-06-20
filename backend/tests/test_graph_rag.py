"""Tests for gnosis/services/graph_rag.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest


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
# _get_instance
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
# ingest_note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_note_noop_when_unavailable():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod
    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", False):
        svc = GraphRAGService()
    await svc.ingest_note("Title", "Body", user_id=1)


@pytest.mark.asyncio
async def test_ingest_note_calls_ainsert_when_available():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod

    fake_instance = MagicMock()
    fake_instance.ainsert = AsyncMock()

    svc = GraphRAGService()
    svc._instances[1] = fake_instance

    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", True):
        await svc.ingest_note("Title", "Body", user_id=1)

    fake_instance.ainsert.assert_called_once()


# ---------------------------------------------------------------------------
# query — fallback when unavailable
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
# query — single-graph fast path
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
    fake_llm.is_available = False

    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.QueryParam", MagicMock()), \
         patch("gnosis.services.graph_rag.llm_provider", fake_llm, create=True):
        result = await svc.query("question", user_id=1, owner_ids={1, 2})

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# stream — fallback when unavailable (yields exactly one string)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_yields_fallback_when_unavailable():
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod
    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", False):
        svc = GraphRAGService()
    chunks = [chunk async for chunk in svc.stream("question", user_id=1)]
    assert len(chunks) >= 1
    assert all(isinstance(c, str) for c in chunks)


# ---------------------------------------------------------------------------
# stream — with mocked instance
#
# The source checks for `astream_query`; if absent it falls back to aquery.
# We give the mock an aquery method so the fallback path runs.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_yields_from_instance_via_aquery_fallback():
    """When instance has no astream_query, stream() falls back to aquery."""
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod

    fake_instance = MagicMock(spec=["aquery"])  # spec excludes astream_query
    fake_instance.aquery = AsyncMock(return_value="streamed token")

    svc = GraphRAGService()
    svc._instances[1] = fake_instance

    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.QueryParam", MagicMock()):
        chunks = [chunk async for chunk in svc.stream("question", user_id=1)]

    assert len(chunks) >= 1
    assert "streamed token" in chunks


@pytest.mark.asyncio
async def test_stream_yields_from_astream_query():
    """When instance has astream_query, stream() should iterate it."""
    from gnosis.services.graph_rag import GraphRAGService
    import gnosis.services.graph_rag as gr_mod

    async def _fake_astream_query(*args, **kwargs):
        for token in ["tok1", " tok2", " tok3"]:
            yield token

    fake_instance = MagicMock()
    fake_instance.astream_query = _fake_astream_query

    svc = GraphRAGService()
    svc._instances[1] = fake_instance

    with patch.object(gr_mod, "_LIGHTRAG_AVAILABLE", True), \
         patch("gnosis.services.graph_rag.QueryParam", MagicMock()):
        chunks = [chunk async for chunk in svc.stream("question", user_id=1)]

    assert chunks == ["tok1", " tok2", " tok3"]
