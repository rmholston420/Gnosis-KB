"""Unit tests for gnosis/routers/ai.py.

All LLM, graph_rag, hybrid_search, and DB calls are mocked so tests run
without Ollama, Qdrant, or a real database.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared note factory
# ---------------------------------------------------------------------------

def _note(note_id="id-001", title="Test Note", body="Body text here.", owner_id=1):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.owner_id = owner_id
    n.note_type = "permanent"
    n.status = "active"
    n.folder = "10-zettelkasten"
    n.is_deleted = False
    n.created_at = datetime.now(timezone.utc)
    return n


def _session_with_note(note):
    scalars = MagicMock()
    scalars.scalar_one_or_none.return_value = note
    scalars.scalars.return_value.all.return_value = [note]
    result = MagicMock()
    result.scalar_one_or_none.return_value = note
    result.scalars.return_value.all.return_value = [note]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# _build_rag_context
# ---------------------------------------------------------------------------

def test_build_rag_context_empty_hits_returns_empty_string():
    from gnosis.routers.ai import _build_rag_context
    assert _build_rag_context([]) == ""


def test_build_rag_context_formats_hits():
    from gnosis.routers.ai import _build_rag_context
    hits = [{"title": "Note A", "text_snippet": "Some insight.", "folder": "10-zettelkasten"}]
    result = _build_rag_context(hits)
    assert "Note A" in result
    assert "Some insight." in result
    assert "Relevant notes" in result


# ---------------------------------------------------------------------------
# _parse_json_list
# ---------------------------------------------------------------------------

def test_parse_json_list_extracts_json_array():
    from gnosis.routers.ai import _parse_json_list
    assert _parse_json_list('["a", "b", "c"]') == ["a", "b", "c"]


def test_parse_json_list_falls_back_to_line_parsing():
    from gnosis.routers.ai import _parse_json_list
    result = _parse_json_list("- tag-one\n- tag-two\n- tag-three")
    assert "tag-one" in result
    assert "tag-two" in result


def test_parse_json_list_handles_empty_string():
    from gnosis.routers.ai import _parse_json_list
    assert _parse_json_list("") == []


# ---------------------------------------------------------------------------
# _get_note_or_404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_note_or_404_returns_note():
    from gnosis.routers.ai import _get_note_or_404
    n = _note()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = n
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)
    with patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s):
        result = await _get_note_or_404("id-001", db, {1})
    assert result.id == "id-001"


@pytest.mark.asyncio
async def test_get_note_or_404_raises_404():
    from fastapi import HTTPException
    from gnosis.routers.ai import _get_note_or_404
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)
    with (
        patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
        pytest.raises(HTTPException) as exc_info,
    ):
        await _get_note_or_404("missing", db, {1})
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# POST /ai/chat  — three branches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_uses_graph_rag_when_available():
    from gnosis.routers.ai import chat
    from gnosis.schemas.ai import ChatRequest

    user = MagicMock()
    user.id = 1

    with (
        patch("gnosis.routers.ai.graph_rag") as mock_gr,
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
    ):
        mock_gr.is_available = AsyncMock(return_value=True)
        mock_gr.query = AsyncMock(return_value="Graph answer")
        mock_llm.is_available = False

        result = await chat(
            req=ChatRequest(message="What is epistemology?"),
            session=AsyncMock(),
            current_user=user,
            owner_ids={1},
        )

    assert result.answer == "Graph answer"


@pytest.mark.asyncio
async def test_chat_falls_back_to_qdrant_rag():
    from gnosis.routers.ai import chat
    from gnosis.schemas.ai import ChatRequest

    user = MagicMock()
    user.id = 1

    with (
        patch("gnosis.routers.ai.graph_rag") as mock_gr,
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
        patch("gnosis.routers.ai._qdrant_rag_complete", AsyncMock(return_value="Qdrant answer")),
    ):
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_llm.is_available = True

        result = await chat(
            req=ChatRequest(message="Tell me about PKM."),
            session=AsyncMock(),
            current_user=user,
            owner_ids={1},
        )

    assert result.answer == "Qdrant answer"


@pytest.mark.asyncio
async def test_chat_raises_503_when_no_provider():
    from fastapi import HTTPException
    from gnosis.routers.ai import chat
    from gnosis.schemas.ai import ChatRequest

    user = MagicMock()
    user.id = 1

    with (
        patch("gnosis.routers.ai.graph_rag") as mock_gr,
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
        pytest.raises(HTTPException) as exc_info,
    ):
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_llm.is_available = False

        await chat(
            req=ChatRequest(message="Hello?"),
            session=AsyncMock(),
            current_user=user,
            owner_ids={1},
        )

    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# POST /ai/summarize/{note_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_note_returns_summary():
    from gnosis.routers.ai import summarize_note

    n = _note()
    db = _session_with_note(n)

    with (
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
        patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
    ):
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value="  Two sentence summary.  ")
        result = await summarize_note(note_id=n.id, session=db, owner_ids={1})

    assert result.summary == "Two sentence summary."
    assert result.note_id == n.id


@pytest.mark.asyncio
async def test_summarize_note_raises_503_when_no_llm():
    from fastapi import HTTPException
    from gnosis.routers.ai import summarize_note

    with (
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
        pytest.raises(HTTPException) as exc_info,
    ):
        mock_llm.is_available = False
        await summarize_note(note_id="x", session=AsyncMock(), owner_ids={1})

    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# POST /ai/suggest-tags/{note_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_suggest_tags_returns_parsed_tags():
    from gnosis.routers.ai import suggest_tags

    n = _note()
    db = _session_with_note(n)

    with (
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
        patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
    ):
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value='["zettelkasten", "pkm"]')
        result = await suggest_tags(note_id=n.id, session=db, owner_ids={1})

    assert "zettelkasten" in result.suggested_tags


@pytest.mark.asyncio
async def test_suggest_tags_raises_503_when_no_llm():
    from fastapi import HTTPException
    from gnosis.routers.ai import suggest_tags

    with (
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
        pytest.raises(HTTPException) as exc_info,
    ):
        mock_llm.is_available = False
        await suggest_tags(note_id="x", session=AsyncMock(), owner_ids={1})

    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# POST /ai/critique/{note_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_critique_note_parses_json_response():
    from gnosis.routers.ai import critique_note

    n = _note()
    db = _session_with_note(n)
    critique_json = json.dumps({
        "atomicity": "Good", "connectivity": "Needs links",
        "self_containedness": "OK", "insight_density": "High", "overall": "Solid",
    })

    with (
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
        patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
    ):
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value=critique_json)
        result = await critique_note(note_id=n.id, session=db, owner_ids={1})

    assert result.atomicity == "Good"
    assert result.overall == "Solid"


# ---------------------------------------------------------------------------
# GET /ai/orphan-audit  — no LLM branch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orphan_audit_returns_empty_items_when_no_llm():
    from gnosis.routers.ai import orphan_audit

    notes = [_note(note_id=f"n{i}", title=f"Orphan {i}") for i in range(2)]
    scalars_result = MagicMock()
    scalars_result.scalars.return_value.all.return_value = notes
    db = AsyncMock()
    db.execute = AsyncMock(return_value=scalars_result)

    with (
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
        patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
    ):
        mock_llm.is_available = False
        result = await orphan_audit(limit=10, session=db, owner_ids={1})

    assert result.orphan_count == 2
    assert result.items == []


# ---------------------------------------------------------------------------
# GET /ai/providers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_providers_returns_unavailable_when_no_llm():
    from gnosis.routers.ai import get_providers

    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = False
        result = await get_providers(_=MagicMock())

    assert result.available is False
    assert result.provider == "none"


@pytest.mark.asyncio
async def test_get_providers_returns_active_provider_when_available():
    from gnosis.routers.ai import get_providers

    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        mock_llm.active_provider = "groq"
        mock_llm.active_model = "llama3-8b"
        mock_llm._available = []  # no ollama, skip HTTP call
        result = await get_providers(_=MagicMock())

    assert result.available is True
    assert result.provider == "groq"
    assert result.model == "llama3-8b"


# ---------------------------------------------------------------------------
# _build_moc_markdown
# ---------------------------------------------------------------------------

def test_build_moc_markdown_contains_frontmatter_and_wikilinks():
    from gnosis.routers.ai import _build_moc_markdown
    from gnosis.schemas.ai import MocSection

    sections = [
        MocSection(heading="Foundations", summary="Core ideas.", wikilinks=["Note A", "Note B"]),
    ]
    md = _build_moc_markdown("epistemology", "MOC — Epistemology", sections)
    assert "MOC — Epistemology" in md
    assert "[[Note A]]" in md
    assert "type: moc" in md
