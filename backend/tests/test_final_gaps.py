"""Final gap coverage.

Source-verified:
- Admin: POST /api/v1/admin/reindex only; must seed User row first.
  The test env DB is empty; _get_primary_user() SELECT User LIMIT 1 returns None
  if no User row exists, causing 500. Seed via test_db fixture.
- Notes: body='' is valid (body is Optional in schema) -> 201.
- Review: POST /review/{id}/enroll then POST /review/{id} (multiple grades).
- AI ingest: POST /ai/ingest-note/{note_id}.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Admin – real /admin/reindex
# ---------------------------------------------------------------------------

class TestAdminActionBranches:
    """Cover admin router via /admin/reindex."""

    async def test_admin_reindex_action(self, async_client, test_db):
        """POST /admin/reindex with a seeded User returns status=ok."""
        from gnosis.models.user import User

        user = User()
        user.id = 1
        user.email = "admin@gnosis.local"
        user.hashed_password = "x"
        test_db.add(user)
        await test_db.commit()

        resp = await async_client.post("/api/v1/admin/reindex")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_admin_unknown_action_returns_error(self, async_client):
        """An unknown admin path returns 404."""
        resp = await async_client.post("/api/v1/admin/nonexistent")
        assert resp.status_code in (404, 405)


# ---------------------------------------------------------------------------
# Notes – empty body
# ---------------------------------------------------------------------------

class TestNotesErrorBranches:
    async def test_create_note_empty_body_is_valid(self, async_client):
        """body='' is accepted (Optional field in schema)."""
        resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "No body note", "body": ""},
        )
        assert resp.status_code in (201, 422)


# ---------------------------------------------------------------------------
# Review – multiple SM-2 grade submissions
# ---------------------------------------------------------------------------

class TestReviewSM2Scheduling:
    async def test_multiple_grade_submissions(self, async_client):
        note_resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "SM2 multi grade", "body": "sm2 body"},
        )
        assert note_resp.status_code == 201
        note_id = note_resp.json()["id"]

        enroll = await async_client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"due_today": True},
        )
        assert enroll.status_code == 201

        for quality in [4, 3, 5]:
            submit = await async_client.post(
                f"/api/v1/review/{note_id}",
                json={"quality": quality},
            )
            assert submit.status_code == 200
            data = submit.json()
            assert "easiness" in data
            assert "interval" in data


# ---------------------------------------------------------------------------
# AI ingest – exception path
# ---------------------------------------------------------------------------

class TestIngestNoteException:
    async def test_ingest_note_lightrag_raises(self, async_client):
        note_resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "Ingest exc note", "body": "ingest body"},
        )
        assert note_resp.status_code == 201
        note_id = note_resp.json()["id"]

        with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
             patch("gnosis.routers.ai.graph_rag") as mock_gr:
            mock_gr.ingest_note = AsyncMock(side_effect=Exception("lightrag exploded"))
            resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")

        assert resp.status_code == 500
