"""Tests for routers/ai.py — AI endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gnosis.models.note import Note

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_note(
    db,
    note_id: str = "ai-note-1",
    title: str = "AI Test Note",
    folder: str = "10-zettelkasten",
    body: str = "This is a test note body for AI operations.",
) -> Note:
    note = Note(
        id=note_id,
        title=title,
        slug=note_id,                  # unique non-null
        body=body,
        body_html=f"<p>{body}</p>",
        folder=folder,
        owner_id=1,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


_LLM_PATCH = "gnosis.routers.ai.llm_provider"
_GRAPH_PATCH = "gnosis.routers.ai.graph_rag"
_HYBRID_PATCH = "gnosis.routers.ai.hybrid_search"


def _mock_llm(answer: str = "AI response"):
    m = MagicMock()
    m.is_available = True
    m.complete = AsyncMock(return_value=answer)
    async def _stream(*a, **kw):
        yield "token1"
        yield " token2"
    m.stream = _stream
    return m


def _mock_graph(available: bool = False, answer: str = ""):
    m = MagicMock()
    m.is_available = AsyncMock(return_value=available)
    m.query = AsyncMock(return_value=answer)
    async def _stream(*a, **kw):
        yield "graph-token"
    m.stream = _stream
    return m


# ---------------------------------------------------------------------------
# GET /api/v1/ai/providers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_providers_unavailable(client):
    mock_llm = MagicMock()
    mock_llm.is_available = False
    with patch(_LLM_PATCH, mock_llm):
        r = await client.get("/api/v1/ai/providers")
    assert r.status_code == 200
    assert r.json()["available"] is False


@pytest.mark.asyncio
async def test_get_providers_available(client):
    mock_llm = MagicMock()
    mock_llm.is_available = True
    mock_llm.active_provider = "ollama"
    mock_llm.active_model = "llama3"
    mock_llm._available = ["ollama"]
    with patch(_LLM_PATCH, mock_llm), \
         patch("gnosis.routers.ai.httpx.AsyncClient") as mock_http:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3"}]}
        mock_async_client = AsyncMock()
        mock_async_client.get = AsyncMock(return_value=mock_resp)
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
        r = await client.get("/api/v1/ai/providers")
    assert r.status_code == 200
    assert r.json()["available"] is True


# ---------------------------------------------------------------------------
# POST /api/v1/ai/chat
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_uses_qdrant_rag_when_graph_unavailable(client):
    with patch(_GRAPH_PATCH, _mock_graph(available=False)), \
         patch(_LLM_PATCH, _mock_llm("vault answer")), \
         patch(_HYBRID_PATCH, return_value=[]):
        r = await client.post("/api/v1/ai/chat", json={"message": "What is spaced repetition?"})
    assert r.status_code == 200
    assert r.json()["answer"] == "vault answer"


@pytest.mark.asyncio
async def test_chat_uses_graph_rag_when_available(client):
    with patch(_GRAPH_PATCH, _mock_graph(available=True, answer="graph answer")), \
         patch(_LLM_PATCH, _mock_llm()):
        r = await client.post("/api/v1/ai/chat", json={"message": "question"})
    assert r.status_code == 200
    assert r.json()["answer"] == "graph answer"


@pytest.mark.asyncio
async def test_chat_503_when_no_provider(client):
    mock_llm = MagicMock()
    mock_llm.is_available = False
    with patch(_GRAPH_PATCH, _mock_graph(available=False)), \
         patch(_LLM_PATCH, mock_llm):
        r = await client.post("/api/v1/ai/chat", json={"message": "question"})
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# POST /api/v1/ai/summarize/{note_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_returns_summary(client, test_db):
    await _make_note(test_db, note_id="sum-1")
    with patch(_LLM_PATCH, _mock_llm("A concise summary.")):
        r = await client.post("/api/v1/ai/summarize/sum-1")
    assert r.status_code == 200
    assert r.json()["summary"] == "A concise summary."


@pytest.mark.asyncio
async def test_summarize_404_missing_note(client):
    with patch(_LLM_PATCH, _mock_llm()):
        r = await client.post("/api/v1/ai/summarize/ghost")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_summarize_503_no_llm(client, test_db):
    await _make_note(test_db, note_id="sum-503")
    mock_llm = MagicMock()
    mock_llm.is_available = False
    with patch(_LLM_PATCH, mock_llm):
        r = await client.post("/api/v1/ai/summarize/sum-503")
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# POST /api/v1/ai/suggest-tags/{note_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_suggest_tags_returns_tags(client, test_db):
    await _make_note(test_db, note_id="tag-note")
    with patch(_LLM_PATCH, _mock_llm('["zettelkasten", "spaced-repetition"]')):
        r = await client.post("/api/v1/ai/suggest-tags/tag-note")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["suggested_tags"], list)


@pytest.mark.asyncio
async def test_suggest_tags_503_no_llm(client, test_db):
    await _make_note(test_db, note_id="tag-note-2")
    mock_llm = MagicMock()
    mock_llm.is_available = False
    with patch(_LLM_PATCH, mock_llm):
        r = await client.post("/api/v1/ai/suggest-tags/tag-note-2")
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# POST /api/v1/ai/suggest-links/{note_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_suggest_links_returns_suggestions(client, test_db):
    await _make_note(test_db, note_id="link-note")
    with patch(_LLM_PATCH, _mock_llm('["Other Note"]')):
        r = await client.post("/api/v1/ai/suggest-links/link-note")
    assert r.status_code == 200
    assert "suggestions" in r.json()


@pytest.mark.asyncio
async def test_suggest_links_503_no_llm(client, test_db):
    await _make_note(test_db, note_id="link-note-2")
    mock_llm = MagicMock()
    mock_llm.is_available = False
    with patch(_LLM_PATCH, mock_llm):
        r = await client.post("/api/v1/ai/suggest-links/link-note-2")
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# POST /api/v1/ai/critique/{note_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_critique_returns_critique(client, test_db):
    await _make_note(test_db, note_id="critique-note")
    raw = '{"atomicity": "good", "connectivity": "weak", "self_containedness": "ok", "insight_density": "high", "overall": "solid"}'
    with patch(_LLM_PATCH, _mock_llm(raw)):
        r = await client.post("/api/v1/ai/critique/critique-note")
    assert r.status_code == 200
    data = r.json()
    assert data["atomicity"] == "good"
    assert data["overall"] == "solid"


@pytest.mark.asyncio
async def test_critique_503_no_llm(client, test_db):
    await _make_note(test_db, note_id="critique-note-2")
    mock_llm = MagicMock()
    mock_llm.is_available = False
    with patch(_LLM_PATCH, mock_llm):
        r = await client.post("/api/v1/ai/critique/critique-note-2")
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/v1/ai/orphan-audit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orphan_audit_empty_vault(client):
    with patch(_LLM_PATCH, _mock_llm()):
        r = await client.get("/api/v1/ai/orphan-audit")
    assert r.status_code == 200
    data = r.json()
    assert data["orphan_count"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_orphan_audit_with_orphan_notes(client, test_db):
    await _make_note(test_db, note_id="orphan-1", title="Orphan One")
    await _make_note(test_db, note_id="orphan-2", title="Orphan Two")
    raw_json = '[{"note_id": "orphan-1", "title": "Orphan One", "suggestions": ["Link A"]}]'
    with patch(_LLM_PATCH, _mock_llm(raw_json)):
        r = await client.get("/api/v1/ai/orphan-audit")
    assert r.status_code == 200
    data = r.json()
    assert data["orphan_count"] >= 1


# ---------------------------------------------------------------------------
# POST /api/v1/ai/daily-review
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_review_no_inbox_notes(client):
    with patch(_LLM_PATCH, _mock_llm()):
        r = await client.post("/api/v1/ai/daily-review")
    assert r.status_code == 200
    data = r.json()
    assert data["inbox_note_count"] == 0
    assert data["summary"] == "No inbox notes today."


@pytest.mark.asyncio
async def test_daily_review_with_inbox_notes(client, test_db):
    await _make_note(test_db, note_id="inbox-today", folder="00-inbox")
    raw = '{"summary": "Great captures today.", "action_items": ["Process note A"]}'
    with patch(_LLM_PATCH, _mock_llm(raw)):
        r = await client.post("/api/v1/ai/daily-review")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v1/ai/stream/chat
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_chat_qdrant_path(client):
    """When LightRAG is unavailable, SSE falls through to Qdrant/LLM stream."""
    with patch(_GRAPH_PATCH, _mock_graph(available=False)), \
         patch(_LLM_PATCH, _mock_llm()), \
         patch(_HYBRID_PATCH, return_value=[]):
        r = await client.get("/api/v1/ai/stream/chat?message=hello")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


@pytest.mark.asyncio
async def test_stream_chat_graph_rag_path(client):
    """When LightRAG is available, SSE uses graph_rag.stream."""
    with patch(_GRAPH_PATCH, _mock_graph(available=True)), \
         patch(_LLM_PATCH, _mock_llm()):
        r = await client.get("/api/v1/ai/stream/chat?message=hello")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_stream_chat_no_provider(client):
    """When neither LightRAG nor LLM is available, SSE emits an error event."""
    mock_llm = MagicMock()
    mock_llm.is_available = False
    with patch(_GRAPH_PATCH, _mock_graph(available=False)), \
         patch(_LLM_PATCH, mock_llm):
        r = await client.get("/api/v1/ai/stream/chat?message=hello")
    assert r.status_code == 200
    assert b"error" in r.content or b"[DONE]" in r.content


# ---------------------------------------------------------------------------
# POST /api/v1/ai/generate-moc
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_moc_no_matching_notes(client):
    with patch(_LLM_PATCH, _mock_llm()):
        r = await client.post("/api/v1/ai/generate-moc", json={"topic": "nonexistenttopicxyz"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_generate_moc_503_no_llm(client):
    mock_llm = MagicMock()
    mock_llm.is_available = False
    with patch(_LLM_PATCH, mock_llm):
        r = await client.post("/api/v1/ai/generate-moc", json={"topic": "anything"})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_generate_moc_returns_markdown(client, test_db):
    await _make_note(
        test_db,
        note_id="moc-note-1",
        title="Spaced Repetition Systems",
        body="spaced repetition is a learning technique",
    )
    raw = '[{"heading": "Learning", "summary": "About learning", "wikilinks": ["Spaced Repetition Systems"]}]'
    with patch(_LLM_PATCH, _mock_llm(raw)):
        r = await client.post("/api/v1/ai/generate-moc", json={"topic": "spaced repetition"})
    assert r.status_code == 200
    data = r.json()
    assert "markdown" in data
    assert data["topic"] == "spaced repetition"
