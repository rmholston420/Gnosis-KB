"""Notes CRUD router.

Handles all note lifecycle operations:
- Create (writes .md to vault → triggers vault sync)
- Read (single note with backlinks, list with filters)
- Update (writes .md to vault → triggers vault sync)
- Delete (soft delete in DB; vault file preserved)
- Special endpoints: backlinks, outlinks, orphans, daily note, templates,
  wikilink title search

Isolation contract
------------------
Every ``select(Note)`` MUST be wrapped in ``scoped_note_stmt()`` so that
cross-vault reads are impossible at the router layer.  The only exception
is the internal ``_get_note_or_404`` helper, which applies the scope itself
and additionally raises HTTP 403 when the authenticated user does not own
(or share) the requested note.

Legacy owner_id=0 sentinel
---------------------------
Notes written before multi-user support carry owner_id=0.  These are
treated as unowned and raise HTTP 403 for all normal users.  Run
``scripts/fix_owner_ids.py`` to reassign them to a real owner.

Dependency pattern
------------------
All read endpoints declare::

   owner_ids: set[int] = Depends(get_vault_owner_ids)

Write endpoints (update, delete, daily-note creation) that also need the
calling user's identity keep::

   current_user: User = Depends(get_current_user)
   owner_ids:    set[int] = Depends(get_vault_owner_ids)

get_vault_owner_ids honours the optional ``X-Vault-Owner-Id`` request header
so the frontend VaultSwitcher can scope a request to a shared vault without
any router-level changes.
"""

import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from slugify import slugify  # python-slugify v8+ uses 'slugify' as the module name
from sqlalchemy import func, or_, select
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

# prefix is /notes only — main.py prepends /api/v1 when including this router
router = APIRouter(prefix="/notes", tags=["notes"])


# ---------------------------------------------------------------------------
# Helper: load note with relationships + ownership check
# ---------------------------------------------------------------------------


