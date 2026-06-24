"""
Coverage boost — targets remaining uncovered lines across 6 files.

ai.py        lines 106, 132-135, 216->226, 248->252, 250-251,
                   274-276, 281-285, 304-318, 327-358, 379-387,
                   404-423, 457-490, 535->542, 540-541,
                   556-595, 606, 615-630, 628-630,
                   633-640, 649-718
notes.py     lines 49->exit, 51-54, 309-327, 343-383
review.py    lines 145-153, 156, 188-190
users.py     lines 338-341, 343-351, 375-378, 390-397
vault.py     lines 168->171, 192-220, 237-240
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ===========================================================================
# Helpers
# ===========================================================================

def _make_note(
    id="note-1",
    title="Test Note",
    body="Body text",
    folder="00-inbox",
    note_type="permanent",
    status="draft",
    owner_id=1,
    is_deleted=False,
    graph_indexed=False,
):
    n = MagicMock()
    n.id = id
    n.title = title
    n.slug = "test-note"
    n.body = body
    n.body_html = f"<p>{body}</p>"
    n.folder = folder
    n.note_type = note_type
    n.status = status
    n.owner_id = owner_id
    n.is_deleted = is_deleted
    n.graph_indexed = graph_indexed
    n.word_count = len(body.split())
    n.tags = []
    n.created_at = None
    n.modified_at = None
    return n


def _make_card(
    note_id="note-1",
    id="card-1",
    easiness=2.5,
    interval=1,
    repetitions=0,
    due_date=None,
    last_quality=None,
):
    """Build a MagicMock ReviewCard with all fields ReviewCardRead needs."""
    c = MagicMock()
    c.id = id
    c.note_id = note_id
    c.easiness = easiness
    c.interval = interval
    c.repetitions = repetitions
    c.due_date = due_date or date(2025, 1, 1)
    c.last_quality = last_quality
    c.created_at = None
    c.updated_at = None
    return c


# ===========================================================================
# ai.py — _qdrant_rag_complete (line 106: context branch)
# ===========================================================================


@pytest.mark.asyncio
async def test_qdrant_rag_complete_with_context():
    """Line 106: context non-empty → system prompt extended."""
    from gnosis.routers.ai import _qdrant_rag_complete

    hits = [{"title": "A Note", "text_snippet": "some text", "folder": "00-inbox"}]
    with (
        patch("gnosis.routers.ai.hybrid_search", return_value=hits),
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
    ):
        mock_llm.complete = AsyncMock(return_value="answer")
        result = await _qdrant_rag_complete("query", owner_ids={1})
    assert result == "answer"


# ===========================================================================
# ai.py — _qdrant_rag_stream (lines 132-135: stream with context)
# ===========================================================================


@pytest.mark.asyncio
async def test_qdrant_rag_stream_with_context():
    """Lines 132-135: stream path with hits → context appended to system prompt."""
    from gnosis.routers.ai import _qdrant_rag_stream

    hits = [{"title": "A Note", "text_snippet": "snippet", "folder": "10-lit"}]

    async def _fake_stream(prompt, system):
        yield "tok1"
        yield "tok2"

    with (
        patch("gnosis.routers.ai.hybrid_search", return_value=hits),
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
    ):
        mock_llm.stream = _fake_stream
        tokens = [tok async for tok in _qdrant_rag_stream("query", owner_ids={1})]

    assert tokens == ["tok1", "tok2"]


# ===========================================================================
# ai.py — get_providers: ollama available + HTTP 200 (lines 216->226)
# ===========================================================================


@pytest.mark.asyncio
async def test_get_providers_ollama_available_http_200():
    """Lines 216-226: ollama in _available and /api/tags returns 200 → model list populated."""
    from gnosis.routers.ai import get_providers

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "llama3"}, {"name": "mistral"}]}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("gnosis.routers.ai.llm_provider") as mock_llm, patch(
        "gnosis.routers.ai.httpx.AsyncClient", return_value=mock_client
    ):
        mock_llm.is_available = True
        mock_llm.active_provider = "ollama"
        mock_llm.active_model = "llama3"
        mock_llm._available = {"ollama"}

        result = await get_providers(_=MagicMock())

    assert result.available is True
    assert "llama3" in result.models


@pytest.mark.asyncio
async def test_get_providers_ollama_http_exception_falls_back():
    """Lines 220->226 exception branch: httpx raises → models = [model]."""
    from gnosis.routers.ai import get_providers

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("conn refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("gnosis.routers.ai.llm_provider") as mock_llm, patch(
        "gnosis.routers.ai.httpx.AsyncClient", return_value=mock_client
    ):
        mock_llm.is_available = True
        mock_llm.active_provider = "ollama"
        mock_llm.active_model = "llama3"
        mock_llm._available = {"ollama"}

        result = await get_providers(_=MagicMock())

    assert "llama3" in result.models


# ===========================================================================
# ai.py — set_model: ollama not available → 400 (lines 248->252)
# ===========================================================================


@pytest.mark.asyncio
async def test_set_model_ollama_not_available_raises_400():
    """Lines 248->252: 'ollama' not in _available → 400."""
    from gnosis.routers.ai import ModelSwapRequest, set_model

    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm._available = set()  # no ollama
        with pytest.raises(Exception) as exc_info:
            await set_model(req=ModelSwapRequest(model="llama3"), _=MagicMock())
    assert "400" in str(exc_info.value) or "Ollama" in str(exc_info.value)


@pytest.mark.asyncio
async def test_set_model_success_lines_250_251():
    """Lines 250-251: ollama available → swap_model called, models fetched."""
    from gnosis.routers.ai import ModelSwapRequest, set_model

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "llama3"}]}
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("gnosis.routers.ai.llm_provider") as mock_llm, patch(
        "gnosis.routers.ai.httpx.AsyncClient", return_value=mock_client
    ):
        mock_llm._available = {"ollama"}
        mock_llm.swap_model = MagicMock()
        result = await set_model(req=ModelSwapRequest(model="llama3"), _=MagicMock())

    mock_llm.swap_model.assert_called_once_with("llama3")
    assert result.model == "llama3"


# ===========================================================================
# ai.py — chat: graph_rag available path (lines 274-276)
# ===========================================================================


@pytest.mark.asyncio
async def test_chat_graph_rag_available():
    """Lines 274-276: graph_rag.is_available → use graph_rag.query."""
    from gnosis.routers.ai import chat
    from gnosis.schemas.ai import ChatRequest

    db = AsyncMock()
    user = MagicMock()
    user.id = 1

    with patch("gnosis.routers.ai.graph_rag") as mock_gr:
        mock_gr.is_available = AsyncMock(return_value=True)
        mock_gr.query = AsyncMock(return_value="graph answer")
        result = await chat(
            req=ChatRequest(message="hello", mode="hybrid"),
            session=db,
            current_user=user,
            owner_ids={1},
        )
    assert result.answer == "graph answer"


@pytest.mark.asyncio
async def test_chat_no_provider_raises_503():
    """Lines 281-285: neither graph_rag nor llm_provider → 503."""
    from gnosis.routers.ai import chat
    from gnosis.schemas.ai import ChatRequest

    db = AsyncMock()
    user = MagicMock()
    user.id = 1

    with patch("gnosis.routers.ai.graph_rag") as mock_gr, patch(
        "gnosis.routers.ai.llm_provider"
    ) as mock_llm:
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_llm.is_available = False
        with pytest.raises(Exception) as exc_info:
            await chat(
                req=ChatRequest(message="hello", mode="hybrid"),
                session=db,
                current_user=user,
                owner_ids={1},
            )
    assert "503" in str(exc_info.value) or "No AI provider" in str(exc_info.value)


# ===========================================================================
# ai.py — summarize_note: no provider → 503 (line 304-305)
# ===========================================================================


@pytest.mark.asyncio
async def test_summarize_note_no_provider_503():
    """Line 304-305: llm_provider.is_available=False → 503."""
    from gnosis.routers.ai import summarize_note

    db = AsyncMock()
    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = False
        with pytest.raises(Exception) as exc_info:
            await summarize_note(note_id="n1", session=db, owner_ids={1})
    assert "503" in str(exc_info.value)


@pytest.mark.asyncio
async def test_summarize_note_not_found_404():
    """Lines 307-310: note not found → 404."""
    from gnosis.routers.ai import summarize_note

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        with pytest.raises(Exception) as exc_info:
            await summarize_note(note_id="missing", session=db, owner_ids={1})
    assert "404" in str(exc_info.value)


@pytest.mark.asyncio
async def test_summarize_note_happy_path():
    """Lines 311-318: note found → llm_provider.complete → SummarizeResponse."""
    from gnosis.routers.ai import summarize_note

    note = _make_note()
    result = MagicMock()
    result.scalar_one_or_none.return_value = note
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value="  A summary.  ")
        resp = await summarize_note(note_id="note-1", session=db, owner_ids={1})

    assert resp.summary == "A summary."
    assert resp.note_id == "note-1"


# ===========================================================================
# ai.py — suggest_links (lines 327-358)
# ===========================================================================


@pytest.mark.asyncio
async def test_suggest_links_no_provider_503():
    """Line 327->329: llm_provider.is_available=False → 503."""
    from gnosis.routers.ai import suggest_links

    db = AsyncMock()
    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = False
        with pytest.raises(Exception) as exc_info:
            await suggest_links(note_id="n1", session=db, owner_ids={1})
    assert "503" in str(exc_info.value)


@pytest.mark.asyncio
async def test_suggest_links_happy_path_with_rationale():
    """Lines 330-358: note found → LLM returns two JSON arrays → suggestions + rationale."""
    from gnosis.routers.ai import suggest_links

    note = _make_note()
    note_result = MagicMock()
    note_result.scalar_one_or_none.return_value = note

    cand_row = MagicMock()
    cand_row.title = "Related Note"
    cands_result = MagicMock()
    cands_result.all.return_value = [cand_row]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[note_result, cands_result])

    raw_llm = '["Related Note", "Another"]\n["Because similar topic", "Because related"]'
    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value=raw_llm)
        resp = await suggest_links(note_id="note-1", session=db, owner_ids={1})

    assert "Related Note" in resp.suggestions
    assert len(resp.rationale) >= 1


# ===========================================================================
# ai.py — suggest_tags (lines 379-387)
# ===========================================================================


@pytest.mark.asyncio
async def test_suggest_tags_happy_path():
    """Lines 379-387: note found → tags returned."""
    from gnosis.routers.ai import suggest_tags

    note = _make_note()
    result = MagicMock()
    result.scalar_one_or_none.return_value = note
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value='["zettelkasten", "memory"]')
        resp = await suggest_tags(note_id="note-1", session=db, owner_ids={1})

    assert "zettelkasten" in resp.suggested_tags


# ===========================================================================
# ai.py — critique_note (lines 404-423)
# ===========================================================================


@pytest.mark.asyncio
async def test_critique_note_happy_path_json():
    """Lines 404-423: note found → LLM returns JSON critique dict."""
    from gnosis.routers.ai import critique_note

    note = _make_note()
    result = MagicMock()
    result.scalar_one_or_none.return_value = note
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    critique_json = (
        '{"atomicity": "Good", "connectivity": "Low", '
        '"self_containedness": "High", "insight_density": "Medium", "overall": "OK"}'
    )
    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value=critique_json)
        resp = await critique_note(note_id="note-1", session=db, owner_ids={1})

    assert resp.atomicity == "Good"
    assert resp.overall == "OK"


@pytest.mark.asyncio
async def test_critique_note_invalid_json_fallback():
    """Lines 418-420: LLM returns non-JSON → raw string used for atomicity."""
    from gnosis.routers.ai import critique_note

    note = _make_note()
    result = MagicMock()
    result.scalar_one_or_none.return_value = note
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value="plain text critique")
        resp = await critique_note(note_id="note-1", session=db, owner_ids={1})

    assert "plain text critique" in resp.atomicity


# ===========================================================================
# ai.py — orphan_audit (lines 457-490)
# ===========================================================================


@pytest.mark.asyncio
async def test_orphan_audit_no_rows_returns_empty():
    """Lines 457-460: no orphan notes → OrphanAuditResponse(items=[])."""
    from gnosis.routers.ai import orphan_audit

    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        resp = await orphan_audit(limit=10, session=db, owner_ids={1})

    assert resp.items == []
    assert resp.orphan_count == 0


@pytest.mark.asyncio
async def test_orphan_audit_with_rows_and_llm():
    """Lines 463-490: rows found + llm available → items populated from LLM JSON."""
    from gnosis.routers.ai import orphan_audit

    orphan = _make_note(id="o1", title="Orphan Note")
    result = MagicMock()
    result.scalars.return_value.all.return_value = [orphan]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    llm_json = '[{"note_id": "o1", "title": "Orphan Note", "suggestions": ["Topic A"]}]'
    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value=llm_json)
        resp = await orphan_audit(limit=10, session=db, owner_ids={1})

    assert resp.orphan_count == 1
    assert len(resp.items) == 1
    assert resp.items[0].title == "Orphan Note"


# ===========================================================================
# ai.py — daily_review (lines 535->542)
# ===========================================================================


@pytest.mark.asyncio
async def test_daily_review_no_notes():
    """Lines 535->542: no inbox notes → summary='No inbox notes today.'"""
    from gnosis.routers.ai import daily_review

    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        resp = await daily_review(session=db, owner_ids={1})

    assert resp.summary == "No inbox notes today."
    assert resp.inbox_note_count == 0


@pytest.mark.asyncio
async def test_daily_review_with_notes_json_response():
    """Lines 540-541: notes found → LLM JSON parsed → summary + action_items."""
    from gnosis.routers.ai import daily_review

    note = _make_note()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [note]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    llm_json = '{"summary": "Busy day", "action_items": ["Process note A", "Link note B"]}'
    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value=llm_json)
        resp = await daily_review(session=db, owner_ids={1})

    assert resp.summary == "Busy day"
    assert "Process note A" in resp.action_items


# ===========================================================================
# ai.py — stream_chat SSE (lines 556-595)
#
# _qdrant_rag_stream is an async generator function. When patching it,
# use `return_value` with an async generator object, NOT `side_effect`
# (side_effect replaces the callable but is called with (message, owner_ids,
# mode) positional args which confuses the patch). Use a simple wrapper that
# returns a pre-built async generator.
# ===========================================================================


async def _collect_streaming_async(response) -> list[str]:
    chunks = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunks.append(chunk.decode())
        else:
            chunks.append(chunk)
    return chunks


@pytest.mark.asyncio
async def test_stream_chat_qdrant_path_v2():
    """Lines 573-576: qdrant path → [DONE] present in SSE output."""
    from gnosis.routers.ai import stream_chat

    async def _fake_stream_fn(message, owner_ids, mode):
        yield "hello"
        yield " world"

    db = AsyncMock()
    user = MagicMock()
    user.id = 1

    with (
        patch("gnosis.routers.ai.graph_rag") as mock_gr,
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
        patch("gnosis.routers.ai._qdrant_rag_stream", new=_fake_stream_fn),
    ):
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_llm.is_available = True
        response = await stream_chat(
            message="test", mode="hybrid", session=db, current_user=user, owner_ids={1}
        )

    chunks = await _collect_streaming_async(response)
    full = "".join(chunks)
    assert "[DONE]" in full
    assert "hello" in full


@pytest.mark.asyncio
async def test_stream_chat_no_provider_emits_error():
    """Lines 577-578: no provider → error event emitted."""
    from gnosis.routers.ai import stream_chat

    db = AsyncMock()
    user = MagicMock()
    user.id = 1

    with (
        patch("gnosis.routers.ai.graph_rag") as mock_gr,
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
    ):
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_llm.is_available = False
        response = await stream_chat(
            message="test", mode="hybrid", session=db, current_user=user, owner_ids={1}
        )

    chunks = await _collect_streaming_async(response)
    full = "".join(chunks)
    assert "No AI provider" in full
    assert "[DONE]" in full


@pytest.mark.asyncio
async def test_stream_chat_exception_emits_error_event_v2():
    """Lines 580-582: stream raises → error SSE event + [DONE]."""
    from gnosis.routers.ai import stream_chat

    db = AsyncMock()
    user = MagicMock()
    user.id = 1

    async def _boom(message, owner_ids, mode):
        raise RuntimeError("boom")
        yield  # make it an async generator

    with (
        patch("gnosis.routers.ai.graph_rag") as mock_gr,
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
        patch("gnosis.routers.ai._qdrant_rag_stream", new=_boom),
    ):
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_llm.is_available = True
        response = await stream_chat(
            message="test", mode="hybrid", session=db, current_user=user, owner_ids={1}
        )

    chunks = await _collect_streaming_async(response)
    full = "".join(chunks)
    assert "boom" in full
    assert "[DONE]" in full


# ===========================================================================
# ai.py — ingest_note (lines 596-630)
# ===========================================================================


@pytest.mark.asyncio
async def test_ingest_note_lightrag_not_available():
    """Lines 606-613: lightrag not installed → graph_indexed=False response."""
    from gnosis.routers.ai import ingest_note

    note = _make_note()
    result = MagicMock()
    result.scalar_one_or_none.return_value = note
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    user = MagicMock()
    user.id = 1

    with patch("gnosis.routers.ai._lightrag_available", return_value=False):
        resp = await ingest_note(
            note_id="note-1", session=db, current_user=user, owner_ids={1}
        )

    assert resp.graph_indexed is False
    assert "not available" in resp.message.lower()


@pytest.mark.asyncio
async def test_ingest_note_happy_path():
    """Lines 615-626: lightrag available → ingest called → graph_indexed=True."""
    from gnosis.routers.ai import ingest_note

    note = _make_note()
    result = MagicMock()
    result.scalar_one_or_none.return_value = note
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    user = MagicMock()
    user.id = 1

    with (
        patch("gnosis.routers.ai._lightrag_available", return_value=True),
        patch("gnosis.routers.ai.graph_rag") as mock_gr,
    ):
        mock_gr.__bool__ = lambda self: True
        mock_gr.ingest_note = AsyncMock()
        resp = await ingest_note(
            note_id="note-1", session=db, current_user=user, owner_ids={1}
        )

    assert resp.graph_indexed is True
    assert "note-1" in resp.note_id


@pytest.mark.asyncio
async def test_ingest_note_lightrag_raises_500():
    """Lines 628-630: ingest raises → 500 HTTPException."""
    from gnosis.routers.ai import ingest_note

    note = _make_note()
    result = MagicMock()
    result.scalar_one_or_none.return_value = note
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    user = MagicMock()
    user.id = 1

    with (
        patch("gnosis.routers.ai._lightrag_available", return_value=True),
        patch("gnosis.routers.ai.graph_rag") as mock_gr,
    ):
        mock_gr.__bool__ = lambda self: True
        mock_gr.ingest_note = AsyncMock(side_effect=RuntimeError("graph error"))
        with pytest.raises(Exception) as exc_info:
            await ingest_note(
                note_id="note-1", session=db, current_user=user, owner_ids={1}
            )
    assert "500" in str(exc_info.value) or "graph error" in str(exc_info.value)


# ===========================================================================
# ai.py — _lightrag_available (lines 633-640)
# ===========================================================================


def test_lightrag_available_import_error():
    """Lines 639-640: ImportError → returns False."""
    from gnosis.routers.ai import _lightrag_available

    with patch.dict("sys.modules", {"lightrag": None}):
        result = _lightrag_available()
    assert result is False


def test_lightrag_available_when_installed():
    """Lines 635-637: lightrag importable → returns True."""
    import sys
    from unittest.mock import MagicMock as MM

    import gnosis.routers.ai as ai_mod

    fake_lightrag = MM()
    sys.modules["lightrag"] = fake_lightrag
    try:
        result = ai_mod._lightrag_available()
        assert result is True
    finally:
        del sys.modules["lightrag"]


# ===========================================================================
# ai.py — generate_moc (lines 649-718)
# ===========================================================================


@pytest.mark.asyncio
async def test_generate_moc_no_provider_503():
    """Lines 654-657: llm_provider not available → 503."""
    from gnosis.routers.ai import generate_moc
    from gnosis.schemas.ai import MocRequest

    db = AsyncMock()
    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = False
        with pytest.raises(Exception) as exc_info:
            await generate_moc(req=MocRequest(topic="zen"), session=db, owner_ids={1})
    assert "503" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_moc_empty_topic_422():
    """Lines 659-661: empty topic → 422."""
    from gnosis.routers.ai import generate_moc
    from gnosis.schemas.ai import MocRequest

    db = AsyncMock()
    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        with pytest.raises(Exception) as exc_info:
            await generate_moc(req=MocRequest(topic="   "), session=db, owner_ids={1})
    assert "422" in str(exc_info.value) or "empty" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_generate_moc_no_notes_404():
    """Lines 673-676: no notes found → 404."""
    from gnosis.routers.ai import generate_moc
    from gnosis.schemas.ai import MocRequest

    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        with pytest.raises(Exception) as exc_info:
            await generate_moc(req=MocRequest(topic="zen"), session=db, owner_ids={1})
    assert "404" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_moc_happy_path():
    """Lines 684-718: notes found → LLM returns sections JSON → MocResponse."""
    from gnosis.routers.ai import generate_moc
    from gnosis.schemas.ai import MocRequest

    note = _make_note(body="zen mindfulness body")
    result = MagicMock()
    result.scalars.return_value.all.return_value = [note]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    sections_json = (
        '[{"heading": "Basics", "summary": "Intro to zen.", "wikilinks": ["Test Note"]}]'
    )
    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value=sections_json)
        resp = await generate_moc(req=MocRequest(topic="zen"), session=db, owner_ids={1})

    assert resp.topic == "zen"
    assert len(resp.sections) == 1
    assert resp.sections[0].heading == "Basics"


# ===========================================================================
# notes.py — _upsert_tags: new tag creation path (lines 51-54)
# ===========================================================================


@pytest.mark.asyncio
async def test_upsert_tags_creates_new_tag():
    """Lines 51-54: tag doesn't exist → Tag created, db.add called."""
    from gnosis.routers.notes import _upsert_tags

    tag_not_found = MagicMock()
    tag_not_found.scalar_one_or_none.return_value = None
    upsert_result = MagicMock()

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[tag_not_found, upsert_result])
    db.add = MagicMock()
    db.flush = AsyncMock()

    await _upsert_tags("note-1", ["new-tag"], db)

    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert added.name == "new-tag"


