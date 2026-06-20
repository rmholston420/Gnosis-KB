"""Gap-filling tests for gnosis/services/fts.py.

Covers:
- fulltext_search: SQL error path, folder/note_type/tags filter branches,
  result mapping, elapsed_ms present
- suggest_completions: happy path

All DB calls are mocked — no real Postgres needed.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gnosis.services.fts import fulltext_search, suggest_completions


def _make_db(rows=None, raise_exc=None):
    """Return a mock AsyncSession whose execute returns rows or raises."""
    db = AsyncMock()
    if raise_exc is not None:
        db.execute.side_effect = raise_exc
    else:
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = rows or []
        mock_result.mappings.return_value = mock_mappings
        db.execute.return_value = mock_result
    return db


def _row(note_id="n1", title="T", slug="t", folder="00-inbox",
         note_type="permanent", status="draft", word_count=5,
         score=0.75, highlight="<mark>hi</mark>", tags=None):
    return {
        "note_id": note_id,
        "title": title,
        "slug": slug,
        "folder": folder,
        "note_type": note_type,
        "status": status,
        "word_count": word_count,
        "score": score,
        "highlight": highlight,
        "tags": tags or ["a"],
    }


@pytest.mark.asyncio
async def test_fulltext_search_returns_results():
    db = _make_db(rows=[_row()])
    result = await fulltext_search(db, "hello")
    assert result["results"][0]["note_id"] == "n1"
    assert result["elapsed_ms"] >= 0


@pytest.mark.asyncio
async def test_fulltext_search_sql_error_returns_empty():
    db = _make_db(raise_exc=Exception("connection refused"))
    result = await fulltext_search(db, "query")
    assert result == {"results": [], "elapsed_ms": 0.0}


@pytest.mark.asyncio
async def test_fulltext_search_with_folder_filter():
    db = _make_db(rows=[_row(folder="02-areas")])
    result = await fulltext_search(db, "q", folder="02-areas")
    assert result["results"][0]["folder"] == "02-areas"


@pytest.mark.asyncio
async def test_fulltext_search_with_note_type_filter():
    db = _make_db(rows=[])
    result = await fulltext_search(db, "q", note_type="literature")
    assert result["results"] == []


@pytest.mark.asyncio
async def test_fulltext_search_with_tags_filter():
    db = _make_db(rows=[_row(tags=["python"])])
    result = await fulltext_search(db, "q", tags=["python", "testing"])
    assert result["results"][0]["tags"] == ["python"]


@pytest.mark.asyncio
async def test_fulltext_search_null_optional_fields():
    """slug/folder/note_type/status/highlight/tags may be None in the row."""
    row = _row(slug=None, folder=None, note_type=None,
               status=None, highlight=None, tags=None)
    db = _make_db(rows=[row])
    result = await fulltext_search(db, "q")
    r = result["results"][0]
    assert r["slug"] == ""
    assert r["tags"] == []


@pytest.mark.asyncio
async def test_fulltext_search_combined_filters():
    db = _make_db(rows=[])
    result = await fulltext_search(
        db, "q",
        folder="01-projects",
        note_type="permanent",
        tags=["x"],
    )
    assert result["results"] == []


@pytest.mark.asyncio
async def test_suggest_completions_returns_titles():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("Alpha",), ("Alpha Go",)]
    db.execute.return_value = mock_result

    titles = await suggest_completions(db, "Alpha")
    assert titles == ["Alpha", "Alpha Go"]


@pytest.mark.asyncio
async def test_suggest_completions_respects_limit():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    db.execute.return_value = mock_result

    titles = await suggest_completions(db, "nothing", limit=3)
    assert titles == []
    call_params = db.execute.call_args[0][1]
    assert call_params["limit"] == 3
