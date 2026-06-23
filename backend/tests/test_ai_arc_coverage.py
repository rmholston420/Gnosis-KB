"""
Arc coverage for ai.py — all existing tests preserved; the two failing
IngestNoteExceptionArc tests are corrected to patch the real symbol.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers shared across tests in this file
# ---------------------------------------------------------------------------

def _make_note(note_id="note-arc-1", title="Arc Note", body="body", owner_id=1):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.owner_id = owner_id
    n.is_deleted = False
    return n


# ---------------------------------------------------------------------------
# TestIngestNoteExceptionArc  — was using wrong patch target
# ---------------------------------------------------------------------------

class TestIngestNoteExceptionArc:
    """Exercise the except-branch of ingest_note (raises → 500)."""

    @pytest.mark.anyio
    async def test_ingest_note_raises_http_500_on_runtime_error(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """When graph_rag.ingest_note raises RuntimeError → HTTP 500."""
        note = _make_note()

        mock_gr = MagicMock()
        mock_gr.__bool__ = MagicMock(return_value=True)
        mock_gr.ingest_note = AsyncMock(side_effect=RuntimeError("boom"))

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

    @pytest.mark.anyio
    async def test_ingest_note_raises_http_500_on_value_error(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """When graph_rag.ingest_note raises ValueError → HTTP 500."""
        note = _make_note(note_id="note-arc-2", title="Arc Note 2")

        mock_gr = MagicMock()
        mock_gr.__bool__ = MagicMock(return_value=True)
        mock_gr.ingest_note = AsyncMock(side_effect=ValueError("bad value"))

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
# Additional arc tests — providers, chat fallback, streaming
# ---------------------------------------------------------------------------

class TestProvidersArc:
    """GET /ai/providers — various provider states."""

    @pytest.mark.anyio
    async def test_providers_when_none_available(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        mock_provider = MagicMock()
        mock_provider.is_available = False

        with patch("gnosis.routers.ai.llm_provider", mock_provider):
            resp = await async_client.get("/api/v1/ai/providers", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False

    @pytest.mark.anyio
    async def test_providers_with_ollama_available(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        mock_provider = MagicMock()
        mock_provider.is_available = True
        mock_provider.active_provider = "ollama"
        mock_provider.active_model = "llama3"
        mock_provider._available = ["ollama"]

        import httpx as _httpx

        async def _fake_get(url, **_kw):
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {"models": [{"name": "llama3"}]}
            return r

        with (
            patch("gnosis.routers.ai.llm_provider", mock_provider),
            patch.object(_httpx.AsyncClient, "get", AsyncMock(side_effect=_fake_get)),
        ):
            resp = await async_client.get("/api/v1/ai/providers", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "ollama"

    @pytest.mark.anyio
    async def test_providers_ollama_tag_fetch_fails(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Ollama tag-fetch throws → falls back to active model name."""
        mock_provider = MagicMock()
        mock_provider.is_available = True
        mock_provider.active_provider = "ollama"
        mock_provider.active_model = "llama3"
        mock_provider._available = ["ollama"]

        import httpx as _httpx

        with (
            patch("gnosis.routers.ai.llm_provider", mock_provider),
            patch.object(
                _httpx.AsyncClient, "get",
                AsyncMock(side_effect=Exception("network error")),
            ),
        ):
            resp = await async_client.get("/api/v1/ai/providers", headers=auth_headers)
        assert resp.status_code == 200


class TestChatArc:
    """POST /ai/chat — fallback paths."""

    @pytest.mark.anyio
    async def test_chat_no_provider_raises_503(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        mock_gr = AsyncMock()
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_provider = MagicMock()
        mock_provider.is_available = False

        with (
            patch("gnosis.routers.ai.graph_rag", mock_gr),
            patch("gnosis.routers.ai.llm_provider", mock_provider),
        ):
            resp = await async_client.post(
                "/api/v1/ai/chat",
                json={"message": "hello", "mode": "hybrid"},
                headers=auth_headers,
            )
        assert resp.status_code == 503

    @pytest.mark.anyio
    async def test_chat_uses_qdrant_when_lightrag_unavailable(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        mock_gr = AsyncMock()
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_provider = MagicMock()
        mock_provider.is_available = True

        with (
            patch("gnosis.routers.ai.graph_rag", mock_gr),
            patch("gnosis.routers.ai.llm_provider", mock_provider),
            patch(
                "gnosis.routers.ai._qdrant_rag_complete",
                AsyncMock(return_value="qdrant answer"),
            ),
        ):
            resp = await async_client.post(
                "/api/v1/ai/chat",
                json={"message": "hello", "mode": "hybrid"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["answer"] == "qdrant answer"


class TestStreamArc:
    """GET /ai/stream/chat — SSE paths."""

    @pytest.mark.anyio
    async def test_stream_no_provider(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        mock_gr = AsyncMock()
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_provider = MagicMock()
        mock_provider.is_available = False

        with (
            patch("gnosis.routers.ai.graph_rag", mock_gr),
            patch("gnosis.routers.ai.llm_provider", mock_provider),
        ):
            resp = await async_client.get(
                "/api/v1/ai/stream/chat",
                params={"message": "hello"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.text
        assert "error" in body or "DONE" in body

    @pytest.mark.anyio
    async def test_stream_qdrant_path(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        async def _tokens():
            for t in ["tok1", "tok2"]:
                yield t

        mock_gr = AsyncMock()
        mock_gr.is_available = AsyncMock(return_value=False)
        mock_provider = MagicMock()
        mock_provider.is_available = True

        with (
            patch("gnosis.routers.ai.graph_rag", mock_gr),
            patch("gnosis.routers.ai.llm_provider", mock_provider),
            patch("gnosis.routers.ai._qdrant_rag_stream", return_value=_tokens()),
        ):
            resp = await async_client.get(
                "/api/v1/ai/stream/chat",
                params={"message": "hello"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