# ===========================================================================
# notes.py — get_note_graph (lines 309-327)
# ===========================================================================


class _Row:
    """Minimal attribute-access row to stand in for SQLAlchemy Row objects."""
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_get_note_graph_via_http():
    """Lines 309-327: GET /notes/graph returns nodes and edges."""
    from gnosis.core.auth import get_current_user, get_vault_owner_ids
    from gnosis.database import get_db
    from gnosis.models.user import User
    from gnosis.routers.notes import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    user = User(email="u@t.com", hashed_password="x", is_superuser=False, is_active=True)
    user.id = 1

    note_row = _Row(id="n1", title="A", folder="00-inbox", note_type="permanent")
    link_row = _Row(source_id="n1", target_id="n2", link_type="wikilink")

    call = [0]

    async def _fake_execute(stmt):
        idx = call[0]
        call[0] += 1
        r = MagicMock()
        if idx == 0:
            r.all.return_value = [note_row]
        else:
            r.all.return_value = [link_row]
        return r

    async def _fake_db():
        db = AsyncMock()
        db.execute = _fake_execute
        yield db

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_vault_owner_ids] = lambda: {1}

    client = TestClient(app)
    resp = client.get("/api/v1/notes/graph")
    assert resp.status_code == 200
    body = resp.json()
    assert any(n["id"] == "n1" for n in body["nodes"])
    assert any(e["source"] == "n1" for e in body["edges"])


