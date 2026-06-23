"""Coverage tests for gnosis/routers/review.py.

ReviewEnroll schema has TWO fields:
  note_id: str      (required)
  due_today: bool   (default True)

enroll_note makes TWO db.execute() calls:
  1. select(Note).where(Note.id == note_id) -> scalar_one_or_none() -> None -> 404
  2. (never reached in the 404 path)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.database import get_db
from gnosis.routers.review import router


def _make_app(db=None):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    _db = db or _make_db_empty()

    async def _get_db():
        yield _db

    app.dependency_overrides[get_db] = _get_db
    return app


def _none_result():
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    res.scalars.return_value.all.return_value = []
    return res


def _make_db_empty():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(side_effect=lambda *a, **kw: _none_result())
    db.scalar = AsyncMock(return_value=0)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.delete = AsyncMock()
    db.refresh = AsyncMock()
    return db


def test_get_due_queue_empty():
    resp = TestClient(_make_app()).get("/api/v1/review/queue")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_stats_returns_200():
    resp = TestClient(_make_app()).get("/api/v1/review/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert "due_today" in body
    assert "total_enrolled" in body


def test_enroll_note_not_found_returns_404():
    """POST /review/{note_id}/enroll -> 404 when Note is not in DB.

    ReviewEnroll requires: note_id (str) + due_today (bool).
    Both must be present or Pydantic returns 422 before hitting the endpoint.
    """
    resp = TestClient(_make_app()).post(
        "/api/v1/review/nonexistent-id/enroll",
        json={"note_id": "nonexistent-id", "due_today": False},
    )
    assert resp.status_code == 404


def test_submit_review_card_not_found_returns_404():
    resp = TestClient(_make_app()).post(
        "/api/v1/review/missing-card",
        json={"quality": 3},
    )
    assert resp.status_code == 404


def test_unenroll_not_found_returns_404():
    resp = TestClient(_make_app()).delete("/api/v1/review/ghost")
    assert resp.status_code == 404
