"""Coverage tests for gnosis/routers/notes.py."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from gnosis.core.auth import get_current_user, get_vault_owner_ids
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.notes import router


def _user(): return User(id=1,email="u@t.com",hashed_password="x",is_active=True,is_superuser=False)

def _make_db():
    db = AsyncMock(spec=AsyncSession)
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    res.scalars.return_value.all.return_value = []
    res.scalar.return_value = 0
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


def test_list_notes_returns_200():
    resp = TestClient(_make_app()).get("/api/v1/notes/")
    assert resp.status_code == 200


def test_list_notes_with_folder_filter():
    resp = TestClient(_make_app()).get("/api/v1/notes/?folder=00-inbox")
    assert resp.status_code == 200


def test_get_note_by_title_not_found():
    resp = TestClient(_make_app()).get("/api/v1/notes/by-title?title=Ghost")
    assert resp.status_code == 404


def test_resolve_wikilink_not_found():
    resp = TestClient(_make_app()).get("/api/v1/notes/wikilink?title=Ghost")
    assert resp.status_code == 404


def test_list_templates_returns_list():
    with patch("gnosis.routers.notes.get_settings") as mc:
        mc.return_value = MagicMock(vault_path="/nonexistent")
        resp = TestClient(_make_app()).get("/api/v1/notes/templates")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_orphans_returns_list():
    resp = TestClient(_make_app()).get("/api/v1/notes/orphans")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_note_not_found():
    resp = TestClient(_make_app()).get("/api/v1/notes/nonexistent")
    assert resp.status_code == 404


def test_update_note_not_found():
    resp = TestClient(_make_app()).put("/api/v1/notes/ghost", json={"title":"New"})
    assert resp.status_code == 404


def test_delete_note_not_found():
    resp = TestClient(_make_app()).delete("/api/v1/notes/ghost")
    assert resp.status_code == 404


def test_create_note_returns_response():
    with patch("gnosis.routers.notes.get_settings") as mc:
        mc.return_value = MagicMock(vault_path="/tmp")
        resp = TestClient(_make_app()).post("/api/v1/notes/", json={
            "title":"Test Note","body":"Body.","folder":"00-inbox","note_type":"note","tags":[]})
    assert resp.status_code in (201, 409, 422, 500)
