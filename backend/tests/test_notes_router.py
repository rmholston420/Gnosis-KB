"""Unit tests for gnosis/routers/notes.py — no DB, no HTTP client.

Tests call handler functions directly; DB dependencies are replaced by
AsyncMock sessions, and auth dependencies are bypassed via direct kwargs.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from gnosis.routers.notes import (
    _note_to_read,
    _get_note_or_404,
    _upsert_tags,
    list_notes,
    get_note_by_title,
    resolve_wikilink,
    list_templates,
    list_orphan_notes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


def _note(id="n1", title="T", tags=None, outgoing=None, incoming=None,
          folder="00-inbox", note_type="permanent", status="active",
          owner_id=1, is_deleted=False):
    n = MagicMock()
    n.id = id; n.title = title; n.slug = "t"; n.body = "Body."; n.body_html = "<p>Body.</p>"
    n.note_type = note_type; n.status = status; n.vault_path = f"{folder}/{id}.md"
    n.folder = folder; n.source_url = None; n.word_count = 1
    n.created_at = _now(); n.modified_at = _now(); n.last_reviewed = None
    n.is_deleted = is_deleted; n.vector_indexed = False; n.graph_indexed = False
    n.frontmatter = {}; n.owner_id = owner_id
    n.tags = tags if tags is not None else []
    n.outgoing_links = outgoing or []
    n.incoming_links = incoming or []
    return n


def _tag(name):
    t = MagicMock(); t.name = name; return t


def _session_exec(rows=None, scalar=None):
    """Session whose .execute() always returns rows via scalars().unique().all()
    or scalar_one_or_none()."""
    sess = AsyncMock()
    r = MagicMock()
    r.scalar_one_or_none.return_value = scalar
    r.scalar_one.return_value = len(rows) if rows is not None else 0
    r.scalars.return_value.unique.return_value.all.return_value = rows or []
    r.scalars.return_value.unique.return_value.one_or_none.return_value = scalar
    r.first.return_value = scalar
    sess.execute = AsyncMock(return_value=r)
    sess.flush = AsyncMock()
    sess.commit = AsyncMock()
    sess.add = MagicMock()
    return sess


# ---------------------------------------------------------------------------
# _note_to_read()
# ---------------------------------------------------------------------------

def test_note_to_read_basic():
    note = _note(id="abc", title="Alpha", tags=[_tag("x"), _tag("y")])
    read = _note_to_read(note)
    assert read.id == "abc"
    assert read.tags == ["x", "y"]


def test_note_to_read_tags_not_list_returns_empty():
    """Regression: if note.tags is not a list (uselist=False bug) we get []."""
    note = _note()
    note.tags = None  # simulate collapsed uselist=False scalar
    read = _note_to_read(note)
    assert read.tags == []


def test_note_to_read_tags_scalar_returns_empty():
    """If tags is a single Tag object (uselist=False returning 1 row), guard returns []."""
    note = _note()
    note.tags = _tag("only-one")  # scalar, not a list
    read = _note_to_read(note)
    assert read.tags == []


def test_note_to_read_links_populated():
    lnk = MagicMock(source_id="n1", target_id="n2",
                    link_text="n2", link_type="wikilink", context=None)
    note = _note(id="n1", outgoing=[lnk])
    read = _note_to_read(note)
    assert len(read.outgoing_links) == 1
    assert read.outgoing_links[0].target_id == "n2"


# ---------------------------------------------------------------------------
# _get_note_or_404()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_note_or_404_found():
    note = _note(id="n1", owner_id=1)
    sess = _session_exec(scalar=note)
    result = await _get_note_or_404("n1", sess, {1})
    assert result.id == "n1"


@pytest.mark.asyncio
async def test_get_note_or_404_missing_raises():
    from gnosis.core.exceptions import NoteNotFoundError
    sess = _session_exec(scalar=None)
    with pytest.raises(NoteNotFoundError):
        await _get_note_or_404("ghost", sess, {1})


@pytest.mark.asyncio
async def test_get_note_or_404_wrong_owner_raises_403():
    note = _note(id="n1", owner_id=99)
    sess = _session_exec(scalar=note)
    with pytest.raises(HTTPException) as exc_info:
        await _get_note_or_404("n1", sess, {1})
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_note_or_404_zero_owner_no_access_raises_403():
    note = _note(id="n1", owner_id=0)
    sess = _session_exec(scalar=note)
    with pytest.raises(HTTPException) as exc_info:
        await _get_note_or_404("n1", sess, {1})
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# list_notes()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_notes_empty():
    sess = _session_exec(rows=[], scalar=0)
    # make count query return 0
    call = [0]
    async def _exec(stmt, *a, **kw):
        call[0] += 1
        r = MagicMock()
        r.scalar_one.return_value = 0
        r.scalars.return_value.unique.return_value.all.return_value = []
        return r
    sess.execute = _exec
    result = await list_notes(
        folder=None, note_type=None, status=None, tags=None, q=None,
        page=1, page_size=20, db=sess, owner_ids={1},
    )
    assert result.total == 0
    assert result.items == []


@pytest.mark.asyncio
async def test_list_notes_with_filters():
    notes = [_note(id=f"n{i}", tags=[_tag("x")]) for i in range(3)]
    call = [0]
    async def _exec(stmt, *a, **kw):
        call[0] += 1
        r = MagicMock()
        r.scalar_one.return_value = 3
        r.scalars.return_value.unique.return_value.all.return_value = notes
        return r
    sess = AsyncMock()
    sess.execute = _exec
    result = await list_notes(
        folder="00-inbox", note_type="permanent", status="active",
        tags=["x"], q="Body",
        page=1, page_size=20, db=sess, owner_ids={1},
    )
    assert result.total == 3
    assert len(result.items) == 3


# ---------------------------------------------------------------------------
# get_note_by_title()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_note_by_title_found():
    note = _note(title="Alpha")
    sess = _session_exec(scalar=note)
    result = await get_note_by_title(title="Alpha", db=sess, owner_ids={1})
    assert result.title == "Alpha"


@pytest.mark.asyncio
async def test_get_note_by_title_not_found_raises_404():
    sess = _session_exec(scalar=None)
    with pytest.raises(HTTPException) as exc_info:
        await get_note_by_title(title="Ghost", db=sess, owner_ids={1})
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# resolve_wikilink()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_wikilink_found():
    row = MagicMock(id="n1", title="Alpha", slug="alpha")
    r = MagicMock(); r.first.return_value = row
    sess = AsyncMock(); sess.execute = AsyncMock(return_value=r)
    result = await resolve_wikilink(title="Alpha", db=sess, owner_ids={1})
    assert result["id"] == "n1"


@pytest.mark.asyncio
async def test_resolve_wikilink_not_found_raises_404():
    r = MagicMock(); r.first.return_value = None
    sess = AsyncMock(); sess.execute = AsyncMock(return_value=r)
    with pytest.raises(HTTPException) as exc_info:
        await resolve_wikilink(title="Ghost", db=sess, owner_ids={1})
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# list_templates()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_templates_returns_list():
    tmpl = _note(id="t1", note_type="template", tags=[_tag("tmpl")])
    r = MagicMock()
    r.scalars.return_value.unique.return_value.all.return_value = [tmpl]
    sess = AsyncMock(); sess.execute = AsyncMock(return_value=r)
    result = await list_templates(db=sess, owner_ids={1})
    assert len(result) == 1
    assert result[0]["id"] == "t1"


# ---------------------------------------------------------------------------
# list_orphan_notes()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_orphans_empty():
    r = MagicMock()
    r.scalars.return_value.unique.return_value.all.return_value = []
    sess = AsyncMock(); sess.execute = AsyncMock(return_value=r)
    result = await list_orphan_notes(db=sess, owner_ids={1})
    assert result == []


@pytest.mark.asyncio
async def test_list_orphans_returns_items():
    orphan = _note(id="o1", tags=[])
    r = MagicMock()
    r.scalars.return_value.unique.return_value.all.return_value = [orphan]
    sess = AsyncMock(); sess.execute = AsyncMock(return_value=r)
    result = await list_orphan_notes(db=sess, owner_ids={1})
    assert len(result) == 1
    assert result[0].id == "o1"


# ---------------------------------------------------------------------------
# _upsert_tags() — regression: always inserts via association table, never
# touches Note.tags ORM collection (avoids the uselist=False collapse bug)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_tags_creates_missing_tag():
    """When the tag doesn't exist yet, a new Tag row is added and flushed."""
    call = [0]
    async def _exec(stmt, *a, **kw):
        call[0] += 1
        r = MagicMock()
        # First call: select(Tag) → not found; second call: insert NoteTag
        r.scalar_one_or_none.return_value = None
        return r
    sess = AsyncMock()
    sess.execute = _exec
    sess.flush = AsyncMock()
    sess.add = MagicMock()
    await _upsert_tags("n1", ["newtag"], sess)
    sess.add.assert_called_once()  # Tag row added
    sess.flush.assert_awaited()  # flushed before FK insert


@pytest.mark.asyncio
async def test_upsert_tags_existing_tag_no_add():
    """When the tag already exists, no new Tag is added."""
    existing_tag = _tag("existing")
    call = [0]
    async def _exec(stmt, *a, **kw):
        call[0] += 1
        r = MagicMock()
        r.scalar_one_or_none.return_value = existing_tag
        return r
    sess = AsyncMock()
    sess.execute = _exec
    sess.flush = AsyncMock()
    sess.add = MagicMock()
    await _upsert_tags("n1", ["existing"], sess)
    sess.add.assert_not_called()  # no new Tag row


@pytest.mark.asyncio
async def test_upsert_tags_empty_list_is_noop():
    sess = AsyncMock()
    sess.execute = AsyncMock()
    await _upsert_tags("n1", [], sess)
    sess.execute.assert_not_called()
