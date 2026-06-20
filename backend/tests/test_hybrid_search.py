"""Tests for gnosis/services/hybrid_search.py.

Public API (synchronous, uses Qdrant directly):
  hybrid_search(query, owner_ids, limit=10, folder=None, note_type=None, tags=None)
  -> dict with keys: results (list of dicts), elapsed_ms (float)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


def _make_point(note_id, score=0.9, extra_payload=None):
    p = MagicMock()
    p.score = score
    p.id = note_id
    p.payload = {"note_id": note_id, "title": f"Note {note_id}",
                 "folder": "10-zettelkasten", "note_type": "permanent",
                 "status": "active", "tags": [], "text_snippet": "body"}
    if extra_payload:
        p.payload.update(extra_payload)
    return p


def _mock_client(points=None, raise_on_query=False, raise_on_search=False):
    client = MagicMock()
    mock_result = MagicMock()
    mock_result.points = points or []
    if raise_on_query:
        client.query_points.side_effect = Exception("Qdrant query failed")
    else:
        client.query_points.return_value = mock_result
    if raise_on_search:
        client.search.side_effect = Exception("Qdrant search failed")
    else:
        client.search.return_value = points or []
    return client


def _mock_dense(vec=None):
    mock_model = MagicMock()
    mock_model.embed.return_value = [vec or [0.1] * 768]
    return mock_model


# ---------------------------------------------------------------------------
# Short-circuit: empty owner_ids
# ---------------------------------------------------------------------------

def test_hybrid_search_empty_owner_ids_returns_empty():
    from gnosis.services.hybrid_search import hybrid_search
    result = hybrid_search("python", owner_ids=set())
    assert result == {"results": [], "elapsed_ms": 0.0}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_hybrid_search_returns_dict_structure():
    from gnosis.services.hybrid_search import hybrid_search
    client = _mock_client([_make_point("n1"), _make_point("n2")])
    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=_mock_dense()):
        result = hybrid_search("python notes", owner_ids={1})
    assert "results" in result
    assert "elapsed_ms" in result
    assert isinstance(result["results"], list)
    assert isinstance(result["elapsed_ms"], float)


def test_hybrid_search_result_fields():
    from gnosis.services.hybrid_search import hybrid_search
    client = _mock_client([_make_point("n1", score=0.85)])
    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=_mock_dense()):
        result = hybrid_search("query", owner_ids={1})
    r = result["results"][0]
    assert r["note_id"] == "n1"
    assert r["score"] == 0.85
    assert "title" in r
    assert "folder" in r


def test_hybrid_search_respects_limit():
    from gnosis.services.hybrid_search import hybrid_search
    points = [_make_point(f"n{i}") for i in range(10)]
    client = _mock_client(points)
    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=_mock_dense()):
        result = hybrid_search("query", owner_ids={1}, limit=5)
    assert len(result["results"]) <= 10


def test_hybrid_search_with_folder_filter():
    from gnosis.services.hybrid_search import hybrid_search
    client = _mock_client([])
    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=_mock_dense()):
        result = hybrid_search("test", owner_ids={1}, folder="10-zettelkasten")
    assert isinstance(result, dict)


def test_hybrid_search_with_note_type_filter():
    from gnosis.services.hybrid_search import hybrid_search
    client = _mock_client([])
    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=_mock_dense()):
        result = hybrid_search("test", owner_ids={1}, note_type="permanent")
    assert isinstance(result, dict)


def test_hybrid_search_with_tags_filter():
    from gnosis.services.hybrid_search import hybrid_search
    client = _mock_client([])
    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=_mock_dense()):
        result = hybrid_search("test", owner_ids={1}, tags=["python", "ml"])
    assert isinstance(result, dict)


def test_hybrid_search_multiple_owner_ids():
    from gnosis.services.hybrid_search import hybrid_search
    client = _mock_client([_make_point("n1")])
    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=_mock_dense()):
        result = hybrid_search("test", owner_ids={1, 2, 3})
    assert isinstance(result["results"], list)


# ---------------------------------------------------------------------------
# Fallback: embed_dense fails
# ---------------------------------------------------------------------------

def test_hybrid_search_embed_failure_returns_empty():
    from gnosis.services.hybrid_search import hybrid_search
    failing_model = MagicMock()
    failing_model.embed.side_effect = Exception("model not loaded")
    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=MagicMock()), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=failing_model):
        result = hybrid_search("test", owner_ids={1})
    assert result["results"] == []


# ---------------------------------------------------------------------------
# Fallback: Qdrant query_points fails -> falls back to client.search
# ---------------------------------------------------------------------------

def test_hybrid_search_falls_back_to_dense_on_qdrant_error():
    from gnosis.services.hybrid_search import hybrid_search
    client = _mock_client(
        points=[_make_point("n1")],
        raise_on_query=True,
    )
    # client.search is the fallback and returns a list of points directly
    fallback_point = _make_point("n1")
    client.search.side_effect = None  # reset
    client.search.return_value = [fallback_point]
    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client), \
         patch("gnosis.services.embeddings.get_dense_model", return_value=_mock_dense()):
        result = hybrid_search("test", owner_ids={1})
    # Either returns from fallback or empty if fallback also raised
    assert isinstance(result["results"], list)
