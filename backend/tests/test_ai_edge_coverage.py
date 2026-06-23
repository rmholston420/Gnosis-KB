"""
Edge-case coverage for gnosis/routers/ai.py — ingest_note guard paths.

All four tests were failing because they patched a non-existent symbol.
Correct patch target: gnosis.routers.ai._lightrag_available
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient


def _make_note(note_id="edge-note-1", title="Edge Note", body="body text", owner_id=1):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.owner_id = owner_id
    return n


# ---------------------------------------------------------------------------
# Guard branch: _lightrag_available() returns False
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ingest_note_returns_unavailable_when_lightrag_check_fails(
    async_client: AsyncClient, auth_headers: dict
):
    """If _lightrag_available() is False the endpoint returns graph_indexed=False."""
    note = _make_note()

    with (
        patch("gnosis.routers.ai._get_note_or_404", AsyncMock(return_value=note)),
        patch("gnosis.routers.ai._lightrag_available", return_value=False),
    ):
        resp = await async_client.post(
            f"/api/v1/ai/ingest-note/{note.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["graph_indexed"] is False
    assert "not available" in data["message"].lower()


# ---------------------------------------------------------------------------
# Exception branch: ingest raises → 500
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ingest_note_raises_500_when_graph_ingest_fails(
    async_client: AsyncClient, auth_headers: dict
):
    """If graph_rag.ingest_note raises an exception → HTTP 500."""
    note = _make_note(note_id="edge-note-2", title="Edge Note 2")

    mock_gr = MagicMock()
    mock_gr.__bool__ = MagicMock(return_value=True)
    mock_gr.ingest_note = AsyncMock(side_effect=RuntimeError("ingest exploded"))

    with (
        patch("gnosis.routers.ai._get_note_or_404", AsyncMock(return_value=note)),
        patch("gnosis.routers.ai._lightrag_available", return_value=True),
        patch("gnosis.routers.ai.graph_rag", mock_gr),
    ):
        resp = await async_client.post(
            f"/api/v1/ai/ingest-note/{note.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 500
    assert "LightRAG ingest failed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Happy path: successful ingest
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ingest_note_success_marks_graph_indexed(
    async_client: AsyncClient, auth_headers: dict
):
    """Successful ingest returns graph_indexed=True."""
    note = _make_note(note_id="edge-note-3", title="Edge Note 3")

    mock_gr = MagicMock()
    mock_gr.__bool__ = MagicMock(return_value=True)
    mock_gr.ingest_note = AsyncMock(return_value=None)

    with (
        patch("gnosis.routers.ai._get_note_or_404", AsyncMock(return_value=note)),
        patch("gnosis.routers.ai._lightrag_available", return_value=True),
        patch("gnosis.routers.ai.graph_rag", mock_gr),
        patch("gnosis.routers.ai.update", MagicMock()),
    ):
        resp = await async_client.post(
            f"/api/v1/ai/ingest-note/{note.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["graph_indexed"] is True


# ---------------------------------------------------------------------------
# Null owner_id path
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ingest_note_null_owner_id_uses_zero(
    async_client: AsyncClient, auth_headers: dict
):
    """owner_id=None → effective_uid=0 without crashing."""
    note = _make_note(note_id="edge-note-4", owner_id=None)

    mock_gr = MagicMock()
    mock_gr.__bool__ = MagicMock(return_value=True)
    mock_gr.ingest_note = AsyncMock(return_value=None)

    with (
        patch("gnosis.routers.ai._get_note_or_404", AsyncMock(return_value=note)),
        patch("gnosis.routers.ai._lightrag_available", return_value=True),
        patch("gnosis.routers.ai.graph_rag", mock_gr),
        patch("gnosis.routers.ai.update", MagicMock()),
    ):
        resp = await async_client.post(
            f"/api/v1/ai/ingest-note/{note.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["graph_indexed"] is True
    # Verify ingest_note was called with user_id=0
    mock_gr.ingest_note.assert_called_once()
    call_kwargs = mock_gr.ingest_note.call_args.kwargs
    assert call_kwargs.get("user_id") == 0