async def _get_note_or_404(
    note_id: str,
    db: AsyncSession,
    owner_ids: set[int],
) -> Note:
    """Fetch a note by ID within the caller's accessible vaults.

    Raises HTTP 403 for:
    - Cross-vault access (note.owner_id not in owner_ids)
    - Legacy owner_id=0 sentinel (unowned notes) unless caller explicitly
      has 0 in their owner_ids set (admin use only).
    """
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

    # Guard legacy owner_id=0 sentinel — treat as unowned/admin-only
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
    """Convert a Note ORM instance to NoteRead schema."""
    from gnosis.schemas.note import LinkSchema
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
        tags=[t.name for t in (note.tags if isinstance(note.tags, list) else ([note.tags] if note.tags else []))],
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
    q: Optional[str] = Query(None, description="Full-text filter on title"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteListResponse:
    """List notes with optional filters and pagination."""
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
    notes = result.scalars().unique().all()  # .unique() required when selectinload is used with collections

    return NoteListResponse(
        items=[
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
                tags=[t.name for t in (n.tags if isinstance(n.tags, list) else ([n.tags] if n.tags else []))],
            )
            for n in notes
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


# ---------------------------------------------------------------------------
# Wikilink title search  (GET /notes/by-title)
# IMPORTANT: Must be declared BEFORE /{note_id} routes to avoid FastAPI
# treating "by-title" as a note_id path parameter.
# ---------------------------------------------------------------------------


@router.get("/by-title", response_model=NoteListResponse, summary="Search notes by title (wikilink resolution)")
async def notes_by_title(
    q: str = Query(..., description="Title text to search (case-insensitive contains)"),
    page_size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteListResponse:
    """Wikilink resolution endpoint.

    Returns notes whose title contains ``q`` (case-insensitive), scoped to the
    caller's accessible vaults.  Used by the NoteDetailPanel wikilink chips
    and the NoteEditor [[autocomplete]] dropdown.
    """
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
                id=n.id,
                title=n.title,
                slug=n.slug,
                note_type=n.note_type,
                status=n.status,
                folder=n.folder,
                word_count=n.word_count,
                created_at=n.created_at,
                modified_at=n.modified_at,
                tags=[t.name for t in (n.tags if isinstance(n.tags, list) else ([n.tags] if n.tags else []))],
            )
            for n in notes
        ],
        total=total,
        page=1,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


# ---------------------------------------------------------------------------
# Note templates  (GET /notes/templates)
# IMPORTANT: Also before /{note_id}.
# ---------------------------------------------------------------------------


@router.get("/templates", summary="List available note templates")
async def list_templates() -> list[dict]:
    """Return the built-in note template gallery.

    Each entry contains:
    - id: machine key used by the frontend
    - name: display name
    - description: one-line purpose description
    - note_type: default note_type for notes created from this template
    - folder: suggested vault folder
    - body: Markdown body with placeholder tokens ({{ TITLE }}, {{ DATE }}, ...)
    """
    return [
        {
            "id": "blank",
            "name": "Blank Note",
            "description": "Start with an empty canvas.",
            "note_type": "permanent",
            "folder": "10-zettelkasten",
            "body": "",
            "icon": "file",
        },
        {
            "id": "zettel",
            "name": "Zettelkasten Slip",
            "description": "Atomic concept note with one clear idea.",
            "note_type": "permanent",
            "folder": "10-zettelkasten",
            "body": (
                "## Main Idea\n\n"
                "<!-- State the single idea this note captures. -->\n\n"
                "## Elaboration\n\n"
                "## References\n\n"
                "## Links\n\n"
                "- [[Related Note]]"
            ),
            "icon": "zap",
        },
        {
            "id": "literature",
            "name": "Literature Note",
            "description": "Capture and process a source (book, paper, article).",
            "note_type": "literature",
            "folder": "30-literature",
            "body": (
                "## Source\n\n"
                "- **Title:** \n"
                "- **Author:** \n"
                "- **Year:** \n"
                "- **URL:** \n\n"
                "## Key Points\n\n"
                "1. \n\n"
                "## My Take\n\n"
                "## Fleeting Quotes\n\n"
                "> Quote here\n\n"
                "## Links\n\n"
            ),
            "icon": "book-open",
        },
        {
            "id": "project",
            "name": "Project Note",
            "description": "Track a bounded project with goals and tasks.",
            "note_type": "project",
            "folder": "20-projects",
            "body": (
                "## Goal\n\n"
                "## Why This Matters\n\n"
                "## Tasks\n\n"
                "- [ ] \n"
                "- [ ] \n\n"
                "## Notes\n\n"
                "## Resources\n\n"
                "## Status\n\n"
                "- **Started:** {{ DATE }}\n"
                "- **Target:** \n"
            ),
            "icon": "layout",
        },
        {
            "id": "moc",
            "name": "Map of Content",
            "description": "Index and navigate a topic cluster.",
            "note_type": "moc",
            "folder": "00-mocs",
            "body": (
                "## Overview\n\n"
                "<!-- What territory does this MOC cover? -->\n\n"
                "## Core Notes\n\n"
                "- [[Note A]]"
                "- [[Note B]]\n\n"
                "## Sub-Topics\n\n"
                "## Entry Points\n\n"
            ),
            "icon": "map",
        },
        {
            "id": "meeting",
            "name": "Meeting Note",
            "description": "Capture decisions and action items from a meeting.",
            "note_type": "fleeting",
            "folder": "00-inbox",
            "body": (
                "## Date & Attendees\n\n"
                "- **Date:** {{ DATE }}\n"
                "- **Attendees:** \n\n"
                "## Agenda\n\n"
                "1. \n\n"
                "## Decisions\n\n"
                "## Action Items\n\n"
                "- [ ] (owner) \n\n"
                "## Follow-Up Notes\n\n"
            ),
            "icon": "users",
        },
        {
            "id": "dharma",
            "name": "Dharma Teaching",
            "description": "Record a teaching, practice instruction, or reflection.",
            "note_type": "permanent",
            "folder": "40-teachings",
            "body": (
                "## Teaching / Source\n\n"
                "- **Teacher:** \n"
                "- **Lineage:** \n"
                "- **Date received:** {{ DATE }}\n\n"
                "## Core Teaching\n\n"
                "## Practice Instructions\n\n"
                "## Personal Reflection\n\n"
                "## Links to Other Teachings\n\n"
                "- [[Related Teaching]]"
            ),
            "icon": "sun",
        },
    ]


# ---------------------------------------------------------------------------
# Create note
# ---------------------------------------------------------------------------


@router.post("/", response_model=NoteRead, status_code=status.HTTP_201_CREATED, summary="Create note")
async def create_note(
    data: NoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    """Create a new note and write it to the authenticated user's vault."""
    from gnosis.core.namespace import resolve_vault_path

    settings = get_settings()

    note_id = data.id or generate_note_id()
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
    vault_dir = vault_root / data.folder
    filename = f"{note_id}-{slug[:50]}.md"
    vault_file = vault_dir / filename
    vault_path_rel = f"{data.folder}/{filename}"

    try:
        write_note_file(vault_file, title, data.body, fm)
    except Exception as e:
        raise VaultWriteError(str(vault_file), str(e)) from e

    import mistune
    renderer = mistune.create_markdown(plugins=["strikethrough", "footnotes", "table", "task_lists"])
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
    # Explicitly initialise the tags collection to an empty list.
    # SQLAlchemy's lazy="selectin" relationship does NOT pre-populate the
    # in-memory list on a brand-new (pre-flush) instance — it stays None
    # until either the object is loaded from the DB or we set it here.
    # Without this, note.tags.append(tag) raises:
    #   AttributeError: 'NoneType' object has no attribute 'append'
    note.tags = []

    db.add(note)

    # Flush the Note INSERT so the row exists in the DB before we touch the
    # tags relationship.  The explicit note.tags = [] above ensures append()
    # works on the in-memory collection before the DB round-trip.
    await db.flush()

    for tag_name in (data.tags or []):
        tag_result = await db.execute(select(Tag).where(Tag.name == tag_name))
        tag = tag_result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=tag_name)
            db.add(tag)
            await db.flush()  # ensure Tag row exists before appending
        note.tags.append(tag)

    await db.commit()

    # Re-fetch with all relationships eagerly loaded so _note_to_read never
    # triggers lazy-loading outside a greenlet context.
    owner_ids_full = {current_user.id}
    note = await _get_note_or_404(note_id, db, owner_ids_full)
    return _note_to_read(note)


# ---------------------------------------------------------------------------
# Orphan notes
# ---------------------------------------------------------------------------


@router.get("/orphans", response_model=list[NoteListItem], summary="Get orphan notes")
async def get_orphan_notes(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[NoteListItem]:
    """Return notes with zero incoming AND zero outgoing links."""
    notes_with_links = (
        select(Note.id)
        .where(
            or_(
                Note.id.in_(select(Link.source_id)),
                Note.id.in_(select(Link.target_id)),
            )
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
            tags=[t.name for t in (n.tags if isinstance(n.tags, list) else ([n.tags] if n.tags else []))],
        )
        for n in notes
    ]


# ---------------------------------------------------------------------------
# Daily note
# ---------------------------------------------------------------------------


@router.get("/daily", response_model=NoteRead, summary="Get or create today's daily note")
async def get_or_create_daily_note(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteRead:
    """Get today's daily note or create it if it does not exist."""
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
            note_id=note_id,
            title=f"Daily Note — {today_str}",
            note_type="journal",
            status="in-progress",
        )
        vault_root = resolve_vault_path(current_user)
        vault_file = vault_root / "60-journals" / f"{today_str}.md"
        write_note_file(vault_file, f"Daily Note — {today_str}", body, fm)

        note = Note(
            id=note_id,
            title=f"Daily Note — {today_str}",
            slug=slugify(f"daily-note-{today_str}"),
            body=body,
            body_html=f"<h1>Daily Note — {today_str}</h1>",
            note_type="journal",
            status="in-progress",
            vault_path=vault_path_rel,
            folder="60-journals",
            word_count=len(body.split()),
            frontmatter=fm,
            is_deleted=False,
            vector_indexed=False,
            graph_indexed=False,
            owner_id=current_user.id,
        )
        note.tags = []  # initialise collection — same fix as create_note
        db.add(note)
        await db.commit()
        await db.refresh(note)
        note = await _get_note_or_404(note_id, db, owner_ids)

    return _note_to_read(note)


# ---------------------------------------------------------------------------
# Get note by ID
# ---------------------------------------------------------------------------


@router.get("/{note_id}", response_model=NoteRead, summary="Get note by ID")
async def get_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteRead:
    """Retrieve a note by its timestamp ID."""
    note = await _get_note_or_404(note_id, db, owner_ids)
    return _note_to_read(note)


# ---------------------------------------------------------------------------
# Update note
# ---------------------------------------------------------------------------


@router.put("/{note_id}", response_model=NoteRead, summary="Update note")
async def update_note(
    note_id: str,
    data: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> NoteRead:
    """Update an existing note and write changes to the vault file."""
    from gnosis.core.namespace import resolve_vault_path

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
        renderer = mistune.create_markdown(plugins=["strikethrough", "footnotes", "table", "task_lists"])
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

    if data.tags is not None:
        note.tags.clear()
        await db.flush()  # flush the tag-association deletes before re-adding
        for tag_name in data.tags:
            tag_result = await db.execute(select(Tag).where(Tag.name == tag_name))
            tag = tag_result.scalar_one_or_none()
            if not tag:
                tag = Tag(name=tag_name)
                db.add(tag)
                await db.flush()  # ensure Tag row exists before appending
            note.tags.append(tag)

    if data.frontmatter is not None:
        note.frontmatter = {**(note.frontmatter or {}), **data.frontmatter}

    note.vector_indexed = False
    await db.commit()

    vault_root = resolve_vault_path(current_user)
    vault_file = vault_root / note.vault_path
    fm = {**(note.frontmatter or {}), "title": note.title, "modified": datetime.now(timezone.utc).isoformat()}
    try:
        write_note_file(vault_file, note.title, note.body, fm)
    except Exception as e:
        raise VaultWriteError(str(vault_file), str(e)) from e

    note = await _get_note_or_404(note_id, db, owner_ids)
    return _note_to_read(note)


# ---------------------------------------------------------------------------
# Delete note (soft)
# ---------------------------------------------------------------------------


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft delete note")
async def delete_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> None:
    """Soft-delete a note (sets is_deleted=True; vault file is preserved)."""
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


@router.get("/{note_id}/backlinks", response_model=list[NoteListItem], summary="Get backlinks")
async def get_backlinks(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[NoteListItem]:
    """Return all notes that link TO this note."""
    base_stmt = (
        select(Note)
        .options(selectinload(Note.tags))
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
            tags=[t.name for t in (n.tags if isinstance(n.tags, list) else ([n.tags] if n.tags else []))],
        )
        for n in notes
    ]


@router.get("/{note_id}/outlinks", response_model=list[NoteListItem], summary="Get outlinks")
async def get_outlinks(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[NoteListItem]:
    """Return all notes that this note links TO."""
    base_stmt = (
        select(Note)
        .options(selectinload(Note.tags))
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
            tags=[t.name for t in (n.tags if isinstance(n.tags, list) else ([n.tags] if n.tags else []))],
        )
        for n in notes
    ]
