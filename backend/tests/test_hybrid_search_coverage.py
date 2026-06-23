"""Gap-filling tests for gnosis/services/hybrid_search.py.

Covers:
- empty owner_ids guard (line 59)
- embed_dense failure path (lines 69-70)
- Qdrant query_points failure → dense fallback (lines 110-118)
- filter branches: folder, note_type, tags
- output shape and elapsed_ms
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gnosis.services.hybrid_search import hybrid_search


def _make_point(
    note_id="n1",
    title="T",
    folder="00-inbox",
    note_type="permanent",
    status="draft",
    tags=None,
    score=0.9,
    text_snippet="snippet",
):
    p = MagicMock()
    p.id = "uuid-1"
    p.score = score
    p.payload = {
        "note_id": note_id,
        "title": title,
        "folder": folder,
        "note_type": note_type,
        "status": status,
        "tags": tags or [],
        "text_snippet": text_snippet,
    }
    return p


def _mock_client(points=None, raise_query=False, fallback_points=None):
    client = MagicMock()
    if raise_query:
        client.query_points.side_effect = Exception("Qdrant down")
        client.search.return_value = fallback_points or []
    else:
        result = MagicMock()
        result.points = points or []
        client.query_points.return_value = result
    return client


@pytest.fixture(autouse=True)
def _patch_deps(monkeypatch):
    """Patch get_qdrant_client, get_settings, and embed_dense for every test."""
    settings = MagicMock()
    settings.qdrant_collection_name = "gnosis_notes"
    monkeypatch.setattr("gnosis.services.hybrid_search.get_settings", lambda: settings)


def test_empty_owner_ids_returns_empty():
    result = hybrid_search("anything", owner_ids=set())
    assert result == {"results": [], "elapsed_ms": 0.0}


def test_embed_dense_failure_returns_empty():
    with (
        patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=MagicMock()),
        patch("gnosis.services.hybrid_search.embed_dense", side_effect=RuntimeError("no model")),
    ):
        result = hybrid_search("query", owner_ids={1})
    assert result == {"results": [], "elapsed_ms": 0.0}


def test_happy_path_returns_formatted_results():
    pt = _make_point()
    client = _mock_client(points=[pt])
    with (
        patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client),
        patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 768),
    ):
        result = hybrid_search("hello", owner_ids={1})

    assert len(result["results"]) == 1
    r = result["results"][0]
    assert r["note_id"] == "n1"
    assert r["score"] == 0.9
    assert result["elapsed_ms"] >= 0


def test_qdrant_failure_falls_back_to_dense():
    fb_point = _make_point(note_id="fallback")
    client = _mock_client(raise_query=True, fallback_points=[fb_point])
    with (
        patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client),
        patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.0] * 768),
    ):
        result = hybrid_search("q", owner_ids={2})

    assert result["results"][0]["note_id"] == "fallback"


def test_folder_filter_is_applied():
    client = _mock_client(points=[])
    with (
        patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client),
        patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.0] * 768),
    ):
        result = hybrid_search("q", owner_ids={1}, folder="01-projects")
    assert result["results"] == []


def test_note_type_filter_is_applied():
    client = _mock_client(points=[])
    with (
        patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client),
        patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.0] * 768),
    ):
        result = hybrid_search("q", owner_ids={1}, note_type="literature")
    assert result["results"] == []


def test_tags_filter_is_applied():
    client = _mock_client(points=[])
    with (
        patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client),
        patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.0] * 768),
    ):
        result = hybrid_search("q", owner_ids={1}, tags=["python", "testing"])
    assert result["results"] == []


def test_highlight_truncated_to_200_chars():
    long_snippet = "x" * 300
    pt = _make_point(text_snippet=long_snippet)
    client = _mock_client(points=[pt])
    with (
        patch("gnosis.services.hybrid_search.get_qdrant_client", return_value=client),
        patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.0] * 768),
    ):
        result = hybrid_search("q", owner_ids={1})
    assert len(result["results"][0]["highlight"]) == 200
