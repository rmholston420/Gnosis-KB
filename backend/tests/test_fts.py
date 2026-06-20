"""Tests for gnosis/services/fts.py.

Public API:
  fulltext_search(db, query, *, limit=10, folder=None, note_type=None, tags=None)
  suggest_completions(db, partial_query, *, limit=5)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest


def _make_db(rows=None):
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows or []
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_fulltext_search_returns_dict():
    from gnosis.services.fts import fulltext_search
    db = _make_db([])
    result = await fulltext_search(db, "python")
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_fulltext_search_empty_query_returns_early():
    from gnosis.services.fts import fulltext_search
    db = _make_db([])
    result = await fulltext_search(db, "")
    # empty query should return quickly — may return empty results dict
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_fulltext_search_with_filters():
    from gnosis.services.fts import fulltext_search
    db = _make_db([])
    result = await fulltext_search(
        db, "neural networks",
        limit=5,
        folder="10-zettelkasten",
        note_type="permanent",
        tags=["ml"],
    )
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_fulltext_search_calls_execute():
    from gnosis.services.fts import fulltext_search
    db = _make_db([])
    await fulltext_search(db, "test query")
    assert db.execute.called


@pytest.mark.asyncio
async def test_suggest_completions_returns_list():
    from gnosis.services.fts import suggest_completions
    db = _make_db([])
    result = await suggest_completions(db, "py")
    # Should return a list (possibly empty if DB is mocked)
    assert isinstance(result, list)
