"""Additional coverage tests for gnosis/routers/ai.py complex branches."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _note(note_id="n1", title="Note Title", body="Body text", folder="10-zettelkasten"):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.folder = folder
    n.note_type = "evergreen"
    n.status = "active"
    n.is_deleted = False
    n.created_at = datetime.now(timezone.utc)
    return n


@pytest.mark.asyncio
async def test_orphan_audit_returns_items_when_llm_json_parses():
    from gnosis.routers.ai import orphan_audit

    rows = [_note("o1", "Orphan One"), _note("o2", "Orphan Two")]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = rows
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)
    raw = '[{"note_id": "o1", "title": "Orphan One", "suggestions": ["Topic A", "Topic B"]}]'

    with (
        patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
    ):
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value=raw)
        result = await orphan_audit(limit=10, session=db, owner_ids={1})

    assert result.orphan_count == 2
    assert len(result.items) == 1
    assert result.items[0].note_id == "o1"
    assert result.items[0].suggestions == ["Topic A", "Topic B"]


@pytest.mark.asyncio
async def test_generate_moc_rejects_blank_topic_before_querying():
    from gnosis.routers.ai import generate_moc
    from gnosis.schemas.ai import MocRequest

    db = AsyncMock()

    with patch("gnosis.routers.ai.llm_provider") as mock_llm:
        mock_llm.is_available = True
        with pytest.raises(HTTPException) as exc:
            await generate_moc(MocRequest(topic="   "), session=db, owner_ids={1})

    assert exc.value.status_code == 422
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_generate_moc_returns_empty_sections_when_llm_output_not_json():
    from gnosis.routers.ai import generate_moc
    from gnosis.schemas.ai import MocRequest

    notes = [_note("m1", "Topic Note", "topic appears here")]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = notes
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    with (
        patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
        patch("gnosis.routers.ai.llm_provider") as mock_llm,
    ):
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value="not valid json")
        result = await generate_moc(MocRequest(topic="topic", max_notes=5), session=db, owner_ids={1})

    assert result.topic == "topic"
    assert result.note_count == 1
    assert result.sections == []
    assert "# MOC — Topic" in result.markdown


@pytest.mark.asyncio
async def test_ingest_note_returns_unavailable_when_lightrag_check_fails():
    from gnosis.routers.ai import ingest_note

    db = AsyncMock()
    user = MagicMock()
    user.id = 1
    note = _note("ing1", "Ingest Me", "Body")
    note.owner_id = 5

    with (
        patch("gnosis.routers.ai._get_note_or_404", new=AsyncMock(return_value=note)),
        patch("gnosis.routers.ai.graph_rag", object()),
        patch("gnosis.routers.ai._LIGHTRAG_AVAILABLE_CHECK", return_value=False),
    ):
        result = await ingest_note("ing1", session=db, current_user=user, owner_ids={1})

    assert result.graph_indexed is False
    assert "not available" in result.message.lower()
    db.execute.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_note_raises_500_when_graph_ingest_fails():
    from gnosis.routers.ai import ingest_note

    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    user = MagicMock()
    user.id = 1
    note = _note("ing2", "Broken", "Body")
    note.owner_id = 9

    fake_graph = MagicMock()
    fake_graph.ingest_note = AsyncMock(side_effect=RuntimeError("graph fail"))

    with (
        patch("gnosis.routers.ai._get_note_or_404", new=AsyncMock(return_value=note)),
        patch("gnosis.routers.ai.graph_rag", fake_graph),
        patch("gnosis.routers.ai._LIGHTRAG_AVAILABLE_CHECK", return_value=True),
    ):
        with pytest.raises(HTTPException) as exc:
            await ingest_note("ing2", session=db, current_user=user, owner_ids={1})

    assert exc.value.status_code == 500
    assert "LightRAG ingest failed" in exc.value.detail
    db.commit.assert_not_awaited()
