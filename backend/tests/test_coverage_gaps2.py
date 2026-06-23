"""Coverage for miscellaneous gaps – admin reindex, review scheduling/unenroll."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Admin – POST /admin/reindex
# ---------------------------------------------------------------------------


class TestAdminReindex:
    async def test_admin_reindex_no_legacy_notes(self, async_client, test_db):
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
# Mirrors the exact fixture signature of the passing test in
# test_coverage_remaining.py::TestReviewSubmitLastReviewed which uses
# (self, client, vault_dir) — vault_dir is required so conftest wires
# settings.vault_path to a real temp directory before the app starts.
# ---------------------------------------------------------------------------


class TestReviewScheduling:
    async def test_submit_review_updates_note(self, client, vault_dir):
        note_resp = await client.post(
            "/api/v1/notes/",
            json={
                "title": "Review sched note",
                "body": "body text",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert note_resp.status_code == 201
        note_id = note_resp.json()["id"]

        enroll = await client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"note_id": note_id, "due_today": True},
        )
        assert enroll.status_code == 201

        submit = await client.post(
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
    async def test_unenroll_note(self, client, vault_dir):
        note_resp = await client.post(
            "/api/v1/notes/",
            json={
                "title": "Unenroll note",
                "body": "body",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert note_resp.status_code == 201
        note_id = note_resp.json()["id"]

        enroll = await client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"note_id": note_id, "due_today": True},
        )
        assert enroll.status_code == 201

        unenroll = await client.delete(f"/api/v1/review/{note_id}")
        assert unenroll.status_code == 204

        # confirm card is gone — second DELETE must 404
        confirm = await client.delete(f"/api/v1/review/{note_id}")
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
    async def test_ingest_note_exception_returns_500(self, client, vault_dir):
        note_resp = await client.post(
            "/api/v1/notes/",
            json={
                "title": "Ingest err note",
                "body": "body",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert note_resp.status_code == 201
        note_id = note_resp.json()["id"]

        with (
            patch("gnosis.routers.ai._lightrag_available", return_value=True),
            patch("gnosis.routers.ai.graph_rag") as mock_gr,
        ):
            mock_gr.ingest_note = AsyncMock(side_effect=RuntimeError("fail"))
            resp = await client.post(f"/api/v1/ai/ingest-note/{note_id}")

        assert resp.status_code == 500
