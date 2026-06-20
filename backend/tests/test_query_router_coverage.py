"""Coverage tests for gnosis/routers/query.py."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from gnosis.core.auth import get_current_user, get_vault_owner_ids
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.query import router


def _user(): return User(id=1,email="u@t.com",hashed_password="x",is_active=True,is_superuser=False)

def _make_db():
    db = AsyncMock(spec=AsyncSession)
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    res.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=res)
    db.add = MagicMock(); db.flush = AsyncMock()
    db.commit = AsyncMock(); db.delete = AsyncMock(); db.refresh = AsyncMock()
    return db


def _make_app(db=None, user=None):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    _db = db or _make_db(); _user = user or _user()
    async def _get_db(): yield _db
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_vault_owner_ids] = lambda: {1}
    return app


def test_run_query_returns_200():
    fake = {"rows": [{"id":"1","title":"N"}], "columns":["id","title"], "row_count":1}
    with patch("gnosis.routers.query.parse_query") as mp, \
         patch("gnosis.routers.query.execute_query", new_callable=AsyncMock, return_value=fake):
        mp.return_value = MagicMock()
        resp = TestClient(_make_app()).post("/api/v1/query/run",
            json={"gql":"SELECT title FROM notes","owner_ids":[1]})
    assert resp.status_code == 200


def test_list_saved_returns_empty_list():
    resp = TestClient(_make_app()).get("/api/v1/query/saved")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_saved_not_found_returns_404():
    resp = TestClient(_make_app()).get("/api/v1/query/saved/999")
    assert resp.status_code == 404


def test_delete_saved_not_found_returns_404():
    resp = TestClient(_make_app()).delete("/api/v1/query/saved/999")
    assert resp.status_code in (404, 403)


def test_run_query_parse_error_returns_error():
    with patch("gnosis.routers.query.parse_query", side_effect=Exception("bad")):
        resp = TestClient(_make_app()).post("/api/v1/query/run",
            json={"gql":"INVALID","owner_ids":[1]})
    assert resp.status_code in (400, 422, 500)
