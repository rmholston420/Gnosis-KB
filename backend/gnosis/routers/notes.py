"""Notes CRUD router."""

import math
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

    This avoids touching the Note.tags ORM collection, which is None on a
    brand-new Note instance (lazy='selectin' does not initialise the list
    until the object is loaded from the DB).  vault_sync.py uses the same
    pattern.
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
    if q:
        query = query.where(Note.title.ilike(f"%{q}%"))
    if tags:
        for tag in tags:
            query = query.where(
                Note.id.in_(select(NoteTag.c.note_id).where(NoteTag.c.tag_id == tag))
            )

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()
    query = query.order_by(Note.modified_at.desc().nullslast(), Note.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    notes = result.scalars().unique().all()

    return NoteListResponse(
        items=[
            NoteListItem(
                id=n.id, title=n.title, slug=n.slug, note_type=n.note_type,
                status=n.status, folder=n.folder, word_count=n.word_count,
                created_at=n.created_at, modified_at=n.modified_at,
                tags=[t.name for t in (n.tags if isinstance(n.tags, list) else [])],
            )
            for n in notes
        ],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


# ---------------------------------------------------------------------------
# Wikilink title search  (GET /notes/by-title) — BEFORE /{note_id}
# ---------------------------------------------------------------------------


@router.get("/by-title", response_model=NoteListResponse)
async def notes_by_title(
    q: str = Query(...),
    page_size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteListResponse:
    query = scoped_note_stmt(
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.is_deleted.is_(False), Note.title.ilike(f"%{q}%")),
        owner_ids,
    )
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()
    query = query.order_by(Note.title).limit(page_size)
    result = await db.execute(query)
    notes = result.scalars().unique().all()
    return NoteListResponse(
        items=[
            NoteListItem(
                id=n.id, title=n.title, slug=n.slug, note_type=n.note_type,
                status=n.status, folder=n.folder, word_count=n.word_count,
                created_at=n.created_at, modified_at=n.modified_at,
                tags=[t.name for t in (n.tags if isinstance(n.tags, list) else [])],
            )
            for n in notes
        ],
        total=total, page=1, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


# ---------------------------------------------------------------------------
# Templates  (GET /notes/templates) — BEFORE /{note_id}
# ---------------------------------------------------------------------------


@router.get("/templates", summary="List available note templates")
async def list_templates() -> list[dict]:
    return [
        {"id": "blank", "name": "Blank Note", "description": "Start with an empty canvas.",
         "note_type": "permanent", "folder": "10-zettelkasten", "body": "", "icon": "file"},
        {"id": "zettel", "name": "Zettelkasten Slip",
         "description": "Atomic concept note with one clear idea.",
         "note_type": "permanent", "folder": "10-zettelkasten",
         "body": "## Main Idea\n\n## Elaboration\n\n## References\n\n## Links\n\n- [[Related Note]]",
         "icon": "zap"},
        {"id": "literature", "name": "Literature Note",
         "description": "Capture and process a source.",
         "note_type": "literature", "folder": "30-literature",
         "body": "## Source\n\n- **Title:** \n- **Author:** \n\n## Key Points\n\n## My Take\n\n## Links\n",
         "icon": "book-open"},
        {"id": "project", "name": "Project Note",
         "description": "Track a bounded project.",
         "note_type": "project", "folder": "20-projects",
         "body": "## Goal\n\n## Tasks\n\n- [ ] \n\n## Status\n",
         "icon": "layout"},
        {"id": "moc", "name": "Map of Content",
         "description": "Index and navigate a topic cluster.",
         "note_type": "moc", "folder": "00-mocs",
         "body": "## Overview\n\n## Core Notes\n\n- [[Note A]]\n\n## Sub-Topics\n",
         "icon": "map"},
        {"id": "dharma", "name": "Dharma Teaching",
         "description": "Record a teaching or practice instruction.",
         "note_type": "permanent", "folder": "40-teachings",
         "body": "## Teaching / Source\n\n- **Teacher:** \n- **Lineage:** \n\n## Core Teaching\n\n## Practice Instructions\n\n## Personal Reflection\n",
         "icon": "sun"},
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

    note_id = data.id or generate_note_id()
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

    # Insert tags via association table — do NOT use note.tags.append().
    # Note.tags is lazy='selectin' and is None on a new instance until the
    # object is loaded from the DB. Direct insert avoids that entirely.
    if data.tags:
        await _upsert_tags(note_id, data.tags, db)

    await db.commit()
    note = await _get_note_or_404(note_id, db, owner_ids)
    return _note_to_read(note)


# ---------------------------------------------------------------------------
# Orphan notes
# ---------------------------------------------------------------------------


@router.get("/orphans", response_model=list[NoteListItem])
async def get_orphan_notes(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[NoteListItem]:
    notes_with_links = select(Note.id).where(
        or_(
            Note.id.in_(select(Link.source_id)),
            Note.id.in_(select(Link.target_id)),
        )
    )
    base_stmt = (
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.is_deleted.is_(False), Note.id.not_in(notes_with_links))
        .order_by(Note.created_at.desc())
    )
    result = await db.execute(scoped_note_stmt(base_stmt, owner_ids))
    notes = result.scalars().unique().all()
    return [
        NoteListItem(
            id=n.id, title=n.title, slug=n.slug, note_type=n.note_type,
            status=n.status, folder=n.folder, word_count=n.word_count,
            created_at=n.created_at, modified_at=n.modified_at,
            tags=[t.name for t in (n.tags if isinstance(n.tags, list) else [])],
        )
        for n in notes
    ]


# ---------------------------------------------------------------------------
# Daily note
# ---------------------------------------------------------------------------


@router.get("/daily", response_model=NoteRead)
async def get_or_create_daily_note(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteRead:
    from gnosis.core.namespace import resolve_vault_path

    today = date.today()
    today_str = today.isoformat()
    vault_path_rel = f"60-journals/{today_str}.md"

    daily_stmt = scoped_note_stmt(
        select(Note)
        .options(
            selectinload(Note.tags),
            selectinload(Note.outgoing_links),
            selectinload(Note.incoming_links),
        )
        .where(Note.vault_path == vault_path_rel, Note.is_deleted.is_(False)),
        owner_ids,
    )
    result = await db.execute(daily_stmt)
    note = result.scalars().unique().one_or_none()

    if note is None:
        body = (
            f"# Daily Note — {today_str}\n\n"
            "## Priorities\n\n1. \n2. \n3. \n\n"
            "## Capture\n\n## Reflection\n"
        )
        note_id = generate_note_id(datetime.combine(today, datetime.min.time()))
        fm = build_default_frontmatter(
            note_id=note_id, title=f"Daily Note — {today_str}",
            note_type="journal", status="in-progress",
        )
        vault_root = resolve_vault_path(current_user)
        write_note_file(
            vault_root / "60-journals" / f"{today_str}.md",
            f"Daily Note — {today_str}", body, fm,
        )
        note = Note(
            id=note_id, title=f"Daily Note — {today_str}",
            slug=slugify(f"daily-note-{today_str}"), body=body,
            body_html=f"<h1>Daily Note — {today_str}</h1>",
            note_type="journal", status="in-progress",
            vault_path=vault_path_rel, folder="60-journals",
            word_count=len(body.split()), frontmatter=fm,
            is_deleted=False, vector_indexed=False, graph_indexed=False,
            owner_id=current_user.id,
        )
        db.add(note)
        await db.flush()  # INSERT note row before FK
        # Daily notes have no tags — no _upsert_tags call needed.
        await db.commit()
        note = await _get_note_or_404(note_id, db, owner_ids)

    return _note_to_read(note)


# ---------------------------------------------------------------------------
# Get note by ID
# ---------------------------------------------------------------------------


@router.get("/{note_id}", response_model=NoteRead)
async def get_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteRead:
    note = await _get_note_or_404(note_id, db, owner_ids)
    return _note_to_read(note)


# ---------------------------------------------------------------------------
# Update note
# ---------------------------------------------------------------------------


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

    if note.owner_id is not None and note.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can view but not edit notes in a shared vault.",
        )

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
        note.frontmatter = {**(note.frontmatter or {}), **data.frontmatter}

    if data.tags is not None:
        # Replace tags: delete existing associations then re-insert.
        await db.execute(delete(NoteTag).where(NoteTag.c.note_id == note_id))
        await db.flush()
        await _upsert_tags(note_id, data.tags, db)

    note.vector_indexed = False
    await db.commit()

    vault_root = resolve_vault_path(current_user)
    vault_file = vault_root / note.vault_path
    fm = {**(note.frontmatter or {}), "title": note.title,
          "modified": datetime.now(timezone.utc).isoformat()}
    try:
        write_note_file(vault_file, note.title, note.body, fm)
    except Exception as e:
        raise VaultWriteError(str(vault_file), str(e)) from e

    note = await _get_note_or_404(note_id, db, owner_ids)
    return _note_to_read(note)


# ---------------------------------------------------------------------------
# Delete note (soft)
# ---------------------------------------------------------------------------


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> None:
    note = await _get_note_or_404(note_id, db, owner_ids)
    if note.owner_id is not None and note.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete notes in a shared vault.",
        )
    note.is_deleted = True
    await db.commit()


# ---------------------------------------------------------------------------
# Backlinks / outlinks
# ---------------------------------------------------------------------------


@router.get("/{note_id}/backlinks", response_model=list[NoteListItem])
async def get_backlinks(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[NoteListItem]:
    base_stmt = (
        select(Note).options(selectinload(Note.tags))
        .join(Link, Link.source_id == Note.id)
        .where(Link.target_id == note_id, Note.is_deleted.is_(False))
    )
    result = await db.execute(scoped_note_stmt(base_stmt, owner_ids))
    notes = result.scalars().unique().all()
    return [
        NoteListItem(
            id=n.id, title=n.title, slug=n.slug, note_type=n.note_type,
            status=n.status, folder=n.folder, word_count=n.word_count,
            created_at=n.created_at, modified_at=n.modified_at,
            tags=[t.name for t in (n.tags if isinstance(n.tags, list) else [])],
        )
        for n in notes
    ]


@router.get("/{note_id}/outlinks", response_model=list[NoteListItem])
async def get_outlinks(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[NoteListItem]:
    base_stmt = (
        select(Note).options(selectinload(Note.tags))
        .join(Link, Link.target_id == Note.id)
        .where(Link.source_id == note_id, Note.is_deleted.is_(False))
    )
    result = await db.execute(scoped_note_stmt(base_stmt, owner_ids))
    notes = result.scalars().unique().all()
    return [
        NoteListItem(
            id=n.id, title=n.title, slug=n.slug, note_type=n.note_type,
            status=n.status, folder=n.folder, word_count=n.word_count,
            created_at=n.created_at, modified_at=n.modified_at,
            tags=[t.name for t in (n.tags if isinstance(n.tags, list) else [])],
        )
        for n in notes
    ]
