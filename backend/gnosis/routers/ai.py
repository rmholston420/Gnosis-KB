"""
AI Router — /api/v1/ai

Endpoints:
  POST /chat                 — LightRAG hybrid vault query
  POST /summarize/{note_id}  — AI summary of a single note
  POST /suggest-links/{note_id} — Suggest wikilinks for a note
  POST /suggest-tags/{note_id}  — Suggest tags for a note
  POST /critique/{note_id}   — Zettelkasten atomicity critique
  GET  /orphan-audit         — AI-powered orphan remediation suggestions
  POST /daily-review         — Daily review from inbox notes
  GET  /stream/chat          — SSE streaming chat (query param: message, mode)
  POST /generate-moc         — Map of Content generator (Feature 3)

RAG pipeline
------------
Chat and stream/chat use Qdrant hybrid search (dense + sparse prefetch,
RRF fusion) to retrieve relevant note snippets, then inject them as
system context before calling the LLM. LightRAG is used when available
and its instance is warm; otherwise Qdrant RAG is the primary path.

Namespace contract
------------------
Every endpoint is scoped to the authenticated user’s accessible vault set.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import get_current_user, get_vault_owner_ids
from gnosis.core.namespace import scoped_note_stmt
from gnosis.database import get_session
from gnosis.models.link import Link
from gnosis.models.note import Note
from gnosis.models.user import User
from gnosis.schemas.ai import (
    ChatRequest,
    ChatResponse,
    CritiqueResponse,
    DailyReviewResponse,
    LinkSuggestionsResponse,
    MocRequest,
    MocResponse,
    MocSection,
    OrphanAuditItem,
    OrphanAuditResponse,
    SummarizeResponse,
    TagSuggestionsResponse,
)
from gnosis.services.graph_rag import graph_rag
from gnosis.services.llm_provider import llm_provider
from gnosis.services.vector_store import hybrid_search

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])

_VAULT_SYSTEM_PROMPT = (
    "You are Gnosis, a personal knowledge assistant. "
    "You have access to the user’s private Zettelkasten vault. "
    "Answer questions using the vault context provided. "
    "If the context does not contain enough information, say so honestly — "
    "do not invent notes or facts. "
    "Keep answers concise and cite note titles when relevant."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_rag_context(hits: list[dict]) -> str:
    """Format Qdrant search hits into a system-prompt context block."""
    if not hits:
        return ""
    parts = ["Relevant notes from the vault:\n"]
    for i, h in enumerate(hits, 1):
        title = h.get("title", "Untitled")
        snippet = h.get("text_snippet", "").strip()
        folder = h.get("folder", "")
        parts.append(f"{i}. [{title}] ({folder})\n{snippet}\n")
    return "\n".join(parts)


async def _qdrant_rag_complete(
    message: str,
    owner_ids: set[int],
    mode: str = "hybrid",
) -> str:
    """Retrieve vault context via Qdrant then complete with LLM."""
    hits = hybrid_search(message, owner_ids=owner_ids, top_k=5)
    context = _build_rag_context(hits)
    system = _VAULT_SYSTEM_PROMPT
    if context:
        system = system + "\n\n" + context
    return await llm_provider.complete(prompt=message, system=system)


async def _qdrant_rag_stream(
    message: str,
    owner_ids: set[int],
    mode: str = "hybrid",
) -> AsyncGenerator[str, None]:
    """Retrieve vault context via Qdrant then stream tokens from LLM."""
    hits = hybrid_search(message, owner_ids=owner_ids, top_k=5)
    context = _build_rag_context(hits)
    system = _VAULT_SYSTEM_PROMPT
    if context:
        system = system + "\n\n" + context
    async for token in llm_provider.stream(prompt=message, system=system):
        yield token


async def _get_note_or_404(
    note_id: str,
    session: AsyncSession,
    owner_ids: set[int],
) -> Note:
    """Fetch a note by ID, scoped to *owner_ids*, or raise HTTP 404."""
    base = (
        select(Note)
        .where(Note.id == note_id, Note.is_deleted.is_(False))
    )
    stmt = scoped_note_stmt(base, owner_ids)
    result = await session.execute(stmt)
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note {note_id!r} not found")
    return note


def _parse_json_list(text: str) -> list[str]:
    """Extract a JSON array from LLM output that may contain surrounding prose."""
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return [str(item) for item in result]
        except json.JSONDecodeError:
            pass
    lines = [
        re.sub(r"^[\-\*\d\.\)]+\s*", "", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]
    return [line for line in lines if line][:10]


def _build_moc_markdown(topic: str, moc_title: str, sections: list[MocSection]) -> str:
    """Render a list of MocSection objects into a full Markdown MOC body."""
    from datetime import datetime
    now = datetime.now()
    ts = now.strftime("%Y%m%d-%H%M%S")
    frontmatter = (
        f"---\n"
        f"id: {ts}\n"
        f"title: {moc_title}\n"
        f"type: moc\n"
        f"status: evergreen\n"
        f"tags: moc, {topic.lower().replace(' ', '-')}\n"
        f"created: {now.isoformat(timespec='seconds')}\n"
        f"modified: {now.isoformat(timespec='seconds')}\n"
        f"---\n\n"
    )
    body_parts = [f"# {moc_title}\n"]
    body_parts.append(
        f"> Auto-generated Map of Content for **{topic}**.  \n"
        f"> Edit freely — the vault watcher will sync all wikilinks.\n\n"
    )
    for section in sections:
        body_parts.append(f"## {section.heading}\n\n")
        if section.summary:
            body_parts.append(f"{section.summary}\n\n")
        for link in section.wikilinks:
            body_parts.append(f"- [[{link}]]\n")
        body_parts.append("\n")
    return frontmatter + "".join(body_parts)


# ---------------------------------------------------------------------------
# POST /ai/chat
# ---------------------------------------------------------------------------

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="RAG-powered chat over the vault",
)
async def chat(
    req: ChatRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> ChatResponse:
    # Prefer LightRAG when warm; fall back to Qdrant RAG; then bare LLM.
    if await graph_rag.is_available(current_user.id):
        answer = await graph_rag.query(
            req.message, user_id=current_user.id, owner_ids=owner_ids, mode=req.mode
        )
    elif llm_provider.is_available:
        answer = await _qdrant_rag_complete(req.message, owner_ids=owner_ids, mode=req.mode)
    else:
        raise HTTPException(
            status_code=503,
            detail="No AI provider is available. Start Ollama or configure GROQ_API_KEY.",
        )
    return ChatResponse(answer=answer, mode=req.mode, session_id=req.session_id)


# ---------------------------------------------------------------------------
# POST /ai/summarize/{note_id}
# ---------------------------------------------------------------------------

@router.post("/summarize/{note_id}", response_model=SummarizeResponse)
async def summarize_note(
    note_id: str,
    session: AsyncSession = Depends(get_session),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> SummarizeResponse:
    if not llm_provider.is_available:
        raise HTTPException(status_code=503, detail="No LLM provider available")
    note = await _get_note_or_404(note_id, session, owner_ids)
    prompt = (
        f"Note title: {note.title}\n\nNote body:\n{note.body[:6000]}\n\n"
        "Write a concise 2–4 sentence summary of this note. "
        "Focus on the core idea and its significance."
    )
    summary = await llm_provider.complete(prompt, temperature=0.2)
    return SummarizeResponse(note_id=note_id, summary=summary.strip())


# ---------------------------------------------------------------------------
# POST /ai/suggest-links/{note_id}
# ---------------------------------------------------------------------------

@router.post("/suggest-links/{note_id}", response_model=LinkSuggestionsResponse)
async def suggest_links(
    note_id: str,
    session: AsyncSession = Depends(get_session),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> LinkSuggestionsResponse:
    if not llm_provider.is_available:
        raise HTTPException(status_code=503, detail="No LLM provider available")
    note = await _get_note_or_404(note_id, session, owner_ids)
    base = (
        select(Note.id, Note.title)
        .where(Note.id != note_id, Note.is_deleted.is_(False))
        .order_by(func.random())
        .limit(80)
    )
    stmt = scoped_note_stmt(base, owner_ids)
    result = await session.execute(stmt)
    candidates = result.all()
    titles_text = "\n".join(f"- {row.title}" for row in candidates)
    prompt = (
        f"Source note: {note.title}\n\nBody (excerpt):\n{note.body[:3000]}\n\n"
        f"Existing notes in the vault:\n{titles_text}\n\n"
        "Which 3–5 vault notes would make the most meaningful wikilinks from the source note? "
        "Return a JSON array of note titles only. Example: [\"Title A\", \"Title B\"]\n"
        "Also provide a brief rationale for each as a second JSON array of strings."
    )
    raw = await llm_provider.complete(prompt, temperature=0.3)
    arrays = re.findall(r"\[.*?\]", raw, re.DOTALL)
    suggestions: list[str] = []
    rationale: list[str] = []
    if arrays:
        try:
            suggestions = json.loads(arrays[0])
        except json.JSONDecodeError:
            suggestions = _parse_json_list(arrays[0])
    if len(arrays) >= 2:
        try:
            rationale = json.loads(arrays[1])
        except json.JSONDecodeError:
            rationale = _parse_json_list(arrays[1])
    return LinkSuggestionsResponse(
        note_id=note_id,
        suggestions=[str(s) for s in suggestions],
        rationale=[str(r) for r in rationale],
    )


# ---------------------------------------------------------------------------
# POST /ai/suggest-tags/{note_id}
# ---------------------------------------------------------------------------

@router.post("/suggest-tags/{note_id}", response_model=TagSuggestionsResponse)
async def suggest_tags(
    note_id: str,
    session: AsyncSession = Depends(get_session),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> TagSuggestionsResponse:
    if not llm_provider.is_available:
        raise HTTPException(status_code=503, detail="No LLM provider available")
    note = await _get_note_or_404(note_id, session, owner_ids)
    prompt = (
        f"Note title: {note.title}\n\nBody:\n{note.body[:3000]}\n\n"
        "Suggest 3–8 concise, lowercase tags for this note. "
        "Tags should be single words or short hyphenated phrases. "
        "Return a JSON array of strings. Example: [\"zettelkasten\", \"spaced-repetition\"]"
    )
    raw = await llm_provider.complete(prompt, temperature=0.2)
    tags = _parse_json_list(raw)
    return TagSuggestionsResponse(note_id=note_id, tags=tags)


# ---------------------------------------------------------------------------
# POST /ai/critique/{note_id}
# ---------------------------------------------------------------------------

@router.post("/critique/{note_id}", response_model=CritiqueResponse)
async def critique_note(
    note_id: str,
    session: AsyncSession = Depends(get_session),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> CritiqueResponse:
    if not llm_provider.is_available:
        raise HTTPException(status_code=503, detail="No LLM provider available")
    note = await _get_note_or_404(note_id, session, owner_ids)
    prompt = (
        f"Note title: {note.title}\n\nBody:\n{note.body[:4000]}\n\n"
        "Critique this note from a Zettelkasten perspective. Evaluate:\n"
        "1. Atomicity: Does it contain exactly one idea?\n"
        "2. Autonomy: Can it stand alone without external context?\n"
        "3. Connections: Does it suggest links to other concepts?\n"
        "4. Clarity: Is the core insight expressed clearly?\n\n"
        "Provide a score (1-10) for each dimension and a brief suggestion for improvement. "
        "Format as JSON: {\"atomicity\": {\"score\": N, \"suggestion\": \"...\"},...}"
    )
    raw = await llm_provider.complete(prompt, temperature=0.3)
    critique_data: dict = {}
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            critique_data = json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return CritiqueResponse(
        note_id=note_id,
        critique=critique_data or {"raw": raw},
        overall_score=(
            sum(v.get("score", 5) for v in critique_data.values() if isinstance(v, dict)) //
            max(len(critique_data), 1)
        ) if critique_data else 5,
    )


# ---------------------------------------------------------------------------
# GET /ai/orphan-audit
# ---------------------------------------------------------------------------

@router.get("/orphan-audit", response_model=OrphanAuditResponse)
async def orphan_audit(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> OrphanAuditResponse:
    linked_ids = (
        select(Note.id)
        .join(Link, (Link.source_id == Note.id) | (Link.target_id == Note.id))
    )
    base = (
        select(Note)
        .where(
            Note.is_deleted.is_(False),
            Note.id.not_in(linked_ids),
        )
        .order_by(Note.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(scoped_note_stmt(base, owner_ids))
    rows = result.scalars().all()

    if not rows or not llm_provider.is_available:
        return OrphanAuditResponse(items=[], total=len(rows))

    titles_body = "\n".join(
        f"- [{r.title}]: {r.body[:200]}..." for r in rows
    )
    prompt = (
        f"These {len(rows)} notes have no incoming or outgoing wikilinks (orphans):\n\n"
        f"{titles_body}\n\n"
        "For each orphan note, suggest:\n"
        "1. A reason it might be isolated (missing context, too broad, duplicate?).\n"
        "2. A concrete action (link to X, split into Y and Z, archive).\n"
        "Return as a JSON array: [{\"title\": \"...\", \"reason\": \"...\", \"action\": \"...\"}]\n"
        "Be concise — one sentence per field."
    )
    raw = await llm_provider.complete(prompt, temperature=0.4)
    items: list[OrphanAuditItem] = []
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if json_match:
        try:
            parsed_items = json.loads(json_match.group())
            items = [
                OrphanAuditItem(
                    note_id=next(
                        (r.id for r in rows if r.title == item.get("title")), ""
                    ),
                    title=item.get("title", ""),
                    reason=item.get("reason", ""),
                    action=item.get("action", ""),
                )
                for item in parsed_items
                if isinstance(item, dict)
            ]
        except json.JSONDecodeError:
            pass
    return OrphanAuditResponse(items=items, total=len(rows))


# ---------------------------------------------------------------------------
# POST /ai/daily-review
# ---------------------------------------------------------------------------

@router.post("/daily-review", response_model=DailyReviewResponse)
async def daily_review(
    session: AsyncSession = Depends(get_session),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> DailyReviewResponse:
    today_str = date.today().isoformat()
    base = (
        select(Note)
        .where(
            Note.folder == "00-inbox",
            Note.is_deleted.is_(False),
            func.date(Note.created_at) == today_str,
        )
        .order_by(Note.created_at.desc())
        .limit(20)
    )
    result = await session.execute(scoped_note_stmt(base, owner_ids))
    notes = result.scalars().all()
    if not notes or not llm_provider.is_available:
        return DailyReviewResponse(
            date=today_str, summary="No inbox notes today.", suggestions=[], note_count=len(notes)
        )
    notes_text = "\n\n".join(
        f"### {n.title}\n{n.body[:500]}" for n in notes
    )
    prompt = (
        f"Today’s inbox notes ({today_str}):\n\n{notes_text}\n\n"
        "Provide:\n"
        "1. A brief synthesis of today’s captures (2-3 sentences).\n"
        "2. 3-5 actionable suggestions (process, link, promote to project, etc).\n"
        "Format: {\"summary\": \"...\", \"suggestions\": [\"...\", ...]}"
    )
    raw = await llm_provider.complete(prompt, temperature=0.3)
    summary_text = raw
    suggestions: list[str] = []
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            summary_text = parsed.get("summary", raw)
            suggestions = parsed.get("suggestions", [])
        except json.JSONDecodeError:
            pass
    return DailyReviewResponse(
        date=today_str,
        summary=summary_text,
        suggestions=suggestions,
        note_count=len(notes),
    )


# ---------------------------------------------------------------------------
# GET /ai/stream/chat  (SSE)
# ---------------------------------------------------------------------------

@router.get("/stream/chat")
async def stream_chat(
    message: str = Query(..., min_length=1),
    mode: str = Query("hybrid", pattern="^(hybrid|local|naive)$"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> StreamingResponse:
    """SSE endpoint: streams the AI answer token-by-token, scoped to accessible vaults.

    RAG pipeline priority:
      1. LightRAG (when installed and warm for current user)
      2. Qdrant hybrid search → context-injected LLM stream (default)
      3. Error if no LLM available
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            if await graph_rag.is_available(current_user.id):
                async for token in graph_rag.stream(
                    message, user_id=current_user.id, owner_ids=owner_ids, mode=mode
                ):
                    yield f"data: {json.dumps({'token': token})}\n\n"
            elif llm_provider.is_available:
                async for token in _qdrant_rag_stream(
                    message, owner_ids=owner_ids, mode=mode
                ):
                    yield f"data: {json.dumps({'token': token})}\n\n"
            else:
                yield f"data: {json.dumps({'error': 'No AI provider available'})}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.exception("SSE stream error")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# POST /ai/generate-moc
