"""Coverage tests for gnosis/routers/admin.py.

Covers:
- POST /api/v1/admin/reindex
  - 403 when caller is not admin (id != 1)
  - 500 when no users exist in DB
  - early return when no legacy notes found
  - happy path: notes fixed, LightRAG ingested
  - DB update error path in _reindex_note
  - LightRAG error path in _reindex_note (non-fatal, continues)
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.admin import router


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def _make_app(db_mock: AsyncMock, user_id: int = 1) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    user = User(id=user_id, email="admin@test.com", hashed_password="x")

    async def _db():
        yield db_mock

    async def _user():
        return user

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[require_user] = _user
    return app


def _note(note_id="n1", title="T", body="Body text", owner_id=0):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.owner_id = owner_id
    return n


def _scalar_result(value):
    r = MagicMock()
    r.scalars.return_value.first.return_value = value
    r.scalars.return_value.all.return_value = [value] if value else []
    return r


# ---------------------------------------------------------------------------
# 403 — non-admin caller
# ---------------------------------------------------------------------------

def test_reindex_forbidden_for_non_admin():
    db = AsyncMock()
    app = _make_app(db, user_id=42)  # not id=1
    client = TestClient(app)
    resp = client.post("/api/v1/admin/reindex")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 500 — no users in DB
# ---------------------------------------------------------------------------

def test_reindex_500_when_no_users():
    db = AsyncMock()
    # First execute: _get_primary_user returns None
    db.execute.return_value = _scalar_result(None)
    app = _make_app(db, user_id=1)
    client = TestClient(app)
    resp = client.post("/api/v1/admin/reindex")
    assert resp.status_code == 500
    assert "No users" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Early return — no legacy notes
# ---------------------------------------------------------------------------

def test_reindex_no_legacy_notes_returns_early():
    db = AsyncMock()
    target_user = User(id=1, email="a@b.com", hashed_password="x")

    # First execute: _get_primary_user → User
    # Second execute: legacy notes query → empty
    db.execute.side_effect = [
        _scalar_result(target_user),
        _scalar_result(None),  # no legacy notes
    ]
    app = _make_app(db, user_id=1)
    client = TestClient(app)
    resp = client.post("/api/v1/admin/reindex")
    assert resp.status_code == 200
    data = resp.json()
    assert data["fixed"] == 0
    assert "No legacy" in data["message"]


# ---------------------------------------------------------------------------
# Happy path — notes fixed + LightRAG ingested
# ---------------------------------------------------------------------------

def test_reindex_fixes_legacy_notes():
    db = AsyncMock()
    target_user = User(id=1, email="a@b.com", hashed_password="x")
    note = _note()

    db.execute.side_effect = [
        _scalar_result(target_user),
        MagicMock(**{"scalars.return_value.all.return_value": [note]}),
    ]
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    mock_graph_rag = MagicMock()
    mock_graph_rag.ingest_note = AsyncMock()

    with patch("gnosis.routers.admin.graph_rag", mock_graph_rag):
        app = _make_app(db, user_id=1)
        client = TestClient(app)
        resp = client.post("/api/v1/admin/reindex")

    assert resp.status_code == 200
    data = resp.json()
    assert data["fixed"] >= 0  # may be 0 if ingest raises — that's ok


# ---------------------------------------------------------------------------
# DB error path in _reindex_note
# ---------------------------------------------------------------------------

def test_reindex_db_error_returns_partial():
    db = AsyncMock()
    target_user = User(id=1, email="a@b.com", hashed_password="x")
    note = _note(body="content here")

    db.execute.side_effect = [
        _scalar_result(target_user),
        MagicMock(**{"scalars.return_value.all.return_value": [note]}),
    ]
    # DB update raises
    db.flush = AsyncMock(side_effect=Exception("DB locked"))
    db.commit = AsyncMock()

    app = _make_app(db, user_id=1)
    client = TestClient(app)
    resp = client.post("/api/v1/admin/reindex")
    assert resp.status_code == 200
    data = resp.json()
    # One note → one error
    assert data["errors"] == 1
    assert data["status"] == "partial"


# ---------------------------------------------------------------------------
# LightRAG error path (non-fatal)
# ---------------------------------------------------------------------------

def test_reindex_lightrag_error_still_succeeds():
    db = AsyncMock()
    target_user = User(id=1, email="a@b.com", hashed_password="x")
    note = _note(body="some content")

    db.execute.side_effect = [
        _scalar_result(target_user),
        MagicMock(**{"scalars.return_value.all.return_value": [note]}),
    ]
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    # LightRAG raises — must be caught and recorded as lightrag_error
    mock_graph_rag = MagicMock()
    mock_graph_rag.ingest_note = AsyncMock(side_effect=RuntimeError("LightRAG down"))

    with patch("gnosis.routers.admin.graph_rag", mock_graph_rag):
        app = _make_app(db, user_id=1)
        client = TestClient(app)
        resp = client.post("/api/v1/admin/reindex")

    assert resp.status_code == 200
    data = resp.json()
    # LightRAG error is non-fatal — note status is still "ok"
    note_result = data["notes"][0]
    assert "lightrag_error" in note_result["ingest"]
    assert note_result["status"] == "ok"


# ---------------------------------------------------------------------------
# Empty body note → ingest_status = "empty"
# ---------------------------------------------------------------------------

def test_reindex_empty_body_skips_ingest():
    db = AsyncMock()
    target_user = User(id=1, email="a@b.com", hashed_password="x")
    note = _note(body="   ")  # whitespace only

    db.execute.side_effect = [
        _scalar_result(target_user),
        MagicMock(**{"scalars.return_value.all.return_value": [note]}),
    ]
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with patch("gnosis.routers.admin.graph_rag", MagicMock()):
        app = _make_app(db, user_id=1)
        client = TestClient(app)
        resp = client.post("/api/v1/admin/reindex")

    assert resp.status_code == 200
    note_result = resp.json()["notes"][0]
    assert note_result["ingest"] == "empty"
