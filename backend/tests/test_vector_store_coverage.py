"""Gap-filling tests for gnosis/services/vector_store.py.

Covers:
- _note_id_to_uuid: deterministic, stable UUID derivation
- get_qdrant_client: lazy-init and cached return
- ensure_collection: collection already exists path + create path
- hybrid_search: embed_dense failure, Qdrant failure, owner filter
- upsert_note: embed failure path
- delete_note / delete_note_vector alias
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import gnosis.services.vector_store as vs_mod
from gnosis.services.vector_store import (
    _note_id_to_uuid,
    delete_note,
    delete_note_vector,
    ensure_collection,
    get_qdrant_client,
    hybrid_search,
    upsert_note,
)


@pytest.fixture(autouse=True)
def reset_client():
    original = vs_mod._client
    vs_mod._client = None
    yield
    vs_mod._client = original


# ---------------------------------------------------------------------------
# _note_id_to_uuid
# ---------------------------------------------------------------------------

def test_note_id_to_uuid_is_deterministic():
    assert _note_id_to_uuid("abc") == _note_id_to_uuid("abc")


def test_note_id_to_uuid_differs_for_different_ids():
    assert _note_id_to_uuid("abc") != _note_id_to_uuid("xyz")


def test_note_id_to_uuid_is_string():
    result = _note_id_to_uuid("test-note")
    assert isinstance(result, str)
    assert len(result) == 36  # UUID format


# ---------------------------------------------------------------------------
# get_qdrant_client
# ---------------------------------------------------------------------------

def test_get_qdrant_client_lazy_init():
    mock_instance = MagicMock()
    mock_qdrant_cls = MagicMock(return_value=mock_instance)
    mock_settings = MagicMock(qdrant_url="http://localhost:6333", qdrant_api_key=None)

    with (
        patch("gnosis.services.vector_store.QdrantClient", mock_qdrant_cls),
        patch("gnosis.services.vector_store.get_settings", return_value=mock_settings),
    ):
        client = get_qdrant_client()

    assert client is mock_instance


def test_get_qdrant_client_cached():
    sentinel = MagicMock()
    vs_mod._client = sentinel
    assert get_qdrant_client() is sentinel


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

def test_ensure_collection_skips_if_exists():
    mock_client = MagicMock()
    mock_client.get_collection.return_value = MagicMock()  # no exception = exists
    mock_settings = MagicMock(qdrant_collection_name="gnosis_notes")

    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.get_settings", return_value=mock_settings),
    ):
        ensure_collection()

    mock_client.create_collection.assert_not_called()


def test_ensure_collection_creates_when_not_exists():
    mock_client = MagicMock()
    mock_client.get_collection.side_effect = Exception("not found")
    mock_settings = MagicMock(qdrant_collection_name="gnosis_notes")

    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.get_settings", return_value=mock_settings),
    ):
        ensure_collection()

    mock_client.create_collection.assert_called_once()


# ---------------------------------------------------------------------------
# hybrid_search (vector_store module, not the services one)
# ---------------------------------------------------------------------------

def test_vs_hybrid_search_embed_failure_returns_empty():
    mock_settings = MagicMock(qdrant_collection_name="gnosis_notes")
    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=MagicMock()),
        patch("gnosis.services.vector_store.get_settings", return_value=mock_settings),
        patch("gnosis.services.vector_store.embed_dense", side_effect=RuntimeError("no model")),
    ):
        result = hybrid_search("query", owner_ids={1})
    assert result == []


def test_vs_hybrid_search_qdrant_failure_returns_empty():
    mock_client = MagicMock()
    mock_client.query_points.side_effect = Exception("Qdrant error")
    mock_settings = MagicMock(qdrant_collection_name="gnosis_notes")
    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.get_settings", return_value=mock_settings),
        patch("gnosis.services.vector_store.embed_dense", return_value=[0.0] * 768),
    ):
        result = hybrid_search("query", owner_ids={1})
    assert result == []


def test_vs_hybrid_search_with_owner_filter():
    mock_client = MagicMock()
    result_mock = MagicMock()
    result_mock.points = []
    mock_client.query_points.return_value = result_mock
    mock_settings = MagicMock(qdrant_collection_name="gnosis_notes")
    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.get_settings", return_value=mock_settings),
        patch("gnosis.services.vector_store.embed_dense", return_value=[0.0] * 768),
    ):
        result = hybrid_search("query", owner_ids={42})
    assert result == []


def test_vs_hybrid_search_no_owner_filter():
    mock_client = MagicMock()
    result_mock = MagicMock()
    result_mock.points = []
    mock_client.query_points.return_value = result_mock
    mock_settings = MagicMock(qdrant_collection_name="gnosis_notes")
    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.get_settings", return_value=mock_settings),
        patch("gnosis.services.vector_store.embed_dense", return_value=[0.0] * 768),
    ):
        result = hybrid_search("query", owner_ids=None)
    assert result == []


# ---------------------------------------------------------------------------
# upsert_note
# ---------------------------------------------------------------------------

def test_upsert_note_embed_failure_returns_early():
    mock_client = MagicMock()
    mock_settings = MagicMock(qdrant_collection_name="gnosis_notes")
    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.get_settings", return_value=mock_settings),
        patch("gnosis.services.vector_store.embed_dense", side_effect=RuntimeError("no GPU")),
    ):
        upsert_note("n1", "T", "B", "folder", "type", "draft", [])

    mock_client.upsert.assert_not_called()


def test_upsert_note_success():
    mock_client = MagicMock()
    mock_settings = MagicMock(qdrant_collection_name="gnosis_notes")
    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.get_settings", return_value=mock_settings),
        patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768),
        patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.1] * 128]),
    ):
        upsert_note("n2", "Title", "Body", "00-inbox", "permanent", "draft", ["tag"], owner_id=7)

    mock_client.upsert.assert_called_once()


# ---------------------------------------------------------------------------
# delete_note / delete_note_vector alias
# ---------------------------------------------------------------------------

def test_delete_note_calls_qdrant_delete():
    mock_client = MagicMock()
    mock_settings = MagicMock(qdrant_collection_name="gnosis_notes")
    with (
        patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
        patch("gnosis.services.vector_store.get_settings", return_value=mock_settings),
    ):
        delete_note("n3")

    mock_client.delete.assert_called_once()


def test_delete_note_vector_is_alias():
    assert delete_note_vector is delete_note
