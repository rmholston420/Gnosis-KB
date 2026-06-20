"""Coverage tests for gnosis/routers/search.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.search import router


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


def _search_result(note_id="n1", title="T", score=0.9):
    r = MagicMock()
    r.note_id = note_id
    r.title = title
    r.score = score
    r.snippet = "...snippet..."
    return r


def test_search_returns_results():
    db = AsyncMock()
    results = [_search_result()]
    with patch("gnosis.routers.search.hybrid_search", new_callable=AsyncMock,
               return_value=results):
        client = TestClient(_make_app(db))
        resp = client.get("/api/v1/search/", params={"q": "python"})
    assert resp.status_code == 200


def test_search_empty_query_returns_empty():
    db = AsyncMock()
    with patch("gnosis.routers.search.hybrid_search", new_callable=AsyncMock,
               return_value=[]):
        client = TestClient(_make_app(db))
        resp = client.get("/api/v1/search/", params={"q": ""})
    assert resp.status_code == 200


def test_search_with_limit():
    db = AsyncMock()
    with patch("gnosis.routers.search.hybrid_search", new_callable=AsyncMock,
               return_value=[_search_result()] * 3):
        client = TestClient(_make_app(db))
        resp = client.get("/api/v1/search/", params={"q": "test", "limit": 3})
    assert resp.status_code == 200
