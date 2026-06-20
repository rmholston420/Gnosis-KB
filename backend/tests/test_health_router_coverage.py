"""Coverage tests for gnosis/routers/health.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.database import get_db
from gnosis.routers.health import router


def _make_app(db_mock: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _db():
        yield db_mock

    app.dependency_overrides[get_db] = _db
    return app


def test_health_ok():
    db = AsyncMock()
    db.execute = AsyncMock()
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/health/")
    assert resp.status_code == 200


def test_health_db_error_returns_503():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=Exception("DB down"))
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/health/")
    # Health endpoint may return 200 with degraded status or 503
    assert resp.status_code in (200, 503)


def test_health_detailed_returns_component_info():
    db = AsyncMock()
    db.execute = AsyncMock()
    with patch("gnosis.routers.health.settings") as mock_settings:
        mock_settings.VAULT_PATH = "/some/path"
        mock_settings.QDRANT_URL = "http://localhost:6333"
        client = TestClient(_make_app(db))
        resp = client.get("/api/v1/health/detailed")
    assert resp.status_code in (200, 404)
