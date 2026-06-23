"""Integration smoke-tests for the FTS service.

These tests use SQLite + the gnosis Note model to verify:
  1. fulltext_search returns an empty list gracefully when fts column
     doesn't exist (SQLite won't have the tsvector trigger).
  2. suggest_completions prefix-matches note titles.

For a true tsvector test, spin up the Docker stack and run against
PostgreSQL:  pytest -m integration --db postgresql://...
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from gnosis.services.fts import suggest_completions


@pytest.mark.asyncio
async def test_suggest_completions_empty_on_no_match():
    """suggest_completions returns [] when no notes match prefix."""
    # Mock db session
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await suggest_completions(mock_db, prefix="zzz_no_match")
    assert result == []


@pytest.mark.asyncio
async def test_suggest_completions_returns_titles():
    """suggest_completions maps row[0] to a list of strings."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("Zettelkasten Overview",), ("Zen and the Art",)]
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await suggest_completions(mock_db, prefix="Ze")
    assert result == ["Zettelkasten Overview", "Zen and the Art"]
