"""Coverage tests for gnosis/routers/health.py."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from gnosis.database import get_db
from gnosis.routers.health import router


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


def test_health_db_ok_qdrant_ok():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    mock_resp = MagicMock(); mock_resp.status_code = 200
    import shutil; disk = shutil.disk_usage("/")
    with patch("gnosis.routers.health.httpx") as mock_httpx, \
         patch("gnosis.routers.health.shutil.disk_usage", return_value=disk):
        mc = AsyncMock()
        mc.__aenter__ = AsyncMock(return_value=mc)
        mc.__aexit__ = AsyncMock(return_value=False)
        mc.get = AsyncMock(return_value=mock_resp)
        mock_httpx.AsyncClient.return_value = mc
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_health_db_error_returns_503():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(side_effect=Exception("conn refused"))
    mock_resp = MagicMock(); mock_resp.status_code = 200
    import shutil; disk = shutil.disk_usage("/")
    with patch("gnosis.routers.health.httpx") as mock_httpx, \
         patch("gnosis.routers.health.shutil.disk_usage", return_value=disk):
        mc = AsyncMock()
        mc.__aenter__ = AsyncMock(return_value=mc)
        mc.__aexit__ = AsyncMock(return_value=False)
        mc.get = AsyncMock(return_value=mock_resp)
        mock_httpx.AsyncClient.return_value = mc
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


def test_health_qdrant_error_returns_503():
    db = AsyncMock(spec=AsyncSession); db.execute = AsyncMock()
    import shutil; disk = shutil.disk_usage("/")
    with patch("gnosis.routers.health.httpx") as mock_httpx, \
         patch("gnosis.routers.health.shutil.disk_usage", return_value=disk):
        mc = AsyncMock()
        mc.__aenter__ = AsyncMock(return_value=mc)
        mc.__aexit__ = AsyncMock(return_value=False)
        mc.get = AsyncMock(side_effect=Exception("qdrant down"))
        mock_httpx.AsyncClient.return_value = mc
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    assert resp.status_code == 503


def test_health_disk_error_is_degraded():
    db = AsyncMock(spec=AsyncSession); db.execute = AsyncMock()
    mock_resp = MagicMock(); mock_resp.status_code = 200
    with patch("gnosis.routers.health.httpx") as mock_httpx, \
         patch("gnosis.routers.health.shutil.disk_usage", side_effect=OSError("no disk")):
        mc = AsyncMock()
        mc.__aenter__ = AsyncMock(return_value=mc)
        mc.__aexit__ = AsyncMock(return_value=False)
        mc.get = AsyncMock(return_value=mock_resp)
        mock_httpx.AsyncClient.return_value = mc
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    assert resp.status_code == 503
