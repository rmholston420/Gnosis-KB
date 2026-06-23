"""Coverage tests for gnosis/routers/tags.py.

The tags router uses get_current_user (not require_user), so we must override
the correct dependency.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import get_current_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.tags import router


def _make_app(db_mock: AsyncMock, user_id: int = 1) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    user = User(
        id=user_id,
        email="u@test.com",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
    )

    async def _db():
        yield db_mock

    async def _user():
        return user

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    return app


def test_list_tags_returns_200():
    """GET /tags/ returns 200 and a list."""
    db = AsyncMock()

    # SQLAlchemy chained: db.execute() -> .mappings() -> .all()
    mock_rows = MagicMock()
    mock_rows.mappings.return_value.all.return_value = [
        {"tag": "python", "count": 3},
        {"tag": "testing", "count": 1},
    ]
    db.execute.return_value = mock_rows

    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/tags/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_list_tags_empty_returns_200():
    """GET /tags/ returns 200 and empty list when no tags exist."""
    db = AsyncMock()
    mock_rows = MagicMock()
    mock_rows.mappings.return_value.all.return_value = []
    db.execute.return_value = mock_rows

    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/tags/")
    assert resp.status_code == 200
    assert resp.json() == []
