"""Coverage tests for gnosis/routers/health.py.

httpx is imported INSIDE the endpoint function body (lazy import), so
we must patch 'httpx.AsyncClient' at the top-level module, not inside
gnosis.routers.health. shutil is imported at the top of health.py,
so it IS patchable as gnosis.routers.health.shutil.disk_usage.
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


def _qdrant_ok():
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

    async def _get_db():
        yield _db

    app.dependency_overrides[get_db] = _get_db
    return app


def test_ping_always_200():
    resp = TestClient(_make_app()).get("/api/v1/health/ping")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pong"


def test_health_all_ok_returns_200():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    # httpx is lazy-imported inside the endpoint, so patch it globally
    with (
        patch("httpx.AsyncClient", return_value=_qdrant_ok()),
        patch("gnosis.routers.health.shutil.disk_usage", return_value=_GOOD_DISK),
    ):
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_health_db_error_returns_503():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(side_effect=Exception("conn refused"))
    with (
        patch("httpx.AsyncClient", return_value=_qdrant_ok()),
        patch("gnosis.routers.health.shutil.disk_usage", return_value=_GOOD_DISK),
    ):
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


def test_health_qdrant_error_returns_503():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    with (
        patch("httpx.AsyncClient", return_value=_qdrant_fail()),
        patch("gnosis.routers.health.shutil.disk_usage", return_value=_GOOD_DISK),
    ):
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


def test_health_disk_error_is_degraded():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    with (
        patch("httpx.AsyncClient", return_value=_qdrant_ok()),
        patch("gnosis.routers.health.shutil.disk_usage", side_effect=OSError("no disk")),
    ):
        resp = TestClient(_make_app(db)).get("/api/v1/health/")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"
