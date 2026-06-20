"""Tests for gnosis.services.vector_store.

All Qdrant I/O and embedding calls are mocked.
No Qdrant server or fastembed model downloads required.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

import gnosis.services.vector_store as vs_module
from gnosis.services.vector_store import (
    _note_id_to_uuid,
    delete_note,
    delete_note_vector,
    ensure_collection,
    get_qdrant_client,
    hybrid_search,
    upsert_note,
)


def _reset_client():
    vs_module._client = None


# ---------------------------------------------------------------------------
# _note_id_to_uuid()
# ---------------------------------------------------------------------------

def test_uuid_is_deterministic():
    assert _note_id_to_uuid("note-abc") == _note_id_to_uuid("note-abc")


def test_uuid_differs_for_different_ids():
    assert _note_id_to_uuid("note-1") != _note_id_to_uuid("note-2")


def test_uuid_is_valid_uuid_format():
    result = _note_id_to_uuid("any-id")
    parsed = uuid.UUID(result)
    assert str(parsed) == result


# ---------------------------------------------------------------------------
# get_qdrant_client()
# ---------------------------------------------------------------------------

def test_get_qdrant_client_singleton():
    _reset_client()
    mock_c = MagicMock()
    with patch("gnosis.services.vector_store.QdrantClient", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_url = "http://localhost:6333"
            s.return_value.qdrant_api_key = None
            c1 = get_qdrant_client()
            c2 = get_qdrant_client()
    assert c1 is c2


def test_get_qdrant_client_uses_settings_url():
    _reset_client()
    with patch("gnosis.services.vector_store.QdrantClient") as cls:
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_url = "http://qdrant:6333"
            s.return_value.qdrant_api_key = "tok"
            get_qdrant_client()
    cls.assert_called_once_with(url="http://qdrant:6333", api_key="tok")


# ---------------------------------------------------------------------------
# ensure_collection()
# ---------------------------------------------------------------------------

def test_ensure_collection_skips_create_when_exists():
    mock_c = MagicMock()
    mock_c.get_collection.return_value = MagicMock()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            ensure_collection()
    mock_c.create_collection.assert_not_called()


def test_ensure_collection_creates_when_missing():
    mock_c = MagicMock()
    mock_c.get_collection.side_effect = Exception("not found")
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            ensure_collection()
    mock_c.create_collection.assert_called_once()
    kw = mock_c.create_collection.call_args.kwargs
    assert kw["collection_name"] == "gnosis_notes"
    assert "dense" in kw["vectors_config"]
    assert "colbert" in kw["vectors_config"]
    assert "sparse" in kw["sparse_vectors_config"]


# ---------------------------------------------------------------------------
# upsert_note()
# ---------------------------------------------------------------------------

def test_upsert_note_calls_upsert():
    mock_c = MagicMock()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            with patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768):
                with patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.1] * 128]):
                    upsert_note(
                        note_id="2024-01-01-test",
                        title="T", body="B",
                        folder="10-zettelkasten",
                        note_type="permanent",
                        status="active",
                        tags=["a", "b"],
                        owner_id=7,
                    )
    mock_c.upsert.assert_called_once()
    point = mock_c.upsert.call_args.kwargs["points"][0]
    assert point.payload["note_id"] == "2024-01-01-test"
    assert point.payload["owner_id"] == 7
    assert point.payload["tags"] == ["a", "b"]


def test_upsert_note_none_owner_uses_sentinel():
    mock_c = MagicMock()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            with patch("gnosis.services.vector_store.embed_dense", return_value=[0.0] * 768):
                with patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.0] * 128]):
                    upsert_note("n", "T", "B", "00-inbox", "fleeting", "draft", [], owner_id=None)
    point = mock_c.upsert.call_args.kwargs["points"][0]
    assert point.payload["owner_id"] == 0


def test_upsert_note_skips_on_embed_error():
    mock_c = MagicMock()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            with patch("gnosis.services.vector_store.embed_dense", side_effect=RuntimeError("no model")):
                upsert_note("n", "T", "B", "00-inbox", "fleeting", "draft", [])
    mock_c.upsert.assert_not_called()


def test_upsert_note_stable_uuid():
    mock_c = MagicMock()
    ids = []
    for _ in range(2):
        with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
            with patch("gnosis.services.vector_store.get_settings") as s:
                s.return_value.qdrant_collection_name = "gnosis_notes"
                with patch("gnosis.services.vector_store.embed_dense", return_value=[0.0] * 768):
                    with patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.0] * 128]):
                        upsert_note("stable", "T", "B", "00-inbox", "fleeting", "draft", [])
        ids.append(mock_c.upsert.call_args.kwargs["points"][0].id)
    assert ids[0] == ids[1]


# ---------------------------------------------------------------------------
# delete_note() / delete_note_vector alias
# ---------------------------------------------------------------------------

def test_delete_note_calls_client_delete():
    mock_c = MagicMock()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            delete_note("2024-01-01-test")
    mock_c.delete.assert_called_once()
    assert mock_c.delete.call_args.kwargs["collection_name"] == "gnosis_notes"


def test_delete_note_uses_deterministic_uuid():
    mock_c = MagicMock()
    note_id = "2024-06-01-note"
    expected = _note_id_to_uuid(note_id)
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            delete_note(note_id)
    selector = mock_c.delete.call_args.kwargs["points_selector"]
    assert expected in selector.points


def test_delete_note_vector_is_alias():
    assert delete_note_vector is delete_note


# ---------------------------------------------------------------------------
# hybrid_search()
# ---------------------------------------------------------------------------

def test_hybrid_search_returns_payloads():
    mock_c = MagicMock()
    p1, p2 = MagicMock(), MagicMock()
    p1.payload = {"note_id": "n1"}
    p2.payload = {"note_id": "n2"}
    mock_c.query_points.return_value.points = [p1, p2]
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            with patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768):
                results = hybrid_search("query")
    assert [r["note_id"] for r in results] == ["n1", "n2"]


def test_hybrid_search_empty_on_embed_failure():
    with patch("gnosis.services.vector_store.embed_dense", side_effect=RuntimeError("no")):
        assert hybrid_search("q") == []


def test_hybrid_search_empty_on_qdrant_failure():
    mock_c = MagicMock()
    mock_c.query_points.side_effect = Exception("down")
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            with patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768):
                assert hybrid_search("q") == []


def test_hybrid_search_owner_filter_includes_sentinel():
    mock_c = MagicMock()
    mock_c.query_points.return_value.points = []
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            with patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768):
                hybrid_search("q", owner_ids={1, 2}, include_legacy=True)
    prefetch = mock_c.query_points.call_args.kwargs["prefetch"][0]
    allowed = prefetch.filter.should[0].match.any
    assert 0 in allowed
    assert 1 in allowed


def test_hybrid_search_no_filter_when_owner_ids_none():
    mock_c = MagicMock()
    mock_c.query_points.return_value.points = []
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            with patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768):
                hybrid_search("q", owner_ids=None)
    prefetch = mock_c.query_points.call_args.kwargs["prefetch"][0]
    assert prefetch.filter is None


def test_hybrid_search_skips_none_payloads():
    mock_c = MagicMock()
    good, null = MagicMock(), MagicMock()
    good.payload = {"note_id": "ok"}
    null.payload = None
    mock_c.query_points.return_value.points = [good, null]
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_c):
        with patch("gnosis.services.vector_store.get_settings") as s:
            s.return_value.qdrant_collection_name = "gnosis_notes"
            with patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768):
                results = hybrid_search("q")
    assert len(results) == 1
    assert results[0]["note_id"] == "ok"