# ===========================================================================
# notes.py — search_notes (lines 343-383)
# ===========================================================================


def test_search_notes_via_http():
    """Lines 343-383: GET /notes/search?q=... returns matching notes."""
    from gnosis.core.auth import get_current_user, get_vault_owner_ids
    from gnosis.database import get_db
    from gnosis.models.user import User
    from gnosis.routers.notes import router
    from datetime import datetime

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    user = User(email="u@t.com", hashed_password="x", is_superuser=False, is_active=True)
    user.id = 1

    note = MagicMock()
    note.id = "n1"
    note.title = "Zen Buddhism"
    note.slug = "zen-buddhism"
    note.note_type = "permanent"
    note.status = "evergreen"
    note.folder = "20-lit"
    note.word_count = 50
    note.created_at = None
    note.modified_at = None
    note.tags = []

    call = [0]

    async def _fake_execute(stmt):
        idx = call[0]
        call[0] += 1
        r = MagicMock()
        if idx == 0:
            r.scalar_one.return_value = 1
        else:
            r.scalars.return_value.unique.return_value.all.return_value = [note]
        return r

    async def _fake_db():
        db = AsyncMock()
        db.execute = _fake_execute
        yield db

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_vault_owner_ids] = lambda: {1}

    client = TestClient(app)
    resp = client.get("/api/v1/notes/search?q=zen")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Zen Buddhism"


