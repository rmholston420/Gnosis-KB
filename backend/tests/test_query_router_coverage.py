"""Coverage tests for gnosis/routers/query.py.

Key facts from the source:
  - QueryRun schema has field: query (str), NOT gql
  - parse_query is SYNC and raises GQLParseError (not generic Exception)
  - execute_query is async and returns (rows, ms)
  - Saved query endpoints filter by current_user.id
  - get_vault_owner_ids dependency must be overridden
"""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from gnosis.core.auth import get_current_user, get_vault_owner_ids
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.query import router
from gnosis.services.query_parser import GQLParseError, ParsedQuery


def _user():
    return User(id=1, email="u@t.com", hashed_password="x", is_active=True, is_superuser=False)


def _make_db():
    db = AsyncMock(spec=AsyncSession)
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    res.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=res)
    db.add = MagicMock(); db.flush = AsyncMock()
    db.commit = AsyncMock(); db.delete = AsyncMock(); db.refresh = AsyncMock()
    return db


def _make_app(db=None):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    _db = db or _make_db()
    async def _get_db(): yield _db
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_vault_owner_ids] = lambda: {1}
    return app


def test_run_query_returns_200():
    """POST /query/run with valid GQL → 200."""
    parsed = ParsedQuery()
    with patch("gnosis.routers.query.parse_query", return_value=parsed), \
         patch("gnosis.routers.query.execute_query",
               new_callable=AsyncMock, return_value=([], 1.0)):
        resp = TestClient(_make_app()).post(
            "/api/v1/query/run",
            json={"query": "FROM 00-inbox"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "rows" in body
    assert body["total"] == 0


def test_run_query_parse_error_returns_422():
    """GQLParseError from parse_query → 422."""
    with patch("gnosis.routers.query.parse_query",
               side_effect=GQLParseError("bad syntax")):
        resp = TestClient(_make_app()).post(
            "/api/v1/query/run",
            json={"query": "INVALID stuff here"},
        )
    assert resp.status_code == 422


def test_list_saved_returns_empty_list():
    """GET /query/saved → [] when no saved queries owned by user."""
    resp = TestClient(_make_app()).get("/api/v1/query/saved")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_saved_not_found_returns_404():
    """GET /query/saved/{id} → 404 when not found."""
    resp = TestClient(_make_app()).get("/api/v1/query/saved/999")
    assert resp.status_code == 404


def test_delete_saved_not_found_returns_404():
    """DELETE /query/saved/{id} → 404 when not found."""
    resp = TestClient(_make_app()).delete("/api/v1/query/saved/999")
    assert resp.status_code == 404


def test_run_query_missing_query_field_returns_422():
    """POST /query/run with missing required 'query' field → 422 from Pydantic."""
    resp = TestClient(_make_app()).post(
        "/api/v1/query/run",
        json={"gql": "FROM 00-inbox"},  # wrong field name
    )
    assert resp.status_code == 422
