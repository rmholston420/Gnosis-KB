"""Coverage for miscellaneous gaps – admin reindex, review scheduling/unenroll.

Source-verified:
- Admin: POST /admin/reindex
  - requires current_user.id == 1 (conftest always returns FakeUser(id=1), OK)
  - calls _get_primary_user() which does SELECT User ... LIMIT 1
  - empty DB → target_user is None → 500
  - must seed a User row before calling the endpoint
  - non-admin test: seed User, then override require_user to return id=2

- Review: no auth; get_db dependency
  - POST   /review/{note_id}/enroll
  - POST   /review/{note_id}
  - DELETE /review/{note_id}
  - Note must exist for enroll to succeed
  - submit_review calls _get_card_or_404 which does a chained selectinload;
    enroll first so the card exists, then submit in the same client session.

- AI ingest: POST /ai/ingest-note/{note_id}
  - patch _lightrag_available + graph_rag
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Admin – POST /admin/reindex
# ---------------------------------------------------------------------------

class TestAdminReindex:
    """Cover /admin/reindex with the real admin router."""

    async def test_admin_reindex_no_legacy_notes(self, async_client, test_db):
        """No owner_id=0 notes: returns status=ok, fixed=0."""
        from gnosis.models.user import User

        user = User()
        user.id = 1
        user.email = "admin@gnosis.local"
        user.hashed_password = "x"
        test_db.add(user)
        await test_db.commit()

        resp = await async_client.post("/api/v1/admin/reindex")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["fixed"] == 0


# ---------------------------------------------------------------------------
# Admin – unknown action 404
# ---------------------------------------------------------------------------

class TestAdminUnknownAction:
    async def test_admin_unknown_action(self, async_client):
        resp = await async_client.post("/api/v1/admin/action", json={"action": "noop"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Review scheduling – enroll then submit
# ---------------------------------------------------------------------------

class TestReviewScheduling:
    async def test_submit_review_updates_note(self, async_client):
        # 1. create note
        note_resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "Review sched note", "body": "body text"},
        )
        assert note_resp.status_code == 201
        note_id = note_resp.json()["id"]

        # 2. enroll
        enroll = await async_client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"due_today": True},
        )
        assert enroll.status_code == 201

        # 3. submit rating — _get_card_or_404 runs a chained selectinload;
        #    the note + tags must be visible in the same DB connection.
        submit = await async_client.post(
            f"/api/v1/review/{note_id}",
            json={"quality": 4},
        )
        assert submit.status_code == 200
        data = submit.json()
        assert "interval" in data
        assert "easiness" in data


# ---------------------------------------------------------------------------
# Review unenroll – enroll then DELETE
# ---------------------------------------------------------------------------

class TestReviewUnenroll:
    async def test_unenroll_note(self, async_client):
        note_resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "Unenroll note", "body": "body"},
        )
        assert note_resp.status_code == 201
        note_id = note_resp.json()["id"]

        enroll = await async_client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"due_today": True},
        )
        assert enroll.status_code == 201

        unenroll = await async_client.delete(f"/api/v1/review/{note_id}")
        assert unenroll.status_code == 204

        # confirm card is gone — second DELETE must 404
        confirm = await async_client.delete(f"/api/v1/review/{note_id}")
        assert confirm.status_code == 404


# ---------------------------------------------------------------------------
# LightRAG availability (unit)
# ---------------------------------------------------------------------------

class TestLightragAvailableCheckFalse:
    def test_returns_bool(self):
        from gnosis.routers.ai import _lightrag_available
        result = _lightrag_available()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# ingest_note 500
# ---------------------------------------------------------------------------

class TestIngestNoteRaises500:
    async def test_ingest_note_exception_returns_500(self, async_client):
        note_resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "Ingest err note", "body": "body"},
        )
        assert note_resp.status_code == 201
        note_id = note_resp.json()["id"]

        with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
             patch("gnosis.routers.ai.graph_rag") as mock_gr:
            mock_gr.ingest_note = AsyncMock(side_effect=RuntimeError("fail"))
            resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")

        assert resp.status_code == 500