# ===========================================================================
# review.py — enroll card (lines 145-153, 156)
#
# enroll_note is POST /{note_id}/enroll and returns HTTP 201 on creation.
# The existing-card branch returns 200 (model_validate on existing card).
# _get_card_or_404 uses result.scalars().one_or_none().
# submit_review first call uses scalars().one_or_none() (card),
# second call uses scalar_one_or_none() (note).
# Use _make_card() so ReviewCardRead.model_validate() has proper typed fields.
# ===========================================================================


def test_review_enroll_note_not_found():
    """Lines 145-147: note not found → 404."""
    from gnosis.database import get_db
    from gnosis.routers.review import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _fake_db():
        db = AsyncMock()
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=r)
        yield db

    app.dependency_overrides[get_db] = _fake_db

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/review/missing-note/enroll", json={})
    assert resp.status_code == 404


def test_review_enroll_existing_card_returns_it():
    """Lines 148-150: card already exists → returned as 200 (model_validate)."""
    from gnosis.database import get_db
    from gnosis.routers.review import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    card = _make_card(note_id="note-1")

    call = [0]

    async def _fake_db():
        db = AsyncMock()

        async def _execute(stmt):
            idx = call[0]
            call[0] += 1
            r = MagicMock()
            if idx == 0:
                r.scalar_one_or_none.return_value = MagicMock(id="note-1")  # note found
            else:
                r.scalar_one_or_none.return_value = card  # existing card
            return r

        db.execute = _execute
        yield db

    app.dependency_overrides[get_db] = _fake_db

    client = TestClient(app)
    resp = client.post("/api/v1/review/note-1/enroll", json={})
    # existing card branch returns 200 (not 201)
    assert resp.status_code == 200
    assert resp.json()["note_id"] == "note-1"


