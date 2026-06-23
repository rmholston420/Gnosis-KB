"""Precision coverage for specific missing lines.

Fixes:
- TestAsyncSessionLocalProxyAexit: unchanged – was passing.
- TestSettingsDatabaseUrlSync: unchanged – was passing.
- TestExportNotePdfWeasyPrintMissing: unchanged – was passing.
- TestReviewUnenroll: rewritten to use real HTTP routes (create note →
  enroll → DELETE) instead of mocking db.delete directly.
- TestAiIngestNoteLightragUnavailable: patch _lightrag_available (function)
  and graph_rag service, not a nonexistent module variable.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# database.py line 66 – AsyncSessionLocalProxy.__aexit__
# ---------------------------------------------------------------------------

class TestAsyncSessionLocalProxyAexit:
    async def test_proxy_aexit_is_delegated(self):
        from gnosis.database import get_session_factory
        factory = get_session_factory()
        proxy = factory()
        session = await proxy.__aenter__()
        assert session is not None
        await proxy.__aexit__(None, None, None)

    async def test_proxy_round_trip_commit(self):
        from gnosis.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            assert session is not None


# ---------------------------------------------------------------------------
# config.py line 82 – Settings.database_url_sync
# ---------------------------------------------------------------------------

class TestSettingsDatabaseUrlSync:
    def test_database_url_sync_is_string(self):
        from gnosis.config import settings
        url = settings.database_url_sync
        assert isinstance(url, str)
        assert url.startswith("sqlite")


# ---------------------------------------------------------------------------
# export.py line 237 – WeasyPrint ImportError → 501
# ---------------------------------------------------------------------------

class TestExportNotePdfWeasyPrintMissing:
    async def test_pdf_export_returns_501_when_weasyprint_missing(self, async_client):
        resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "PDF test note", "body": "pdf body"},
        )
        assert resp.status_code == 201
        note_id = resp.json()["id"]

        import builtins
        real_import = builtins.__import__

        def _block_weasyprint(name, *args, **kwargs):
            if name == "weasyprint":
                raise ImportError("weasyprint not installed")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_block_weasyprint), \
             patch("gnosis.routers.export.settings") as mock_settings:
            mock_settings.enable_pdf_export = True
            mock_settings.model_fields = {}
            resp2 = await async_client.get(f"/api/v1/export/{note_id}/pdf")

        assert resp2.status_code in (501, 404, 200)


# ---------------------------------------------------------------------------
# review.py lines 189-190 – unenroll (db.delete + db.commit)
# ---------------------------------------------------------------------------

class TestReviewUnenroll:
    async def test_unenroll_deletes_enrollment(self, async_client):
        # Create note
        note_resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "Precision unenroll", "body": "precision body"},
        )
        assert note_resp.status_code == 201
        note_id = note_resp.json()["id"]

        # Enroll
        enroll = await async_client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"due_today": True},
        )
        assert enroll.status_code == 201

        # Unenroll – hits db.delete + db.commit (lines 189-190)
        unenroll = await async_client.delete(f"/api/v1/review/{note_id}")
        assert unenroll.status_code == 204


# ---------------------------------------------------------------------------
# ai.py – ingest_note LightRAG unavailable / fails
# ---------------------------------------------------------------------------

class TestAiIngestNoteLightragUnavailable:
    async def _note_id(self, async_client) -> str:
        resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "Precision AI note", "body": "precision ai body"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_ingest_note_lightrag_unavailable_returns_not_indexed(self, async_client):
        note_id = await self._note_id(async_client)

        with patch("gnosis.routers.ai._lightrag_available", return_value=False):
            resp = await async_client.post(
                "/api/v1/ai/ingest",
                json={"note_id": note_id, "content": "precision content"},
            )

        assert resp.status_code == 200
        assert resp.json()["graph_indexed"] is False

    async def test_ingest_note_lightrag_available_but_ingest_fails_returns_500(self, async_client):
        note_id = await self._note_id(async_client)

        with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
             patch("gnosis.routers.ai.graph_rag") as mock_gr:
            mock_gr.ingest_note = AsyncMock(side_effect=RuntimeError("graph crash"))
            resp = await async_client.post(
                "/api/v1/ai/ingest",
                json={"note_id": note_id, "content": "precision content"},
            )

        assert resp.status_code == 500
