"""Tests for gnosis/services/vector_store.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# _note_id_to_uuid
# ---------------------------------------------------------------------------

def test_note_id_to_uuid_is_deterministic():
    from gnosis.services.vector_store import _note_id_to_uuid
    assert _note_id_to_uuid("20240101-000000") == _note_id_to_uuid("20240101-000000")


def test_note_id_to_uuid_is_unique():
    from gnosis.services.vector_store import _note_id_to_uuid
    assert _note_id_to_uuid("a") != _note_id_to_uuid("b")


def test_note_id_to_uuid_returns_string():
    from gnosis.services.vector_store import _note_id_to_uuid
    result = _note_id_to_uuid("some-id")
    assert isinstance(result, str)
    assert len(result) == 36


# ---------------------------------------------------------------------------
# get_qdrant_client — singleton
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
         patch("gnosis.services.vector_store.get_settings",
               return_value=MagicMock(qdrant_collection_name="gnosis_notes")):
        ensure_collection()
    fake_client.create_collection.assert_called_once()


def test_ensure_collection_skips_when_exists():
    from gnosis.services.vector_store import ensure_collection
    fake_client = MagicMock()
    fake_client.get_collection.return_value = MagicMock()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=fake_client), \
         patch("gnosis.services.vector_store.get_settings",
               return_value=MagicMock(qdrant_collection_name="gnosis_notes")):
        ensure_collection()
    fake_client.create_collection.assert_not_called()


# ---------------------------------------------------------------------------
# upsert_note
# Real signature:
#   upsert_note(note_id, title, body, folder, note_type, status, tags, owner_id=None)
# Also calls embed_colbert — must patch that too.
# ---------------------------------------------------------------------------

def _upsert_patches():
    from contextlib import ExitStack
    stack = ExitStack()
    fake_client = MagicMock()
    fake_settings = MagicMock(qdrant_collection_name="gnosis_notes")
    stack.enter_context(patch("gnosis.services.vector_store.get_qdrant_client", return_value=fake_client))
    stack.enter_context(patch("gnosis.services.vector_store.get_settings", return_value=fake_settings))
    stack.enter_context(patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768))
    stack.enter_context(patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.1] * 128]))
    return stack, fake_client


def _extract_upsert_points(fake_client):
    """Robustly extract the 'points' list from a mock upsert() call.

    client.upsert(collection_name=..., points=[...]) is called with keyword
    args in the source, so call_args.kwargs is always the right place to look.
    Positional fallback handles any future refactor.
    """
    call = fake_client.upsert.call_args
    if call is None:
        return []
    if "points" in call.kwargs:
        return call.kwargs["points"]
    # positional: upsert(collection_name, points)
    if len(call.args) >= 2:
        return call.args[1]
    return []


def test_upsert_note_calls_upsert():
    from gnosis.services.vector_store import upsert_note
    stack, fake_client = _upsert_patches()
    with stack:
        upsert_note(
            note_id="20240101-000000",
            title="Test Note",
            body="Body text here.",
            folder="10-zettel",
            note_type="permanent",
            status="published",
            tags=["eeg"],
            owner_id=1,
        )
    fake_client.upsert.assert_called_once()


def test_upsert_note_passes_owner_id_in_payload():
    from gnosis.services.vector_store import upsert_note
    stack, fake_client = _upsert_patches()
    with stack:
        upsert_note(
            note_id="20240101-000000",
            title="T", body="B",
            folder="00-inbox",
            note_type="permanent",
            status="draft",
            tags=[],
            owner_id=42,
        )
    points = _extract_upsert_points(fake_client)
    assert points, "upsert() was not called or 'points' kwarg was missing"
    assert points[0].payload.get("owner_id") == 42


def test_upsert_note_embed_failure_returns_early():
    """If embed_dense raises, upsert_note should swallow the error (no upsert call)."""
    from gnosis.services.vector_store import upsert_note
    fake_client = MagicMock()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=fake_client), \
         patch("gnosis.services.vector_store.get_settings",
               return_value=MagicMock(qdrant_collection_name="gnosis_notes")), \
         patch("gnosis.services.vector_store.embed_dense", side_effect=Exception("no model")), \
         patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.1] * 128]):
        upsert_note(
            note_id="n1", title="T", body="B",
            folder="00-inbox", note_type="permanent",
            status="draft", tags=[], owner_id=1,
        )
    fake_client.upsert.assert_not_called()


# ---------------------------------------------------------------------------
# delete_note
# ---------------------------------------------------------------------------

def test_delete_note_calls_delete():
    from gnosis.services.vector_store import delete_note
    fake_client = MagicMock()
    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=fake_client), \
         patch("gnosis.services.vector_store.get_settings",
               return_value=MagicMock(qdrant_collection_name="gnosis_notes")):
        delete_note("20240101-000000")
    fake_client.delete.assert_called_once()


# ---------------------------------------------------------------------------
# hybrid_search (vector_store version)
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

    with patch("gnosis.services.vector_store.get_qdrant_client", return_value=fake_client), \
         patch("gnosis.services.vector_store.get_settings",
               return_value=MagicMock(qdrant_collection_name="gnosis_notes")), \
         patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768):
        result = hybrid_search("test query", owner_ids={1})

    assert isinstance(result, list)


def test_vs_hybrid_search_empty_owner_ids():
    from gnosis.services.vector_store import hybrid_search
    result = hybrid_search("query", owner_ids=set())
    assert isinstance(result, list)