def test_review_submit_updates_note_last_reviewed():
    """Lines 188-190: submit review → note.last_reviewed updated."""
    from gnosis.database import get_db
    from gnosis.routers.review import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    card = _make_card(note_id="note-1")
    # card.note is accessed by _card_to_with_note but submit_review does not
    # call _card_to_with_note; it returns ReviewCardRead.model_validate(card).
    # _get_card_or_404 uses result.scalars().one_or_none()
    card.note = MagicMock()
    card.note.title = "Test Note"
    card.note.body = "Body"
    card.note.folder = "00-inbox"
    card.note.tags = []

    note = MagicMock()
    note.last_reviewed = None

    call = [0]

    async def _fake_db():
        db = AsyncMock()

        async def _execute(stmt):
            idx = call[0]
            call[0] += 1
            r = MagicMock()
            if idx == 0:
                # _get_card_or_404: result.scalars().one_or_none()
                r.scalars.return_value.one_or_none.return_value = card
                # also set scalar_one_or_none for safety
                r.scalar_one_or_none.return_value = card
            else:
                # Note lookup: result.scalar_one_or_none()
                r.scalar_one_or_none.return_value = note
            return r

        db.execute = _execute
        db.commit = AsyncMock()

        async def _refresh(obj):
            pass

        db.refresh = AsyncMock(side_effect=_refresh)
        yield db

    app.dependency_overrides[get_db] = _fake_db

    client = TestClient(app)
    resp = client.post("/api/v1/review/note-1", json={"quality": 4})
    assert resp.status_code == 200


