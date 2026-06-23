"""Edge-case coverage for gnosis/routers/ai.py – ingest_note paths.

Fixes:
- patch target changed from a nonexistent module-level variable to the
  actual function _lightrag_available and the graph_rag service object.
- graph_rag.ingest_note must be an AsyncMock because the endpoint awaits it.
- owner_id=None test: the endpoint converts None to 0 via ``or 0``.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


async def _create_note(async_client) -> str:
    resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": "Edge note", "body": "edge body"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_ingest_note_returns_unavailable_when_lightrag_check_fails(async_client):
    """When _lightrag_available() returns False, ingest returns graph_indexed=False."""
    note_id = await _create_note(async_client)

    with patch("gnosis.routers.ai._lightrag_available", return_value=False):
        resp = await async_client.post(
            "/api/v1/ai/ingest",
            json={"note_id": note_id, "content": "hello world"},
        )

    assert resp.status_code == 200
    assert resp.json()["graph_indexed"] is False


async def test_ingest_note_raises_500_when_graph_ingest_fails(async_client):
    """When graph_rag.ingest_note raises, the endpoint returns 500."""
    note_id = await _create_note(async_client)

    with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
         patch("gnosis.routers.ai.graph_rag") as mock_gr:
        mock_gr.ingest_note = AsyncMock(side_effect=Exception("graph down"))
        resp = await async_client.post(
            "/api/v1/ai/ingest",
            json={"note_id": note_id, "content": "hello world"},
        )

    assert resp.status_code == 500


async def test_ingest_note_success_marks_graph_indexed(async_client):
    """Happy path: LightRAG available and ingest succeeds → graph_indexed=True."""
    note_id = await _create_note(async_client)

    with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
         patch("gnosis.routers.ai.graph_rag") as mock_gr:
        mock_gr.ingest_note = AsyncMock(return_value=None)
        resp = await async_client.post(
            "/api/v1/ai/ingest",
            json={"note_id": note_id, "content": "hello world"},
        )

    assert resp.status_code == 200
    assert resp.json()["graph_indexed"] is True


async def test_ingest_note_null_owner_id_uses_zero(async_client):
    """owner_id absent from payload is treated as 0 (no crash)."""
    note_id = await _create_note(async_client)

    with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
         patch("gnosis.routers.ai.graph_rag") as mock_gr:
        mock_gr.ingest_note = AsyncMock(return_value=None)
        resp = await async_client.post(
            "/api/v1/ai/ingest",
            json={"note_id": note_id, "content": "hello"},
        )

    assert resp.status_code == 200
