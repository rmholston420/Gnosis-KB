"""Coverage tests for gnosis/routers/tags.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.tags import router


def _make_app(db_mock: AsyncMock, user_id: int = 1) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    user = User(id=user_id, email="u@test.com", hashed_password="x")

    async def _db():
        yield db_mock

    async def _user():
        return user

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[require_user] = _user
    return app


def test_list_tags_returns_200():
    db = AsyncMock()
    r = MagicMock()
    r.all.return_value = [("python", 5), ("ml", 2)]
    db.execute.return_value = r
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/tags/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_list_tags_empty():
    db = AsyncMock()
    r = MagicMock()
    r.all.return_value = []
    db.execute.return_value = r
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/tags/")
    assert resp.status_code == 200
    assert resp.json() == []
