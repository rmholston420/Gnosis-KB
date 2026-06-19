"""AI / RAG router.

Endpoints:
- POST /chat — RAG-powered chat over the vault (LightRAG)
- POST /summarize/{note_id} — AI note summary
- POST /suggest-links/{note_id} — Suggest wikilinks
- POST /suggest-tags/{note_id} — Suggest tags
- POST /critique/{note_id} — Zettelkasten critique
- GET  /stream/chat — SSE streaming chat
- GET  /orphan-audit — AI orphan connection suggestions
- POST /daily-review — Daily inbox review
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.database import get_db
from gnosis.models.note import Note
from gnosis.schemas.ai import (
    ChatRequest,
    ChatResponse,
    CritiqueResponse,
    LinkSuggestion,
    LinkSuggestionsResponse,
    SummarizeResponse,
)
from gnosis.services.graph_rag import query_vault
from gnosis.services.llm_provider import chat_completion, stream_chat_completion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse, summary="RAG chat over the vault")
async def ai_chat(
    req: ChatRequest, db: AsyncSession = Depends(get_db)
) -> ChatResponse:
    """Ask a question about your vault using LightRAG graph-aware retrieval.

    Args:
        req: ChatRequest with message, history, and LightRAG mode.
        db: Database session.

    Returns:
        ChatResponse with answer and cited source note titles.
    """
    answer = await query_vault(req.message, mode=req.mode)
    return ChatResponse(
        answer=answer,
        sources=[],
        mode=req.mode,
        session_id=req.session_id,
    )


@router.get("/stream/chat", summary="Streaming SSE chat")
async def stream_chat(
    message: str,
    mode: str = "hybrid",
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream AI chat responses via Server-Sent Events.

    Connect via EventSource in the browser. Each event is a text chunk.
    The final event has data: '[DONE]'.

    Args:
        message: User question.
        mode: LightRAG query mode.
        db: Database session.

    Returns:
        StreamingResponse with text/event-stream content type.
    """
    messages = [{"role": "user", "content": message}]

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for chunk in stream_chat_completion(messages):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/summarize/{note_id}", response_model=SummarizeResponse, summary="Summarize a note")
async def summarize_note(
    note_id: str, db: AsyncSession = Depends(get_db)
) -> SummarizeResponse:
    """Generate an AI summary of a note.

    Args:
        note_id: Target note ID.
        db: Database session.

    Returns:
        SummarizeResponse with summary, key concepts, and suggested tags.
    """
    result = await db.execute(select(Note).where(Note.id == note_id, Note.is_deleted.is_(False)))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note {note_id} not found")

    prompt = [
        {"role": "system", "content": "You are a knowledge management assistant. Return JSON only."},
        {"role": "user", "content": f"""Summarize this note and extract key concepts and suggested tags.
Title: {note.title}

{note.body}

Return JSON: {{"summary": "...", "key_concepts": [...], "suggested_tags": [...]}}"""},
    ]

    try:
        response = await chat_completion(prompt, temperature=0.3)
        import re
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = {"summary": response, "key_concepts": [], "suggested_tags": []}
    except Exception as e:
        parsed = {"summary": f"Summary unavailable: {e}", "key_concepts": [], "suggested_tags": []}

    return SummarizeResponse(
        note_id=note_id,
        title=note.title,
        summary=parsed.get("summary", ""),
        key_concepts=parsed.get("key_concepts", []),
        suggested_tags=parsed.get("suggested_tags", []),
    )


