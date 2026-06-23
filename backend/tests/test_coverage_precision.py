"""Precision micro-tests to close the last handful of coverage gaps.

Files / lines addressed
-----------------------
  gnosis/database.py      line  66  _AsyncSessionLocalProxy.__aexit__
  gnosis/config.py        line  82  Settings.database_url_sync computed field
  gnosis/routers/export.py line 237 WeasyPrint ImportError → 501
  gnosis/routers/review.py lines 189-190  unenroll_note db.delete + commit
  gnosis/routers/ai.py    ingest_note LightRAG-unavailable fast-return

Design notes
------------
* Every test is self-contained: no shared state, no ordering dependency.
* Patches target the module where the name is *used*, not where it is defined,
  so coverage's branch tracker registers the arc as taken.
* Database proxy tests use the existing AsyncSessionLocal singleton (already
  bound to the test-suite engine by conftest) — never construct a new proxy
  whose factory would be uninitialised.
"""
from __future__ import annotations

import builtins
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# database.py  line 66 — _AsyncSessionLocalProxy.__aexit__
# ===========================================================================

class TestAsyncSessionLocalProxyAexit:
    """Exercise the __aexit__ delegation path on _AsyncSessionLocalProxy.

    Line 66 is `return get_session_factory().__aexit__(*args)` inside
    _AsyncSessionLocalProxy.__aexit__.  The simplest way to hit it is to use
    the singleton AsyncSessionLocal as an async context manager — `async with`
    always calls both __aenter__ and __aexit__ even if the body succeeds.
    """

    @pytest.mark.asyncio
    async def test_proxy_as_async_context_manager_exercises_aexit(self):
        """async with AsyncSessionLocal() calls __aenter__ then __aexit__ (line 66)."""
        from gnosis.database import AsyncSessionLocal

        # AsyncSessionLocal() returns an AsyncSession context manager.
        # The `async with` block guarantees __aexit__ is called on normal exit.
        async with AsyncSessionLocal() as session:
            assert session is not None

    @pytest.mark.asyncio
    async def test_proxy_aexit_called_explicitly(self):
        """Call __aenter__ then __aexit__ directly on the proxy singleton."""
        from gnosis.database import AsyncSessionLocal

        # __aenter__ returns the session; __aexit__ must close it (line 66).
        session = await AsyncSessionLocal.__aenter__()
        assert session is not None
        # __aexit__(exc_type, exc_val, exc_tb) — pass all-None for clean exit
        await AsyncSessionLocal.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_proxy_call_returns_usable_session(self):
        """AsyncSessionLocal() (via __call__) returns an AsyncSession CM."""
        from gnosis.database import AsyncSessionLocal

        cm = AsyncSessionLocal()
        async with cm as session:
            assert session is not None


# ===========================================================================
# config.py  line 82 — Settings.database_url_sync computed field
# ===========================================================================

class TestSettingsDatabaseUrlSync:
    """Access the computed field so line 82 registers as covered."""

    def test_database_url_sync_equals_database_url(self):
        """database_url_sync is a passthrough of database_url (sync Alembic shim)."""
        from gnosis.config import get_settings

        s = get_settings()
        assert s.database_url_sync == s.database_url

    def test_database_url_sync_is_string(self):
        from gnosis.config import Settings

        s = Settings(database_url="sqlite+aiosqlite:///./test_sync.db")
        assert isinstance(s.database_url_sync, str)
        assert "sqlite" in s.database_url_sync


# ===========================================================================
# export.py  line 237 — WeasyPrint ImportError → 501
# ===========================================================================

