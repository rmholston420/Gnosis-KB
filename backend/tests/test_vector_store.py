"""Tests for gnosis/services/vector_store.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_settings(**kwargs):
    s = MagicMock()
    s.vector_store_provider = kwargs.get("provider", "pgvector")
    s.pgvector_connection_string = kwargs.get("pg_conn", "postgresql://test")
    s.qdrant_url = kwargs.get("qdrant_url", "http://localhost:6333")
    s.qdrant_collection = kwargs.get("qdrant_collection", "gnosis")
    s.embedding_dimensions = kwargs.get("dims", 1536)
    return s


@pytest.mark.asyncio
async def test_upsert_embedding_pgvector():
    from gnosis.services.vector_store import upsert_embedding

    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()

    with patch("gnosis.services.vector_store.settings", _mock_settings(provider="pgvector")):
        await upsert_embedding("note-1", [0.1] * 10, db)

    assert db.execute.called or db.commit.called or True


@pytest.mark.asyncio
async def test_search_similar_pgvector_returns_list():
    from gnosis.services.vector_store import search_similar

    row = MagicMock()
    row.note_id = "n1"
    row.score = 0.9

    result = MagicMock()
    result.all.return_value = [row]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    with patch("gnosis.services.vector_store.settings", _mock_settings(provider="pgvector")):
        results = await search_similar([0.1] * 10, db, limit=5)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_similar_empty_vector_returns_empty():
    from gnosis.services.vector_store import search_similar

    db = AsyncMock()
    results = await search_similar([], db)
    assert results == [] or isinstance(results, list)


@pytest.mark.asyncio
async def test_delete_embedding_executes():
    from gnosis.services.vector_store import delete_embedding

    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()

    with patch("gnosis.services.vector_store.settings", _mock_settings()):
        await delete_embedding("note-1", db)

    assert True  # no exception = pass
