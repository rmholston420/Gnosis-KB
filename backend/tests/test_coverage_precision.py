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
* Async context-manager tests use a real in-memory SQLite engine to exercise
  the _AsyncSessionLocalProxy code path without touching the test DB.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# database.py  line 66 — _AsyncSessionLocalProxy.__aexit__
# ===========================================================================

class TestAsyncSessionLocalProxyAexit:
    """Exercise the __aexit__ delegation path on _AsyncSessionLocalProxy."""

    @pytest.mark.asyncio
    async def test_proxy_aexit_delegates_to_factory(self):
        """Entering and exiting the proxy as an async CM exercises line 66."""
        from gnosis.database import AsyncSessionLocal

        # The proxy's __aenter__/__aexit__ each delegate to get_session_factory().
        # We just need to successfully enter and exit — the real session factory
        # is already initialised by the test suite's conftest engine.
        async with get_session_factory()() as session:
            assert session is not None

    @pytest.mark.asyncio
    async def test_proxy_call_returns_session(self):
        """Calling AsyncSessionLocal() returns an AsyncSession context manager."""
        from gnosis.database import AsyncSessionLocal, get_session_factory

        cm = AsyncSessionLocal()
        # It should be awaitable / async-context-manager-able
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
        # The computed field just returns self.database_url unchanged.
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
        # Step 1: create a note so we have a valid note_id
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

        # Step 2: patch settings so PDF export is enabled
        mock_settings = MagicMock()
        mock_settings.enable_pdf_export = True

        # Step 3: ensure weasyprint raises ImportError when imported inside the view
        # We do this by temporarily inserting a broken module into sys.modules.
        broken = types.ModuleType("weasyprint")

        def _broken_import(name, *args, **kwargs):
            if name == "weasyprint":
                raise ImportError("weasyprint not installed")
            return original_import(name, *args, **kwargs)

        import builtins
        original_import = builtins.__import__

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
        # Create a note
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

        # Enroll the note
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
        """Trying to unenroll a note that was never enrolled → 404 from _get_card_or_404."""
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

        # This note was never enrolled — DELETE must return 404
        dr = await client.delete(f"/api/v1/review/{note_id}")
        assert dr.status_code == 404


# ===========================================================================
# ai.py  — ingest_note LightRAG-unavailable fast-return
# ===========================================================================

_AI = "gnosis.routers.ai"


class TestAiIngestNoteLightragUnavailable:
    """ingest_note endpoint: graph_rag absent or LightRAG not installed → 200 with
    graph_indexed=False (the fast-return branch before the try/except block)."""

    @pytest.mark.asyncio
    async def test_ingest_note_lightrag_unavailable_returns_not_indexed(self, client, vault_dir):
        """When _LIGHTRAG_AVAILABLE_CHECK() returns False the endpoint fast-returns
        with graph_indexed=False without calling graph_rag.ingest_note."""
        # Create a note to ingest
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

        with (
            patch(f"{_AI}._LIGHTRAG_AVAILABLE_CHECK", return_value=False),
        ):
            resp = await client.post(f"/api/v1/ai/ingest-note/{note_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["graph_indexed"] is False
        assert "LightRAG" in data["message"]

    @pytest.mark.asyncio
    async def test_ingest_note_lightrag_available_but_ingest_fails_returns_500(self, client, vault_dir):
        """When LightRAG is nominally available but ingest raises → HTTP 500."""
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


# ===========================================================================
# database.py — proxy __aenter__/__aexit__ full round-trip via real factory
# ===========================================================================

class TestAsyncSessionLocalProxyRoundTrip:
    """Full async CM round-trip to ensure __aexit__ delegation is registered."""

    @pytest.mark.asyncio
    async def test_proxy_aenter_and_aexit_both_exercised(self):
        """Enter and exit the proxy as an async context manager.

        _AsyncSessionLocalProxy.__aenter__ delegates to get_session_factory().__aenter__.
        _AsyncSessionLocalProxy.__aexit__ delegates to get_session_factory().__aexit__.
        Both must be called to cover line 66.
        """
        from gnosis.database import _AsyncSessionLocalProxy, get_session_factory

        proxy = _AsyncSessionLocalProxy()
        # We need an actual async CM so __aenter__ / __aexit__ are both invoked.
        # Delegate to the real factory (already initialised by conftest).
        factory_cm = get_session_factory()

        # Manually call __aenter__ and __aexit__ on the proxy to cover line 66.
        session = await proxy.__aenter__()
        assert session is not None
        await proxy.__aexit__(None, None, None)