# ---------------------------------------------------------------------------

@router.post("/generate-moc", response_model=MocResponse)
async def generate_moc(
    req: MocRequest,
    session: AsyncSession = Depends(get_session),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> MocResponse:
    if not llm_provider.is_available:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider available. Start Ollama or configure GROQ_API_KEY.",
        )
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="Topic must not be empty.")

    base = (
        select(Note)
        .where(
            Note.is_deleted.is_(False),
            Note.body.ilike(f"%{topic}%"),
        )
        .order_by(func.random())
        .limit(req.max_notes or 40)
    )
    result = await session.execute(scoped_note_stmt(base, owner_ids))
    notes = result.scalars().all()

    if not notes:
        raise HTTPException(
            status_code=404,
            detail=f"No notes found containing '{topic}'. Add some notes first.",
        )

    notes_context = "\n\n".join(
        f"### {n.title}\nType: {n.note_type} | Status: {n.status}\n{n.body[:400]}"
        for n in notes
    )
    moc_title = req.title or f"MOC — {topic.title()}"
    prompt = (
        f"Create a Map of Content (MOC) for the topic: **{topic}**\n\n"
        f"Available notes (excerpts):\n{notes_context}\n\n"
        f"MOC title: {moc_title}\n\n"
        "Organise the notes into 3-6 thematic sections. For each section provide:\n"
        "— A heading (short phrase)\n"
        "— A one-sentence summary of the section’s theme\n"
        "— A list of note titles that belong in this section (use exact titles)\n\n"
        "Return as JSON:\n"
        "[{\"heading\": \"...\", \"summary\": \"...\", \"wikilinks\": [\"Note Title\", ...]}]\n"
        "Only include notes from the list above. No invented titles."
    )
    raw = await llm_provider.complete(prompt, temperature=0.4, max_tokens=2000)
    sections: list[MocSection] = []
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if json_match:
        try:
            parsed_sections = json.loads(json_match.group())
            sections = [
                MocSection(
                    heading=s.get("heading", "Section"),
                    summary=s.get("summary", ""),
                    wikilinks=s.get("wikilinks", []),
                )
                for s in parsed_sections
                if isinstance(s, dict)
            ]
        except json.JSONDecodeError:
            pass

    moc_body = _build_moc_markdown(topic, moc_title, sections)
    return MocResponse(
        title=moc_title,
        topic=topic,
        sections=sections,
        markdown=moc_body,
        note_count=len(notes),
    )
