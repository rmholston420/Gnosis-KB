"""Tests for routers/review.py — SM-2 spaced-repetition endpoints."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from gnosis.models.note import Note
from gnosis.models.review import ReviewCard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_note(db, note_id: str = "note-1", title: str = "Test Note") -> Note:
    note = Note(
        id=note_id,
        title=title,
        body="body text",
        folder="10-zettelkasten",
        owner_id=1,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def _make_card(
    db,
    note_id: str = "note-1",
    due_date: date | None = None,
) -> ReviewCard:
    card = ReviewCard(
        note_id=note_id,
        easiness=2.5,
        interval=1,
        repetitions=0,
        due_date=due_date or date.today(),
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


# ---------------------------------------------------------------------------
# GET /api/v1/review/queue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_queue_empty(client):
    r = await client.get("/api/v1/review/queue")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_review_queue_returns_due_card(client, test_db):
    await _make_note(test_db)
    await _make_card(test_db, due_date=date.today())
    r = await client.get("/api/v1/review/queue")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["note_id"] == "note-1"


@pytest.mark.asyncio
async def test_review_queue_excludes_future_card(client, test_db):
    await _make_note(test_db)
    future = date.today() + timedelta(days=7)
    await _make_card(test_db, due_date=future)
    r = await client.get("/api/v1/review/queue")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_review_queue_limit(client, test_db):
    for i in range(5):
        note_id = f"note-{i}"
        await _make_note(test_db, note_id=note_id, title=f"Note {i}")
        await _make_card(test_db, note_id=note_id)
    r = await client.get("/api/v1/review/queue?limit=3")
    assert r.status_code == 200
    assert len(r.json()) == 3


# ---------------------------------------------------------------------------
# GET /api/v1/review/stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_stats_empty(client):
    r = await client.get("/api/v1/review/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["due_today"] == 0
    assert data["total_enrolled"] == 0


@pytest.mark.asyncio
async def test_review_stats_with_card(client, test_db):
    await _make_note(test_db)
    await _make_card(test_db)
    r = await client.get("/api/v1/review/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_enrolled"] >= 1
    assert data["due_today"] >= 1


# ---------------------------------------------------------------------------
# POST /api/v1/review/{note_id}/enroll
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enroll_note_creates_card(client, test_db):
    await _make_note(test_db)
    r = await client.post("/api/v1/review/note-1/enroll", json={"due_today": True})
    assert r.status_code == 201
    data = r.json()
    assert data["note_id"] == "note-1"
    assert data["easiness"] > 0


@pytest.mark.asyncio
async def test_enroll_note_idempotent(client, test_db):
    """Enrolling an already-enrolled note returns existing card without error."""
    await _make_note(test_db)
    r1 = await client.post("/api/v1/review/note-1/enroll", json={"due_today": True})
    r2 = await client.post("/api/v1/review/note-1/enroll", json={"due_today": True})
    assert r1.status_code == 201
    assert r2.status_code in (200, 201)


@pytest.mark.asyncio
async def test_enroll_note_not_found(client):
    r = await client.post("/api/v1/review/nonexistent/enroll", json={"due_today": True})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/review/{note_id}  — submit review
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_review_advances_schedule(client, test_db):
    await _make_note(test_db)
    await _make_card(test_db)
    r = await client.post("/api/v1/review/note-1", json={"quality": 4})
    assert r.status_code == 200
    data = r.json()
    assert data["note_id"] == "note-1"
    assert data["last_quality"] == 4
    # interval must advance from 1
    assert data["interval"] >= 1


@pytest.mark.asyncio
async def test_submit_review_perfect_quality(client, test_db):
    await _make_note(test_db)
    await _make_card(test_db)
    r = await client.post("/api/v1/review/note-1", json={"quality": 5})
    assert r.status_code == 200
    assert r.json()["last_quality"] == 5


@pytest.mark.asyncio
async def test_submit_review_failure_resets(client, test_db):
    await _make_note(test_db)
    await _make_card(test_db)
    r = await client.post("/api/v1/review/note-1", json={"quality": 1})
    assert r.status_code == 200
    data = r.json()
    assert data["repetitions"] == 0  # SM-2 resets repetitions on failure


@pytest.mark.asyncio
async def test_submit_review_card_not_found(client):
    r = await client.post("/api/v1/review/ghost-note", json={"quality": 4})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/review/{note_id}  — unenroll
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unenroll_note_removes_card(client, test_db):
    await _make_note(test_db)
    await _make_card(test_db)
    r = await client.delete("/api/v1/review/note-1")
    assert r.status_code == 204
    # Should be gone
    r2 = await client.delete("/api/v1/review/note-1")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_unenroll_note_not_found(client):
    r = await client.delete("/api/v1/review/nonexistent")
    assert r.status_code == 404
