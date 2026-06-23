"""Line-level coverage for gnosis/routers/ai.py.

Fixes:
- patch target is _lightrag_available (a function) and graph_rag service,
  not a nonexistent module-level bool variable.
- graph_rag.ingest_note must be AsyncMock.
- test_lightrag_available_check_returns_bool: call the real function directly
  so we prove it returns a bool in the test environment (lightrag not installed
  → False, or True if installed). Either value is acceptable.
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
        resp = await async_client.post(
            "/api/v1/ai/ingest",
            json={"note_id": note_id, "content": "test content"},
        )

    assert resp.status_code == 200
    assert resp.json()["graph_indexed"] is True


def test_lightrag_available_check_returns_bool():
    """_lightrag_available() must return a bool regardless of installation."""
    result = _lightrag_available()
    assert isinstance(result, bool)
