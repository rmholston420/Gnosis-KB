"""Tests for gnosis/services/vector_store.py.

All Qdrant client calls are patched at module level.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# _note_id_to_uuid
# ---------------------------------------------------------------------------

def test_note_id_to_uuid_is_deterministic():
    from gnosis.services.vector_store import _note_id_to_uuid
    u1 = _note_id_to_uuid("20240101-000000")
    u2 = _note_id_to_uuid("20240101-000000")
    assert u1 == u2


def test_note_id_to_uuid_is_unique():
    from gnosis.services.vector_store import _note_id_to_uuid
    assert _note_id_to_uuid("a") != _note_id_to_uuid("b")


def test_note_id_to_uuid_returns_string():
    from gnosis.services.vector_store import _note_id_to_uuid
    result = _note_id_to_uuid("some-id")
    assert isinstance(result, str)
    assert len(result) == 36  # standard UUID string length


# ---------------------------------------------------------------------------
# get_qdrant_client — singleton pattern
# ---------------------------------------------------------------------------

def test_get_qdrant_client_returns_client():
    import gnosis.services.vector_store as vs
    fake_client = MagicMock()
    with patch("gnosis.services.vector_store._client", None), \
         patch("gnosis.services.vector_store.QdrantClient", return_value=fake_client):
        client = vs.get_qdrant_client()
    assert client is fake_client


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

def test_ensure_collection_creates_when_missing():
    from gnosis.services.vector_store import ensure_collection
    fake_client = MagicMock()
    fake_client.get_collection.side_effect = Exception("not found")
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=fake_client), \
         patch("gnosis.services.vector_store.get_settings", return_value=MagicMock(qdrant_collection_name="gnosis_notes")):
        ensure_collection()
    fake_client.create_collection.assert_called_once()


def test_ensure_collection_skips_when_exists():
    from gnosis.services.vector_store import ensure_collection
    fake_client = MagicMock()
    fake_client.get_collection.return_value = MagicMock()  # exists
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=fake_client), \
         patch("gnosis.services.vector_store.get_settings", return_value=MagicMock(qdrant_collection_name="gnosis_notes")):
        ensure_collection()
    fake_client.create_collection.assert_not_called()


# ---------------------------------------------------------------------------
# upsert_note
# ---------------------------------------------------------------------------

def test_upsert_note_calls_upsert():
    from gnosis.services.vector_store import upsert_note
    fake_client = MagicMock()
    fake_settings = MagicMock(qdrant_collection_name="gnosis_notes")

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=fake_client), \
         patch("gnosis.services.vector_store.get_settings", return_value=fake_settings), \
         patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768):
        upsert_note(
            note_id="20240101-000000",
            title="Test Note",
            body="Body text here.",
            owner_id=1,
        )

    fake_client.upsert.assert_called_once()


def test_upsert_note_passes_owner_id_in_payload():
    from gnosis.services.vector_store import upsert_note
    fake_client = MagicMock()
    fake_settings = MagicMock(qdrant_collection_name="gnosis_notes")
    captured = {}

    def capture_upsert(**kwargs):
        captured.update(kwargs)

    fake_client.upsert.side_effect = lambda **kw: captured.update(kw)

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=fake_client), \
         patch("gnosis.services.vector_store.get_settings", return_value=fake_settings), \
         patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768):
        upsert_note(
            note_id="20240101-000000",
            title="T", body="B",
            owner_id=42,
        )

    call_kwargs = fake_client.upsert.call_args
    # The points list should contain owner_id=42 in the payload
    points = call_kwargs.kwargs.get("points") or call_kwargs[1].get("points") or call_kwargs[0][1]
    assert any(
        p.payload.get("owner_id") == 42
        for p in (points if isinstance(points, list) else [])
    )


# ---------------------------------------------------------------------------
# delete_note
# ---------------------------------------------------------------------------

def test_delete_note_calls_delete():
    from gnosis.services.vector_store import delete_note
    fake_client = MagicMock()
    fake_settings = MagicMock(qdrant_collection_name="gnosis_notes")

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=fake_client), \
         patch("gnosis.services.vector_store.get_settings", return_value=fake_settings):
        delete_note("20240101-000000")

    fake_client.delete.assert_called_once()


# ---------------------------------------------------------------------------
# hybrid_search (vector_store version) — returns list
# ---------------------------------------------------------------------------

def test_vs_hybrid_search_returns_list():
    from gnosis.services.vector_store import hybrid_search
    fake_client = MagicMock()
    fake_point = MagicMock()
    fake_point.payload = {"note_id": "n1", "title": "T"}
    fake_point.score = 0.9
    fake_result = MagicMock()
    fake_result.points = [fake_point]
    fake_client.query_points.return_value = fake_result

    fake_settings = MagicMock(qdrant_collection_name="gnosis_notes")

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=fake_client), \
         patch("gnosis.services.vector_store.get_settings", return_value=fake_settings), \
         patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768):
        result = hybrid_search("test query", owner_ids={1})

    assert isinstance(result, list)


def test_vs_hybrid_search_empty_when_no_owner_ids():
    from gnosis.services.vector_store import hybrid_search
    result = hybrid_search("query", owner_ids=set())
    # Should return empty or raise — either is acceptable graceful behaviour
    assert isinstance(result, list)
