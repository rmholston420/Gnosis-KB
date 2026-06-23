"""Coverage-focused tests for gnosis/routers/admin.py edge branches."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gnosis.models.note import Note
from gnosis.models.user import User


@pytest.mark.asyncio
async def test_reindex_note_returns_error_on_db_update_failure(test_db):
    from gnosis.routers.admin import _reindex_note

    note = Note(id="n1", title="Broken", body="Body", owner_id=0)
    test_db.execute = AsyncMock(side_effect=RuntimeError("db exploded"))
    test_db.flush = AsyncMock()

    result = await _reindex_note(note, 1, test_db)

    assert result["status"] == "error"
    assert result["id"] == "n1"
    assert "db exploded" in result["detail"]
    test_db.flush.assert_not_called()


@pytest.mark.asyncio
async def test_reindex_note_marks_empty_when_body_blank(test_db):
    from gnosis.routers.admin import _reindex_note

    note = Note(id="n2", title="Empty", body="   ", owner_id=0)
    test_db.execute = AsyncMock(return_value=MagicMock())
    test_db.flush = AsyncMock()

    result = await _reindex_note(note, 1, test_db)

    assert result["status"] == "ok"
    assert result["ingest"] == "empty"
    assert result["new_owner_id"] == 1


@pytest.mark.asyncio
async def test_reindex_note_reports_lightrag_error_when_ingest_fails(test_db):
    from gnosis.routers.admin import _reindex_note

    note = Note(id="n3", title="Graph", body="real content", owner_id=0)
    test_db.execute = AsyncMock(return_value=MagicMock())
    test_db.flush = AsyncMock()

    fake_graph = MagicMock()
    fake_graph.ingest_note = AsyncMock(side_effect=RuntimeError("ollama offline"))

    with patch("gnosis.services.graph_rag.graph_rag", fake_graph):
        result = await _reindex_note(note, 7, test_db)

    assert result["status"] == "ok"
    assert result["ingest"].startswith("lightrag_error:")
    assert "ollama offline" in result["ingest"]


@pytest.mark.asyncio
async def test_reindex_legacy_notes_returns_partial_when_one_note_fails(test_db):
    from gnosis.routers.admin import reindex_legacy_notes

    admin = User(id=1, email="admin@example.com", hashed_password="x", is_active=True)
    note_ok = Note(id="ok-note", title="OK", body="Body", owner_id=0, is_deleted=False)
    note_bad = Note(id="bad-note", title="Bad", body="Body", owner_id=0, is_deleted=False)

    first_result = MagicMock()
    first_result.scalars.return_value.first.return_value = admin
    second_result = MagicMock()
    second_result.scalars.return_value.all.return_value = [note_ok, note_bad]
    test_db.execute = AsyncMock(side_effect=[first_result, second_result])
    test_db.commit = AsyncMock()

    rows = [
        {"id": "ok-note", "title": "OK", "status": "ok", "ingest": "ingested"},
        {"id": "bad-note", "title": "Bad", "status": "error", "detail": "boom"},
    ]

    with patch("gnosis.routers.admin._reindex_note", new=AsyncMock(side_effect=rows)):
        result = await reindex_legacy_notes(db=test_db, current_user=admin)

    assert result["status"] == "partial"
    assert result["fixed"] == 1
    assert result["errors"] == 1
    assert result["new_owner_id"] == 1
    assert len(result["notes"]) == 2
    test_db.commit.assert_awaited_once()
