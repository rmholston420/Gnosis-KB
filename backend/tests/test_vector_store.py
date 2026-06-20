"""Unit tests for gnosis/services/vector_store.py.

Covers: _note_id_to_uuid (determinism), get_qdrant_client (singleton),
ensure_collection (exists + creates), hybrid_search (happy + embed fail
+ qdrant fail + owner filter), upsert_note (happy + embed fail),
delete_note.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _note_id_to_uuid
# ---------------------------------------------------------------------------

def test_note_id_to_uuid_is_deterministic():
    from gnosis.services.vector_store import _note_id_to_uuid
    assert _note_id_to_uuid("abc") == _note_id_to_uuid("abc")
    assert _note_id_to_uuid("abc") != _note_id_to_uuid("xyz")


# ---------------------------------------------------------------------------
# get_qdrant_client — singleton behaviour
# ---------------------------------------------------------------------------

def test_get_qdrant_client_returns_same_instance():
    import gnosis.services.vector_store as vs
    mock_client = MagicMock()
    vs._client = mock_client
    assert vs.get_qdrant_client() is mock_client
    vs._client = None  # reset


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

def test_ensure_collection_skips_creation_when_exists():
    from gnosis.services.vector_store import ensure_collection

    mock_client = MagicMock()
    mock_client.get_collection.return_value = MagicMock()  # exists

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        ensure_collection()

    mock_client.create_collection.assert_not_called()


def test_ensure_collection_creates_when_missing():
    from gnosis.services.vector_store import ensure_collection

    mock_client = MagicMock()
    mock_client.get_collection.side_effect = Exception("not found")

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        ensure_collection()

    mock_client.create_collection.assert_called_once()


# ---------------------------------------------------------------------------
# hybrid_search
# ---------------------------------------------------------------------------

def test_hybrid_search_returns_payloads():
    from gnosis.services.vector_store import hybrid_search

    point = MagicMock()
    point.payload = {"note_id": "n1", "title": "My Note"}
    result_mock = MagicMock()
    result_mock.points = [point]
    mock_client = MagicMock()
    mock_client.query_points.return_value = result_mock

    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768),
    ):
        hits = hybrid_search("zettelkasten", owner_ids={1})

    assert len(hits) == 1
    assert hits[0]["note_id"] == "n1"


def test_hybrid_search_returns_empty_on_embed_failure():
    from gnosis.services.vector_store import hybrid_search

    with patch("gnosis.services.vector_store.embed_dense", side_effect=Exception("no model")):
        hits = hybrid_search("query")

    assert hits == []


def test_hybrid_search_returns_empty_on_qdrant_failure():
    from gnosis.services.vector_store import hybrid_search

    mock_client = MagicMock()
    mock_client.query_points.side_effect = Exception("qdrant down")

    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.embed_dense", return_value=[0.0] * 768),
    ):
        hits = hybrid_search("query", owner_ids={1})

    assert hits == []


def test_hybrid_search_no_owner_filter():
    from gnosis.services.vector_store import hybrid_search

    result_mock = MagicMock()
    result_mock.points = []
    mock_client = MagicMock()
    mock_client.query_points.return_value = result_mock

    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.embed_dense", return_value=[0.0] * 768),
    ):
        hits = hybrid_search("query", owner_ids=None)

    # filter_condition should be None — verify query_points was called
    mock_client.query_points.assert_called_once()
    assert hits == []


# ---------------------------------------------------------------------------
# upsert_note
# ---------------------------------------------------------------------------

def test_upsert_note_calls_qdrant_upsert():
    from gnosis.services.vector_store import upsert_note

    mock_client = MagicMock()

    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768),
        patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.1] * 128]),
    ):
        upsert_note(
            note_id="n1", title="Test", body="Body text",
            folder="00-inbox", note_type="fleeting",
            status="active", tags=["test"], owner_id=1,
        )

    mock_client.upsert.assert_called_once()


def test_upsert_note_skips_on_embed_failure():
    from gnosis.services.vector_store import upsert_note

    mock_client = MagicMock()

    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.embed_dense", side_effect=Exception("no model")),
    ):
        upsert_note(
            note_id="n2", title="Bad", body="...",
            folder="00-inbox", note_type="fleeting",
            status="active", tags=[], owner_id=1,
        )

    mock_client.upsert.assert_not_called()


def test_upsert_note_uses_legacy_sentinel_when_owner_none():
    from gnosis.services.vector_store import upsert_note, _LEGACY_OWNER_SENTINEL

    mock_client = MagicMock()
    captured = {}

    def _capture_upsert(**kwargs):
        captured["point"] = kwargs["points"][0]

    mock_client.upsert.side_effect = _capture_upsert

    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.embed_dense", return_value=[0.0] * 768),
        patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.0] * 128]),
    ):
        upsert_note(
            note_id="n3", title="Legacy", body="...",
            folder="00-inbox", note_type="fleeting",
            status="active", tags=[], owner_id=None,
        )

    assert captured["point"].payload["owner_id"] == _LEGACY_OWNER_SENTINEL


# ---------------------------------------------------------------------------
# delete_note / delete_note_vector alias
# ---------------------------------------------------------------------------

def test_delete_note_calls_qdrant_delete():
    from gnosis.services.vector_store import delete_note

    mock_client = MagicMock()

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client):
        delete_note("n1")

    mock_client.delete.assert_called_once()


def test_delete_note_vector_is_alias():
    from gnosis.services.vector_store import delete_note, delete_note_vector
    assert delete_note is delete_note_vector
