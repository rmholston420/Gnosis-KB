"""Write-path handler tests for gnosis/routers/notes.py.

Covers create_note, update_note, delete_note, and get_or_create_daily_note.
All filesystem and DB side-effects are mocked so no real vault is needed.

Mocking strategy
----------------
- write_note_file      → patched to a no-op (avoids touching the filesystem)
- resolve_vault_path   → patched to return a tmp Path so os.makedirs is skipped
- db.add / flush / commit / expunge / delete → AsyncMock no-ops
- _get_note_or_404     → patched to return a pre-built Note MagicMock so the
  post-expunge re-fetch doesn't need a real DB round-trip
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from gnosis.routers.notes import create_note, update_note, delete_note, get_or_create_daily_note
from gnosis.schemas.note import NoteCreate, NoteUpdate
from gnosis.core.exceptions import NoteConflictError


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

def _user(uid=1, username="alice"):
    u = MagicMock()
    u.id = uid
    u.username = username
    u.vault_path = "/vaults/alice"
    return u


def _note_orm(note_id="20240101000000", title="Test Note", slug="test-note",
              body="hello", body_html="<p>hello</p>", folder="00-inbox",
              note_type="permanent", status="active", tags=None,
              incoming_links=None, outgoing_links=None, owner_id=1):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.slug = slug
    n.body = body
    n.body_html = body_html
    n.folder = folder
    n.note_type = note_type
    n.status = status
    n.tags = tags or []
    n.incoming_links = incoming_links or []
    n.outgoing_links = outgoing_links or []
    n.owner_id = owner_id
    n.source_url = None
    n.word_count = len(body.split())
    n.frontmatter = {}
    n.created_at = None
    n.modified_at = None
    n.last_reviewed = None
    n.vector_indexed = False
    n.graph_indexed = False
    n.is_deleted = False
    n.vault_path = f"00-inbox/{note_id}-test-note.md"
    return n


def _db_no_conflict():
    """Session where slug conflict check returns None (no existing note)."""
    r = MagicMock()
    r.scalars.return_value.unique.return_value.one_or_none.return_value = None
    r.scalars.return_value.all.return_value = []
    r.scalar_one_or_none.return_value = None  # Tag lookup
    sess = AsyncMock()
    sess.execute = AsyncMock(return_value=r)
    return sess


def _db_with_conflict():
    """Session where slug conflict check returns an existing note."""
    r = MagicMock()
    r.scalars.return_value.unique.return_value.one_or_none.return_value = _note_orm()
    sess = AsyncMock()
    sess.execute = AsyncMock(return_value=r)
    return sess


# ---------------------------------------------------------------------------
# create_note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_note_happy_path():
    """create_note writes file, inserts note, returns NoteRead."""
    user = _user()
    db = _db_no_conflict()
    returned_note = _note_orm(title="My Note")

    data = NoteCreate(
        title="My Note",
        body="Some body text.",
        folder="00-inbox",
        note_type="permanent",
        status="draft",
        tags=[],
    )

    with (
        patch("gnosis.routers.notes.write_note_file") as mock_write,
        patch("gnosis.routers.notes.resolve_vault_path", return_value=Path("/tmp/vault")),
        patch("gnosis.routers.notes._get_note_or_404", AsyncMock(return_value=returned_note)),
    ):
        result = await create_note(data=data, db=db, current_user=user)

    mock_write.assert_called_once()
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    assert result.title == "My Note"


@pytest.mark.asyncio
async def test_create_note_slug_conflict_raises():
    """create_note raises NoteConflictError when slug already exists."""
    user = _user()
    db = _db_with_conflict()

    data = NoteCreate(
        title="Existing Note",
        body="body",
        folder="00-inbox",
        note_type="permanent",
        status="draft",
        tags=[],
    )

    with (
        patch("gnosis.routers.notes.write_note_file"),
        patch("gnosis.routers.notes.resolve_vault_path", return_value=Path("/tmp/vault")),
    ):
        with pytest.raises(NoteConflictError):
            await create_note(data=data, db=db, current_user=user)


@pytest.mark.asyncio
async def test_create_note_with_tags_calls_upsert():
    """create_note calls _upsert_tags when tags are supplied."""
    user = _user()
    db = _db_no_conflict()
    returned_note = _note_orm(title="Tagged Note", tags=[MagicMock(name="zettel")])

    data = NoteCreate(
        title="Tagged Note",
        body="body",
        folder="10-zettelkasten",
        note_type="permanent",
        status="active",
        tags=["zettel", "idea"],
    )

    with (
        patch("gnosis.routers.notes.write_note_file"),
        patch("gnosis.routers.notes.resolve_vault_path", return_value=Path("/tmp/vault")),
        patch("gnosis.routers.notes._get_note_or_404", AsyncMock(return_value=returned_note)),
        patch("gnosis.routers.notes._upsert_tags", AsyncMock()) as mock_upsert,
    ):
        result = await create_note(data=data, db=db, current_user=user)

    mock_upsert.assert_awaited_once()
    call_tags = mock_upsert.call_args[0][1]  # second positional arg is tag_names
    assert set(call_tags) == {"zettel", "idea"}


@pytest.mark.asyncio
async def test_create_note_vault_write_error_raises():
    """create_note wraps filesystem errors in VaultWriteError."""
    from gnosis.core.exceptions import VaultWriteError
    user = _user()
    db = _db_no_conflict()

    data = NoteCreate(
        title="Boom Note",
        body="body",
        folder="00-inbox",
        note_type="permanent",
        status="draft",
        tags=[],
    )

    with (
        patch("gnosis.routers.notes.write_note_file", side_effect=OSError("disk full")),
        patch("gnosis.routers.notes.resolve_vault_path", return_value=Path("/tmp/vault")),
    ):
        with pytest.raises(VaultWriteError):
            await create_note(data=data, db=db, current_user=user)


# ---------------------------------------------------------------------------
# update_note
# ---------------------------------------------------------------------------

def _db_for_update(existing_note):
    """Session that returns existing_note for the initial _get_note_or_404 call.

    update_note calls _get_note_or_404 twice: once at the top to fetch the
    existing note, once at the end after expunge.  We patch _get_note_or_404
    globally so the DB session only needs to handle tag-related queries.
    """
    r = MagicMock()
    r.scalars.return_value.all.return_value = []
    r.scalar_one_or_none.return_value = None
    sess = AsyncMock()
    sess.execute = AsyncMock(return_value=r)
    return sess


@pytest.mark.asyncio
async def test_update_note_title_and_body():
    """update_note applies title/body changes and returns updated NoteRead."""
    user = _user()
    existing = _note_orm(note_id="n1", title="Old Title", body="old body")
    updated = _note_orm(note_id="n1", title="New Title", body="new body")
    db = _db_for_update(existing)

    with (
        patch("gnosis.routers.notes._get_note_or_404",
              AsyncMock(side_effect=[existing, updated])),
        patch("gnosis.routers.notes.resolve_vault_path", return_value=Path("/tmp/vault")),
        patch("gnosis.routers.notes.write_note_file"),
    ):
        result = await update_note(
            note_id="n1",
            data=NoteUpdate(title="New Title", body="new body"),
            db=db,
            current_user=user,
            owner_ids={1},
        )

    db.commit.assert_awaited_once()
    assert result.title == "New Title"


@pytest.mark.asyncio
async def test_update_note_tags_replaced():
    """update_note deletes old tag associations and calls _upsert_tags."""
    user = _user()
    existing = _note_orm(note_id="n1")
    refreshed = _note_orm(note_id="n1")
    db = _db_for_update(existing)

    with (
        patch("gnosis.routers.notes._get_note_or_404",
              AsyncMock(side_effect=[existing, refreshed])),
        patch("gnosis.routers.notes.resolve_vault_path", return_value=Path("/tmp/vault")),
        patch("gnosis.routers.notes.write_note_file"),
        patch("gnosis.routers.notes._upsert_tags", AsyncMock()) as mock_upsert,
    ):
        await update_note(
            note_id="n1",
            data=NoteUpdate(tags=["new-tag"]),
            db=db,
            current_user=user,
            owner_ids={1},
        )

    mock_upsert.assert_awaited_once()
    assert mock_upsert.call_args[0][1] == ["new-tag"]


@pytest.mark.asyncio
async def test_update_note_status_only():
    """update_note with only status change does not touch body or tags."""
    user = _user()
    existing = _note_orm(note_id="n1", status="draft")
    refreshed = _note_orm(note_id="n1", status="active")
    db = _db_for_update(existing)

    with (
        patch("gnosis.routers.notes._get_note_or_404",
              AsyncMock(side_effect=[existing, refreshed])),
        patch("gnosis.routers.notes.resolve_vault_path", return_value=Path("/tmp/vault")),
        patch("gnosis.routers.notes.write_note_file"),
        patch("gnosis.routers.notes._upsert_tags", AsyncMock()) as mock_upsert,
    ):
        result = await update_note(
            note_id="n1",
            data=NoteUpdate(status="active"),
            db=db,
            current_user=user,
            owner_ids={1},
        )

    mock_upsert.assert_not_awaited()
    assert result.status == "active"


@pytest.mark.asyncio
async def test_update_note_missing_raises_404():
    """update_note propagates NoteNotFoundError (→ 404) from _get_note_or_404."""
    from gnosis.core.exceptions import NoteNotFoundError
    user = _user()
    db = _db_for_update(None)

    with patch(
        "gnosis.routers.notes._get_note_or_404",
        AsyncMock(side_effect=NoteNotFoundError("n1")),
    ):
        with pytest.raises((NoteNotFoundError, HTTPException)):
            await update_note(
                note_id="n1",
                data=NoteUpdate(title="X"),
                db=db,
                current_user=user,
                owner_ids={1},
            )


# ---------------------------------------------------------------------------
# delete_note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_note_soft():
    """Soft delete sets is_deleted=True, does NOT call db.delete."""
    note = _note_orm(note_id="n1")
    db = AsyncMock()

    with patch("gnosis.routers.notes._get_note_or_404", AsyncMock(return_value=note)):
        await delete_note(note_id="n1", hard=False, db=db, owner_ids={1})

    assert note.is_deleted is True
    db.delete.assert_not_awaited()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_note_hard():
    """Hard delete calls db.delete(note), not just is_deleted=True."""
    note = _note_orm(note_id="n1")
    db = AsyncMock()

    with patch("gnosis.routers.notes._get_note_or_404", AsyncMock(return_value=note)):
        await delete_note(note_id="n1", hard=True, db=db, owner_ids={1})

    db.delete.assert_awaited_once_with(note)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_note_missing_raises():
    """delete_note raises when the note is not found."""
    from gnosis.core.exceptions import NoteNotFoundError
    db = AsyncMock()

    with patch(
        "gnosis.routers.notes._get_note_or_404",
        AsyncMock(side_effect=NoteNotFoundError("missing")),
    ):
        with pytest.raises((NoteNotFoundError, HTTPException)):
            await delete_note(note_id="missing", hard=False, db=db, owner_ids={1})


# ---------------------------------------------------------------------------
# get_or_create_daily_note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_note_existing_returned():
    """When a daily note already exists, it is returned without creating a new one."""
    user = _user()
    existing = _note_orm(note_id="daily1", note_type="journal")
    r = MagicMock()
    r.scalars.return_value.unique.return_value.one_or_none.return_value = existing
    db = AsyncMock()
    db.execute = AsyncMock(return_value=r)

    result = await get_or_create_daily_note(
        db=db, current_user=user, owner_ids={1}
    )

    db.add.assert_not_called()
    assert result.note_type == "journal"


@pytest.mark.asyncio
async def test_daily_note_creates_when_missing():
    """When no daily note exists, a new one is created and returned."""
    user = _user()
    new_note = _note_orm(note_id="daily2", note_type="journal", title="Daily Note — 2026-06-20")
    r = MagicMock()
    r.scalars.return_value.unique.return_value.one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=r)

    with (
        patch("gnosis.routers.notes.write_note_file"),
        patch("gnosis.routers.notes.resolve_vault_path", return_value=Path("/tmp/vault")),
        patch("gnosis.routers.notes._get_note_or_404", AsyncMock(return_value=new_note)),
    ):
        result = await get_or_create_daily_note(
            db=db, current_user=user, owner_ids={1}
        )

    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    assert result.note_type == "journal"
