"""Coverage tests for gnosis/routers/review.py.

Endpoints and their actual HTTP shapes:
  GET  /review/queue                        → list (no auth)
  GET  /review/stats                        → ReviewStats (uses db.scalar, not db.execute)
  POST /review/{note_id}/enroll             → 201 | 404; body: ReviewEnroll{due_today: bool}
  POST /review/{note_id}                    → 200 | 404; body: ReviewSubmit{quality: int}
  DELETE /review/{note_id}                  → 204 | 404

Critical: stats uses db.scalar() four times, not db.execute().
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
    async def _get_db(): yield _db
    app.dependency_overrides[get_db] = _get_db
    return app


def _make_db_empty():
    """DB mock where every execute/scalar returns nothing."""
    db = AsyncMock(spec=AsyncSession)
    res = MagicMock()
    res.scalars.return_value.all.return_value = []
    res.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=res)
    # stats uses db.scalar() directly
    db.scalar = AsyncMock(return_value=0)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.delete = AsyncMock()
    db.refresh = AsyncMock()
    return db


def test_get_due_queue_empty():
    """GET /review/queue → [] when no cards due."""
    resp = TestClient(_make_app()).get("/api/v1/review/queue")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_stats_returns_200():
    """GET /review/stats → 200 with ReviewStats fields."""
    resp = TestClient(_make_app()).get("/api/v1/review/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert "due_today" in body
    assert "total_enrolled" in body


def test_enroll_note_not_found_returns_404():
    """POST /review/{note_id}/enroll when note doesn't exist → 404.

    The endpoint queries Note first; scalar_one_or_none → None → 404.
    Payload: {due_today: false} (ReviewEnroll schema).
    """
    resp = TestClient(_make_app()).post(
        "/api/v1/review/nonexistent-id/enroll",
        json={"due_today": False},
    )
    assert resp.status_code == 404


def test_submit_review_card_not_found_returns_404():
    """POST /review/{note_id} when card doesn't exist → 404.

    The endpoint queries ReviewCard; scalar_one_or_none → None → 404.
    Payload: {quality: 3} (ReviewSubmit schema, field name is 'quality').
    """
    resp = TestClient(_make_app()).post(
        "/api/v1/review/missing-card",
        json={"quality": 3},
    )
    assert resp.status_code == 404


def test_unenroll_not_found_returns_404():
    """DELETE /review/{note_id} when card doesn't exist → 404."""
    resp = TestClient(_make_app()).delete("/api/v1/review/ghost")
    assert resp.status_code == 404
