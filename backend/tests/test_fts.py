"""Integration smoke-tests for the FTS service.

Moved from backend/gnosis/services/fts_test.py — test files must not live
inside source packages as they pollute the importable namespace and can be
picked up by __init__.py auto-imports during package discovery.

These tests use SQLite + the gnosis Note model to verify:
  1. fulltext_search returns an empty list gracefully when fts column
     doesn't exist (SQLite won't have the tsvector trigger).
  2. suggest_completions prefix-matches note titles.

For a true tsvector test, spin up the Docker stack and run against
PostgreSQL:  pytest -m integration --db postgresql://...
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_fulltext_search_empty_graceful(async_db_session) -> None:
    """fulltext_search returns an empty result set gracefully on SQLite."""
    from gnosis.services.fts import fulltext_search

    result = await fulltext_search(async_db_session, "anything", owner_ids={1})
    assert result["results"] == []
    assert isinstance(result["elapsed_ms"], (int, float))


@pytest.mark.asyncio
async def test_suggest_completions_prefix(async_db_session, sample_notes) -> None:
    """suggest_completions returns titles that start with the given prefix."""
    from gnosis.services.fts import suggest_completions

    results = await suggest_completions(async_db_session, "Zettel", owner_ids={1})
    assert all(t.startswith("Zettel") for t in results)
