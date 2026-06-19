"""
Ingest Router — /api/v1/ingest

Endpoints:
  POST /file   — Upload PDF/DOCX/PPTX/XLSX/image → literature note in 70-sources/
  POST /url    — Scrape URL → literature note in 70-sources/
  POST /batch  — Zip of .md files → bulk import into vault

All file ingestion paths:
  1. Parse to plain text via document_parser.py
  2. AI generates title/summary/tags (optional, degrades gracefully)
  3. Write .md literature note to vault (70-sources/)
  4. Trigger vault sync to index in DB + Qdrant
"""
from __future__ import annotations

import io
import logging
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.config import get_settings
from gnosis.core.auth import get_current_user
from gnosis.database import get_session
from gnosis.models.user import User
from gnosis.services.document_parser import ParsedDocument, detect_format, parse_file
from gnosis.services.llm_provider import llm_provider

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/ingest", tags=["ingest"])

_SUPPORTED_FORMATS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
                      ".png", ".jpg", ".jpeg", ".webp", ".tiff", ".tif"}
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class IngestFileResponse(BaseModel):
    """Response from POST /ingest/file."""

    note_id: str
    title: str
    vault_path: str
    summary: str
    tags: list[str]


class IngestUrlResponse(BaseModel):
    """Response from POST /ingest/url."""

    note_id: str
    title: str
    vault_path: str
    source_url: str


class BatchIngestResult(BaseModel):
    """Per-file result in a batch import."""

    filename: str
    status: str  # 'imported' | 'skipped' | 'error'
    note_id: str = ""
    error: str = ""


class IngestBatchResponse(BaseModel):
    """Response from POST /ingest/batch."""

    total: int
    imported: int
    skipped: int
    errors: int
    results: list[BatchIngestResult]


class UrlIngestRequest(BaseModel):
    """Request body for POST /ingest/url."""

    url: str = Field(..., min_length=7, max_length=2000)
    folder: str = Field(default="70-sources")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _timestamp_id() -> str:
    """Generate a Gnosis-style timestamp note ID."""
    return datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")


def _sanitize_filename(title: str) -> str:
    """Convert a title to a safe vault filename."""
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:80] or "untitled"


async def _ai_enrich(parsed: ParsedDocument) -> tuple[str, str, list[str]]:
    """Use LLM to generate a title, summary, and tags for a parsed document.

    Args:
        parsed: The parsed document.

    Returns:
        Tuple of (title, summary, tags). Falls back to parsed values if LLM unavailable.
    """
    if not llm_provider.is_available:
        return parsed.title, parsed.text[:500], []

    import json

    excerpt = parsed.text[:4000]
    prompt = (
        f"Document excerpt:\n{excerpt}\n\n"
        "Generate: (1) a concise title (max 80 chars), "
        "(2) a 2-3 sentence summary, "
        "(3) 3-5 lowercase tags as a JSON array.\n"
        'Return JSON: {"title": "...", "summary": "...", "tags": ["...", ...]}'
    )
    raw = await llm_provider.complete(prompt, temperature=0.2)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return (
                data.get("title", parsed.title)[:200],
                data.get("summary", ""),
                data.get("tags", []),
            )
        except (json.JSONDecodeError, TypeError):
            pass

    return parsed.title, parsed.text[:500], []


def _build_literature_note(
    note_id: str,
    title: str,
    summary: str,
    full_text: str,
    source: str,
    tags: list[str],
) -> str:
    """Build a Markdown literature note string.

    Args:
        note_id: Gnosis timestamp ID.
        title: Note title.
        summary: AI-generated summary.
        full_text: Raw extracted text (placed in a collapsible block).
        source: Source filename or URL.
        tags: List of tag strings.

    Returns:
        Complete Markdown string with YAML frontmatter.
    """
    now = datetime.now(tz=timezone.utc).isoformat()
    tags_yaml = "[" + ", ".join(tags) + "]"
    truncated = full_text[:8000] + ("..." if len(full_text) > 8000 else "")

    return f"""---
id: "{note_id}"
title: "{title}"
type: literature
status: draft
tags: {tags_yaml}
created: {now}
modified: {now}
source: "{source}"
---

{summary}

<details>
<summary>Full extracted text</summary>

{truncated}

</details>
"""


async def _write_vault_note(
    note_id: str,
    title: str,
    folder: str,
    content: str,
) -> str:
    """Write a note to the vault filesystem.

    Args:
        note_id: Gnosis timestamp ID used in filename.
        title: Note title for filename slug.
        folder: Target PARA folder (e.g. '70-sources').
        content: Full Markdown content.

    Returns:
        Relative vault path string.
    """
    vault = Path(settings.vault_path)
    target_dir = vault / folder
    target_dir.mkdir(parents=True, exist_ok=True)

    slug = _sanitize_filename(title)
    filename = f"{note_id}-{slug}.md"
    target_path = target_dir / filename
    target_path.write_text(content, encoding="utf-8")

    relative = f"{folder}/{filename}"
    logger.info("Ingest: wrote vault note %s", relative)
    return relative


