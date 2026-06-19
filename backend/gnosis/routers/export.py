"""Export router — Obsidian vault zip export and single-note Markdown download.

PDF export via WeasyPrint is gated behind a feature flag (ENABLE_PDF_EXPORT=true)
because WeasyPrint requires system-level Cairo/Pango packages.
"""
from __future__ import annotations

import io
import os
import zipfile
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.config import settings
from gnosis.database import get_db
from gnosis.models.note import Note

router = APIRouter(prefix="/export", tags=["export"])


def _note_to_markdown(note: Note) -> str:
    """Serialise a Note ORM row back to a .md file string with YAML frontmatter."""
    fm_lines = [
        "---",
        f'id: "{note.id}"',
        f'title: "{note.title}"',
        f"type: {note.note_type}",
        f"status: {getattr(note, 'status', 'draft')}",
        f"created: {getattr(note, 'created_at', date.today()).isoformat()}",
        f"modified: {getattr(note, 'modified_at', date.today()).isoformat()}",
        "---",
        "",
    ]
    return "\n".join(fm_lines) + (note.body or "")


@router.get("/vault.zip", summary="Export entire vault as Obsidian-compatible zip")
async def export_vault_zip(db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Stream a zip archive of all non-deleted notes as .md files with frontmatter."""
    result = await db.execute(
        select(Note).where(Note.is_deleted == False)  # noqa: E712
    )
    notes = result.scalars().all()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for note in notes:
            vault_path = getattr(note, "vault_path", None) or f"{note.id}.md"
            zf.writestr(vault_path, _note_to_markdown(note))
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=gnosis-vault.zip"},
    )


@router.get("/note/{note_id}.md", summary="Download a single note as Markdown")
async def export_note_md(note_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Return a single note as a downloadable .md file."""
    result = await db.execute(select(Note).where(Note.id == note_id))
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


@router.get("/note/{note_id}.pdf", summary="Export a single note as PDF (requires ENABLE_PDF_EXPORT=true)")
async def export_note_pdf(note_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Render a note to PDF via WeasyPrint.  Requires ENABLE_PDF_EXPORT=true and weasyprint installed."""
    if not getattr(settings, "enable_pdf_export", False):
        raise HTTPException(status_code=501, detail="PDF export is disabled. Set ENABLE_PDF_EXPORT=true.")
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
    except ImportError:
        raise HTTPException(status_code=501, detail="weasyprint not installed")

    result = await db.execute(select(Note).where(Note.id == note_id))
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
