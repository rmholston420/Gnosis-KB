"""Arc coverage for gnosis/routers/ai.py.

Source-verified facts (ai.py read directly):
- Providers endpoint: httpx branch ONLY runs if "ollama" in llm_provider._available
  Must patch llm_provider._available and httpx.AsyncClient both.
- Ingest endpoint URL: POST /ai/ingest-note/{note_id}  (path param, no body)
- _lightrag_available is a module-level function; patch as gnosis.routers.ai._lightrag_available
- graph_rag is imported at module top: from gnosis.services.graph_rag import graph_rag
  Patch as gnosis.routers.ai.graph_rag
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Providers – Ollama available / tag-fetch fails
# ---------------------------------------------------------------------------

class TestProvidersArc:
    """Cover the Ollama-available and Ollama-tag-fetch-fails branches.

    The httpx block in get_providers() only runs when:
        "ollama" in llm_provider._available
    So we must patch that attribute too.
    """

    async def test_providers_with_ollama_available(self, async_client):
        """When Ollama /api/tags returns 200, models list is populated."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3:8b"}]}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.active_provider = "ollama"
        mock_llm.active_model = "llama3:8b"
        mock_llm._available = {"ollama"}

        with patch("gnosis.routers.ai.httpx.AsyncClient", return_value=mock_client), \
             patch("gnosis.routers.ai.llm_provider", mock_llm):
            resp = await async_client.get("/api/v1/ai/providers")

        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert "llama3:8b" in data["models"]

    async def test_providers_ollama_tag_fetch_fails(self, async_client):
        """When Ollama /api/tags raises, models list falls back gracefully."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.active_provider = "ollama"
        mock_llm.active_model = "llama3:8b"
        mock_llm._available = {"ollama"}

        with patch("gnosis.routers.ai.httpx.AsyncClient", return_value=mock_client), \
             patch("gnosis.routers.ai.llm_provider", mock_llm):
            resp = await async_client.get("/api/v1/ai/providers")

        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        # Falls back to [active_model]
        assert data["models"] == ["llama3:8b"]


# ---------------------------------------------------------------------------
# ingest_note – exception arcs
# POST /ai/ingest-note/{note_id}  (path param, no body)
# ---------------------------------------------------------------------------

class TestIngestNoteExceptionArc:
    """Cover RuntimeError and ValueError paths inside ingest_note."""

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
            resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")

        assert resp.status_code == 500

    async def test_ingest_note_raises_http_500_on_value_error(self, async_client):
        note_id = await self._create_note(async_client)

        with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
             patch("gnosis.routers.ai.graph_rag") as mock_gr:
            mock_gr.ingest_note = AsyncMock(side_effect=ValueError("bad val"))
            resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")

        assert resp.status_code == 500
