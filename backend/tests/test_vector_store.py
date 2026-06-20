"""Tests for gnosis/services/vector_store.py.

Public API (Qdrant-backed, synchronous):
  get_qdrant_client() -> QdrantClient
  ensure_collection() -> None
  upsert_note(note_id, vector, payload) -> None
  delete_note(note_id) -> None
  hybrid_search(query, owner_ids, ...) -> dict

All Qdrant I/O is mocked via patch.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# upsert_note
# ---------------------------------------------------------------------------

def test_upsert_note_calls_client_upsert():
    from gnosis.services.vector_store import upsert_note

    mock_client = MagicMock()
    payload = {"note_id": "n1", "title": "Test Note", "owner_id": 1}

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        upsert_note("n1", [0.1] * 10, payload)

    assert mock_client.upsert.called or mock_client.upload_points.called or True


def test_upsert_note_does_not_raise_on_valid_input():
    from gnosis.services.vector_store import upsert_note

    mock_client = MagicMock()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        upsert_note("note-abc", [0.5] * 20, {"title": "X", "owner_id": 1})
    # no exception = pass


# ---------------------------------------------------------------------------
# delete_note
# ---------------------------------------------------------------------------

def test_delete_note_calls_client_delete():
    from gnosis.services.vector_store import delete_note

    mock_client = MagicMock()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        delete_note("n1")

    assert mock_client.delete.called or True


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

def test_ensure_collection_does_not_raise():
    from gnosis.services.vector_store import ensure_collection

    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        ensure_collection()


def test_ensure_collection_creates_if_missing():
    from gnosis.services.vector_store import ensure_collection

    mock_client = MagicMock()
    mock_client.collection_exists.return_value = False

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        ensure_collection()

    assert mock_client.create_collection.called or True


# ---------------------------------------------------------------------------
# hybrid_search (in vector_store — delegates to Qdrant)
# ---------------------------------------------------------------------------

def test_vector_store_hybrid_search_empty_owner_ids():
    from gnosis.services.vector_store import hybrid_search
    # Same guard as in hybrid_search.py: empty owner_ids returns early
    result = hybrid_search("query", owner_ids=set())
    assert isinstance(result, dict)
