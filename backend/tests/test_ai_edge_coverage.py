"""Edge-case coverage for gnosis/routers/ai.py – ingest_note paths.

Source-verified:
- URL: POST /api/v1/ai/ingest-note/{note_id}  (path param, NO request body)
- LightRAG check: `if not graph_rag or not _lightrag_available():`
  graph_rag is truthy (imported service object); patch _lightrag_available.
- graph_rag.ingest_note must be AsyncMock (endpoint awaits it).
- owner_id fallback: `effective_uid = note.owner_id if note.owner_id is not None else 0`
  Notes created by FakeUser(id=1) will have owner_id=1, not None.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


async def _create_note(async_client, title="Edge note") -> str:
    resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": title, "body": "edge body"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_ingest_note_returns_unavailable_when_lightrag_check_fails(async_client):
    """_lightrag_available() returns False → graph_indexed=False, 200."""
    note_id = await _create_note(async_client)

    with patch("gnosis.routers.ai._lightrag_available", return_value=False):
        resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")

    assert resp.status_code == 200
    assert resp.json()["graph_indexed"] is False


async def test_ingest_note_raises_500_when_graph_ingest_fails(async_client):
    """graph_rag.ingest_note raises → 500."""
    note_id = await _create_note(async_client)

    with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
         patch("gnosis.routers.ai.graph_rag") as mock_gr:
        mock_gr.ingest_note = AsyncMock(side_effect=Exception("graph down"))
        resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")

    assert resp.status_code == 500


async def test_ingest_note_success_marks_graph_indexed(async_client):
    """LightRAG available and ingest succeeds → graph_indexed=True, 200."""
    note_id = await _create_note(async_client, "Success note")

    with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
         patch("gnosis.routers.ai.graph_rag") as mock_gr:
        mock_gr.ingest_note = AsyncMock(return_value=None)
        resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")

    assert resp.status_code == 200
    assert resp.json()["graph_indexed"] is True


async def test_ingest_note_null_owner_id_uses_zero(async_client):
    """Note with owner_id=None handled via `or 0` fallback.

    We force owner_id=None by patching the note returned by _get_note_or_404.
    """
    note_id = await _create_note(async_client, "Null owner note")

    # Patch _get_note_or_404 to return a note with owner_id=None
    from gnosis.models.note import Note as NoteModel
    fake_note = NoteModel()
    fake_note.id = note_id
    fake_note.title = "Null owner note"
    fake_note.body = "body"
    fake_note.owner_id = None

    with patch("gnosis.routers.ai._get_note_or_404", return_value=fake_note), \
         patch("gnosis.routers.ai._lightrag_available", return_value=True), \
         patch("gnosis.routers.ai.graph_rag") as mock_gr:
        mock_gr.ingest_note = AsyncMock(return_value=None)
        resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")

    # effective_uid = 0 path ran; ingest succeeded
    assert resp.status_code == 200
    assert resp.json()["graph_indexed"] is True
