"""Coverage tests for gnosis/routers/review.py.

enroll_note makes TWO db.execute() calls:
  1. select(Note)       → scalar_one_or_none() → None  (note not found → 404)
  2. select(ReviewCard) → scalar_one_or_none() → None  (no existing card)

So the db.execute mock needs side_effect=[res_none, res_none] for the 404
path to work (first None triggers the early 404 raise, so only 1 call is
actually made — side_effect list just needs at least 1 entry).
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


def _none_result():
    """A db.execute result where scalar_one_or_none() / scalars().all() return nothing."""
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    res.scalars.return_value.all.return_value = []
    return res


def _make_db_empty():
    db = AsyncMock(spec=AsyncSession)
    # Use side_effect list so any number of execute() calls each get a fresh None result
    db.execute = AsyncMock(side_effect=lambda *a, **kw: _none_result())
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
    """POST /review/{note_id}/enroll → 404 when Note.scalar_one_or_none() is None.

    The endpoint does:
      note_result = await db.execute(select(Note)...)
      if note_result.scalar_one_or_none() is None: raise 404

    Using a lambda side_effect means each call returns a fresh MagicMock
    with scalar_one_or_none() == None.
    """
    resp = TestClient(_make_app()).post(
        "/api/v1/review/nonexistent-id/enroll",
        json={"due_today": False},
    )
    assert resp.status_code == 404


def test_submit_review_card_not_found_returns_404():
    """POST /review/{note_id} → 404 when ReviewCard not found.

    _get_card_or_404 calls db.execute(select(ReviewCard)...)
    and raises 404 if scalar_one_or_none() is None.
    """
    resp = TestClient(_make_app()).post(
        "/api/v1/review/missing-card",
        json={"quality": 3},
    )
    assert resp.status_code == 404


def test_unenroll_not_found_returns_404():
    """DELETE /review/{note_id} → 404 when card not found."""
    resp = TestClient(_make_app()).delete("/api/v1/review/ghost")
    assert resp.status_code == 404
