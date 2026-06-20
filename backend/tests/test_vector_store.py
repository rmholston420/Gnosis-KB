"""Unit tests for gnosis/services/vector_store.py.

Patches the Qdrant client so no real Qdrant instance is needed.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _qdrant_patch(module_path="gnosis.services.vector_store.get_qdrant_client"):
    """Return a context manager that patches get_qdrant_client."""
    mock_client = MagicMock()
    mock_client.upsert = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.search = AsyncMock(return_value=[])
    mock_client.query_points = AsyncMock(return_value=MagicMock(points=[]))
    return patch(module_path, return_value=mock_client), mock_client


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_collection_creates_if_missing():
    from gnosis.services.vector_store import ensure_collection
    mock_client = MagicMock()
    mock_client.collection_exists = AsyncMock(return_value=False)
    mock_client.create_collection = AsyncMock()

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        await ensure_collection()

    mock_client.create_collection.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_collection_skips_if_exists():
    from gnosis.services.vector_store import ensure_collection
    mock_client = MagicMock()
    mock_client.collection_exists = AsyncMock(return_value=True)
    mock_client.create_collection = AsyncMock()

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        await ensure_collection()

    mock_client.create_collection.assert_not_awaited()


# ---------------------------------------------------------------------------
# upsert_note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_note_calls_qdrant_upsert():
    from gnosis.services.vector_store import upsert_note

    mock_client = MagicMock()
    mock_client.upsert = AsyncMock()

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768), \
         patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.1] * 128]):
        await upsert_note(
            note_id="abc123",
            title="Test Note",
            body="Some body text.",
            metadata={"folder": "10-zettelkasten"},
        )

    mock_client.upsert.assert_awaited_once()


# ---------------------------------------------------------------------------
# delete_note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_note_calls_qdrant_delete():
    from gnosis.services.vector_store import delete_note

    mock_client = MagicMock()
    mock_client.delete = AsyncMock()

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        await delete_note("abc123")

    mock_client.delete.assert_awaited_once()


# ---------------------------------------------------------------------------
# search_notes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_notes_returns_list():
    from gnosis.services.vector_store import search_notes

    mock_point = MagicMock()
    mock_point.id = "abc"
    mock_point.score = 0.9
    mock_point.payload = {"title": "A", "folder": "10"}

    mock_client = MagicMock()
    mock_client.query_points = AsyncMock(
        return_value=MagicMock(points=[mock_point])
    )

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768), \
         patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.1] * 128]):
        results = await search_notes("test query", limit=5)

    assert isinstance(results, list)
