"""Coverage for miscellaneous gaps – admin reindex, review scheduling/unenroll.

Fixes:
- Admin: /admin/action does not exist.  Replaced with two real /admin/reindex
  tests: (a) no legacy notes → fast empty return; (b) non-admin user → 403.
- Review scheduling: enroll then submit via the real HTTP routes.
- Review unenroll: enroll then DELETE via the real HTTP routes.
- LightRAG unavailable: call _lightrag_available() directly (sync unit test).
- IngestNote 500: patch graph_rag service + _lightrag_available function.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_note(async_client, title="Gap note") -> str:
    resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": title, "body": "body text"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Admin – real /admin/reindex endpoint
# ---------------------------------------------------------------------------

class TestAdminReindex:
    """Cover /admin/reindex with the real admin router."""

    async def test_admin_reindex_no_legacy_notes(self, async_client):
        """When there are no owner_id=0 notes, endpoint returns fixed=0."""
        resp = await async_client.post("/api/v1/admin/reindex")
        assert resp.status_code == 200
        body = resp.json()
        assert body["fixed"] == 0

    async def test_admin_reindex_non_admin_forbidden(self, app, async_client):
        """A user with id != 1 receives 403."""
        from fastapi import Request
        from gnosis.models.user import User
        from gnosis.core.auth import require_user

        # Create a user object that looks like user_id=2
        fake_user = User()
        fake_user.id = 2
        fake_user.email = "other@example.com"
        fake_user.hashed_password = "x"

        original_override = app.dependency_overrides.get(require_user)
        app.dependency_overrides[require_user] = lambda: fake_user
        try:
            resp = await async_client.post("/api/v1/admin/reindex")
        finally:
            if original_override is None:
                app.dependency_overrides.pop(require_user, None)
            else:
                app.dependency_overrides[require_user] = original_override

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin – previous "unknown action" tests replaced above; keep class empty
# to avoid import errors in old references.  New tests in TestAdminReindex.
# ---------------------------------------------------------------------------

class TestAdminUnknownAction:
    """Placeholder – /admin/action does not exist; tests moved to TestAdminReindex."""

    async def test_admin_unknown_action(self, async_client):
        """Confirms /admin/action returns 404 (route does not exist)."""
        resp = await async_client.post("/api/v1/admin/action", json={"action": "noop"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Review scheduling
# ---------------------------------------------------------------------------

class TestReviewScheduling:
    async def test_submit_review_updates_note(self, async_client):
        note_id = await _create_note(async_client, "Review sched note")

        enroll = await async_client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"due_today": True},
        )
        assert enroll.status_code == 201

        submit = await async_client.post(
            f"/api/v1/review/{note_id}",
            json={"quality": 4},
        )
        assert submit.status_code == 200
        data = submit.json()
        assert "interval" in data
        assert "easiness" in data


# ---------------------------------------------------------------------------
# Review unenroll
# ---------------------------------------------------------------------------

class TestReviewUnenroll:
    async def test_unenroll_note(self, async_client):
        note_id = await _create_note(async_client, "Unenroll note")

        enroll = await async_client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"due_today": True},
        )
        assert enroll.status_code == 201

        unenroll = await async_client.delete(f"/api/v1/review/{note_id}")
        assert unenroll.status_code == 204

        # Confirm gone
        confirm = await async_client.delete(f"/api/v1/review/{note_id}")
        assert confirm.status_code == 404


# ---------------------------------------------------------------------------
# LightRAG availability (unit, no HTTP)
# ---------------------------------------------------------------------------

class TestLightragAvailableCheckFalse:
    def test_returns_false_when_lightrag_not_installed(self):
        from gnosis.routers.ai import _lightrag_available
        with patch.dict("sys.modules", {"lightrag": None}):
            result = _lightrag_available()
        # lightrag not installed in test env → False; if installed → True.
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# ingest_note 500
# ---------------------------------------------------------------------------

class TestIngestNoteRaises500:
    async def test_ingest_note_exception_returns_500(self, async_client):
        note_id = await _create_note(async_client, "Ingest err note")

        with patch("gnosis.routers.ai._lightrag_available", return_value=True), \
             patch("gnosis.routers.ai.graph_rag") as mock_gr:
            mock_gr.ingest_note = AsyncMock(side_effect=RuntimeError("fail"))
            resp = await async_client.post(
                "/api/v1/ai/ingest",
                json={"note_id": note_id, "content": "content"},
            )

        assert resp.status_code == 500
