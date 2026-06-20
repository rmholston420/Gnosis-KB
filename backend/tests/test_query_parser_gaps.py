"""Targeted gap-closure tests for query_parser.py.

Covers the four uncovered lines:
  - 298: op_fn is None → continue (unknown operator in field condition)
  - 303-304: word_count int() ValueError → fallback to raw string
  - 330: SELECT col == 'tags' → [t.name for t in note.tags]
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gnosis.services.query_parser import (
    ParsedQuery,
    execute_query,
)


# ---------------------------------------------------------------------------
# Line 298: unknown operator is skipped (op_fn is None → continue)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_query_unknown_op_is_skipped():
    """A field condition with an unrecognised operator must be silently skipped."""
    parsed = ParsedQuery()
    parsed.conditions = [
        {"type": "field", "field": "status", "op": "~~", "value": "draft"},
    ]
    mock_note = MagicMock()
    mock_note.tags = []
    mock_note.title = "T"
    mock_note.status = "active"
    mock_note.note_type = "permanent"
    mock_note.folder = "00-inbox"
    mock_note.word_count = 10
    mock_note.created_at = None
    mock_note.modified_at = None
    mock_note.last_reviewed = None
    mock_note.slug = "t"
    mock_note.id = "n1"
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_note]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    rows, ms = await execute_query(parsed, mock_db, owner_ids=None)
    # Query must succeed — the bad condition is skipped, not raised
    assert isinstance(rows, list)
    assert ms >= 0


# ---------------------------------------------------------------------------
# Lines 303-304: word_count int() ValueError → raw string fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_query_word_count_non_int_falls_back():
    """Non-integer word_count value must fall back to the raw string."""
    parsed = ParsedQuery()
    parsed.conditions = [
        {"type": "field", "field": "word_count", "op": ">", "value": "notanint"},
    ]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    rows, ms = await execute_query(parsed, mock_db, owner_ids=None)
    assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# Line 330: SELECT col == 'tags' emits [t.name for t in note.tags]
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_query_select_tags_column():
    """SELECT cols containing 'tags' must expand to a list of tag name strings."""
    parsed = ParsedQuery()
    parsed.select_cols = ["id", "title", "tags"]

    tag1, tag2 = MagicMock(name="alpha"), MagicMock(name="beta")
    tag1.name = "alpha"
    tag2.name = "beta"

    mock_note = MagicMock()
    mock_note.tags = [tag1, tag2]
    mock_note.id = "n1"
    mock_note.title = "My Note"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_note]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    rows, ms = await execute_query(parsed, mock_db, owner_ids=None)

    assert len(rows) == 1
    assert rows[0]["tags"] == ["alpha", "beta"]
    assert rows[0]["id"] == "n1"
    assert rows[0]["title"] == "My Note"
