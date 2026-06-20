"""Coverage tests for gnosis/routers/review.py."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from gnosis.database import get_db
from gnosis.routers.review import router


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
    return app


def test_get_due_queue_empty():
    resp = TestClient(_make_app()).get("/api/v1/review/queue")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_stats_returns_200():
    db = _make_db()
    results = [MagicMock(scalar=MagicMock(return_value=v)) for v in [5, 2, 10, 0]]
    db.execute = AsyncMock(side_effect=iter(results))
    resp = TestClient(_make_app(db)).get("/api/v1/review/stats")
    assert resp.status_code == 200


def test_enroll_note_not_found_returns_404():
    resp = TestClient(_make_app()).post("/api/v1/review/nonexistent/enroll")
    assert resp.status_code == 404


def test_submit_review_card_not_found_returns_404():
    resp = TestClient(_make_app()).post("/api/v1/review/missing", json={"grade": 3})
    assert resp.status_code == 404


def test_unenroll_not_found_returns_404():
    resp = TestClient(_make_app()).delete("/api/v1/review/ghost")
    assert resp.status_code == 404
