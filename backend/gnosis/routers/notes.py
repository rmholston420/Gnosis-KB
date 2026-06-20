"""Notes CRUD router."""

import math
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from slugify import slugify
from sqlalchemy import func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gnosis.config import get_settings
from gnosis.core.exceptions import NoteConflictError, NoteNotFoundError, VaultWriteError
from gnosis.core.namespace import scoped_note_stmt
from gnosis.database import get_db
from gnosis.models.link import Link
from gnosis.models.note import Note
from gnosis.models.tag import NoteTag, Tag
from gnosis.models.user import User
from gnosis.schemas.note import (
    NoteCreate,
    NoteListItem,
    NoteListResponse,
    NoteRead,
    NoteUpdate,
)
from gnosis.services.markdown_parser import (
    build_default_frontmatter,
    generate_note_id,
    write_note_file,
)
from gnosis.core.auth import get_current_user, get_vault_owner_ids

router = APIRouter(prefix="/notes", tags=["notes"])


# ---------------------------------------------------------------------------
# Helper: upsert tags via association table (bypasses ORM collection)
# ---------------------------------------------------------------------------


async def _upsert_tags(note_id: str, tag_names: list[str], db: AsyncSession) -> None:
    """Insert note<->tag associations directly into the note_tags table.

    This avoids touching the Note.tags ORM collection, which is uninitialised
    on a brand-new Note instance until the object is loaded from the DB.
    vault_sync.py uses the same pattern.
    """
    for tag_name in tag_names:
        tag_result = await db.execute(select(Tag).where(Tag.name == tag_name))
        tag = tag_result.scalar_one_or_none()
        if tag is None:
            tag = Tag(name=tag_name)
            db.add(tag)
            await db.flush()  # ensure Tag row exists before FK insert
        # Upsert the association row; ignore if it already exists.
        await db.execute(
            insert(NoteTag)
            .values(note_id=note_id, tag_id=tag_name)
            .prefix_with("OR IGNORE")  # SQLite; Postgres uses ON CONFLICT DO NOTHING
        )


# ---------------------------------------------------------------------------
# Helper: load note with relationships + ownership check
# ---------------------------------------------------------------------------


async def _get_note_or_404(
    note_id: str,
    db: AsyncSession,
    owner_ids: set[int],
) -> Note:
    raw = await db.execute(
        select(Note)
        .options(
            selectinload(Note.tags),
            selectinload(Note.outgoing_links),
            selectinload(Note.incoming_links),
        )
        .where(Note.id == note_id, Note.is_deleted.is_(False))
    )
    note = raw.scalars().unique().one_or_none()
    if note is None:
        raise NoteNotFoundError(note_id)

    if note.owner_id == 0 and 0 not in owner_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This note has no owner assigned. Run scripts/fix_owner_ids.py to reassign.",
        )

    if note.owner_id is not None and note.owner_id not in owner_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this note's vault.",
        )
    return note


def _note_to_read(note: Note) -> NoteRead:
    from gnosis.schemas.note import LinkSchema
    tags = note.tags if isinstance(note.tags, list) else []
    return NoteRead(
        id=note.id,
        title=note.title,
        slug=note.slug,
        body=note.body,
        body_html=note.body_html,
        note_type=note.note_type,
        status=note.status,
        vault_path=note.vault_path,
        folder=note.folder,
        source_url=note.source_url,
        word_count=note.word_count,
        created_at=note.created_at,
        modified_at=note.modified_at,
        last_reviewed=note.last_reviewed,
        is_deleted=note.is_deleted,
        vector_indexed=note.vector_indexed,
        graph_indexed=note.graph_indexed,
        frontmatter=note.frontmatter or {},
        tags=[t.name for t in tags],
        outgoing_links=[
            LinkSchema(
                source_id=lnk.source_id,
                target_id=lnk.target_id,
                link_text=lnk.link_text,
                link_type=lnk.link_type,
                context=lnk.context,
            )
            for lnk in (note.outgoing_links or [])
        ],
        incoming_links=[
            LinkSchema(
                source_id=lnk.source_id,
                target_id=lnk.target_id,
                link_text=lnk.link_text,
                link_type=lnk.link_type,
                context=lnk.context,
            )
            for lnk in (note.incoming_links or [])
        ],
    )


