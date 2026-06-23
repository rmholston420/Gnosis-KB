"""Coverage tests for gnosis/routers/admin.py.

The /admin/reindex guard is: ``if current_user.id != 1 → 403``.
Superuser flag is NOT checked.  Tests reflect this.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.admin import router


# id=1 → admin (passes guard); id=2 → non-admin (fails guard)
def _admin_user():
    return User(id=1, email="admin@t.com", hashed_password="x", is_active=True, is_superuser=False)


def _regular_user():
    return User(id=2, email="user@t.com", hashed_password="x", is_active=True, is_superuser=False)


def _make_db():
    db = AsyncMock(spec=AsyncSession)
    res = MagicMock()
    res.scalars.return_value.all.return_value = []
    res.scalars.return_value.first.return_value = None
    res.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=res)
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    return db


def _make_app(user=None, db=None):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    _u = user or _regular_user()
    _db = db or _make_db()

    async def _get_db():
        yield _db

    app.dependency_overrides[require_user] = lambda: _u
    app.dependency_overrides[get_db] = _get_db
    return app


def test_reindex_non_admin_id_returns_403():
    """user.id != 1 → 403 regardless of is_superuser."""
    resp = TestClient(_make_app(user=_regular_user())).post("/api/v1/admin/reindex")
    assert resp.status_code == 403


def test_reindex_admin_id_no_users_returns_500():
    """user.id == 1 but DB has no users → 500 (target_user is None)."""
    db = _make_db()
    # _get_primary_user query returns no user; scalars().first() → None
    no_user = MagicMock()
    no_user.scalars.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=no_user)
    resp = TestClient(_make_app(user=_admin_user(), db=db)).post("/api/v1/admin/reindex")
    assert resp.status_code == 500


def test_reindex_admin_id_no_legacy_notes_returns_200():
    """user.id == 1, primary user found, no legacy notes → 200 with fixed=0."""
    db = _make_db()
    primary_user = _admin_user()

    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        res = MagicMock()
        if call_count == 1:
            # _get_primary_user: scalars().first() → primary_user
            res.scalars.return_value.first.return_value = primary_user
        else:
            # SELECT legacy notes: scalars().all() → []
            res.scalars.return_value.all.return_value = []
        return res

    db.execute = _execute
    resp = TestClient(_make_app(user=_admin_user(), db=db)).post("/api/v1/admin/reindex")
    assert resp.status_code == 200
    body = resp.json()
    assert body["fixed"] == 0
    assert body["status"] == "ok"
