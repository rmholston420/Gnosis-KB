"""Unit tests for gnosis/services/hybrid_search.py.

hybrid_search() is synchronous and uses get_qdrant_client() + embed_dense().
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_point(note_id, score=0.9):
    p = MagicMock()
    p.id = note_id
    p.score = score
    p.payload = {
        "note_id": note_id,
        "title": f"Note {note_id}",
        "folder": "10",
        "note_type": "permanent",
        "status": "active",
        "tags": [],
        "text_snippet": "snippet",
    }
    return p


def _mock_qdrant(points):
    client = MagicMock()
    client.query_points = MagicMock(
        return_value=MagicMock(points=points)
    )
    client.search = MagicMock(return_value=points)
    return client


# ---------------------------------------------------------------------------
# Basic happy path
# ---------------------------------------------------------------------------

def test_hybrid_search_returns_results():
    from gnosis.services.hybrid_search import hybrid_search

    pts = [_make_point("n1"), _make_point("n2")]
    mock_client = _mock_qdrant(pts)

    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 768):
        out = hybrid_search("test", owner_ids={1})

    assert len(out["results"]) == 2
    assert out["results"][0]["note_id"] == "n1"


def test_hybrid_search_result_fields():
    from gnosis.services.hybrid_search import hybrid_search

    pts = [_make_point("n1", score=0.85)]
    mock_client = _mock_qdrant(pts)

    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 768):
        out = hybrid_search("q", owner_ids={1})

    r = out["results"][0]
    assert "note_id" in r
    assert "score" in r
    assert "elapsed_ms" in out


# ---------------------------------------------------------------------------
# Empty owner_ids short-circuits
# ---------------------------------------------------------------------------

def test_hybrid_search_empty_owner_ids_returns_empty():
    from gnosis.services.hybrid_search import hybrid_search
    out = hybrid_search("q", owner_ids=set())
    assert out["results"] == []


# ---------------------------------------------------------------------------
# Embed failure returns empty
# ---------------------------------------------------------------------------

def test_hybrid_search_embed_failure_returns_empty():
    from gnosis.services.hybrid_search import hybrid_search

    with patch("gnosis.services.hybrid_search.embed_dense", side_effect=RuntimeError("no model")), \
         patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=MagicMock()):
        out = hybrid_search("q", owner_ids={1})

    assert out["results"] == []


# ---------------------------------------------------------------------------
# Qdrant failure falls back to dense search
# ---------------------------------------------------------------------------

def test_hybrid_search_falls_back_to_dense_on_qdrant_error():
    from gnosis.services.hybrid_search import hybrid_search

    pts = [_make_point("n1")]
    mock_client = MagicMock()
    mock_client.query_points.side_effect = RuntimeError("Qdrant down")
    mock_client.search.return_value = pts  # fallback dense search

    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 768):
        out = hybrid_search("q", owner_ids={1})

    assert len(out["results"]) == 1


# ---------------------------------------------------------------------------
# Optional filters
# ---------------------------------------------------------------------------

def test_hybrid_search_with_folder_filter():
    from gnosis.services.hybrid_search import hybrid_search

    mock_client = _mock_qdrant([])
    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 768):
        out = hybrid_search("q", owner_ids={1}, folder="10-zettelkasten")

    assert "results" in out


def test_hybrid_search_with_tags_filter():
    from gnosis.services.hybrid_search import hybrid_search

    mock_client = _mock_qdrant([])
    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 768):
        out = hybrid_search("q", owner_ids={1}, tags=["python", "ml"])

    assert "results" in out
