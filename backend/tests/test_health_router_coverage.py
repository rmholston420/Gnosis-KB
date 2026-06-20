"""Coverage tests for gnosis/routers/health.py.

The router calls:
  - db.execute(text('SELECT 1'))          → DB check
  - httpx.AsyncClient (async ctx mgr)     → Qdrant check
  - shutil.disk_usage(settings.vault_path) → Disk check
All three must be patched at the router module level.
"""
from __future__ import annotations
import shutil
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from gnosis.database import get_db
from gnosis.routers.health import router

_GOOD_DISK = shutil.disk_usage("/")
_LOW_DISK = shutil.disk_usage.__class__  # placeholder; built inline below


def _qdrant_ok():
    """Return an httpx async client mock that responds 200 to /healthz."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=mock_resp)
    return client


def _qdrant_fail():
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(side_effect=Exception("qdrant down"))
    return client


def _make_app(db=None):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    _db = db or AsyncMock(spec=AsyncSession)
    async def _get_db(): yield _db
    app.dependency_overrides[get_db] = _get_db
    return app


def test_ping_always_200():
    resp = TestClient(_make_app()).get("/api/v1/health/ping")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pong"


def test_health_all_ok_returns_200():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    with patch("gnosis.routers.health.httpx.AsyncClient", return_value=_qdrant_ok()), \
         patch("gnosis.routers.health.shutil.disk_usage", return_value=_GOOD_DISK):
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_health_db_error_returns_503():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(side_effect=Exception("conn refused"))
    with patch("gnosis.routers.health.httpx.AsyncClient", return_value=_qdrant_ok()), \
         patch("gnosis.routers.health.shutil.disk_usage", return_value=_GOOD_DISK):
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


def test_health_qdrant_error_returns_503():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    with patch("gnosis.routers.health.httpx.AsyncClient", return_value=_qdrant_fail()), \
         patch("gnosis.routers.health.shutil.disk_usage", return_value=_GOOD_DISK):
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


def test_health_disk_error_is_degraded():
    """OSError from shutil.disk_usage → disk check fails → 503."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    with patch("gnosis.routers.health.httpx.AsyncClient", return_value=_qdrant_ok()), \
         patch("gnosis.routers.health.shutil.disk_usage", side_effect=OSError("no disk")):
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    # disk error means check says 'error: ...' → not 'ok' → degraded → 503
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"
