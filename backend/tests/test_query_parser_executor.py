"""Tests for the execute_query() path in gnosis/services/query_parser.py.

The executor touches the DB via AsyncSession — we mock the session so no
real database is needed.
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_note(
    id="n1",
    title="Note Title",
    status="active",
    note_type="permanent",
    folder="10-zettelkasten",
    word_count=120,
    tags=None,
    created_at=None,
    modified_at=None,
    last_reviewed=None,
    slug="note-title",
    is_deleted=False,
):
    note = MagicMock()
    note.id = id
    note.title = title
    note.status = status
    note.note_type = note_type
    note.folder = folder
    note.word_count = word_count
    note.slug = slug
    note.is_deleted = is_deleted
    note.created_at = created_at or datetime(2025, 1, 1, tzinfo=UTC)
    note.modified_at = modified_at or datetime(2025, 6, 1, tzinfo=UTC)
    note.last_reviewed = last_reviewed
    note.tags = tags or []
    return note


def _make_db(notes):
    """Return a mock AsyncSession whose execute() returns *notes*."""
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = notes
    db.execute = AsyncMock(return_value=result)
    return db


# ---------------------------------------------------------------------------
# Basic execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_query_returns_rows_and_ms():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    note = _make_note()
    db = _make_db([note])
    parsed = ParsedQuery()

    rows, ms = await execute_query(parsed, db)

    assert isinstance(rows, list)
    assert len(rows) == 1
    assert isinstance(ms, float)


@pytest.mark.asyncio
async def test_execute_query_row_has_expected_fields():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    tag = MagicMock(); tag.name = "python"
    note = _make_note(tags=[tag])
    db = _make_db([note])
    parsed = ParsedQuery(select_cols=["id", "title", "status"])

    rows, _ = await execute_query(parsed, db)

    assert rows[0]["id"] == "n1"
    assert rows[0]["title"] == "Note Title"
    assert rows[0]["status"] == "active"


@pytest.mark.asyncio
async def test_execute_query_serialises_datetime():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    note = _make_note()
    db = _make_db([note])
    parsed = ParsedQuery(select_cols=["modified_at"])

    rows, _ = await execute_query(parsed, db)
    assert isinstance(rows[0]["modified_at"], str)


@pytest.mark.asyncio
async def test_execute_query_empty_result():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    db = _make_db([])
    rows, _ = await execute_query(ParsedQuery(), db)
    assert rows == []


# ---------------------------------------------------------------------------
# FROM clause
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_query_from_folder_applies_filter():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    note = _make_note(folder="10-zettelkasten")
    db = _make_db([note])
    parsed = ParsedQuery(from_folder="10")

    rows, _ = await execute_query(parsed, db)
    db.execute.assert_called()


# ---------------------------------------------------------------------------
# WHERE tag condition
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_query_tag_condition():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    tag = MagicMock(); tag.name = "eeg"
    note = _make_note(tags=[tag])
    db = _make_db([note])
    parsed = ParsedQuery(conditions=[{"type": "tag", "tag": "eeg"}])

    rows, _ = await execute_query(parsed, db)
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# WHERE field conditions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_query_field_eq_condition():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    note = _make_note(status="draft")
    db = _make_db([note])
    parsed = ParsedQuery(
        conditions=[{"type": "field", "field": "status", "op": "=", "value": "draft"}]
    )
    rows, _ = await execute_query(parsed, db)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_execute_query_word_count_gt_coerces_int():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    note = _make_note(word_count=200)
    db = _make_db([note])
    parsed = ParsedQuery(
        conditions=[{"type": "field", "field": "word_count", "op": ">", "value": "100"}]
    )
    rows, _ = await execute_query(parsed, db)
    db.execute.assert_called()


@pytest.mark.asyncio
async def test_execute_query_unknown_op_is_skipped():
    """An op not in _OP_MAP should be silently skipped (no crash)."""
    from gnosis.services.query_parser import ParsedQuery, execute_query

    note = _make_note()
    db = _make_db([note])
    parsed = ParsedQuery(
        conditions=[{"type": "field", "field": "status", "op": "~", "value": "x"}]
    )
    rows, _ = await execute_query(parsed, db)
    assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# SORT direction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_query_sort_asc():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    db = _make_db([])
    parsed = ParsedQuery(sort_field="created_at", sort_dir="ASC")
    _, _ = await execute_query(parsed, db)
    db.execute.assert_called()


@pytest.mark.asyncio
async def test_execute_query_sort_desc():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    db = _make_db([])
    parsed = ParsedQuery(sort_field="modified_at", sort_dir="DESC")
    _, _ = await execute_query(parsed, db)
    db.execute.assert_called()


# ---------------------------------------------------------------------------
# owner_ids namespace scoping
# scoped_note_stmt is imported LOCALLY inside execute_query, so we must
# patch it at the source: gnosis.core.namespace.scoped_note_stmt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_query_calls_scoped_note_stmt_when_owner_ids_given():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    db = _make_db([])
    parsed = ParsedQuery()

    # scoped_note_stmt must return something that supports SQLAlchemy chaining.
    # The easiest approach: let it return the real base statement unchanged.
    # We just verify it was called.
    original_import = None

    def fake_scoped(stmt, owner_ids, **kwargs):
        fake_scoped.called = True
        fake_scoped.owner_ids = owner_ids
        return stmt  # pass through so execute() chain still works

    fake_scoped.called = False

    with patch("gnosis.core.namespace.scoped_note_stmt", side_effect=fake_scoped):
        await execute_query(parsed, db, owner_ids={1, 2})

    assert fake_scoped.called
    assert fake_scoped.owner_ids == {1, 2}


@pytest.mark.asyncio
async def test_execute_query_no_scope_when_owner_ids_none():
    from gnosis.services.query_parser import ParsedQuery, execute_query

    db = _make_db([])
    parsed = ParsedQuery()

    with patch("gnosis.core.namespace.scoped_note_stmt") as mock_scoped:
        await execute_query(parsed, db, owner_ids=None)
        mock_scoped.assert_not_called()
