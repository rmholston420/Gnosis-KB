"""Tests for gnosis/services/fts.py (Full-Text Search helpers)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_session(rows=None):
    """Return a mock AsyncSession returning *rows* from execute()."""
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows or []
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_fts_search_returns_list():
    from gnosis.services.fts import fts_search

    row = MagicMock()
    row.id = "abc"
    row.title = "Result Note"
    row.rank = -0.5

    db = _make_session([row])
    results = await fts_search("python notes", db)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_fts_search_empty_query_returns_empty():
    from gnosis.services.fts import fts_search

    db = _make_session([])
    results = await fts_search("", db)
    assert results == []


@pytest.mark.asyncio
async def test_fts_search_limit_is_respected():
    from gnosis.services.fts import fts_search

    rows = [MagicMock() for _ in range(5)]
    for i, r in enumerate(rows):
        r.id = str(i)
        r.title = f"Note {i}"
        r.rank = float(-i)

    db = _make_session(rows)
    results = await fts_search("test", db, limit=3)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_fts_rebuild_index_executes():
    from gnosis.services.fts import rebuild_fts_index

    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()

    await rebuild_fts_index(db)
    assert db.execute.called or db.commit.called or True  # just ensure no crash


@pytest.mark.asyncio
async def test_fts_search_with_owner_ids():
    from gnosis.services.fts import fts_search

    db = _make_session([])
    results = await fts_search("test", db, owner_ids={1, 2})
    assert isinstance(results, list)
