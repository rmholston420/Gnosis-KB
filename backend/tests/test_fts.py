"""Tests for gnosis/services/fts.py.

Public API:
  fulltext_search(db, query, *, limit=10, folder=None, note_type=None, tags=None)
    -> dict with keys: results (list), elapsed_ms (float)
  suggest_completions(db, prefix, limit=8) -> list[str]
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_db(mappings=None, fetchall=None):
    """Return a mock AsyncSession."""
    db = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = mappings or []
    result.fetchall.return_value = fetchall or []
    db.execute = AsyncMock(return_value=result)
    return db


# ---------------------------------------------------------------------------
# fulltext_search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fulltext_search_returns_dict():
    from gnosis.services.fts import fulltext_search

    db = _make_db()
    result = await fulltext_search(db, "python")
    assert isinstance(result, dict)
    assert "results" in result
    assert "elapsed_ms" in result


@pytest.mark.asyncio
async def test_fulltext_search_results_is_list():
    from gnosis.services.fts import fulltext_search

    db = _make_db()
    result = await fulltext_search(db, "machine learning")
    assert isinstance(result["results"], list)


@pytest.mark.asyncio
async def test_fulltext_search_calls_execute():
    from gnosis.services.fts import fulltext_search

    db = _make_db()
    await fulltext_search(db, "test query")
    assert db.execute.called


@pytest.mark.asyncio
async def test_fulltext_search_with_folder_filter():
    from gnosis.services.fts import fulltext_search

    db = _make_db()
    result = await fulltext_search(db, "notes", folder="10-zettelkasten")
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_fulltext_search_with_note_type_filter():
    from gnosis.services.fts import fulltext_search

    db = _make_db()
    result = await fulltext_search(db, "notes", note_type="permanent")
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_fulltext_search_with_tags_filter():
    from gnosis.services.fts import fulltext_search

    db = _make_db()
    result = await fulltext_search(db, "notes", tags=["python", "ml"])
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_fulltext_search_with_all_filters():
    from gnosis.services.fts import fulltext_search

    db = _make_db()
    result = await fulltext_search(
        db,
        "neural",
        limit=5,
        folder="10-zettelkasten",
        note_type="permanent",
        tags=["ml"],
    )
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_fulltext_search_elapsed_ms_is_float():
    from gnosis.services.fts import fulltext_search

    db = _make_db()
    result = await fulltext_search(db, "test")
    assert isinstance(result["elapsed_ms"], float)


@pytest.mark.asyncio
async def test_fulltext_search_returns_empty_on_db_error():
    from gnosis.services.fts import fulltext_search

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=Exception("DB down"))
    result = await fulltext_search(db, "test")
    assert result["results"] == []


@pytest.mark.asyncio
async def test_fulltext_search_maps_row_fields():
    """Rows with the expected mapping keys should be serialised correctly."""
    from gnosis.services.fts import fulltext_search

    row = {
        "note_id": "n1",
        "title": "My Note",
        "slug": "my-note",
        "folder": "10-zettelkasten",
        "note_type": "permanent",
        "status": "active",
        "score": 0.95,
        "highlight": "<mark>python</mark> code",
        "tags": ["python"],
    }
    db = _make_db(mappings=[row])
    result = await fulltext_search(db, "python")
    assert len(result["results"]) == 1
    r = result["results"][0]
    assert r["note_id"] == "n1"
    assert r["score"] == 0.95
    assert "python" in r["tags"]


# ---------------------------------------------------------------------------
# suggest_completions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggest_completions_returns_list():
    from gnosis.services.fts import suggest_completions

    db = _make_db(fetchall=[])
    result = await suggest_completions(db, "py")
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_suggest_completions_returns_titles():
    from gnosis.services.fts import suggest_completions

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = [("Python Basics",), ("Python Advanced",)]
    db.execute = AsyncMock(return_value=result_mock)
    result = await suggest_completions(db, "Py")
    assert "Python Basics" in result
    assert "Python Advanced" in result


@pytest.mark.asyncio
async def test_suggest_completions_empty_returns_empty_list():
    from gnosis.services.fts import suggest_completions

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = []
    db.execute = AsyncMock(return_value=result_mock)
    result = await suggest_completions(db, "zzz")
    assert result == []


@pytest.mark.asyncio
async def test_suggest_completions_respects_limit():
    from gnosis.services.fts import suggest_completions

    db = _make_db(fetchall=[])
    # Should accept limit kwarg without raising
    result = await suggest_completions(db, "py", limit=3)
    assert isinstance(result, list)