@router.post("/critique/{note_id}", response_model=CritiqueResponse, summary="Zettelkasten critique")
async def critique_note(
    note_id: str, db: AsyncSession = Depends(get_db)
) -> CritiqueResponse:
    """Critique a note against Zettelkasten principles.

    Evaluates atomicity, connectivity, self-containedness, and insight density.

    Args:
        note_id: Target note ID.
        db: Database session.

    Returns:
        CritiqueResponse with scores and actionable feedback.
    """
    result = await db.execute(select(Note).where(Note.id == note_id, Note.is_deleted.is_(False)))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note {note_id} not found")

    prompt = [
        {"role": "system", "content": "You are a Zettelkasten expert. Return JSON only."},
        {"role": "user", "content": f"""Critique this note on 4 dimensions (score 1-5 each):
1. Atomicity: Does it contain exactly ONE idea?
2. Connectivity: Does it have outgoing links (\u22653 ideal)? Current outgoing links: {len(note.outgoing_links or [])}.
3. Self-containedness: Can it be understood without external context?
4. Insight density: Does it capture 'why this matters'?

Note title: {note.title}
Note body:
{note.body[:2000]}

Return JSON: {{"atomicity_score":N,"atomicity_feedback":"...","connectivity_score":N,"connectivity_feedback":"...","self_containedness_score":N,"self_containedness_feedback":"...","insight_density_score":N,"insight_density_feedback":"...","overall_feedback":"...","action_items":[...]}}"""},
    ]

    try:
        response = await chat_completion(prompt, temperature=0.3)
        import re
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            raise ValueError("No JSON in response")
    except Exception as e:
        parsed = {
            "atomicity_score": 3, "atomicity_feedback": f"Evaluation unavailable: {e}",
            "connectivity_score": 3, "connectivity_feedback": "",
            "self_containedness_score": 3, "self_containedness_feedback": "",
            "insight_density_score": 3, "insight_density_feedback": "",
            "overall_feedback": f"Critique failed: {e}",
            "action_items": [],
        }

    return CritiqueResponse(
        note_id=note_id,
        **{k: parsed.get(k, "") for k in [
            "atomicity_score", "atomicity_feedback",
            "connectivity_score", "connectivity_feedback",
            "self_containedness_score", "self_containedness_feedback",
            "insight_density_score", "insight_density_feedback",
            "overall_feedback",
        ]},
        action_items=parsed.get("action_items", []),
    )


@router.post("/suggest-links/{note_id}", response_model=LinkSuggestionsResponse, summary="Suggest wikilinks")
async def suggest_links(
    note_id: str, db: AsyncSession = Depends(get_db)
) -> LinkSuggestionsResponse:
    """Suggest wikilinks for a note based on semantic similarity.

    Args:
        note_id: Source note ID.
        db: Database session.

    Returns:
        LinkSuggestionsResponse with up to 5 suggested wikilinks.
    """
    result = await db.execute(select(Note).where(Note.id == note_id, Note.is_deleted.is_(False)))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note {note_id} not found")

    # Get other notes for context (limit to 20 most recent for prompt size)
    others_result = await db.execute(
        select(Note.id, Note.title).where(
            Note.is_deleted.is_(False), Note.id != note_id
        ).order_by(Note.created_at.desc()).limit(20)
    )
    others = others_result.all()
    other_titles = [f"- {r.id}: {r.title}" for r in others]

    prompt = [
        {"role": "system", "content": "You are a knowledge management assistant. Return JSON only."},
        {"role": "user", "content": f"""Suggest up to 5 notes to link from this note.

Source note:
Title: {note.title}
Body: {note.body[:1000]}

Available notes:
{chr(10).join(other_titles)}

Return JSON: {{"suggestions": [{{"target_note_id": "...", "target_title": "...", "reason": "...", "confidence": 0.0-1.0}}]}}"""},
    ]

    try:
        response = await chat_completion(prompt, temperature=0.3)
        import re
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        parsed = json.loads(json_match.group()) if json_match else {"suggestions": []}
    except Exception:
        parsed = {"suggestions": []}

    return LinkSuggestionsResponse(
        note_id=note_id,
        suggestions=[
            LinkSuggestion(
                target_note_id=s.get("target_note_id", ""),
                target_title=s.get("target_title", ""),
                reason=s.get("reason", ""),
                confidence=float(s.get("confidence", 0.5)),
            )
            for s in parsed.get("suggestions", [])[:5]
        ],
    )
