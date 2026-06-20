"""Tests for gnosis/services/vector_store.py.

Real public API (Qdrant-backed, synchronous):
  get_qdrant_client() -> QdrantClient
  ensure_collection() -> None
  upsert_note(note_id, title, body, folder, note_type, status, tags, owner_id=None) -> None
  delete_note(note_id) -> None
  delete_note_vector -> alias for delete_note
  hybrid_search(query, owner_ids=None, top_k=5, include_legacy=True) -> list[dict]
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# upsert_note  (note_id, title, body, folder, note_type, status, tags, owner_id)
# ---------------------------------------------------------------------------

def test_upsert_note_calls_client_upsert():
    from gnosis.services.vector_store import upsert_note

    mock_client = MagicMock()
    mock_dense = MagicMock()
    mock_dense.embed.return_value = [[0.1] * 768]
    mock_colbert = MagicMock()
    mock_colbert.embed.return_value = [[[0.1] * 128]]

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=mock_dense), \
         patch("gnosis.services.embeddings.get_colbert_model", return_value=mock_colbert):
        upsert_note(
            note_id="n1",
            title="Test Note",
            body="Some body text.",
            folder="10-zettelkasten",
            note_type="permanent",
            status="active",
            tags=["python"],
            owner_id=1,
        )

    assert mock_client.upsert.called


def test_upsert_note_does_not_raise_on_valid_input():
    from gnosis.services.vector_store import upsert_note

    mock_client = MagicMock()
    mock_dense = MagicMock()
    mock_dense.embed.return_value = [[0.1] * 768]
    mock_colbert = MagicMock()
    mock_colbert.embed.return_value = [[[0.1] * 128]]

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=mock_dense), \
         patch("gnosis.services.embeddings.get_colbert_model", return_value=mock_colbert):
        upsert_note(
            note_id="note-abc",
            title="Another Note",
            body="Body content here.",
            folder="00-inbox",
            note_type="fleeting",
            status="draft",
            tags=[],
        )
    # no exception = pass


# ---------------------------------------------------------------------------
# delete_note
# ---------------------------------------------------------------------------

def test_delete_note_calls_client_delete():
    from gnosis.services.vector_store import delete_note

    mock_client = MagicMock()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        delete_note("n1")

    assert mock_client.delete.called


def test_delete_note_alias_works():
    """delete_note_vector is a backward-compat alias."""
    from gnosis.services.vector_store import delete_note, delete_note_vector
    assert delete_note_vector is delete_note


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

def test_ensure_collection_returns_early_if_exists():
    from gnosis.services.vector_store import ensure_collection

    mock_client = MagicMock()
    mock_client.get_collection.return_value = MagicMock()  # succeeds -> exists

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        ensure_collection()

    assert not mock_client.create_collection.called


def test_ensure_collection_creates_if_missing():
    from gnosis.services.vector_store import ensure_collection

    mock_client = MagicMock()
    mock_client.get_collection.side_effect = Exception("not found")

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        ensure_collection()

    assert mock_client.create_collection.called


# ---------------------------------------------------------------------------
# hybrid_search -> list[dict]
# ---------------------------------------------------------------------------

def test_vector_store_hybrid_search_returns_list_on_success():
    from gnosis.services.vector_store import hybrid_search

    mock_point = MagicMock()
    mock_point.payload = {"note_id": "n1", "title": "Test"}
    mock_result = MagicMock()
    mock_result.points = [mock_point]

    mock_client = MagicMock()
    mock_client.query_points.return_value = mock_result

    mock_dense = MagicMock()
    mock_dense.embed.return_value = [[0.1] * 768]

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=mock_dense):
        result = hybrid_search("python notes", owner_ids={1})

    assert isinstance(result, list)


def test_vector_store_hybrid_search_returns_empty_on_qdrant_error():
    from gnosis.services.vector_store import hybrid_search

    mock_client = MagicMock()
    mock_client.query_points.side_effect = Exception("Qdrant down")

    mock_dense = MagicMock()
    mock_dense.embed.return_value = [[0.1] * 768]

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=mock_dense):
        result = hybrid_search("query", owner_ids={1})

    assert result == []


def test_vector_store_hybrid_search_no_owner_filter():
    """owner_ids=None means no filter — should not raise."""
    from gnosis.services.vector_store import hybrid_search

    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.points = []
    mock_client.query_points.return_value = mock_result

    mock_dense = MagicMock()
    mock_dense.embed.return_value = [[0.1] * 768]

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=mock_dense):
        result = hybrid_search("query")  # owner_ids defaults to None

    assert isinstance(result, list)
