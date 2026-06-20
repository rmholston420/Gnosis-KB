"""Unit tests for gnosis/services/hybrid_search.py.

Focus:
- empty owner_ids short-circuit
- successful hybrid query path
- dense-embedding failure returns empty results
- hybrid query_points failure falls back to dense search
- payload filters (folder, note_type, tags) are attached
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from gnosis.services.hybrid_search import hybrid_search


def _point(pid="p1", score=0.87, payload=None):
    return SimpleNamespace(
        id=pid,
        score=score,
        payload=payload or {
            "note_id": pid,
            "title": "Test Title",
            "folder": "10-zettelkasten",
            "note_type": "permanent",
            "status": "active",
            "tags": ["idea"],
            "text_snippet": "hello world snippet",
        },
    )


def test_hybrid_search_empty_owner_ids_short_circuits():
    result = hybrid_search("test", owner_ids=set())
    assert result == {"results": [], "elapsed_ms": 0.0}


def test_hybrid_search_success_path():
    client = MagicMock()
    client.query_points.return_value = SimpleNamespace(points=[_point("n1", 0.91)])
    settings = SimpleNamespace(qdrant_collection_name="notes")

    with (
        patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client),
        patch("gnosis.services.hybrid_search.get_settings", return_value=settings),
        patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1, 0.2, 0.3]),
    ):
        result = hybrid_search("knowledge graph", owner_ids={1}, limit=5)

    assert len(result["results"]) == 1
    assert result["results"][0]["note_id"] == "n1"
    assert result["results"][0]["score"] == 0.91
    client.query_points.assert_called_once()
    client.search.assert_not_called()


def test_hybrid_search_embed_failure_returns_empty():
    client = MagicMock()
    settings = SimpleNamespace(qdrant_collection_name="notes")

    with (
        patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client),
        patch("gnosis.services.hybrid_search.get_settings", return_value=settings),
        patch("gnosis.services.hybrid_search.embed_dense", side_effect=RuntimeError("boom")),
    ):
        result = hybrid_search("knowledge graph", owner_ids={1})

    assert result == {"results": [], "elapsed_ms": 0.0}
    client.query_points.assert_not_called()
    client.search.assert_not_called()


def test_hybrid_search_query_points_falls_back_to_dense_search():
    client = MagicMock()
    client.query_points.side_effect = RuntimeError("hybrid failed")
    client.search.return_value = [_point("n2", 0.76)]
    settings = SimpleNamespace(qdrant_collection_name="notes")

    with (
        patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client),
        patch("gnosis.services.hybrid_search.get_settings", return_value=settings),
        patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.3, 0.4, 0.5]),
    ):
        result = hybrid_search("semantic search", owner_ids={7}, limit=3)

    assert len(result["results"]) == 1
    assert result["results"][0]["note_id"] == "n2"
    client.query_points.assert_called_once()
    client.search.assert_called_once()


def test_hybrid_search_applies_folder_type_and_tag_filters():
    client = MagicMock()
    client.query_points.return_value = SimpleNamespace(points=[])
    settings = SimpleNamespace(qdrant_collection_name="notes")

    with (
        patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client),
        patch("gnosis.services.hybrid_search.get_settings", return_value=settings),
        patch("gnosis.services.hybrid_search.embed_dense", return_value=[1.0, 2.0]),
    ):
        hybrid_search(
            "zettel", owner_ids={42}, limit=10,
            folder="10-zettelkasten", note_type="permanent", tags=["idea", "ml"],
        )

    kwargs = client.query_points.call_args.kwargs
    prefetch = kwargs["prefetch"]
    query_filter = prefetch[0].filter
    must_conditions = query_filter.must
    keys = [c.key for c in must_conditions]
    assert "owner_id" in keys
    assert "folder" in keys
    assert "note_type" in keys
    assert keys.count("tags") == 2
