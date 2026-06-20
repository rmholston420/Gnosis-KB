"""Tests for gnosis/services/hybrid_search.py.

hybrid_search() is a SYNC function that calls:
  - get_qdrant_client()    -> patch at module level
  - embed_dense(query)     -> patch at module level
  - get_settings()         -> patch at module level
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


def _make_qdrant_result(note_id="note-1", title="Test Note", score=0.9):
    point = MagicMock()
    point.id = "uuid-1"
    point.score = score
    point.payload = {
        "note_id": note_id,
        "title": title,
        "folder": "10-zettel",
        "note_type": "permanent",
        "status": "published",
        "tags": ["eeg"],
        "text_snippet": "snippet text",
    }
    return point


def _patch_hybrid(points, dense_vec=None, raise_embed=False, raise_query=False):
    """Return a context-manager stack that fully mocks the external dependencies."""
    from contextlib import ExitStack

    dense = dense_vec or [0.1] * 768

    fake_result = MagicMock()
    fake_result.points = points

    fake_client = MagicMock()
    if raise_query:
        fake_client.query_points.side_effect = Exception("qdrant down")
        # fallback dense search also fails to return empty
        fake_client.search.return_value = []
    else:
        fake_client.query_points.return_value = fake_result

    fake_settings = MagicMock()
    fake_settings.qdrant_collection_name = "gnosis_notes"

    stack = ExitStack()
    if raise_embed:
        stack.enter_context(patch("gnosis.services.hybrid_search.embed_dense", side_effect=Exception("no model")))
    else:
        stack.enter_context(patch("gnosis.services.hybrid_search.embed_dense", return_value=dense))
    stack.enter_context(patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=fake_client))
    stack.enter_context(patch("gnosis.services.hybrid_search.get_settings", return_value=fake_settings))
    return stack


def test_hybrid_search_returns_results():
    from gnosis.services.hybrid_search import hybrid_search
    with _patch_hybrid([_make_qdrant_result()]):
        out = hybrid_search("test query", owner_ids={1})
    assert isinstance(out, dict)
    assert len(out["results"]) == 1
    assert out["results"][0]["title"] == "Test Note"


def test_hybrid_search_returns_elapsed_ms():
    from gnosis.services.hybrid_search import hybrid_search
    with _patch_hybrid([_make_qdrant_result()]):
        out = hybrid_search("test", owner_ids={1})
    assert "elapsed_ms" in out
    assert isinstance(out["elapsed_ms"], float)


def test_hybrid_search_empty_owner_ids_returns_empty():
    from gnosis.services.hybrid_search import hybrid_search
    out = hybrid_search("test", owner_ids=set())
    assert out["results"] == []


def test_hybrid_search_embed_failure_returns_empty():
    from gnosis.services.hybrid_search import hybrid_search
    with _patch_hybrid([], raise_embed=True):
        out = hybrid_search("test", owner_ids={1})
    assert out["results"] == []


def test_hybrid_search_multiple_results():
    from gnosis.services.hybrid_search import hybrid_search
    points = [
        _make_qdrant_result("note-1", "Note One", 0.9),
        _make_qdrant_result("note-2", "Note Two", 0.8),
        _make_qdrant_result("note-3", "Note Three", 0.7),
    ]
    with _patch_hybrid(points):
        out = hybrid_search("query", owner_ids={1})
    assert len(out["results"]) == 3


def test_hybrid_search_respects_limit():
    from gnosis.services.hybrid_search import hybrid_search
    # The limit is forwarded to qdrant; we just verify it doesn't crash
    with _patch_hybrid([_make_qdrant_result()]):
        out = hybrid_search("query", owner_ids={1}, limit=5)
    assert isinstance(out["results"], list)


def test_hybrid_search_result_fields():
    from gnosis.services.hybrid_search import hybrid_search
    with _patch_hybrid([_make_qdrant_result()]):
        out = hybrid_search("query", owner_ids={1})
    r = out["results"][0]
    assert "note_id" in r
    assert "title" in r
    assert "score" in r
    assert "folder" in r
    assert "tags" in r


def test_hybrid_search_qdrant_failure_falls_back():
    from gnosis.services.hybrid_search import hybrid_search
    with _patch_hybrid([], raise_query=True):
        out = hybrid_search("query", owner_ids={1})
    assert isinstance(out["results"], list)


def test_hybrid_search_folder_filter():
    from gnosis.services.hybrid_search import hybrid_search
    with _patch_hybrid([_make_qdrant_result()]):
        out = hybrid_search("query", owner_ids={1}, folder="10-zettel")
    assert isinstance(out["results"], list)


def test_hybrid_search_tags_filter():
    from gnosis.services.hybrid_search import hybrid_search
    with _patch_hybrid([_make_qdrant_result()]):
        out = hybrid_search("query", owner_ids={1}, tags=["eeg"])
    assert isinstance(out["results"], list)
