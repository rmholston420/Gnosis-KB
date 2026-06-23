"""Arc coverage for gnosis/routers/ai.py.

Fixes:
- TestProvidersArc: patch httpx.AsyncClient at the call-site module so the
  async context-manager used inside the endpoint is fully mocked.
- TestIngestNoteExceptionArc: patch graph_rag.ingest_note as AsyncMock at
  gnosis.routers.ai.graph_rag.ingest_note (the imported name in that module).
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Providers – Ollama available / tag-fetch fails
# ---------------------------------------------------------------------------

class TestProvidersArc:
    """Cover the Ollama-available and Ollama-tag-fetch-fails branches."""

    async def test_providers_with_ollama_available(self, async_client):
        """When Ollama responds 200 the provider list includes ollama."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3:8b"}]}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("gnosis.routers.ai.httpx.AsyncClient", return_value=mock_client):
            resp = await async_client.get("/api/v1/ai/providers")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_providers_ollama_tag_fetch_fails(self, async_client):
        """When Ollama /api/tags raises, provider list still returns cleanly."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))

        with patch("gnosis.routers.ai.httpx.AsyncClient", return_value=mock_client):
            resp = await async_client.get("/api/v1/ai/providers")

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# ingest_note – exception arcs
# ---------------------------------------------------------------------------

class TestIngestNoteExceptionArc:
    """Cover RuntimeError and ValueError paths inside POST /ai/ingest."""

    async def _create_note(self, async_client) -> str:
        resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "Arc note", "body": "arc body"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_ingest_note_raises_http_500_on_runtime_error(self, async_client):
        note_id = await self._create_note(async_client)

        with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
             patch("gnosis.routers.ai.graph_rag") as mock_gr:
            mock_gr.ingest_note = AsyncMock(side_effect=RuntimeError("boom"))
            resp = await async_client.post(
                "/api/v1/ai/ingest",
                json={"note_id": note_id, "content": "some content"},
            )

        assert resp.status_code == 500

    async def test_ingest_note_raises_http_500_on_value_error(self, async_client):
        note_id = await self._create_note(async_client)

        with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
             patch("gnosis.routers.ai.graph_rag") as mock_gr:
            mock_gr.ingest_note = AsyncMock(side_effect=ValueError("bad val"))
            resp = await async_client.post(
                "/api/v1/ai/ingest",
                json={"note_id": note_id, "content": "some content"},
            )

        assert resp.status_code == 500
