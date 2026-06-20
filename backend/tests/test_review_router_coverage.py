"""Coverage tests for gnosis/routers/review.py."""
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


def _make_card(note_id="note-1", easiness=2.5, interval=6,
               repetitions=2, due_days=0, last_quality=4,
               title="Test Note", body="Body text", folder="00-inbox",
               tags=None):
    note = MagicMock()
    note.id = note_id
    note.title = title
    note.body = body
    note.folder = folder
    note.last_reviewed = None
    tag_objs = []
    for t in (tags or ["python"]):
        m = MagicMock()
        m.name = t
        tag_objs.append(m)
    note.tags = tag_objs

    card = MagicMock()
    card.note_id = note_id
    card.easiness = easiness
    card.interval = interval
    card.repetitions = repetitions
    card.due_date = date.today() + timedelta(days=due_days)
    card.last_quality = last_quality
    card.note = note
    return card


def _scalars_list(items):
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _scalar_one(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalars.return_value.first.return_value = value
    return r


# GET /queue
def test_get_due_queue_returns_list():
    db = AsyncMock()
    db.execute.return_value = _scalars_list([_make_card()])
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/review/queue")
    assert resp.status_code == 200
    assert resp.json()[0]["note_id"] == "note-1"


def test_get_due_queue_empty():
    db = AsyncMock()
    db.execute.return_value = _scalars_list([])
    client = TestClient(_make_app(db))
    assert client.get("/api/v1/review/queue").json() == []


# GET /stats
def test_get_stats_returns_counts():
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[3, 10, 50, 2])
    resp = TestClient(_make_app(db)).get("/api/v1/review/stats")
    assert resp.status_code == 200
    assert resp.json()["due_today"] == 3


def test_get_stats_null_defaults_to_zero():
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[None, None, None, None])
    resp = TestClient(_make_app(db)).get("/api/v1/review/stats")
    assert resp.json()["due_today"] == 0


# POST /{note_id}/enroll
def test_enroll_note_not_found_returns_404():
    db = AsyncMock()
    db.execute.return_value = _scalar_one(None)
    resp = TestClient(_make_app(db)).post(
        "/api/v1/review/new-note/enroll",
        json={"note_id": "new-note", "due_today": True},
    )
    assert resp.status_code == 404


def test_enroll_already_enrolled_returns_existing():
    db = AsyncMock()
    note_mock = MagicMock()
    card = _make_card()
    db.execute.side_effect = [_scalar_one(note_mock), _scalar_one(card)]
    resp = TestClient(_make_app(db)).post(
        "/api/v1/review/note-1/enroll",
        json={"note_id": "note-1", "due_today": True},
    )
    assert resp.status_code == 201


def test_enroll_new_card_creates_and_commits():
    """New card path: ReviewCard is constructed, added, committed, refreshed."""
    db = AsyncMock()
    note_mock = MagicMock()
    # First execute -> note exists; second -> no existing card
    db.execute.side_effect = [_scalar_one(note_mock), _scalar_one(None)]
    db.commit = AsyncMock()

    # After db.refresh the card needs real fields for model_validate.
    # We capture what ReviewCard(...) returns (the real ORM object) and
    # set its attributes via the refresh side-effect.
    created_card = None

    async def _refresh(obj):
        nonlocal created_card
        created_card = obj
        # Give the ORM object the minimum fields Pydantic needs
        obj.note_id = "note-new"
        obj.easiness = 2.5
        obj.interval = 1
        obj.repetitions = 0
        obj.due_date = date.today()
        obj.last_quality = None

    db.refresh = _refresh
    db.add = MagicMock()

    resp = TestClient(_make_app(db)).post(
        "/api/v1/review/note-new/enroll",
        json={"note_id": "note-new", "due_today": False},
    )
    assert resp.status_code == 201
    db.add.assert_called_once()
    db.commit.assert_called_once()


# POST /{note_id} — submit review
def test_submit_review_card_not_found():
    db = AsyncMock()
    db.execute.return_value = _scalar_one(None)
    resp = TestClient(_make_app(db)).post("/api/v1/review/missing", json={"quality": 4})
    assert resp.status_code == 404


@pytest.mark.parametrize("quality", [0, 1, 2, 3, 4, 5])
def test_submit_review_all_quality_values(quality):
    db = AsyncMock()
    card = _make_card()
    note_mock = card.note
    db.execute.side_effect = [_scalar_one(card), _scalar_one(note_mock)]

    async def _refresh(obj):
        obj.note_id = "note-1"
        obj.easiness = 2.5
        obj.interval = 6
        obj.repetitions = 2
        obj.due_date = date.today()
        obj.last_quality = quality

    db.refresh = _refresh
    db.commit = AsyncMock()

    resp = TestClient(_make_app(db)).post(f"/api/v1/review/note-1", json={"quality": quality})
    assert resp.status_code == 200
    assert card.last_quality == quality


# DELETE /{note_id}
def test_unenroll_card_not_found():
    db = AsyncMock()
    db.execute.return_value = _scalar_one(None)
    resp = TestClient(_make_app(db)).delete("/api/v1/review/ghost")
    assert resp.status_code == 404


def test_unenroll_happy_path():
    db = AsyncMock()
    card = _make_card()
    db.execute.return_value = _scalar_one(card)
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    resp = TestClient(_make_app(db)).delete("/api/v1/review/note-1")
    assert resp.status_code == 204
    db.delete.assert_called_once_with(card)
