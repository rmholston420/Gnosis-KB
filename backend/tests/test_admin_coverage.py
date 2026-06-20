"""Coverage tests for gnosis/routers/admin.py."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.admin import router


def _user(su=False): return User(id=1,email="a@t.com",hashed_password="x",is_active=True,is_superuser=su)

def _make_db():
    db = AsyncMock(spec=AsyncSession)
    res = MagicMock()
    res.scalars.return_value.all.return_value = []
    res.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=res)
    db.commit = AsyncMock(); db.flush = AsyncMock()
    return db


def _make_app(user=None, db=None):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    _u = user or _user(False); _db = db or _make_db()
    async def _get_db(): yield _db
    app.dependency_overrides[require_user] = lambda: _u
    app.dependency_overrides[get_db] = _get_db
    return app


def test_reindex_non_superuser_returns_403():
    resp = TestClient(_make_app(user=_user(False))).post("/api/v1/admin/reindex")
    assert resp.status_code == 403


def test_reindex_superuser_no_notes_returns_200():
    db = _make_db()
    results = iter([
        MagicMock(**{"scalar_one_or_none.return_value": _user(True)}),
        MagicMock(**{"scalars.return_value.all.return_value": []}),
    ])
    db.execute = AsyncMock(side_effect=results)
    resp = TestClient(_make_app(user=_user(True), db=db)).post("/api/v1/admin/reindex")
    assert resp.status_code == 200
