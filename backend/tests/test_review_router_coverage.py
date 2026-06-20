"""Coverage tests for gnosis/routers/review.py.

Uses FastAPI TestClient with dependency overrides for get_db and
require_user so no real Postgres or auth token is needed.

Covers all endpoints:
  GET  /api/v1/review/queue
  GET  /api/v1/review/stats
  POST /api/v1/review/{note_id}/enroll
  POST /api/v1/review/{note_id}
  DELETE /api/v1/review/{note_id}
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.review import router


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

def _make_app(db_mock: AsyncMock, user: User | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    fake_user = user or User(id=1, email="u@test.com", hashed_password="x")

    async def _db():
        yield db_mock

    async def _user():
        return fake_user

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[require_user] = _user
    return app


def _mock_card(note_id="note-1", easiness=2.5, interval=6,
               repetitions=2, due_days=0, last_quality=4,
               title="T", body="B", folder="00-inbox", tags=None):
    """Build a mock ReviewCard with a joined Note."""
    note = MagicMock()
    note.id = note_id
    note.title = title
    note.body = body
    note.folder = folder
    note.tags = [MagicMock(name=t) for t in (tags or ["python"])]
    note.last_reviewed = None

    card = MagicMock()
    card.note_id = note_id
    card.easiness = easiness
    card.interval = interval
    card.repetitions = repetitions
    card.due_date = date.today() + timedelta(days=due_days)
    card.last_quality = last_quality
    card.note = note
    # Support model_validate
    card.__class__.__name__ = "ReviewCard"
    return card


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalars.return_value.all.return_value = [value] if value else []
    return r


def _scalars_result(values):
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


# ---------------------------------------------------------------------------
# GET /queue
# ---------------------------------------------------------------------------

def test_get_due_queue_returns_list():
    db = AsyncMock()
    card = _mock_card()
    db.execute.return_value = _scalars_result([card])

    with patch("gnosis.routers.review.ReviewCardWithNote") as MockSchema:
        MockSchema.return_value = {"note_id": "note-1"}
        app = _make_app(db)
        client = TestClient(app)
        resp = client.get("/api/v1/review/queue")

    assert resp.status_code == 200


def test_get_due_queue_empty():
    db = AsyncMock()
    db.execute.return_value = _scalars_result([])
    app = _make_app(db)
    client = TestClient(app)
    resp = client.get("/api/v1/review/queue")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------

def test_get_stats_returns_counts():
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[3, 10, 50, 2])
    app = _make_app(db)
    client = TestClient(app)
    resp = client.get("/api/v1/review/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["due_today"] == 3
    assert data["total_enrolled"] == 50


def test_get_stats_null_scalars_default_to_zero():
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[None, None, None, None])
    app = _make_app(db)
    client = TestClient(app)
    resp = client.get("/api/v1/review/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["due_today"] == 0


# ---------------------------------------------------------------------------
# POST /{note_id}/enroll
# ---------------------------------------------------------------------------

def test_enroll_note_not_found_returns_404():
    db = AsyncMock()
    db.execute.return_value = _scalar_result(None)  # Note not found
    app = _make_app(db)
    client = TestClient(app)
    resp = client.post("/api/v1/review/new-note/enroll", json={"due_today": True})
    assert resp.status_code == 404


def test_enroll_already_enrolled_returns_existing():
    db = AsyncMock()
    note_mock = MagicMock()
    card_mock = _mock_card()

    # First execute: find Note; second execute: find existing card
    db.execute.side_effect = [_scalar_result(note_mock), _scalar_result(card_mock)]

    with patch("gnosis.routers.review.ReviewCardRead") as MockRead:
        MockRead.model_validate.return_value = MagicMock(model_dump=lambda: {})
        app = _make_app(db)
        client = TestClient(app)
        resp = client.post("/api/v1/review/note-1/enroll", json={"due_today": True})

    assert resp.status_code == 201


def test_enroll_new_card_creates_and_commits():
    db = AsyncMock()
    note_mock = MagicMock()
    new_card = _mock_card(repetitions=0, interval=1)

    # First execute: find Note; second execute: no existing card
    db.execute.side_effect = [_scalar_result(note_mock), _scalar_result(None)]
    db.refresh = AsyncMock()

    with patch("gnosis.routers.review.ReviewCardRead") as MockRead:
        MockRead.model_validate.return_value = MagicMock(model_dump=lambda: {})
        with patch("gnosis.routers.review.ReviewCard", return_value=new_card):
            app = _make_app(db)
            client = TestClient(app)
            resp = client.post("/api/v1/review/note-new/enroll", json={"due_today": False})

    assert resp.status_code == 201
    db.add.assert_called_once()
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# POST /{note_id}  — submit review
# ---------------------------------------------------------------------------

def test_submit_review_card_not_found_returns_404():
    db = AsyncMock()
    db.execute.return_value = _scalar_result(None)
    app = _make_app(db)
    client = TestClient(app)
    resp = client.post("/api/v1/review/missing", json={"quality": 4})
    assert resp.status_code == 404


@pytest.mark.parametrize("quality", [0, 1, 2, 3, 4, 5])
def test_submit_review_all_quality_values(quality):
    db = AsyncMock()
    card = _mock_card()
    note = card.note

    # First execute: get card (with note.tags eager load)
    # Second execute: get note for last_reviewed update
    db.execute.side_effect = [_scalar_result(card), _scalar_result(note)]
    db.refresh = AsyncMock()

    with patch("gnosis.routers.review.ReviewCardRead") as MockRead:
        MockRead.model_validate.return_value = MagicMock(model_dump=lambda: {})
        app = _make_app(db)
        client = TestClient(app)
        resp = client.post(f"/api/v1/review/note-1", json={"quality": quality})

    assert resp.status_code == 200
    assert card.last_quality == quality


# ---------------------------------------------------------------------------
# DELETE /{note_id}  — unenroll
# ---------------------------------------------------------------------------

def test_unenroll_card_not_found_returns_404():
    db = AsyncMock()
    db.execute.return_value = _scalar_result(None)
    app = _make_app(db)
    client = TestClient(app)
    resp = client.delete("/api/v1/review/ghost")
    assert resp.status_code == 404


def test_unenroll_happy_path_returns_204():
    db = AsyncMock()
    card = _mock_card()
    db.execute.return_value = _scalar_result(card)
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    app = _make_app(db)
    client = TestClient(app)
    resp = client.delete("/api/v1/review/note-1")
    assert resp.status_code == 204
    db.delete.assert_called_once_with(card)
    db.commit.assert_called_once()
