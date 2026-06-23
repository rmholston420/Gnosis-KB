"""Additional AI router tests: daily_review branches and stream_chat generator."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _note(note_id="n1", title="Inbox Note", body="Some content.", folder="00-inbox"):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.folder = folder
    n.note_type = "fleeting"
    n.status = "active"
    n.is_deleted = False
    n.created_at = datetime.now(UTC)
    return n


# ---------------------------------------------------------------------------
# daily_review — no notes branch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_review_returns_no_notes_summary_when_inbox_empty():
    from gnosis.routers.ai import daily_review

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    with patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s):
        result = await daily_review(session=db, owner_ids={1})

    assert result.inbox_note_count == 0
    assert "No inbox" in result.summary
    assert result.action_items == []


@pytest.mark.asyncio
async def test_daily_review_returns_fallback_when_no_llm():
    from gnosis.routers.ai import daily_review

    notes = [_note()]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = notes
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    with (
        patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
    ):
        mock_llm.is_available = False
        result = await daily_review(session=db, owner_ids={1})

    assert result.inbox_note_count == 1
    assert result.action_items == []


@pytest.mark.asyncio
async def test_daily_review_parses_llm_json_response():
    from gnosis.routers.ai import daily_review

    notes = [_note()]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = notes
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    llm_resp = json.dumps({"summary": "Good day.", "action_items": ["Process note A"]})

    with (
        patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
    ):
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value=llm_resp)
        result = await daily_review(session=db, owner_ids={1})

    assert result.summary == "Good day."
    assert "Process note A" in result.action_items


# ---------------------------------------------------------------------------
# stream_chat — SSE event generator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_chat_emits_done_when_no_provider():
    from gnosis.routers.ai import stream_chat

    user = MagicMock()
    user.id = 1

    with (
        patch("gnosis.routers.ai.graph_rag") as mock_gr,
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
    ):
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_llm.is_available = False

        response = await stream_chat(
            message="hi", mode="hybrid",
            session=AsyncMock(), current_user=user, owner_ids={1},
        )
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

    full = "".join(chunks)
    assert "[DONE]" in full
    assert "error" in full or "[DONE]" in full


@pytest.mark.asyncio
async def test_stream_chat_emits_tokens_via_qdrant():
    from gnosis.routers.ai import stream_chat

    user = MagicMock()
    user.id = 1

    async def _fake_stream(message, owner_ids, mode):
        for token in ["Hello", " world"]:
            yield token

    with (
        patch("gnosis.routers.ai.graph_rag") as mock_gr,
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
        patch("gnosis.routers.ai._qdrant_rag_stream", side_effect=_fake_stream),
    ):
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_llm.is_available = True

        response = await stream_chat(
            message="hi", mode="hybrid",
            session=AsyncMock(), current_user=user, owner_ids={1},
        )
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

    full = "".join(chunks)
    assert "Hello" in full
    assert "[DONE]" in full
    assert '"rag_source": "qdrant"' in full
