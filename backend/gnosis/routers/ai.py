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

Dependencies:
  services/llm_provider.py — three-tier LLM fallback
  services/graph_rag.py    — LightRAG for vault-aware answers
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import get_current_user
from gnosis.database import get_session
from gnosis.models.note import Note
from gnosis.models.user import User
from gnosis.schemas.ai import (
    ChatRequest,
    ChatResponse,
    CritiqueResponse,
    DailyReviewResponse,
    LinkSuggestionsResponse,
    OrphanAuditItem,
    OrphanAuditResponse,
    SummarizeResponse,
    TagSuggestionsResponse,
)
from gnosis.services.graph_rag import graph_rag
from gnosis.services.llm_provider import llm_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_note_or_404(note_id: str, session: AsyncSession) -> Note:
    """Fetch a note by ID or raise HTTP 404."""
    result = await session.execute(
        select(Note).where(Note.id == note_id, Note.is_deleted.is_(False))
    )
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
    # Fallback: split on newlines and strip bullets
    lines = [
        re.sub(r"^[\-\*\d\.\)]+\s*", "", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]
    return [line for line in lines if line][:10]


# ---------------------------------------------------------------------------
# POST /ai/chat
# ---------------------------------------------------------------------------

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="RAG-powered chat over the vault",
    description=(
        "Query your entire Gnosis vault using LightRAG dual-level graph-RAG. "
        "Supports three modes: 'local' (entity-specific), "
        "'global' (thematic synthesis), and 'hybrid' (default)."
    ),
)
async def chat(
    req: ChatRequest,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """RAG chat over the full vault.

    Args:
        req: Chat request containing message and query mode.
        session: Database session (unused here, reserved for history persistence).
        _current_user: Authenticated user.

    Returns:
        ChatResponse with answer and mode.
    """
    if graph_rag.is_available:
        answer = await graph_rag.query(req.message, mode=req.mode)
    elif llm_provider.is_available:
        answer = await llm_provider.complete(
            prompt=req.message,
            system=(
                "You are a knowledgeable assistant. The vault graph-RAG is not available "
                "so answer from general knowledge and note that you cannot search the vault."
            ),
        )
    else:
        raise HTTPException(
            status_code=503,
            detail="No AI provider is available. Start Ollama or configure GROQ_API_KEY.",
        )

    return ChatResponse(answer=answer, mode=req.mode, session_id=req.session_id)


# ---------------------------------------------------------------------------
# POST /ai/summarize/{note_id}
# ---------------------------------------------------------------------------

@router.post(
    "/summarize/{note_id}",
    response_model=SummarizeResponse,
    summary="Summarize a note",
)
async def summarize_note(
    note_id: str,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> SummarizeResponse:
    """Generate an AI summary for the specified note.

    Args:
        note_id: Unique timestamp note ID.
        session: Database session.
        _current_user: Authenticated user.

    Returns:
        SummarizeResponse with note_id and summary text.
    """
    if not llm_provider.is_available:
        raise HTTPException(status_code=503, detail="No LLM provider available")

    note = await _get_note_or_404(note_id, session)

    prompt = (
        f"Note title: {note.title}\n\n"
        f"Note body:\n{note.body[:6000]}\n\n"
        "Write a concise 2–4 sentence summary of this note. "
        "Focus on the core idea and its significance."
    )
    summary = await llm_provider.complete(prompt, temperature=0.2)
    return SummarizeResponse(note_id=note_id, summary=summary.strip())


# ---------------------------------------------------------------------------
# POST /ai/suggest-links/{note_id}
# ---------------------------------------------------------------------------

@router.post(
    "/suggest-links/{note_id}",
    response_model=LinkSuggestionsResponse,
    summary="Suggest wikilinks for a note",
)
async def suggest_links(
    note_id: str,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> LinkSuggestionsResponse:
    """Suggest existing notes to link from this note.

    Retrieves a random sample of other note titles and asks the LLM
    to identify conceptually related ones.

    Args:
        note_id: Source note ID.
        session: Database session.
        _current_user: Authenticated user.

    Returns:
        LinkSuggestionsResponse with suggestions and rationale.
    """
    if not llm_provider.is_available:
        raise HTTPException(status_code=503, detail="No LLM provider available")

    note = await _get_note_or_404(note_id, session)

    # Sample up to 80 other note titles for context
    result = await session.execute(
        select(Note.id, Note.title)
        .where(Note.id != note_id, Note.is_deleted.is_(False))
        .order_by(func.random())
        .limit(80)
    )
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

    # Parse two JSON arrays from the response
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

@router.post(
    "/suggest-tags/{note_id}",
    response_model=TagSuggestionsResponse,
    summary="Suggest tags for a note",
)
async def suggest_tags(
    note_id: str,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> TagSuggestionsResponse:
    """Suggest relevant tags for the specified note.

    Args:
        note_id: Note ID.
        session: Database session.
        _current_user: Authenticated user.

    Returns:
        TagSuggestionsResponse with a list of suggested lowercase tags.
    """
    if not llm_provider.is_available:
        raise HTTPException(status_code=503, detail="No LLM provider available")

    note = await _get_note_or_404(note_id, session)

    prompt = (
        f"Note title: {note.title}\n\nBody:\n{note.body[:3000]}\n\n"
        "Suggest 3–8 concise, lowercase tags for this note. "
        "Tags should be single words or hyphenated phrases. "
        "Return a JSON array of strings only. Example: [\"buddhism\", \"epistemology\", \"graph-theory\"]"
    )
    raw = await llm_provider.complete(prompt, temperature=0.2)
    tags = _parse_json_list(raw)
    # Normalise to lowercase, strip whitespace
    tags = [t.lower().strip() for t in tags if t.strip()]

    return TagSuggestionsResponse(note_id=note_id, suggested_tags=tags)


# ---------------------------------------------------------------------------
# POST /ai/critique/{note_id}
# ---------------------------------------------------------------------------

@router.post(
    "/critique/{note_id}",
    response_model=CritiqueResponse,
    summary="Zettelkasten atomicity critique",
)
async def critique_note(
    note_id: str,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> CritiqueResponse:
    """Evaluate a note against Zettelkasten quality criteria.

    Four criteria assessed:
      1. Atomicity — exactly one idea?
      2. Connectivity — at least 3 outgoing links?
      3. Self-containedness — understandable without context?
      4. Insight density — captures why this matters?

    Args:
        note_id: Note to critique.
        session: Database session.
        _current_user: Authenticated user.

    Returns:
        CritiqueResponse with per-criterion feedback and overall assessment.
    """
    if not llm_provider.is_available:
        raise HTTPException(status_code=503, detail="No LLM provider available")

    note = await _get_note_or_404(note_id, session)

    prompt = (
        f"Note title: {note.title}\n\nBody:\n{note.body[:4000]}\n\n"
        "Evaluate this Zettelkasten permanent note on four criteria. "
        "Return a JSON object with exactly these keys: "
        '"atomicity", "connectivity", "self_containedness", "insight_density", "overall". '
        "Each value should be 1–3 sentences of actionable feedback. "
        "Example: {\"atomicity\": \"...\", \"connectivity\": \"...\", "
        '"self_containedness": \"...\", "insight_density\": \"...\", "overall\": \"...\"}'
    )
    raw = await llm_provider.complete(prompt, temperature=0.2)

    # Parse JSON from LLM output
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return CritiqueResponse(note_id=note_id, **data)
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: return raw text in all fields
    return CritiqueResponse(
        note_id=note_id,
        atomicity=raw,
        connectivity="See above",
        self_containedness="See above",
        insight_density="See above",
        overall="Critique returned in atomicity field (JSON parse failed).",
    )


# ---------------------------------------------------------------------------
# GET /ai/orphan-audit
# ---------------------------------------------------------------------------

@router.get(
    "/orphan-audit",
    response_model=OrphanAuditResponse,
    summary="AI-powered orphan audit",
)
async def orphan_audit(
    limit: int = Query(default=10, ge=1, le=50, description="Max orphans to process"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> OrphanAuditResponse:
    """Find isolated notes and suggest connections.

    An orphan is a note with no incoming or outgoing wikilinks.
    For each orphan the LLM suggests 3–5 existing notes to link to.

    Args:
        limit: Maximum number of orphans to audit per request.
        session: Database session.
        _current_user: Authenticated user.

    Returns:
        OrphanAuditResponse with per-orphan connection suggestions.
    """
    # Import here to avoid circular imports
    from gnosis.models.note import Note as NoteModel

    # Notes with no outgoing links (subquery via link table)
    from sqlalchemy import text

    orphan_result = await session.execute(
        text(
            """
            SELECT n.id, n.title, n.body
            FROM notes n
            WHERE n.is_deleted = false
              AND NOT EXISTS (
                  SELECT 1 FROM links l WHERE l.source_id = n.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM links l WHERE l.target_id = n.id
              )
            ORDER BY n.created_at DESC
            LIMIT :lim
            """
        ),
        {"lim": limit},
    )
    orphans = orphan_result.fetchall()

    # Sample potential connection targets
    target_result = await session.execute(
        select(Note.title).where(Note.is_deleted.is_(False)).limit(60)
    )
    candidate_titles = [row[0] for row in target_result.all()]
    titles_text = "\n".join(f"- {t}" for t in candidate_titles)

    items: list[OrphanAuditItem] = []
    for orphan in orphans:
        if not llm_provider.is_available:
            suggestions: list[str] = []
        else:
            prompt = (
                f"Orphan note title: {orphan.title}\n"
                f"Body excerpt: {str(orphan.body)[:1500]}\n\n"
                f"Vault note titles:\n{titles_text}\n\n"
                "Suggest 3–5 vault notes this orphan should link to. "
                "Return a JSON array of note titles only."
            )
            raw = await llm_provider.complete(prompt, temperature=0.3)
            suggestions = _parse_json_list(raw)

        items.append(
            OrphanAuditItem(
                note_id=orphan.id,
                title=orphan.title,
                suggestions=suggestions,
            )
        )

    return OrphanAuditResponse(orphan_count=len(items), items=items)


# ---------------------------------------------------------------------------
# POST /ai/daily-review
# ---------------------------------------------------------------------------

@router.post(
    "/daily-review",
    response_model=DailyReviewResponse,
    summary="Generate daily review from inbox notes",
)
async def daily_review(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> DailyReviewResponse:
    """Synthesise today's inbox notes into a daily review.

    Fetches all notes in the 00-inbox folder created today,
    asks the LLM to produce a summary and action items.

    Args:
        session: Database session.
        _current_user: Authenticated user.

    Returns:
        DailyReviewResponse with date, summary, inbox count, and action items.
    """
    today_str = date.today().isoformat()

    result = await session.execute(
        select(Note)
        .where(
            Note.folder == "00-inbox",
            Note.is_deleted.is_(False),
            func.date(Note.created_at) == today_str,
        )
        .order_by(Note.created_at)
    )
    inbox_notes = result.scalars().all()

    if not inbox_notes:
        return DailyReviewResponse(
            date=today_str,
            summary="No inbox notes captured today.",
            inbox_note_count=0,
            action_items=[],
        )

    notes_text = "\n\n---\n\n".join(
        f"**{n.title}**\n{n.body[:800]}" for n in inbox_notes
    )

    if not llm_provider.is_available:
        return DailyReviewResponse(
            date=today_str,
            summary=f"{len(inbox_notes)} inbox note(s) captured today. LLM unavailable for synthesis.",
            inbox_note_count=len(inbox_notes),
            action_items=[],
        )

    prompt = (
        f"Today's inbox notes ({today_str}):\n\n{notes_text}\n\n"
        "1. Write a 2–4 sentence synthesis of today's captures.\n"
        "2. List 3–5 concrete action items (process, link, or expand these notes).\n"
        "Return as JSON: {\"summary\": \"...\", \"action_items\": [\"...\", ...]}"
    )
    raw = await llm_provider.complete(prompt, temperature=0.3)

    summary = "Daily review generated."
    action_items: list[str] = []
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            summary = data.get("summary", summary)
            action_items = data.get("action_items", [])
        except json.JSONDecodeError:
            summary = raw[:500]

    return DailyReviewResponse(
        date=today_str,
        summary=summary,
        inbox_note_count=len(inbox_notes),
        action_items=action_items,
    )


# ---------------------------------------------------------------------------
# GET /ai/stream/chat  (Server-Sent Events)
# ---------------------------------------------------------------------------

@router.get(
    "/stream/chat",
    summary="SSE streaming chat",
    description=(
        "Server-Sent Events endpoint. Pass ?message=...&mode=hybrid. "
        "Each SSE event contains a text chunk. "
        "Final event has data: [DONE]."
    ),
    response_class=StreamingResponse,
)
async def stream_chat(
    message: str = Query(..., min_length=1, max_length=8000),
    mode: str = Query(default="hybrid"),
) -> StreamingResponse:
    """Stream AI responses via Server-Sent Events.

    Uses LightRAG for vault-aware answers when available,
    falls back to plain LLM completion.

    Args:
        message: User question (query param).
        mode: LightRAG query mode (query param).

    Returns:
        StreamingResponse with SSE text/event-stream content type.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        """Yield SSE-formatted chunks from the LLM."""
        if not llm_provider.is_available:
            yield "data: No AI provider available. Start Ollama or configure GROQ_API_KEY.\n\n"
            yield "data: [DONE]\n\n"
            return

        # For streaming we bypass LightRAG (which doesn't stream natively)
        # and use the direct LLM with a retrieval-augmented system prompt.
        if graph_rag.is_available:
            context = await graph_rag.query(message, mode=mode)
            system = (
                f"You are a knowledge base assistant. "
                f"Use the following vault context to answer:\n\n{context[:4000]}"
            )
        else:
            system = "You are a helpful knowledge management assistant."

        try:
            async for chunk in llm_provider.stream(prompt=message, system=system):
                # Escape newlines within SSE data field
                safe_chunk = chunk.replace("\n", " ")
                yield f"data: {safe_chunk}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.error("SSE stream error: %s", exc)
            yield f"data: Stream error: {exc}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