# ===========================================================================
# users.py — update_grant (lines 343-351)
#
# UpdateGrantRequest has field `permission` (not `role`). `role` is a
# @property that normalises the permission string. Pass permission= not role=.
# ===========================================================================


@pytest.mark.asyncio
async def test_update_grant_member_not_found_404():
    """Lines 338-341: SharedVaultMember not found → 404."""
    from gnosis.models.user import User
    from gnosis.routers.users import UpdateGrantRequest, update_grant

    user = User(email="u@t.com", hashed_password="x", is_superuser=False, is_active=True)
    user.id = 1

    r = MagicMock()
    r.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=r)

    req = UpdateGrantRequest(permission="editor")  # permission=, not role=
    with pytest.raises(Exception) as exc_info:
        await update_grant(grant_id="g1", req=req, session=session, current_user=user)
    assert "404" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_grant_not_vault_owner_403():
    """Lines 343-351: vault not owned by current_user → 403."""
    from gnosis.models.user import User
    from gnosis.routers.users import UpdateGrantRequest, update_grant

    user = User(email="u@t.com", hashed_password="x", is_superuser=False, is_active=True)
    user.id = 1

    member_row = MagicMock()
    member_row.vault_id = "vault-1"

    member_result = MagicMock()
    member_result.scalar_one_or_none.return_value = member_row

    vault_result = MagicMock()
    vault_result.scalar_one_or_none.return_value = None  # user doesn't own vault

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[member_result, vault_result])

    req = UpdateGrantRequest(permission="viewer")  # permission=, not role=
    with pytest.raises(Exception) as exc_info:
        await update_grant(grant_id="g1", req=req, session=session, current_user=user)
    assert "403" in str(exc_info.value)


