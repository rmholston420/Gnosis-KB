"""Precision coverage for specific missing lines.

All tests here are fully isolated where possible.

Targets:
- database.py line 66  – _AsyncSessionLocalProxy.__aexit__ delegation
- config.py line 82    – Settings.database_url_sync computed field
- export.py line 237   – WeasyPrint ImportError → 501 path
- review.py lines 189-190 – unenroll_note DELETE endpoint
- ai.py fast-return    – ingest_note when LightRAG unavailable
- ai.py error path     – ingest_note when LightRAG raises
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# database.py line 66 – _AsyncSessionLocalProxy.__aexit__
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proxy_aexit_is_delegated():
    """__aexit__ must forward to the underlying factory's context manager."""
    from gnosis.database import _AsyncSessionLocalProxy

    mock_session = AsyncMock()
    factory_cm = AsyncMock()
    factory_cm.__aenter__ = AsyncMock(return_value=mock_session)
    factory_cm.__aexit__ = AsyncMock(return_value=False)

    proxy = _AsyncSessionLocalProxy()
    with patch("gnosis.database.get_session_factory", return_value=factory_cm):
        session = await proxy.__aenter__()
        assert session is mock_session
        result = await proxy.__aexit__(None, None, None)
    assert result is False
    factory_cm.__aexit__.assert_awaited_once_with(None, None, None)


@pytest.mark.asyncio
async def test_proxy_aexit_propagates_exc_info():
    """__aexit__ with exc info is forwarded unchanged."""
    from gnosis.database import _AsyncSessionLocalProxy

    factory_cm = AsyncMock()
    factory_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    factory_cm.__aexit__ = AsyncMock(return_value=True)  # suppress

    exc = ValueError("boom")
    proxy = _AsyncSessionLocalProxy()
    with patch("gnosis.database.get_session_factory", return_value=factory_cm):
        await proxy.__aenter__()
        result = await proxy.__aexit__(type(exc), exc, exc.__traceback__)
    assert result is True
    factory_cm.__aexit__.assert_awaited_once_with(type(exc), exc, exc.__traceback__)


# ---------------------------------------------------------------------------
# config.py line 82 – Settings.database_url_sync computed field
# ---------------------------------------------------------------------------


def test_database_url_sync_returns_database_url():
    """database_url_sync computed field returns the raw database_url value."""
    from gnosis.config import settings

    url = settings.database_url_sync
    assert isinstance(url, str)
    assert url == settings.database_url


def test_database_url_sync_is_a_string_url():
    """database_url_sync is a non-empty string beginning with sqlite or postgresql."""
    from gnosis.config import settings

    url = settings.database_url_sync
    assert len(url) > 0
    assert url.startswith(("sqlite", "postgresql"))


# ---------------------------------------------------------------------------
# export.py line 237 – WeasyPrint ImportError → 501
#
# The `from weasyprint import HTML` is inside the endpoint body (lazy import),
# so we block it via builtins.__import__ at request dispatch time.
# Correct endpoint: GET /api/v1/export/note/{note_id}.pdf
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pdf_export_returns_501_when_weasyprint_missing(async_client):
    """GET /api/v1/export/note/{id}.pdf returns 501 when weasyprint is absent."""
    resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": "PDF test note", "body": "pdf body"},
    )
    assert resp.status_code == 201
    note_id = resp.json()["id"]

    _saved_wp = sys.modules.pop("weasyprint", None)

    import builtins
    _real_import = builtins.__import__

    def _blocking_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise ImportError("weasyprint not installed")
        return _real_import(name, *args, **kwargs)

    try:
        with (
            patch("gnosis.routers.export.settings") as mock_settings,
            patch("builtins.__import__", side_effect=_blocking_import),
        ):
            mock_settings.enable_pdf_export = True
            resp2 = await async_client.get(f"/api/v1/export/note/{note_id}.pdf")
    finally:
        if _saved_wp is not None:
            sys.modules["weasyprint"] = _saved_wp

    assert resp2.status_code == 501


# ---------------------------------------------------------------------------
# review.py lines 189-190 – unenroll_note DELETE
#
# ReviewEnroll schema has two required fields: note_id (str) AND due_today (bool).
# Missing note_id returns 422, which then causes the enroll assert to fail
# before the DELETE is ever reached.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_unenroll_note(async_client):
    """Create a note, enroll it (with full ReviewEnroll body), then unenroll."""
    # 1. Create note
    resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": "Review unenroll note", "body": "body"},
    )
    assert resp.status_code == 201
    note_id = resp.json()["id"]

    # 2. Enroll – ReviewEnroll requires note_id AND due_today
    enroll = await async_client.post(
        f"/api/v1/review/{note_id}/enroll",
        json={"note_id": note_id, "due_today": True},
    )
    assert enroll.status_code in (200, 201), (
        f"Enroll failed: {enroll.status_code} {enroll.text}"
    )

    # 3. Unenroll – DELETE /api/v1/review/{note_id} → 204
    unenroll = await async_client.delete(f"/api/v1/review/{note_id}")
    assert unenroll.status_code in (200, 204), (
        f"Unenroll failed: {unenroll.status_code} {unenroll.text}"
    )


# ---------------------------------------------------------------------------
# ai.py – ingest_note paths
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
