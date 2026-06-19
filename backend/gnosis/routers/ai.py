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
    lines = [
        re.sub(r"^[\-\*\d\.\)]+\s*", "", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]
    return [line for line in lines if line][:10]


def _build_moc_markdown(topic: str, moc_title: str, sections: list[MocSection]) -> str:
    """Render a list of MocSection objects into a full Markdown MOC body.

    The output follows Gnosis frontmatter conventions and uses [[WikiLink]]
    syntax so the vault watcher picks up outgoing links on save.
    """
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
    if not llm_provider.is_available:
        raise HTTPException(status_code=503, detail="No LLM provider available")
    note = await _get_note_or_404(note_id, session)
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
    if not llm_provider.is_available:
        raise HTTPException(status_code=503, detail="No LLM provider available")
    note = await _get_note_or_404(note_id, session)
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
        '"self_containedness": \"...\", "insight_density": \"...\", "overall": \"...\"}'
    )
    raw = await llm_provider.complete(prompt, temperature=0.2)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return CritiqueResponse(note_id=note_id, **data)
        except (json.JSONDecodeError, TypeError):
            pass
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
        items.append(OrphanAuditItem(note_id=orphan.id, title=orphan.title, suggestions=suggestions))
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
    async def event_generator() -> AsyncGenerator[str, None]:
        if not llm_provider.is_available:
            yield "data: No AI provider available. Start Ollama or configure GROQ_API_KEY.\n\n"
            yield "data: [DONE]\n\n"
            return
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
                safe_chunk = chunk.replace("\n", " ")
                yield f"data: {safe_chunk}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.error("SSE stream error: %s", exc)
            yield f"data: Stream error: {exc}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# POST /ai/generate-moc  — Feature 3: Map of Content Generator
# ---------------------------------------------------------------------------

@router.post(
    "/generate-moc",
    response_model=MocResponse,
    summary="Generate a Map of Content note",
    description=(
        "Scans the vault for notes matching a topic/tag/folder filter, "
        "asks the LLM to group them into themed H2 sections with wikilinks, "
        "and returns a ready-to-save Markdown MOC note body. "
        "The response also includes a suggested vault_path (80-meta/<slug>.md) "
        "and structured section data for the UI to render before saving."
    ),
)
async def generate_moc(
    req: MocRequest,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> MocResponse:
    """Generate a Map of Content note for a topic.

    Algorithm:
      1. Query vault notes filtered by tag and/or folder.
      2. Build a compact note index (id, title, tags, folder) for the LLM.
      3. Prompt the LLM to organise notes into 3-8 themed sections,
         each with a heading, wikilink list, and one-sentence description.
      4. Parse the JSON structure and render full Markdown.
      5. Return sections + rendered markdown; the frontend decides whether to save.
    """
    if not llm_provider.is_available:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider available. Start Ollama or configure GROQ_API_KEY.",
        )

    # ---- 1. Gather candidate notes -----------------------------------------
    stmt = (
        select(Note)
        .where(Note.is_deleted.is_(False))
        .order_by(Note.modified_at.desc())
        .limit(req.max_notes)
    )
    if req.folder:
        stmt = stmt.where(Note.folder.ilike(f"{req.folder}%"))
    if req.tag:
        from gnosis.models.tag import NoteTag, Tag
        tag_sub = select(NoteTag.note_id).join(Tag).where(
            Tag.name == req.tag.lower()
        )
        stmt = stmt.where(Note.id.in_(tag_sub))

    result = await session.execute(stmt)
    notes = result.scalars().all()

    if len(notes) < 2:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(notes)} note(s) matched the filter. "
                "A MOC needs at least 2 notes. Broaden the topic, tag, or folder."
            ),
        )

    # ---- 2. Build compact note index for the prompt ------------------------
    note_index_lines = []
    for n in notes:
        note_index_lines.append(f"- title: {n.title} | folder: {n.folder or 'root'}")
    note_index = "\n".join(note_index_lines)

    # ---- 3. LLM prompt ------------------------------------------------------
    moc_title = f"MOC — {req.topic.title()}"
    prompt = (
        f"You are a Zettelkasten knowledge architect. "
        f"Generate a Map of Content (MOC) for the topic: '{req.topic}'.\n\n"
        f"Notes available in the vault ({len(notes)} total):\n{note_index}\n\n"
        "Instructions:\n"
        "1. Group these notes into 3–8 meaningful thematic sections.\n"
        "2. Each section gets a short heading (3–6 words), a one-sentence description, "
        "and a list of note titles that belong to it.\n"
        "3. Every note title you include MUST appear exactly as given above.\n"
        "4. Return ONLY valid JSON matching this schema — no prose before or after:\n\n"
        "{\n"
        '  "moc_title": "<concise title for the MOC note>",\n'
        '  "sections": [\n'
        "    {\n"
        '      "heading": "<section heading>",\n'
        '      "summary": "<one sentence>",\n'
        '      "wikilinks": ["<note title A>", "<note title B>"]\n'
        "    }\n"
        "  ]\n"
        "}"
    )
    raw = await llm_provider.complete(prompt, temperature=0.35, max_tokens=2000)

    # ---- 4. Parse LLM JSON --------------------------------------------------
    sections: list[MocSection] = []
    parsed_title = moc_title
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            parsed_title = data.get("moc_title", moc_title)
            for sec in data.get("sections", []):
                sections.append(
                    MocSection(
                        heading=sec.get("heading", "Untitled Section"),
                        summary=sec.get("summary", ""),
                        wikilinks=[
                            str(w) for w in sec.get("wikilinks", []) if isinstance(w, str)
                        ],
                    )
                )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("MOC JSON parse failed: %s", exc)

    # Fallback: put all notes in one section if parsing failed
    if not sections:
        sections = [
            MocSection(
                heading="All Notes",
                summary=f"All {len(notes)} notes related to {req.topic}.",
                wikilinks=[n.title for n in notes],
            )
        ]

    # ---- 5. Build vault_path slug -------------------------------------------
    from python_slugify import slugify  # type: ignore[import-untyped]
    slug = slugify(parsed_title, max_length=80)
    vault_path = f"80-meta/{slug}.md"

    # ---- 6. Render full Markdown --------------------------------------------
    markdown = _build_moc_markdown(req.topic, parsed_title, sections)

    return MocResponse(
        topic=req.topic,
        moc_title=parsed_title,
        vault_path=vault_path,
        sections=sections,
        markdown=markdown,
        note_count=len(notes),
    )