# ---------------------------------------------------------------------------
# List notes
# ---------------------------------------------------------------------------


@router.get("/", response_model=NoteListResponse, summary="List notes")
async def list_notes(
    folder: Optional[str] = Query(None),
    note_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tags: Optional[list[str]] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteListResponse:
    query = scoped_note_stmt(
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.is_deleted.is_(False)),
        owner_ids,
    )

    if folder:
        query = query.where(Note.folder == folder)
    if note_type:
        query = query.where(Note.note_type == note_type)
    if status:
        query = query.where(Note.status == status)
    if tags:
        for tag in tags:
            query = query.where(
                Note.id.in_(select(NoteTag.c.note_id).where(NoteTag.c.tag_id == tag))
            )
    if q:
        query = query.where(
            or_(
                Note.title.ilike(f"%{q}%"),
                Note.body.ilike(f"%{q}%"),
            )
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    query = query.order_by(Note.modified_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().unique().all()

    items = [
        NoteListItem(
            id=n.id,
            title=n.title,
            slug=n.slug,
            note_type=n.note_type,
            status=n.status,
            folder=n.folder,
            word_count=n.word_count,
            created_at=n.created_at,
            modified_at=n.modified_at,
            tags=[t.name for t in (n.tags or [])],
        )
        for n in rows
    ]
    return NoteListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


# ---------------------------------------------------------------------------
# Title-based lookup  (GET /notes/by-title) — BEFORE /{note_id}
# ---------------------------------------------------------------------------


@router.get("/by-title", response_model=NoteRead, summary="Get note by title")
async def get_note_by_title(
    title: str = Query(..., description="Exact title to look up"),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteRead:
    stmt = scoped_note_stmt(
        select(Note)
        .options(
            selectinload(Note.tags),
            selectinload(Note.outgoing_links),
            selectinload(Note.incoming_links),
        )
        .where(Note.title == title, Note.is_deleted.is_(False)),
        owner_ids,
    )
    result = await db.execute(stmt)
    note = result.scalars().unique().one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note with title '{title}' not found")
    return _note_to_read(note)


# ---------------------------------------------------------------------------
# Wikilink title search  (GET /notes/wikilink) — BEFORE /{note_id}
# ---------------------------------------------------------------------------


@router.get("/wikilink", summary="Resolve a wikilink title to a note ID")
async def resolve_wikilink(
    title: str = Query(...),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict:
    stmt = scoped_note_stmt(
        select(Note.id, Note.title, Note.slug)
        .where(
            Note.title.ilike(title),
            Note.is_deleted.is_(False),
        ),
        owner_ids,
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No note found for wikilink '[[{title}]]'")
    return {"id": row.id, "title": row.title, "slug": row.slug}


# ---------------------------------------------------------------------------
# Templates  (GET /notes/templates) — BEFORE /{note_id}
# ---------------------------------------------------------------------------


@router.get("/templates", summary="List available note templates")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[dict]:
    stmt = scoped_note_stmt(
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.note_type == "template", Note.is_deleted.is_(False)),
        owner_ids,
    )
    rows = (await db.execute(stmt)).scalars().unique().all()
    return [
        {"id": n.id, "title": n.title, "folder": n.folder, "tags": [t.name for t in (n.tags or [])]}
        for n in rows
    ]


# ---------------------------------------------------------------------------
# Create note
# ---------------------------------------------------------------------------


@router.post("/", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
async def create_note(
    data: NoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    from gnosis.core.namespace import resolve_vault_path

    # Append a short uuid hex suffix to the timestamp ID so two notes created
    # in the same second (common in fast async tests) never collide on notes.id.
    note_id = data.id or f"{generate_note_id()}-{uuid.uuid4().hex[:6]}"
    title = data.title
    slug = slugify(title)
    owner_ids = {current_user.id}

    existing_stmt = scoped_note_stmt(
        select(Note).where(Note.slug == slug, Note.is_deleted.is_(False)),
        owner_ids, include_null_owner=False,
    )
    existing = await db.execute(existing_stmt)
    if existing.scalars().unique().one_or_none():
        raise NoteConflictError(title)

    fm = build_default_frontmatter(
        note_id=note_id, title=title, note_type=data.note_type,
        status=data.status, tags=data.tags, source_url=data.source_url,
    )
    fm.update(data.frontmatter)

    vault_root = resolve_vault_path(current_user)
    vault_dir = vault_root / data.folder
    filename = f"{note_id}-{slug[:50]}.md"
    vault_path_rel = f"{data.folder}/{filename}"

    try:
        write_note_file(vault_root / data.folder / filename, title, data.body, fm)
    except Exception as e:
        raise VaultWriteError(str(vault_root / data.folder / filename), str(e)) from e

    import mistune
    renderer = mistune.create_markdown(
        plugins=["strikethrough", "footnotes", "table", "task_lists"]
    )
    body_html = str(renderer(data.body))

    note = Note(
        id=note_id, title=title, slug=slug, body=data.body, body_html=body_html,
        note_type=data.note_type, status=data.status, vault_path=vault_path_rel,
        folder=data.folder, source_url=data.source_url,
        word_count=len(data.body.split()), frontmatter=fm,
        last_reviewed=data.last_reviewed, is_deleted=False,
        vector_indexed=False, graph_indexed=False, owner_id=current_user.id,
    )
    db.add(note)
    await db.flush()  # INSERT note row so FK in note_tags is valid

    if data.tags:
        await _upsert_tags(note_id, data.tags, db)

    await db.commit()
    # Expire the note instance so the identity map does not serve stale
    # attribute state (tags=[]) to the selectinload in _get_note_or_404.
    # expire_on_commit=False is set in conftest for test isolation; without
    # this explicit expire the re-query would collide with the cached empty
    # collection and return tags=[].
    db.expire(note)
    note = await _get_note_or_404(note_id, db, owner_ids)
    return _note_to_read(note)


# ---------------------------------------------------------------------------
# Orphan notes
# ---------------------------------------------------------------------------


@router.get("/orphans", response_model=list[NoteListItem])
async def list_orphan_notes(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[NoteListItem]:
    """Return notes with no incoming or outgoing wikilinks."""
    from gnosis.models.link import Link

    linked_ids_stmt = select(Link.source_id).union(select(Link.target_id))
    stmt = scoped_note_stmt(
        select(Note)
        .options(selectinload(Note.tags))
        .where(
            Note.is_deleted.is_(False),
            Note.id.not_in(linked_ids_stmt),
        ),
        owner_ids,
    )
    rows = (await db.execute(stmt)).scalars().unique().all()
    return [
        NoteListItem(
            id=n.id, title=n.title, slug=n.slug, note_type=n.note_type,
            status=n.status, folder=n.folder, word_count=n.word_count,
            created_at=n.created_at, modified_at=n.modified_at,
            tags=[t.name for t in (n.tags or [])],
        )
        for n in rows
    ]


# ---------------------------------------------------------------------------
# Daily note
# ---------------------------------------------------------------------------


@router.post("/daily", response_model=NoteRead, summary="Get or create today's daily note")
async def get_or_create_daily_note(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteRead:
    from gnosis.core.namespace import resolve_vault_path

    today = date.today()
    today_str = today.isoformat()
    folder = "60-journals"

    existing_stmt = scoped_note_stmt(
        select(Note)
        .options(
            selectinload(Note.tags),
            selectinload(Note.outgoing_links),
            selectinload(Note.incoming_links),
        )
        .where(
            Note.folder == folder,
            Note.title == f"Daily Note — {today_str}",
            Note.is_deleted.is_(False),
        ),
        owner_ids,
    )
    result = await db.execute(existing_stmt)
    note = result.scalars().unique().one_or_none()
    if note:
        return _note_to_read(note)

    # Create a new daily note
    import mistune
    from gnosis.services.markdown_parser import build_default_frontmatter, write_note_file
    from gnosis.core.namespace import resolve_vault_path

    note_id = f"{generate_note_id(datetime.combine(today, datetime.min.time()))}-{uuid.uuid4().hex[:4]}"
    title = f"Daily Note — {today_str}"
    slug = slugify(title)
    body = f"# {title}\n\n"
    fm = build_default_frontmatter(
        note_id=note_id, title=title, note_type="journal",
        status="active", tags=[], source_url=None,
    )
    vault_root = resolve_vault_path(current_user)
    filename = f"{note_id}-{slug[:50]}.md"
    vault_path_rel = f"{folder}/{filename}"
    try:
        write_note_file(vault_root / folder / filename, title, body, fm)
    except Exception as e:
        raise VaultWriteError(str(vault_root / folder / filename), str(e)) from e

    renderer = mistune.create_markdown(
        plugins=["strikethrough", "footnotes", "table", "task_lists"]
    )
    body_html = str(renderer(body))

    note = Note(
        id=note_id, title=title, slug=slug, body=body, body_html=body_html,
        note_type="journal", status="active", vault_path=vault_path_rel,
        folder=folder, word_count=len(body.split()), frontmatter=fm,
        is_deleted=False, vector_indexed=False, graph_indexed=False,
        owner_id=current_user.id,
    )
    db.add(note)
    await db.flush()  # INSERT note row before FK
    # Daily notes have no tags — no _upsert_tags call needed.
    await db.commit()
    # Expire so _get_note_or_404's selectinload fires a real SELECT.
    db.expire(note)
    note = await _get_note_or_404(note_id, db, owner_ids)
    return _note_to_read(note)


# ---------------------------------------------------------------------------
# Get / update / delete single note
# ---------------------------------------------------------------------------


@router.get("/{note_id}", response_model=NoteRead)
async def get_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteRead:
    note = await _get_note_or_404(note_id, db, owner_ids)
    return _note_to_read(note)


@router.put("/{note_id}", response_model=NoteRead)
async def update_note(
    note_id: str,
    data: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteRead:
    from gnosis.core.namespace import resolve_vault_path
    from sqlalchemy import delete

    note = await _get_note_or_404(note_id, db, owner_ids)

    if data.title is not None:
        note.title = data.title
        note.slug = slugify(data.title)
    if data.body is not None:
        note.body = data.body
        import mistune
        renderer = mistune.create_markdown(
            plugins=["strikethrough", "footnotes", "table", "task_lists"]
        )
        note.body_html = str(renderer(data.body))
        note.word_count = len(data.body.split())
    if data.note_type is not None:
        note.note_type = data.note_type
    if data.status is not None:
        note.status = data.status
    if data.folder is not None:
        note.folder = data.folder
    if data.source_url is not None:
        note.source_url = data.source_url
    if data.last_reviewed is not None:
        note.last_reviewed = data.last_reviewed
    if data.frontmatter is not None:
        existing_fm = note.frontmatter or {}
        existing_fm.update(data.frontmatter)
        note.frontmatter = existing_fm

    if data.tags is not None:
        # Replace all tags: delete existing associations, re-insert new ones.
        await db.execute(delete(NoteTag).where(NoteTag.c.note_id == note_id))
        await db.flush()
        await _upsert_tags(note_id, data.tags, db)

    await db.flush()
    await db.commit()
    # Expire so the re-fetch gets fresh tag state, not the cached collection.
    db.expire(note)
    note = await _get_note_or_404(note_id, db, owner_ids)
    return _note_to_read(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    hard: bool = Query(False, description="Permanently delete instead of soft-delete"),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> None:
    note = await _get_note_or_404(note_id, db, owner_ids)
    if hard:
        await db.delete(note)
    else:
        note.is_deleted = True
    await db.commit()
