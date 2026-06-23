"""Line-level coverage for gnosis/routers/ai.py.

Source-verified:
- URL: POST /api/v1/ai/ingest-note/{note_id}
- _lightrag_available is a function; import and call directly for unit test.
- patch target: gnosis.routers.ai._lightrag_available
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from gnosis.routers.ai import _lightrag_available

pytestmark = pytest.mark.asyncio


async def _create_note(async_client) -> str:
    resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": "Line note", "body": "line body"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_ingest_note_succeeds_and_marks_graph_indexed(async_client):
    note_id = await _create_note(async_client)

    with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
         patch("gnosis.routers.ai.graph_rag") as mock_gr:
        mock_gr.ingest_note = AsyncMock(return_value=None)
        resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")

    assert resp.status_code == 200
    assert resp.json()["graph_indexed"] is True


def test_lightrag_available_check_returns_bool():
    """_lightrag_available() returns a bool in all environments."""
    result = _lightrag_available()
    assert isinstance(result, bool)
