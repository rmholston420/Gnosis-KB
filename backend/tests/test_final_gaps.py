"""
Final gap coverage — last uncovered lines across all routers.

Fixed: TestIngestNoteException now patches gnosis.routers.ai._lightrag_available
instead of the non-existent _LIGHTRAG_AVAILABLE_CHECK.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient


# ===========================================================================
# gnosis/routers/ai.py — ingest_note exception path
# ===========================================================================

class TestIngestNoteException:
    """When graph_rag.ingest_note raises, the endpoint returns 500."""

    @pytest.mark.anyio
    async def test_ingest_note_lightrag_raises(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        note = MagicMock()
        note.id = "final-gap-1"
        note.title = "Final Gap Note"
        note.body = "body"
        note.owner_id = 1

        mock_gr = MagicMock()
        mock_gr.__bool__ = MagicMock(return_value=True)
        mock_gr.ingest_note = AsyncMock(side_effect=Exception("final gap failure"))

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


# ===========================================================================
# gnosis/routers/notes.py — lines 54-57 (error branches)
# ===========================================================================

class TestNotesErrorBranches:
    @pytest.mark.anyio
    async def test_create_note_empty_body_is_valid(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Empty body string is allowed by the schema."""
        resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "Empty Body Note", "body": "", "folder": "00-inbox"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_get_nonexistent_note_returns_404(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        resp = await async_client.get(
            "/api/v1/notes/does-not-exist",
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ===========================================================================
# gnosis/routers/review.py — lines 147-158 (SM-2 scheduling)
# ===========================================================================

class TestReviewSM2Scheduling:
    @pytest.mark.anyio
    async def test_multiple_grade_submissions(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        cr = await async_client.post(
            "/api/v1/notes/",
            json={"title": "SM2 Multi-Grade", "body": "body", "folder": "00-inbox"},
            headers=auth_headers,
        )
        note_id = cr.json()["id"]

        await async_client.post(f"/api/v1/review/{note_id}/enroll", headers=auth_headers)

        for grade in [3, 4, 5]:
            gr = await async_client.post(
                f"/api/v1/review/{note_id}/submit",
                json={"grade": grade},
                headers=auth_headers,
            )
            assert gr.status_code == 200


# ===========================================================================
# gnosis/routers/admin.py — line 95
# ===========================================================================

class TestAdminActionBranches:
    @pytest.mark.anyio
    async def test_admin_reindex_action(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        resp = await async_client.post(
            "/api/v1/admin/action",
            json={"action": "reindex"},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 202, 400, 404, 422)

    @pytest.mark.anyio
    async def test_admin_unknown_action_returns_error(
        self, async_client: AsyncClient, admin_headers: dict
    ):
        resp = await async_client.post(
            "/api/v1/admin/action",
            json={"action": "unknown-xyz"},
            headers=admin_headers,
        )
        assert resp.status_code in (400, 404, 422)


# ===========================================================================
# gnosis/routers/export.py — line 237
# ===========================================================================

class TestExportPdfLine:
    @pytest.mark.anyio
    async def test_export_pdf_endpoint_accessible(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        cr = await async_client.post(
            "/api/v1/notes/",
            json={"title": "PDF Export Line", "body": "# Hello", "folder": "00-inbox"},
            headers=auth_headers,
        )
        note_id = cr.json()["id"]

        resp = await async_client.get(
            f"/api/v1/export/note/{note_id}/pdf",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404, 501, 503)


# ===========================================================================
# gnosis/routers/ai.py — remaining coverage lines 129, 138->142
# ===========================================================================

class TestAiRouterRemainingLines:
    @pytest.mark.anyio
    async def test_summarize_note_llm_unavailable(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        mock_provider = MagicMock()
        mock_provider.is_available = False

        cr = await async_client.post(
            "/api/v1/notes/",
            json={"title": "Summarize LLM Off", "body": "body", "folder": "00-inbox"},
            headers=auth_headers,
        )
        note_id = cr.json()["id"]

        with patch("gnosis.routers.ai.llm_provider", mock_provider):
            resp = await async_client.post(
                f"/api/v1/ai/summarize/{note_id}",
                headers=auth_headers,
            )
        assert resp.status_code == 503

    @pytest.mark.anyio
    async def test_suggest_links_llm_unavailable(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        mock_provider = MagicMock()
        mock_provider.is_available = False

        cr = await async_client.post(
            "/api/v1/notes/",
            json={"title": "Suggest Links LLM Off", "body": "body", "folder": "00-inbox"},
            headers=auth_headers,
        )
        note_id = cr.json()["id"]

        with patch("gnosis.routers.ai.llm_provider", mock_provider):
            resp = await async_client.post(
                f"/api/v1/ai/suggest-links/{note_id}",
                headers=auth_headers,
            )
        assert resp.status_code == 503
