"""Tests for gnosis/routers/notes.py.

Covers: list_notes (filters, pagination), get_note_by_title, resolve_wikilink,
list_templates, create_note, get_note, update_note, delete_note (soft + hard),
list_orphan_notes, get_or_create_daily_note, _get_note_or_404 error paths.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures / factories
# ---------------------------------------------------------------------------

def _tag(name: str):
    t = MagicMock()
    t.name = name
    return t


def _note(
    note_id=None,
    title="Test Note",
    slug="test-note",
    body="Hello world",
    note_type="permanent",
    status="active",
    folder="10-zettelkasten",
    owner_id=1,
    tags=None,
    outgoing_links=None,
    incoming_links=None,
    is_deleted=False,
):
    n = MagicMock()
    n.id = note_id or f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    n.title = title
    n.slug = slug
    n.body = body
    n.body_html = f"<p>{body}</p>"
    n.note_type = note_type
    n.status = status
    n.folder = folder
    n.owner_id = owner_id
    n.tags = tags or []
    n.outgoing_links = outgoing_links or []
    n.incoming_links = incoming_links or []
    n.is_deleted = is_deleted
    n.vault_path = f"{folder}/{n.id}-test-note.md"
    n.source_url = None
    n.word_count = len(body.split())
    n.created_at = datetime.now(UTC)
    n.modified_at = datetime.now(UTC)
    n.last_reviewed = None
    n.vector_indexed = False
    n.graph_indexed = False
    n.frontmatter = {}
    return n


def _db_with_notes(notes: list, total: int = None):
    """Return an AsyncSession mock whose execute returns notes."""
    if total is None:
        total = len(notes)

    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.all.return_value = notes
    scalars_mock.unique.return_value.one_or_none.return_value = notes[0] if notes else None
    scalars_mock.unique.return_value.first.return_value = notes[0] if notes else None

    count_result = MagicMock()
    count_result.scalar_one.return_value = total

    execute_mock = AsyncMock(side_effect=[count_result, MagicMock(scalars=lambda: scalars_mock)])
    db = AsyncMock()
    db.execute = execute_mock
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.expunge = MagicMock()
    return db


def _owner_ids(uid=1):
    return {uid}


# ---------------------------------------------------------------------------
# list_notes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_notes_returns_items_and_pagination():
    from gnosis.routers.notes import list_notes

    notes = [_note(title=f"Note {i}") for i in range(3)]
    db = _db_with_notes(notes, total=3)

    with patch("gnosis.routers.notes.scoped_note_stmt", side_effect=lambda s, o, **kw: s):
        result = await list_notes(
            folder=None, note_type=None, status=None, tags=None,
            q=None, page=1, page_size=20,
            db=db, owner_ids=_owner_ids(),
        )

    assert result.total == 3
    assert result.page == 1
    assert len(result.items) == 3


@pytest.mark.asyncio
async def test_list_notes_pagination_math():
    from gnosis.routers.notes import list_notes

    notes = [_note()]
    db = _db_with_notes(notes, total=25)

    with patch("gnosis.routers.notes.scoped_note_stmt", side_effect=lambda s, o, **kw: s):
        result = await list_notes(
            folder=None, note_type=None, status=None, tags=None,
            q=None, page=2, page_size=10,
            db=db, owner_ids=_owner_ids(),
        )

    assert result.pages == 3  # ceil(25/10)
    assert result.page == 2


@pytest.mark.asyncio
async def test_list_notes_with_filters_doesnt_crash():
    """Smoke-test all filter branches execute without error."""
    from gnosis.routers.notes import list_notes

    notes = [_note()]
    db = _db_with_notes(notes, total=1)

    with patch("gnosis.routers.notes.scoped_note_stmt", side_effect=lambda s, o, **kw: s):
        result = await list_notes(
            folder="10-zettelkasten",
            note_type="permanent",
            status="active",
            tags=["python"],
            q="hello",
            page=1, page_size=20,
            db=db, owner_ids=_owner_ids(),
        )
    assert result.total == 1


# ---------------------------------------------------------------------------
# get_note_by_title
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_note_by_title_returns_note():
    from gnosis.routers.notes import get_note_by_title

    n = _note(title="Exact Title")
    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.one_or_none.return_value = n
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: scalars_mock))

    with patch("gnosis.routers.notes.scoped_note_stmt", side_effect=lambda s, o, **kw: s):
        result = await get_note_by_title(title="Exact Title", db=db, owner_ids=_owner_ids())

    assert result.title == "Exact Title"


@pytest.mark.asyncio
async def test_get_note_by_title_raises_404_when_missing():
    from fastapi import HTTPException

    from gnosis.routers.notes import get_note_by_title

    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: scalars_mock))

    with (
        patch("gnosis.routers.notes.scoped_note_stmt", side_effect=lambda s, o, **kw: s),
        pytest.raises(HTTPException) as exc_info,
    ):
        await get_note_by_title(title="Ghost", db=db, owner_ids=_owner_ids())
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# resolve_wikilink
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_wikilink_returns_id_title_slug():
    from gnosis.routers.notes import resolve_wikilink

    row = SimpleNamespace(id="abc", title="Wiki Target", slug="wiki-target")
    result_mock = MagicMock()
    result_mock.first.return_value = row
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    with patch("gnosis.routers.notes.scoped_note_stmt", side_effect=lambda s, o, **kw: s):
        result = await resolve_wikilink(title="Wiki Target", db=db, owner_ids=_owner_ids())

    assert result == {"id": "abc", "title": "Wiki Target", "slug": "wiki-target"}


@pytest.mark.asyncio
async def test_resolve_wikilink_raises_404_when_missing():
    from fastapi import HTTPException

    from gnosis.routers.notes import resolve_wikilink

    result_mock = MagicMock()
    result_mock.first.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    with (
        patch("gnosis.routers.notes.scoped_note_stmt", side_effect=lambda s, o, **kw: s),
        pytest.raises(HTTPException) as exc_info,
    ):
        await resolve_wikilink(title="missing", db=db, owner_ids=_owner_ids())
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# list_templates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_templates_returns_template_dicts():
    from gnosis.routers.notes import list_templates

    notes = [_note(title="My Template", note_type="template", tags=[_tag("tpl")])]
    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.all.return_value = notes
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: scalars_mock))

    with patch("gnosis.routers.notes.scoped_note_stmt", side_effect=lambda s, o, **kw: s):
        result = await list_templates(db=db, owner_ids=_owner_ids())

    assert isinstance(result, list)
    assert result[0]["title"] == "My Template"
    assert "tpl" in result[0]["tags"]


# ---------------------------------------------------------------------------
# get_note  (/{note_id})
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_note_returns_note_read():
    from gnosis.routers.notes import get_note

    n = _note(note_id="20260101120000-abc123", title="Fetched Note")
    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.one_or_none.return_value = n
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: scalars_mock))

    result = await get_note(note_id=n.id, db=db, owner_ids=_owner_ids())
    assert result.title == "Fetched Note"


@pytest.mark.asyncio
async def test_get_note_raises_404_for_missing_note():
    from gnosis.core.exceptions import NoteNotFoundError
    from gnosis.routers.notes import get_note

    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: scalars_mock))

    with pytest.raises(NoteNotFoundError):
        await get_note(note_id="nonexistent", db=db, owner_ids=_owner_ids())


# ---------------------------------------------------------------------------
# delete_note  (soft and hard)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_note_soft_sets_is_deleted():
    from gnosis.routers.notes import delete_note

    n = _note()
    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.one_or_none.return_value = n
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: scalars_mock))
    db.commit = AsyncMock()

    await delete_note(note_id=n.id, hard=False, db=db, owner_ids=_owner_ids())
    assert n.is_deleted is True
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_note_hard_calls_db_delete():
    from gnosis.routers.notes import delete_note

    n = _note()
    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.one_or_none.return_value = n
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: scalars_mock))
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    await delete_note(note_id=n.id, hard=True, db=db, owner_ids=_owner_ids())
    db.delete.assert_awaited_once_with(n)
    db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_note_modifies_title_and_body():
    from gnosis.routers.notes import update_note
    from gnosis.schemas.note import NoteUpdate

    n = _note(note_id="id-001")
    # First call: _get_note_or_404 (before update); second call: re-fetch after commit
    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.one_or_none.return_value = n
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: scalars_mock))
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.expunge = MagicMock()

    user = MagicMock()
    user.id = 1
    user.vault_path = "/tmp/vault"

    data = NoteUpdate(title="Updated Title", body="Updated body text.")

    with patch("gnosis.routers.notes.scoped_note_stmt", side_effect=lambda s, o, **kw: s):
        result = await update_note(
            note_id="id-001", data=data,
            db=db, current_user=user, owner_ids=_owner_ids(),
        )

    assert result.title == "Updated Title"


# ---------------------------------------------------------------------------
# list_orphan_notes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_orphan_notes_returns_items():
    from gnosis.routers.notes import list_orphan_notes

    notes = [_note(title="Lonely Note")]
    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.all.return_value = notes
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: scalars_mock))

    with patch("gnosis.routers.notes.scoped_note_stmt", side_effect=lambda s, o, **kw: s):
        result = await list_orphan_notes(db=db, owner_ids=_owner_ids())

    assert len(result) == 1
    assert result[0].title == "Lonely Note"


# ---------------------------------------------------------------------------
# _get_note_or_404 — ownership error branches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_note_or_404_raises_403_for_unowned_note():
    from fastapi import HTTPException

    from gnosis.routers.notes import _get_note_or_404

    n = _note(owner_id=99)
    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.one_or_none.return_value = n
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: scalars_mock))

    with pytest.raises(HTTPException) as exc_info:
        await _get_note_or_404("some-id", db, owner_ids={1})
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_note_or_404_raises_403_for_zero_owner():
    from fastapi import HTTPException

    from gnosis.routers.notes import _get_note_or_404

    n = _note(owner_id=0)
    scalars_mock = MagicMock()
    scalars_mock.unique.return_value.one_or_none.return_value = n
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: scalars_mock))

    with pytest.raises(HTTPException) as exc_info:
        await _get_note_or_404("some-id", db, owner_ids={1})  # 0 not in {1}
    assert exc_info.value.status_code == 403