class TestExportNotePdfWeasyPrintMissing:
    """export.py line 237: ImportError from weasyprint → HTTP 501."""

    @pytest.mark.asyncio
    async def test_pdf_export_weasyprint_not_installed_returns_501(self, client, vault_dir):
        """When enable_pdf_export=True but weasyprint is not importable → 501."""
        cr = await client.post(
            "/api/v1/notes/",
            json={
                "title": "PDF Export WeasyPrint Test Note",
                "body": "Content for PDF export test.",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert cr.status_code == 201
        note_id = cr.json()["id"]

        mock_settings = MagicMock()
        mock_settings.enable_pdf_export = True

        original_import = builtins.__import__

        def _broken_import(name, *args, **kwargs):
            if name == "weasyprint":
                raise ImportError("weasyprint not installed")
            return original_import(name, *args, **kwargs)

        with (
            patch("gnosis.routers.export.settings", mock_settings),
            patch.object(builtins, "__import__", side_effect=_broken_import),
        ):
            resp = await client.get(f"/api/v1/export/note/{note_id}.pdf")

        assert resp.status_code == 501
        assert "weasyprint" in resp.json()["detail"].lower()


# ===========================================================================
# review.py  lines 189-190 — unenroll_note: db.delete + commit
# ===========================================================================

class TestReviewUnenroll:
    """review.py DELETE /{note_id}: db.delete(card) + db.commit()."""

    @pytest.mark.asyncio
    async def test_unenroll_enrolled_note_returns_204(self, client, vault_dir):
        """Enroll a note then DELETE it — exercises lines 189-190."""
        cr = await client.post(
            "/api/v1/notes/",
            json={
                "title": "Unenroll Coverage Target Note",
                "body": "Body for unenroll test.",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert cr.status_code == 201
        note_id = cr.json()["id"]

        er = await client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"note_id": note_id, "due_today": False},
        )
        assert er.status_code == 201

        # Unenroll — exercises db.delete(card) + db.commit() (lines 189-190)
        dr = await client.delete(f"/api/v1/review/{note_id}")
        assert dr.status_code == 204

    @pytest.mark.asyncio
    async def test_unenroll_not_enrolled_note_returns_404(self, client, vault_dir):
        """Trying to unenroll a note that was never enrolled → 404."""
        cr = await client.post(
            "/api/v1/notes/",
            json={
                "title": "Unenroll 404 Coverage Note",
                "body": "Body.",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert cr.status_code == 201
        note_id = cr.json()["id"]

        dr = await client.delete(f"/api/v1/review/{note_id}")
        assert dr.status_code == 404


# ===========================================================================
# ai.py  — ingest_note LightRAG-unavailable fast-return + error path
# ===========================================================================

_AI = "gnosis.routers.ai"


class TestAiIngestNoteLightragUnavailable:
    """ingest_note: LightRAG absent → 200 graph_indexed=False; ingest error → 500."""

    @pytest.mark.asyncio
    async def test_ingest_note_lightrag_unavailable_returns_not_indexed(self, client, vault_dir):
        """_LIGHTRAG_AVAILABLE_CHECK() == False → fast-return with graph_indexed=False."""
        cr = await client.post(
            "/api/v1/notes/",
            json={
                "title": "LightRAG Ingest Coverage Note",
                "body": "Content for LightRAG ingest test.",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert cr.status_code == 201
        note_id = cr.json()["id"]

        with patch(f"{_AI}._LIGHTRAG_AVAILABLE_CHECK", return_value=False):
            resp = await client.post(f"/api/v1/ai/ingest-note/{note_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["graph_indexed"] is False
        assert "LightRAG" in data["message"]

    @pytest.mark.asyncio
    async def test_ingest_note_lightrag_available_but_ingest_fails_returns_500(self, client, vault_dir):
        """LightRAG available but ingest_note raises → HTTP 500."""
        cr = await client.post(
            "/api/v1/notes/",
            json={
                "title": "LightRAG Ingest Error Note",
                "body": "Content for ingest error test.",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert cr.status_code == 201
        note_id = cr.json()["id"]

        mock_graph = MagicMock()
        mock_graph.is_available = AsyncMock(return_value=True)
        mock_graph.ingest_note = AsyncMock(side_effect=RuntimeError("ingest boom"))

        with (
            patch(f"{_AI}.graph_rag", mock_graph),
            patch(f"{_AI}._LIGHTRAG_AVAILABLE_CHECK", return_value=True),
        ):
            resp = await client.post(f"/api/v1/ai/ingest-note/{note_id}")

        assert resp.status_code == 500
        assert "ingest boom" in resp.json()["detail"]
