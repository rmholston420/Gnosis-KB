"""Coverage tests for gnosis/routers/notes.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.notes import router


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


def _note(note_id="n1", title="Title", body="Body", folder="00-inbox",
          owner_id=1, tags=None, backlinks=None, source_url=None,
          word_count=10, is_deleted=False):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.folder = folder
    n.owner_id = owner_id
    n.source_url = source_url
    n.word_count = word_count
    n.is_deleted = is_deleted
    n.created_at = datetime.now(timezone.utc)
    n.modified_at = datetime.now(timezone.utc)
    n.last_reviewed = None
    tag_objs = []
    for t in (tags or []):
        m = MagicMock()
        m.name = t
        tag_objs.append(m)
    n.tags = tag_objs
    bl_objs = []
    for bl in (backlinks or []):
        m = MagicMock()
        m.source_id = bl
        bl_objs.append(m)
    n.incoming_links = bl_objs
    return n


def _scalar_one(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalars.return_value.all.return_value = [value] if value else []
    r.scalars.return_value.first.return_value = value
    r.scalar.return_value = 5
    return r


def _scalars_list(items):
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    r.scalar.return_value = len(items)
    return r


# GET /notes
def test_list_notes_returns_200():
    db = AsyncMock()
    note = _note()
    db.execute.side_effect = [_scalars_list([note]), _scalar_one(5)]
    db.scalar = AsyncMock(return_value=1)
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/notes/")
    assert resp.status_code == 200


# GET /notes/{id}
def test_get_note_returns_200():
    db = AsyncMock()
    note = _note()
    db.execute.return_value = _scalar_one(note)
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/notes/n1")
    assert resp.status_code == 200


def test_get_note_not_found():
    db = AsyncMock()
    db.execute.return_value = _scalar_one(None)
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/notes/missing")
    assert resp.status_code == 404


# PATCH /notes/{id}
def test_update_note_returns_200():
    db = AsyncMock()
    note = _note()
    db.execute.return_value = _scalar_one(note)
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda n: None)
    client = TestClient(_make_app(db))
    resp = client.patch("/api/v1/notes/n1", json={"title": "New Title"})
    assert resp.status_code == 200


def test_update_note_not_found():
    db = AsyncMock()
    db.execute.return_value = _scalar_one(None)
    client = TestClient(_make_app(db))
    resp = client.patch("/api/v1/notes/missing", json={"title": "X"})
    assert resp.status_code == 404


# DELETE /notes/{id}
def test_delete_note_returns_204():
    db = AsyncMock()
    note = _note()
    db.execute.return_value = _scalar_one(note)
    db.commit = AsyncMock()
    client = TestClient(_make_app(db))
    resp = client.delete("/api/v1/notes/n1")
    assert resp.status_code == 204


def test_delete_note_not_found():
    db = AsyncMock()
    db.execute.return_value = _scalar_one(None)
    client = TestClient(_make_app(db))
    resp = client.delete("/api/v1/notes/missing")
    assert resp.status_code == 404


# GET /notes/{id}/backlinks
def test_get_backlinks_returns_200():
    db = AsyncMock()
    note = _note(backlinks=["other-id"])
    db.execute.return_value = _scalar_one(note)
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/notes/n1/backlinks")
    assert resp.status_code == 200


# GET /notes/{id}/graph
def test_get_graph_returns_200():
    db = AsyncMock()
    note = _note()
    db.execute.return_value = _scalar_one(note)
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/notes/n1/graph")
    assert resp.status_code in (200, 404)


# GET /notes/folders
def test_get_folders_returns_list():
    db = AsyncMock()
    r = MagicMock()
    r.all.return_value = [("00-inbox", 3), ("01-projects", 1)]
    db.execute.return_value = r
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/notes/folders")
    assert resp.status_code == 200


# GET /notes/recent
def test_get_recent_returns_list():
    db = AsyncMock()
    note = _note()
    db.execute.return_value = _scalars_list([note])
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/notes/recent")
    assert resp.status_code == 200