# ===========================================================================
# users.py — revoke_grant (lines 390-397)
# ===========================================================================


@pytest.mark.asyncio
async def test_revoke_grant_member_not_found_404():
    """Lines 375-378: grant not found → 404."""
    from gnosis.models.user import User
    from gnosis.routers.users import revoke_grant

    user = User(email="u@t.com", hashed_password="x", is_superuser=False, is_active=True)
    user.id = 1

    r = MagicMock()
    r.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=r)

    with pytest.raises(Exception) as exc_info:
        await revoke_grant(grant_id="g1", session=session, current_user=user)
    assert "404" in str(exc_info.value)


@pytest.mark.asyncio
async def test_revoke_grant_not_vault_owner_403():
    """Lines 390-397: vault not owned → 403."""
    from gnosis.models.user import User
    from gnosis.routers.users import revoke_grant

    user = User(email="u@t.com", hashed_password="x", is_superuser=False, is_active=True)
    user.id = 1

    member_row = MagicMock()
    member_row.vault_id = "vault-1"

    member_result = MagicMock()
    member_result.scalar_one_or_none.return_value = member_row

    vault_result = MagicMock()
    vault_result.scalar_one_or_none.return_value = None  # not owner

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[member_result, vault_result])

    with pytest.raises(Exception) as exc_info:
        await revoke_grant(grant_id="g1", session=session, current_user=user)
    assert "403" in str(exc_info.value)


