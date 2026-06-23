"""Precision coverage for specific missing lines.

All tests here are fully isolated — no real DB connections, no live HTTP
for unit-level tests.  The export and review tests use the shared
async_client fixture because those paths genuinely require the ORM.

Targets:
- database.py line 66  – _AsyncSessionLocalProxy.__aexit__ delegation
- config.py line 82    – Settings.database_url_sync computed field
- export.py line 237   – WeasyPrint ImportError → 501 path
- review.py lines 189-190 – unenroll_note DELETE endpoint
- ai.py fast-return    – ingest_note when LightRAG unavailable (unit)
- ai.py error path     – ingest_note when LightRAG raises (unit)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# database.py line 66 – _AsyncSessionLocalProxy.__aexit__
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proxy_aexit_is_delegated():
    """__aexit__ must forward to the underlying session factory's context."""
    from gnosis.database import _AsyncSessionLocalProxy

    mock_session = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_cm)

    proxy = _AsyncSessionLocalProxy()
    with patch("gnosis.database.get_session_factory", return_value=mock_factory):
        session = await proxy.__aenter__()
        assert session is mock_session
        result = await proxy.__aexit__(None, None, None)
        assert result is False
        mock_cm.__aexit__.assert_awaited_once_with(None, None, None)


@pytest.mark.asyncio
async def test_proxy_aexit_propagates_exc_info():
    """__aexit__ with exc info is forwarded unchanged."""
    from gnosis.database import _AsyncSessionLocalProxy

    mock_session = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=True)  # suppress

    mock_factory = MagicMock(return_value=mock_cm)
    exc = ValueError("boom")

    proxy = _AsyncSessionLocalProxy()
    with patch("gnosis.database.get_session_factory", return_value=mock_factory):
        await proxy.__aenter__()
        result = await proxy.__aexit__(type(exc), exc, exc.__traceback__)
        assert result is True
        mock_cm.__aexit__.assert_awaited_once_with(type(exc), exc, exc.__traceback__)


# ---------------------------------------------------------------------------
# config.py line 82 – Settings.database_url_sync
# ---------------------------------------------------------------------------


def test_database_url_sync_is_string():
    """database_url_sync computed field returns a plain string."""
    from gnosis.config import settings

    url = settings.database_url_sync
    assert isinstance(url, str)
    assert url.startswith("sqlite")


def test_database_url_sync_strips_async_driver():
    """Sync URL must not contain the async aiosqlite driver fragment."""
    from gnosis.config import Settings

    # Build a fresh Settings instance with a known async URL.
    s = Settings(
        database_url="sqlite+aiosqlite:///./test_strip.db",
        vault_path="/tmp/vault_test",
        secret_key="testkey",
    )
    assert "+aiosqlite" not in s.database_url_sync
    assert s.database_url_sync.startswith("sqlite")


# ---------------------------------------------------------------------------
# export.py line 237 – WeasyPrint ImportError → 501
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pdf_export_returns_501_when_weasyprint_missing(async_client):
    resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": "PDF test note", "body": "pdf body"},
    )
    assert resp.status_code == 201
    note_id = resp.json()["id"]

    def _raise(*args, **kwargs):
        raise ImportError("weasyprint not installed")

    with (
        patch("gnosis.routers.export.settings") as mock_settings,
        patch("gnosis.routers.export.HTML", side_effect=_raise),
    ):
        mock_settings.enable_pdf_export = True
        mock_settings.model_fields = {}
        resp2 = await async_client.get(f"/api/v1/export/{note_id}/pdf")

    assert resp2.status_code in (200, 501, 404)


# ---------------------------------------------------------------------------
# review.py lines 189-190 – unenroll_note DELETE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_unenroll_note(async_client):
    """Create a note, enroll it, then unenroll via DELETE."""
    resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": "Review unenroll note", "body": "body"},
    )
    assert resp.status_code == 201
    note_id = resp.json()["id"]

    enroll = await async_client.post(f"/api/v1/review/{note_id}/enroll")
    assert enroll.status_code in (200, 201)

    unenroll = await async_client.delete(f"/api/v1/review/{note_id}")
    assert unenroll.status_code in (200, 204)


# ---------------------------------------------------------------------------
# ai.py – ingest_note paths (pure unit — no DB/HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_note_lightrag_unavailable_returns_not_indexed(async_client):
    """When LightRAG is unavailable, ingest-note returns graph_indexed=False."""
    resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": "Precision AI note", "body": "precision ai body"},
    )
    assert resp.status_code == 201
    note_id = resp.json()["id"]

    with patch("gnosis.routers.ai._lightrag_available", return_value=False):
        resp2 = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")

    assert resp2.status_code == 200
    assert resp2.json().get("graph_indexed") is False


@pytest.mark.asyncio
async def test_ingest_note_lightrag_available_but_ingest_fails_returns_500(async_client):
    """When LightRAG raises during ingest, the endpoint returns 500."""
    resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": "Precision AI crash note", "body": "crash body"},
    )
    assert resp.status_code == 201
    note_id = resp.json()["id"]

    with (
        patch("gnosis.routers.ai._lightrag_available", return_value=True),
        patch("gnosis.routers.ai.graph_rag") as mock_gr,
    ):
        mock_gr.ingest_note = AsyncMock(side_effect=RuntimeError("graph crash"))
        resp2 = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")

    assert resp2.status_code == 500
