"""Unit tests for gnosis/services/vector_store.py.

All Qdrant calls are synchronous (no asyncio). Patches get_qdrant_client
and embed_* so no real Qdrant or fastembed is needed.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _mock_client():
    c = MagicMock()
    c.get_collection = MagicMock()
    c.create_collection = MagicMock()
    c.upsert = MagicMock()
    c.delete = MagicMock()
    c.query_points = MagicMock(return_value=MagicMock(points=[]))
    return c


# ---------------------------------------------------------------------------
# _note_id_to_uuid
# ---------------------------------------------------------------------------

def test_note_id_to_uuid_is_stable():
    from gnosis.services.vector_store import _note_id_to_uuid
    assert _note_id_to_uuid("abc") == _note_id_to_uuid("abc")


def test_note_id_to_uuid_different_ids_differ():
    from gnosis.services.vector_store import _note_id_to_uuid
    assert _note_id_to_uuid("abc") != _note_id_to_uuid("xyz")


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

def test_ensure_collection_creates_when_missing():
    from gnosis.services.vector_store import ensure_collection
    from qdrant_client.http.exceptions import UnexpectedResponse

    mock_client = _mock_client()
    mock_client.get_collection.side_effect = UnexpectedResponse(
        status_code=404, reason_phrase="Not Found",
        content=b"", headers={}
    )

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        ensure_collection()

    mock_client.create_collection.assert_called_once()


def test_ensure_collection_skips_when_exists():
    from gnosis.services.vector_store import ensure_collection

    mock_client = _mock_client()
    mock_client.get_collection.return_value = MagicMock()  # exists, no raise

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        ensure_collection()

    mock_client.create_collection.assert_not_called()


# ---------------------------------------------------------------------------
# upsert_note
# ---------------------------------------------------------------------------

def test_upsert_note_calls_client_upsert():
    from gnosis.services.vector_store import upsert_note

    mock_client = _mock_client()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768), \
         patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.1] * 128]):
        upsert_note(
            note_id="n1",
            title="Title",
            body="Body",
            folder="10-zettelkasten",
            note_type="permanent",
            status="active",
            tags=["python"],
            owner_id=1,
        )

    mock_client.upsert.assert_called_once()


def test_upsert_note_silently_skips_on_embed_error():
    from gnosis.services.vector_store import upsert_note

    mock_client = _mock_client()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.vector_store.embed_dense", side_effect=RuntimeError("no model")):
        # Should not raise
        upsert_note(
            note_id="n2", title="T", body="B",
            folder="00", note_type="fleeting", status="draft", tags=[]
        )

    mock_client.upsert.assert_not_called()


# ---------------------------------------------------------------------------
# delete_note
# ---------------------------------------------------------------------------

def test_delete_note_calls_client_delete():
    from gnosis.services.vector_store import delete_note

    mock_client = _mock_client()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        delete_note("n1")

    mock_client.delete.assert_called_once()


# ---------------------------------------------------------------------------
# hybrid_search (vector_store version — sync, no fts)
# ---------------------------------------------------------------------------

def test_vector_store_hybrid_search_returns_payloads():
    from gnosis.services.vector_store import hybrid_search

    fake_point = MagicMock()
    fake_point.payload = {"note_id": "n1", "title": "T"}

    mock_client = _mock_client()
    mock_client.query_points.return_value = MagicMock(points=[fake_point])

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768):
        results = hybrid_search("test", owner_ids={1})

    assert len(results) == 1
    assert results[0]["note_id"] == "n1"


def test_vector_store_hybrid_search_returns_empty_on_embed_error():
    from gnosis.services.vector_store import hybrid_search

    mock_client = _mock_client()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.vector_store.embed_dense", side_effect=RuntimeError("fail")):
        results = hybrid_search("test", owner_ids={1})

    assert results == []
