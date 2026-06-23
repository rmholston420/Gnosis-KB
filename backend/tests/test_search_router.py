"""Unit tests for gnosis/routers/search.py.

Covers:
- fulltext mode: delegates to fulltext_search, maps results correctly
- hybrid mode: delegates to hybrid_search, maps results correctly
- hybrid mode fallback: hybrid_search raises, falls back to fulltext
- suggest endpoint: delegates to suggest_completions
- _map_results: correctly maps raw dict fields to SearchResult
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gnosis.routers.search import _map_results, search, suggest

_FULLTEXT_PATCH = "gnosis.routers.search.fulltext_search"
_HYBRID_PATCH = "gnosis.routers.search.hybrid_search"
_SUGGEST_PATCH = "gnosis.routers.search.suggest_completions"


def _raw_result(note_id="n1", score=0.9):
    return {
        "note_id": note_id,
        "title": "Test Note",
        "slug": "test-note",
        "folder": "10-zettelkasten",
        "note_type": "permanent",
        "status": "active",
        "score": score,
        "highlight": "<mark>test</mark>",
        "tags": ["idea"],
    }


def _db():
    return AsyncMock()


def _user():
    u = MagicMock()
    u.id = 1
    return u


# ---------------------------------------------------------------------------
# _map_results
# ---------------------------------------------------------------------------


def test_map_results_creates_search_result_objects():
    raw = [_raw_result("n1", 0.88), _raw_result("n2", 0.77)]
    results = _map_results(raw)
    assert len(results) == 2
    assert results[0].note_id == "n1"
    assert results[0].score == 0.88
    assert results[1].note_id == "n2"
    assert results[0].tags == ["idea"]


def test_map_results_empty_list():
    assert _map_results([]) == []


# ---------------------------------------------------------------------------
# search — fulltext mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_fulltext_mode_delegates_to_fulltext_search():
    fts_response = {"results": [_raw_result("n1")], "elapsed_ms": 12.5}

    with patch(_FULLTEXT_PATCH, AsyncMock(return_value=fts_response)) as mock_fts:
        response = await search(
            q="graph",
            limit=10,
            folder=None,
            note_type=None,
            tags=None,
            mode="fulltext",
            db=_db(),
            owner_ids={1},
        )

    mock_fts.assert_awaited_once()
    assert response.mode == "fulltext"
    assert response.query == "graph"
    assert len(response.results) == 1
    assert response.results[0].note_id == "n1"
    assert response.elapsed_ms == 12.5


# ---------------------------------------------------------------------------
# search — hybrid mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_hybrid_mode_delegates_to_hybrid_search():
    hybrid_response = {"results": [_raw_result("n2", 0.95)], "elapsed_ms": 8.3}

    with patch(_HYBRID_PATCH, MagicMock(return_value=hybrid_response)) as mock_hyb:
        response = await search(
            q="knowledge",
            limit=5,
            folder="10-zettelkasten",
            note_type="permanent",
            tags=["idea"],
            mode="hybrid",
            db=_db(),
            owner_ids={1},
        )

    mock_hyb.assert_called_once()
    assert response.mode == "hybrid"
    assert len(response.results) == 1
    assert response.results[0].note_id == "n2"
    call_kwargs = mock_hyb.call_args.kwargs
    assert call_kwargs["folder"] == "10-zettelkasten"
    assert call_kwargs["note_type"] == "permanent"
    assert call_kwargs["tags"] == ["idea"]


@pytest.mark.asyncio
async def test_search_hybrid_falls_back_to_fulltext_on_error():
    fts_response = {"results": [_raw_result("n3", 0.6)], "elapsed_ms": 20.0}

    with (
        patch(_HYBRID_PATCH, MagicMock(side_effect=RuntimeError("qdrant down"))),
        patch(_FULLTEXT_PATCH, AsyncMock(return_value=fts_response)) as mock_fts,
    ):
        response = await search(
            q="zettel",
            limit=10,
            folder=None,
            note_type=None,
            tags=None,
            mode="hybrid",
            db=_db(),
            owner_ids={1},
        )

    mock_fts.assert_awaited_once()
    # mode is overridden to fulltext in fallback response
    assert response.mode == "fulltext"
    assert response.results[0].note_id == "n3"


@pytest.mark.asyncio
async def test_search_hybrid_returns_empty_when_no_results():
    with patch(_HYBRID_PATCH, MagicMock(return_value={"results": [], "elapsed_ms": 1.0})):
        response = await search(
            q="obscure",
            limit=10,
            folder=None,
            note_type=None,
            tags=None,
            mode="hybrid",
            db=_db(),
            owner_ids={1},
        )
    assert response.results == []
    assert response.total == 0


# ---------------------------------------------------------------------------
# suggest endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggest_delegates_to_suggest_completions():
    with patch(_SUGGEST_PATCH, AsyncMock(return_value=["Alpha", "Alphabet"])) as mock_sug:
        result = await suggest(q="Al", limit=5, db=_db(), owner_ids={1})

    mock_sug.assert_awaited_once()
    assert result == ["Alpha", "Alphabet"]
    call_kwargs = mock_sug.call_args.kwargs
    assert call_kwargs["limit"] == 5