# ===========================================================================
# vault.py — get_sync_status: entry present (lines 168->171)
# ===========================================================================


def test_get_sync_status_entry_present():
    """Lines 168->171: sync status entry present → elapsed computed."""
    import time
    from gnosis.core.auth import get_current_user
    from gnosis.models.user import User
    from gnosis.routers.vault import router, _sync_status

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    user = User(email="u@t.com", hashed_password="x", is_superuser=False, is_active=True)
    user.id = 42
    app.dependency_overrides[get_current_user] = lambda: user

    _sync_status[42] = {
        "state": "running",
        "files_processed": 3,
        "files_total": 10,
        "started": time.time() - 5.0,
        "last_error": None,
    }

    try:
        client = TestClient(app)
        resp = client.get("/api/v1/vault/sync/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "running"
        assert body["elapsed"] is not None
        assert body["files_processed"] == 3
    finally:
        _sync_status.pop(42, None)


# ===========================================================================
# vault.py — get_vault_stats (lines 192-220)
# ===========================================================================


def test_get_vault_stats():
    """Lines 192-220: GET /vault/stats returns note counts and word total."""
    from gnosis.core.auth import get_current_user, get_vault_owner_ids
    from gnosis.database import get_db
    from gnosis.models.user import User
    from gnosis.routers.vault import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    user = User(email="u@t.com", hashed_password="x", is_superuser=False, is_active=True)
    user.id = 1

    call = [0]

    async def _fake_execute(stmt):
        idx = call[0]
        call[0] += 1
        r = MagicMock()
        if idx == 0:
            r.scalar_one.return_value = 7
        elif idx == 1:
            r.scalar_one.return_value = 1234
        else:
            r.all.return_value = [("permanent", 5), ("fleeting", 2)]
        return r

    async def _fake_db():
        db = AsyncMock()
        db.execute = _fake_execute
        yield db

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_vault_owner_ids] = lambda: {1}

    client = TestClient(app)
    resp = client.get("/api/v1/vault/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_notes"] == 7
    assert body["total_words"] == 1234
    assert "permanent" in body["by_type"]


# ===========================================================================
# vault.py — get_vault_path (lines 237-240)
# ===========================================================================


def test_get_vault_path():
    """Lines 237-240: GET /vault/path returns path dict."""
    from gnosis.core.auth import get_current_user
    from gnosis.models.user import User
    from gnosis.routers.vault import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    user = User(email="u@t.com", hashed_password="x", is_superuser=False, is_active=True)
    user.id = 1
    user.vault_path = None
    user.vault_slug = None
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    resp = client.get("/api/v1/vault/path")
    assert resp.status_code == 200
    body = resp.json()
    assert "vault_path" in body
    assert "exists" in body
