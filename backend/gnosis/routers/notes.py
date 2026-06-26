"""Notes CRUD router."""

import math
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from slugify import slugify
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gnosis.core.auth import get_current_user, get_vault_owner_ids
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

router = APIRouter(prefix="/notes", tags=["notes"])


# ---------------------------------------------------------------------------
# Helper: upsert tags via association table (bypasses ORM collection)
# ---------------------------------------------------------------------------


async def _upsert_tags(note_id: str, tag_names: list[str], db: AsyncSession) -> None:
    """Insert note<->tag associations directly into the note_tags table.

    This avoids touching the Note.tags ORM collection, which is uninitialised
    on a brand-new Note instance until the object is loaded from the DB.
    vault_sync.py uses the same pattern.

    Uses PostgreSQL ``ON CONFLICT DO NOTHING`` so duplicate rows are silently
    ignored on both PostgreSQL (production) and SQLite (test, via the standard
    insert().prefix_with fallback).  Bug 2 fix: replaced the SQLite-only
    ``.prefix_with("OR IGNORE")`` with the dialect-aware approach below.
    """
    for tag_name in tag_names:
        tag_result = await db.execute(select(Tag).where(Tag.name == tag_name))
        tag = tag_result.scalar_one_or_none()
        if tag is None:
            tag = Tag(name=tag_name)
            db.add(tag)
            await db.flush()  # ensure Tag row exists before FK insert
        # Bug 2 fix: use PostgreSQL on_conflict_do_nothing() instead of SQLite
        # OR IGNORE prefix.  The pg_insert dialect variant is imported at the
        # top of this module from sqlalchemy.dialects.postgresql.
        stmt = pg_insert(NoteTag).values(note_id=note_id, tag_id=tag.id).on_conflict_do_nothing()
        await db.execute(stmt)


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
        slug=note.slug or "",
        body=note.body or "",
        body_html=note.body_html or "",
        note_type=note.note_type or "permanent",
        status=note.status or "draft",
        vault_path=note.vault_path,
        folder=note.folder or "00-inbox",
        source_url=note.source_url,
        word_count=note.word_count or 0,
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
    folder: str | None = Query(None),
    note_type: str | None = Query(None),
    status: str | None = Query(None),
    tags: list[str] | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteListResponse:
    query = scoped_note_stmt(
        select(Note).options(selectinload(Note.tags)).where(Note.is_deleted.is_(False)),
        owner_ids,
    )

    if folder:
        query = query.where(Note.folder == folder)
    if note_type:
        query = query.where(Note.note_type == note_type)
    if status:
        query = query.where(Note.status == status)
    if tags:
        # Filter by tag name: join through the tags table to match by name (not raw tag_id int)
        for tag_name in tags:
            tag_subq = (
                select(NoteTag.c.note_id)
                .join(Tag, Tag.id == NoteTag.c.tag_id)
                .where(Tag.name == tag_name)
            )
            query = query.where(Note.id.in_(tag_subq))
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
            slug=n.slug or "",
            note_type=n.note_type or "permanent",
            status=n.status or "draft",
            folder=n.folder or "00-inbox",
            word_count=n.word_count or 0,
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
# Title-based lookup  (GET /notes/by-title) -- BEFORE /{note_id}
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
# Wikilink title search  (GET /notes/wikilink) -- BEFORE /{note_id}
# ---------------------------------------------------------------------------


