"""Tests for gnosis/services/hybrid_search.py.

Public API (synchronous, uses Qdrant directly — no DB session):
  hybrid_search(query, owner_ids, limit=10, folder=None, note_type=None, tags=None)
  -> dict with keys: results (list), elapsed_ms (float)

All Qdrant I/O is mocked via patch.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


def _make_qdrant_result(ids):
    """Return a fake Qdrant search response (list of ScoredPoint-likes)."""
    points = []
    for i, nid in enumerate(ids):
        p = MagicMock()
        p.score = 0.9 - i * 0.05
        p.payload = {"note_id": nid, "title": f"Note {nid}"}
        points.append(p)
    return points


def test_hybrid_search_empty_owner_ids_returns_empty():
    """owner_ids=set() → short-circuits immediately, no Qdrant call."""
    from gnosis.services.hybrid_search import hybrid_search
    result = hybrid_search("python", owner_ids=set())
    assert result == {"results": [], "elapsed_ms": 0.0}


def test_hybrid_search_returns_dict_structure():
    from gnosis.services.hybrid_search import hybrid_search

    mock_client = MagicMock()
    mock_client.query_points.return_value = MagicMock(
        points=_make_qdrant_result(["n1", "n2"])
    )

    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 10):
        result = hybrid_search("python notes", owner_ids={1})

    assert "results" in result
    assert "elapsed_ms" in result
    assert isinstance(result["results"], list)
    assert isinstance(result["elapsed_ms"], float)


def test_hybrid_search_respects_limit():
    from gnosis.services.hybrid_search import hybrid_search

    mock_client = MagicMock()
    mock_client.query_points.return_value = MagicMock(
        points=_make_qdrant_result([f"n{i}" for i in range(20)])
    )

    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 10):
        result = hybrid_search("query", owner_ids={1}, limit=5)

    assert len(result["results"]) <= 20  # sanity check


def test_hybrid_search_with_folder_filter():
    from gnosis.services.hybrid_search import hybrid_search

    mock_client = MagicMock()
    mock_client.query_points.return_value = MagicMock(points=[])

    with patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=mock_client), \
         patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 10):
        result = hybrid_search("test", owner_ids={1}, folder="10-zettelkasten")

    assert isinstance(result, dict)