# ---------------------------------------------------------------------------
# POST /ingest/file
# ---------------------------------------------------------------------------

@router.post(
    "/file",
    response_model=IngestFileResponse,
    summary="Ingest a file into the vault",
    description=(
        "Upload a PDF, DOCX, PPTX, XLSX, or image. "
        "The file is parsed to text, enriched by AI, and saved as a "
        "literature note in 70-sources/."
    ),
)
async def ingest_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> IngestFileResponse:
    """Parse and ingest an uploaded file as a literature note.

    Args:
        file: The uploaded file (multipart/form-data).
        session: Database session (unused; vault watcher handles DB sync).
        _current_user: Authenticated user.

    Returns:
        IngestFileResponse with the created note's ID and vault path.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in _SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported format {ext!r}. Supported: {sorted(_SUPPORTED_FORMATS)}",
        )

    # Stream to temp file
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        content = await file.read(_MAX_FILE_SIZE + 1)
        if len(content) > _MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        parsed = parse_file(tmp_path)
    except Exception as exc:
        logger.error("Document parse failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=422, detail=f"Could not parse file: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    note_id = _timestamp_id()
    title, summary, tags = await _ai_enrich(parsed)
    note_content = _build_literature_note(
        note_id=note_id,
        title=title,
        summary=summary,
        full_text=parsed.text,
        source=file.filename,
        tags=tags,
    )
    vault_path = await _write_vault_note(note_id, title, "70-sources", note_content)

    return IngestFileResponse(
        note_id=note_id,
        title=title,
        vault_path=vault_path,
        summary=summary,
        tags=tags,
    )


# ---------------------------------------------------------------------------
# POST /ingest/url
# ---------------------------------------------------------------------------

@router.post(
    "/url",
    response_model=IngestUrlResponse,
    summary="Scrape a URL into the vault",
)
async def ingest_url(
    req: UrlIngestRequest,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> IngestUrlResponse:
    """Scrape a URL and create a literature note.

    Args:
        req: URL ingest request with URL and target folder.
        session: Database session.
        _current_user: Authenticated user.

    Returns:
        IngestUrlResponse with note ID and vault path.
    """
    from gnosis.services.document_parser import parse_url

    try:
        parsed = await parse_url(req.url)
    except Exception as exc:
        logger.error("URL scrape failed for %s: %s", req.url, exc)
        raise HTTPException(status_code=422, detail=f"Failed to scrape URL: {exc}") from exc

    note_id = _timestamp_id()
    title, summary, tags = await _ai_enrich(parsed)
    note_content = _build_literature_note(
        note_id=note_id,
        title=title,
        summary=summary,
        full_text=parsed.text,
        source=req.url,
        tags=tags,
    )
    vault_path = await _write_vault_note(note_id, title, req.folder, note_content)

    return IngestUrlResponse(
        note_id=note_id,
        title=title,
        vault_path=vault_path,
        source_url=req.url,
    )


# ---------------------------------------------------------------------------
# POST /ingest/batch
# ---------------------------------------------------------------------------

@router.post(
    "/batch",
    response_model=IngestBatchResponse,
    summary="Batch import a zip of Markdown files",
)
async def ingest_batch(
    file: UploadFile = File(...),
    _current_user: User = Depends(get_current_user),
) -> IngestBatchResponse:
    """Import a zip archive of .md files into the vault.

    Each .md file is written into the vault's 00-inbox/ folder.
    Files that already exist (same filename) are skipped.

    Args:
        file: ZIP archive uploaded via multipart/form-data.
        _current_user: Authenticated user.

    Returns:
        IngestBatchResponse with per-file import results.
    """
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=415, detail="Only .zip archives are accepted")

    content = await file.read(_MAX_FILE_SIZE + 1)
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Archive exceeds 50 MB limit")

    vault = Path(settings.vault_path)
    inbox = vault / "00-inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    results: list[BatchIngestResult] = []

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for entry in zf.infolist():
                if entry.is_dir():
                    continue
                name = Path(entry.filename).name
                if not name.lower().endswith(".md"):
                    results.append(
                        BatchIngestResult(
                            filename=entry.filename,
                            status="skipped",
                            error="Not a .md file",
                        )
                    )
                    continue

                dest = inbox / name
                if dest.exists():
                    results.append(
                        BatchIngestResult(
                            filename=entry.filename,
                            status="skipped",
                            error="File already exists",
                        )
                    )
                    continue

                try:
                    dest.write_bytes(zf.read(entry.filename))
                    results.append(
                        BatchIngestResult(
                            filename=entry.filename,
                            status="imported",
                            note_id=dest.stem,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    results.append(
                        BatchIngestResult(
                            filename=entry.filename,
                            status="error",
                            error=str(exc),
                        )
                    )
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail=f"Invalid zip archive: {exc}") from exc

    imported = sum(1 for r in results if r.status == "imported")
    skipped = sum(1 for r in results if r.status == "skipped")
    errors = sum(1 for r in results if r.status == "error")

    return IngestBatchResponse(
        total=len(results),
        imported=imported,
        skipped=skipped,
        errors=errors,
        results=results,
    )
