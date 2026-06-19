"""Document ingestion router.

Supports:
  - POST /file: Upload and parse PDF/DOCX/PPTX/XLSX/image → Markdown literature note
  - POST /url: Scrape URL → Markdown literature note (basic httpx fetch)
  - POST /batch: Import a zip of Markdown files into the vault
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.database import get_db
from gnosis.schemas.note import NoteCreate, NoteRead
from gnosis.services.document_parser import SUPPORTED_MIME_TYPES, parse_document
from gnosis.services.llm_provider import chat_completion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


@router.post("/file", response_model=NoteRead, status_code=status.HTTP_201_CREATED, summary="Ingest a document file")
async def ingest_file(
    file: UploadFile = File(...),
    folder: str = Form(default="70-sources"),
    db: AsyncSession = Depends(get_db),
) -> NoteRead:
    """Upload and parse a document, then create a literature note in the vault.

    Supported formats: PDF, DOCX, PPTX, XLSX, PNG, JPG.
    The AI generates a title, summary, and suggested wikilinks.

    Args:
        file: Uploaded document file.
        folder: Target PARA folder (default: 70-sources).
        db: Database session.

    Returns:
        Created NoteRead for the literature note.
    """
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {mime_type}",
        )

    # Save upload to temp file
    suffix = Path(file.filename or "upload").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        extracted_text = parse_document(tmp_path, mime_type)
    finally:
        tmp_path.unlink(missing_ok=True)

    # AI: generate title + summary
    prompt = [
        {"role": "system", "content": "You are a knowledge management assistant. Return JSON only."},
        {"role": "user", "content": f"""Analyze this document and generate a knowledge base entry.
Original filename: {file.filename}
Extracted text (first 3000 chars):
{extracted_text[:3000]}

Return JSON: {{"title": "...", "summary": "...", "tags": [...], "key_concepts": [...]}}"""},
    ]

    try:
        response = await chat_completion(prompt, temperature=0.3)
        import json, re
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        ai_data = json.loads(json_match.group()) if json_match else {}
    except Exception:
        ai_data = {}

    title = ai_data.get("title") or Path(file.filename or "Untitled").stem
    summary = ai_data.get("summary", "")
    tags = ai_data.get("tags", [])

    # Build note body: AI summary + collapsed original text
    body = f"""{summary}

<details>
<summary>Original extracted text</summary>

{extracted_text[:10000]}
</details>
"""

    from gnosis.routers.notes import create_note
    return await create_note(
        NoteCreate(
            title=title,
            body=body,
            note_type="literature",
            status="draft",
            folder=folder,
            tags=tags,
            source_url=f"file://{file.filename}",
        ),
        db=db,
    )


@router.post("/url", response_model=NoteRead, status_code=status.HTTP_201_CREATED, summary="Ingest a URL")
async def ingest_url(
    url: str = Form(...),
    folder: str = Form(default="70-sources"),
    db: AsyncSession = Depends(get_db),
) -> NoteRead:
    """Scrape a URL and create a literature note from its content.

    Args:
        url: URL to scrape.
        folder: Target PARA folder.
        db: Database session.

    Returns:
        Created NoteRead for the literature note.
    """
    import httpx

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            page_text = resp.text[:5000]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Failed to fetch URL: {e}") from e

    prompt = [
        {"role": "system", "content": "You are a knowledge management assistant. Return JSON only."},
        {"role": "user", "content": f"""Analyze this web page and create a literature note.
URL: {url}
Page content:
{page_text}

Return JSON: {{"title": "...", "summary": "...", "tags": [...]}}"""},
    ]

    try:
        response = await chat_completion(prompt, temperature=0.3)
        import json, re
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        ai_data = json.loads(json_match.group()) if json_match else {}
    except Exception:
        ai_data = {"title": url, "summary": page_text[:500], "tags": []}

    body = f"{ai_data.get('summary', '')}\n\nSource: [{url}]({url})\n"

    from gnosis.routers.notes import create_note
    return await create_note(
        NoteCreate(
            title=ai_data.get("title", url),
            body=body,
            note_type="literature",
            status="draft",
            folder=folder,
            tags=ai_data.get("tags", []),
            source_url=url,
        ),
        db=db,
    )
