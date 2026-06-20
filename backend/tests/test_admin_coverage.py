"""Coverage tests for gnosis/routers/admin.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.admin import router


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


def _note(note_id="n1", title="T", body="Body text"):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    return n


def _user_result(user):
    r = MagicMock()
    r.scalars.return_value.first.return_value = user
    return r


def _notes_result(notes):
    r = MagicMock()
    r.scalars.return_value.all.return_value = notes
    return r


# 403
def test_reindex_forbidden_for_non_admin():
    db = AsyncMock()
    resp = TestClient(_make_app(db, user_id=42)).post("/api/v1/admin/reindex")
    assert resp.status_code == 403


# 500 — no users
def test_reindex_500_when_no_users():
    db = AsyncMock()
    db.execute.return_value = _user_result(None)
    resp = TestClient(_make_app(db, user_id=1)).post("/api/v1/admin/reindex")
    assert resp.status_code == 500
    assert "No users" in resp.json()["detail"]


# Early return — no legacy notes
def test_reindex_no_legacy_notes_returns_early():
    db = AsyncMock()
    target = User(id=1, email="a@b.com", hashed_password="x")
    db.execute.side_effect = [_user_result(target), _notes_result([])]
    resp = TestClient(_make_app(db, user_id=1)).post("/api/v1/admin/reindex")
    assert resp.status_code == 200
    assert resp.json()["fixed"] == 0


# Happy path
def test_reindex_fixes_legacy_notes():
    db = AsyncMock()
    target = User(id=1, email="a@b.com", hashed_password="x")
    note = _note(body="real content")
    db.execute.side_effect = [_user_result(target), _notes_result([note])]
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    mock_rag = MagicMock()
    mock_rag.ingest_note = AsyncMock()

    # Must be active when _reindex_note executes the lazy import
    with patch("gnosis.services.graph_rag.graph_rag", mock_rag):
        resp = TestClient(_make_app(db, user_id=1)).post("/api/v1/admin/reindex")

    assert resp.status_code == 200
    assert resp.json()["notes"][0]["status"] == "ok"


# DB error
def test_reindex_db_error_returns_partial():
    db = AsyncMock()
    target = User(id=1, email="a@b.com", hashed_password="x")
    note = _note(body="content")
    db.execute.side_effect = [_user_result(target), _notes_result([note])]
    db.flush = AsyncMock(side_effect=Exception("DB locked"))
    db.commit = AsyncMock()

    resp = TestClient(_make_app(db, user_id=1)).post("/api/v1/admin/reindex")
    assert resp.status_code == 200
    assert resp.json()["status"] == "partial"


# LightRAG error (non-fatal)
def test_reindex_lightrag_error_still_succeeds():
    db = AsyncMock()
    target = User(id=1, email="a@b.com", hashed_password="x")
    note = _note(body="some content")
    db.execute.side_effect = [_user_result(target), _notes_result([note])]
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    mock_rag = MagicMock()
    mock_rag.ingest_note = AsyncMock(side_effect=RuntimeError("LightRAG down"))

    with patch("gnosis.services.graph_rag.graph_rag", mock_rag):
        resp = TestClient(_make_app(db, user_id=1)).post("/api/v1/admin/reindex")

    assert resp.status_code == 200
    result = resp.json()["notes"][0]
    assert "lightrag_error" in result["ingest"]
    assert result["status"] == "ok"


# Empty body
def test_reindex_empty_body_skips_ingest():
    db = AsyncMock()
    target = User(id=1, email="a@b.com", hashed_password="x")
    note = _note(body="   ")
    db.execute.side_effect = [_user_result(target), _notes_result([note])]
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    mock_rag = MagicMock()
    mock_rag.ingest_note = AsyncMock()

    with patch("gnosis.services.graph_rag.graph_rag", mock_rag):
        resp = TestClient(_make_app(db, user_id=1)).post("/api/v1/admin/reindex")

    assert resp.status_code == 200
    assert resp.json()["notes"][0]["ingest"] == "empty"
    mock_rag.ingest_note.assert_not_called()