@router.get("/wikilink", summary="Resolve a wikilink title to a note ID")
async def resolve_wikilink(
    title: str = Query(...),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict:
    stmt = scoped_note_stmt(
        select(Note.id, Note.title, Note.slug).where(
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
# Tags  (GET /notes/tags) -- BEFORE /{note_id}
# Returns a plain string[] of distinct tag names for the current user.
# Used by api.listTags() for autocomplete and tag-filter dropdowns.
# ---------------------------------------------------------------------------


@router.get("/tags", summary="Distinct tag names for the current user")
async def list_note_tags(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[str]:
    """Return alphabetically sorted tag names visible to the requesting user."""
    stmt = (
        select(Tag.name)
        .join(NoteTag, Tag.id == NoteTag.c.tag_id)
        .join(Note, Note.id == NoteTag.c.note_id)
        .where(
            Note.owner_id.in_(owner_ids),
            Note.is_deleted.is_(False),
        )
        .distinct()
        .order_by(Tag.name.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# Folders  (GET /notes/folders) -- BEFORE /{note_id}
# Returns a string[] of distinct folder names for the current user.
# ---------------------------------------------------------------------------


@router.get("/folders", summary="Distinct folder names for the current user")
async def list_note_folders(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[str]:
    """Return sorted distinct folder values from notes visible to the requesting user."""
    stmt = (
        select(Note.folder)
        .where(
            Note.owner_id.in_(owner_ids),
            Note.is_deleted.is_(False),
            Note.folder.isnot(None),
        )
        .distinct()
        .order_by(Note.folder.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [f for f in rows if f]


# ---------------------------------------------------------------------------
# Templates  (GET /notes/templates) -- BEFORE /{note_id}
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
# Graph  (GET /notes/graph) -- BEFORE /{note_id}
# ---------------------------------------------------------------------------


@router.get("/graph", summary="Note graph (nodes + edges)")
async def get_note_graph(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict:
    from gnosis.models.link import Link

    notes_stmt = scoped_note_stmt(
        select(Note.id, Note.title, Note.folder, Note.note_type).where(Note.is_deleted.is_(False)),
        owner_ids,
    )
    notes_rows = (await db.execute(notes_stmt)).all()
    nodes = [
        {"id": r.id, "title": r.title, "folder": r.folder, "note_type": r.note_type}
        for r in notes_rows
    ]

    links_stmt = select(Link.source_id, Link.target_id, Link.link_type)
    links_rows = (await db.execute(links_stmt)).all()
    edges = [
        {"source": r.source_id, "target": r.target_id, "type": r.link_type} for r in links_rows
    ]

    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Search  (GET /notes/search) -- BEFORE /{note_id}
# ---------------------------------------------------------------------------


@router.get("/search", response_model=NoteListResponse, summary="Full-text search")
async def search_notes(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteListResponse:
    base = scoped_note_stmt(
        select(Note)
        .options(selectinload(Note.tags))
        .where(
            Note.is_deleted.is_(False),
            or_(
                Note.title.ilike(f"%{q}%"),
                Note.body.ilike(f"%{q}%"),
            ),
        ),
        owner_ids,
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                base.order_by(Note.modified_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    items = [
        NoteListItem(
            id=n.id,
            title=n.title,
            slug=n.slug or "",
            note_type=n.note_type or "permanent",
            status=n.status or "draft",
            folder=n.folder or "00-inbox",
            word_count=n.word_count or 0,
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
# Orphan notes
# ---------------------------------------------------------------------------


@router.get("/orphans", response_model=list[NoteListItem])
async def list_orphan_notes(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[NoteListItem]:
    """Return notes with no incoming or outgoing wikilinks."""

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
            id=n.id,
            title=n.title,
            slug=n.slug or "",
            note_type=n.note_type or "permanent",
            status=n.status or "draft",
            folder=n.folder or "00-inbox",
            word_count=n.word_count or 0,
            created_at=n.created_at,
            modified_at=n.modified_at,
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
            Note.title == f"Daily Note -- {today_str}",
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

    note_id = (
        f"{generate_note_id(datetime.combine(today, datetime.min.time()))}-{uuid.uuid4().hex[:4]}"
    )
    title = f"Daily Note -- {today_str}"
    slug = slugify(title)
    body = f"# {title}\n\n"
    fm = build_default_frontmatter(
        note_id=note_id,
        title=title,
        note_type="journal",
        status="active",
        tags=[],
        source_url=None,
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
        id=note_id,
        title=title,
        slug=slug,
        body=body,
        body_html=body_html,
        note_type="journal",
        status="active",
        vault_path=vault_path_rel,
        folder=folder,
        word_count=len(body.split()),
        frontmatter=fm,
        is_deleted=False,
        vector_indexed=False,
        graph_indexed=False,
        owner_id=current_user.id,
    )
    db.add(note)
    await db.flush()
    await db.commit()
    db.expunge(note)
    note = await _get_note_or_404(note_id, db, owner_ids)
    return _note_to_read(note)


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
        owner_ids,
        include_null_owner=False,
    )
    existing = await db.execute(existing_stmt)
    if existing.scalars().unique().one_or_none():
        raise NoteConflictError(title)

    fm = build_default_frontmatter(
        note_id=note_id,
        title=title,
        note_type=data.note_type,
        status=data.status,
        tags=data.tags,
        source_url=data.source_url,
    )
    fm.update(data.frontmatter)

    vault_root = resolve_vault_path(current_user)
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
        id=note_id,
        title=title,
        slug=slug,
        body=data.body,
        body_html=body_html,
        note_type=data.note_type,
        status=data.status,
        vault_path=vault_path_rel,
        folder=data.folder,
        source_url=data.source_url,
        word_count=len(data.body.split()),
        frontmatter=fm,
        last_reviewed=data.last_reviewed,
        is_deleted=False,
        vector_indexed=False,
        graph_indexed=False,
        owner_id=current_user.id,
    )
    db.add(note)
    await db.flush()  # INSERT note row so FK in note_tags is valid

    if data.tags:
        await _upsert_tags(note_id, data.tags, db)

    await db.commit()
    db.expunge(note)
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
        await db.execute(delete(NoteTag).where(NoteTag.c.note_id == note_id))
        await db.flush()
        await _upsert_tags(note_id, data.tags, db)

    await db.flush()
    await db.commit()
    db.expunge(note)
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
