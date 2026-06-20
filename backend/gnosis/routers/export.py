"""Export router — vault zip / JSON export and single-note Markdown download.

Endpoints
---------
GET /export/?format=markdown   — zip of all user notes as .md files
GET /export/?format=json        — JSON array of all user notes with metadata
GET /export/vault.zip           — alias kept for backwards compat
GET /export/note/{id}.md        — single note markdown download
GET /export/note/{id}.pdf       — single note PDF (requires ENABLE_PDF_EXPORT=true)

The ?format= endpoint is what the SettingsPage export button calls.
The owner_id filter ensures users only receive their own notes.

Loading strategy note
~~~~~~~~~~~~~~~~~~~~~
Note.tags now uses lazy='select' (explicit load only).  The explicit
.options(selectinload(Note.tags)) calls below are the sole load path.
Do NOT add a second .options() call for the same relationship on the
same query — that would trigger the double-load collapse again.
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gnosis.config import settings
from gnosis.database import get_db
from gnosis.models.note import Note
from gnosis.core.auth import get_current_user
from gnosis.models.user import User

router = APIRouter(prefix="/export", tags=["export"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(val: object) -> str:
    """Safely convert a date/datetime/str to ISO-8601 string."""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return str(val) if val is not None else ""


def _note_to_markdown(note: Note) -> str:
    """Serialise a Note ORM row to a .md string with YAML frontmatter.

    note.tags is a list of Tag ORM objects (loaded by selectinload); extract
    .name from each rather than passing the object to str.join.
    """
    _tags = note.tags if isinstance(note.tags, list) else []
    tags_str = ", ".join(t.name if hasattr(t, "name") else str(t) for t in _tags)
    fm_lines = [
        "---",
        f'id: "{note.id}"',
        f'title: "{note.title}"',
        f"type: {note.note_type}",
        f"status: {getattr(note, 'status', 'draft')}",
        f"folder: {note.folder or ''}",
        f"tags: [{tags_str}]",
        f"created: {_iso(getattr(note, 'created_at', date.today()))}",
        f"modified: {_iso(getattr(note, 'modified_at', date.today()))}",
        "---",
        "",
    ]
    return "\n".join(fm_lines) + (note.body or "")


def _note_to_dict(note: Note) -> dict:
    """Serialise a Note ORM row to a plain dict for JSON export."""
    _tags = note.tags if isinstance(note.tags, list) else []
    return {
        "id": note.id,
        "title": note.title,
        "body": note.body or "",
        "folder": note.folder or "",
        "note_type": note.note_type,
        "status": getattr(note, "status", "draft"),
        "tags": [t.name if hasattr(t, "name") else str(t) for t in _tags],
        "vault_path": note.vault_path or "",
        "word_count": note.word_count or 0,
        "created_at": _iso(getattr(note, "created_at", None)),
        "modified_at": _iso(getattr(note, "modified_at", None)),
    }


async def _fetch_user_notes(db: AsyncSession, owner_id: int) -> list[Note]:
    """Return all non-deleted notes owned by *owner_id*, tags eagerly loaded.

    A single selectinload(Note.tags) is the correct and complete load path
    now that Note.tags uses lazy='select'.  Do not add a second one.
    """
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(
            Note.owner_id == owner_id,
            Note.is_deleted == False,  # noqa: E712
        )
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Primary export endpoint (used by SettingsPage)
# ---------------------------------------------------------------------------

@router.get(
    "/",
    summary="Export vault in chosen format",
    responses={
        200: {"description": "Zip archive (markdown) or JSON payload"},
    },
)
async def export_vault(
    format: str = Query("markdown", pattern="^(markdown|json)$"),  # noqa: A002
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Export all notes for the authenticated user.

    - ``format=markdown`` → zip archive of .md files (application/zip)
    - ``format=json``     → JSON array of note objects (application/json)
    """
    notes = await _fetch_user_notes(db, current_user.id)
    today = date.today().isoformat()

    if format == "json":
        payload = json.dumps([_note_to_dict(n) for n in notes], ensure_ascii=False, indent=2)
        filename = f"gnosis-export-{today}.json"
        return Response(
            content=payload.encode("utf-8"),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # markdown zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for note in notes:
            vault_path = getattr(note, "vault_path", None) or f"{note.id}.md"
            zf.writestr(vault_path, _note_to_markdown(note))
    buf.seek(0)
    filename = f"gnosis-export-{today}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Legacy / convenience endpoints
# ---------------------------------------------------------------------------

@router.get("/vault.zip", summary="Export entire vault as Obsidian-compatible zip (legacy)")
async def export_vault_zip(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream a zip archive of all user notes as .md files with frontmatter."""
    notes = await _fetch_user_notes(db, current_user.id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for note in notes:
            vault_path = getattr(note, "vault_path", None) or f"{note.id}.md"
            zf.writestr(vault_path, _note_to_markdown(note))
    buf.seek(0)
    today = date.today().isoformat()
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="gnosis-vault-{today}.zip"'},
    )


@router.get("/note/{note_id}.md", summary="Download a single note as Markdown")
async def export_note_md(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Return a single note as a downloadable .md file."""
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.id == note_id, Note.owner_id == current_user.id)
    )
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    content = _note_to_markdown(note)
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in note.title)[:80]
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
    )


@router.get(
    "/note/{note_id}.pdf",
    summary="Export a single note as PDF (requires ENABLE_PDF_EXPORT=true)",
)
async def export_note_pdf(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Render a note to PDF via WeasyPrint. Requires ENABLE_PDF_EXPORT=true."""
    if not getattr(settings, "enable_pdf_export", False):
        raise HTTPException(
            status_code=501, detail="PDF export is disabled. Set ENABLE_PDF_EXPORT=true."
        )
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
    except ImportError:
        raise HTTPException(status_code=501, detail="weasyprint not installed")

    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.id == note_id, Note.owner_id == current_user.id)
    )
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")

    html_content = f"<html><body><h1>{note.title}</h1>{note.body_html}</body></html>"
    pdf_bytes = HTML(string=html_content).write_pdf()
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in note.title)[:80]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
    )
