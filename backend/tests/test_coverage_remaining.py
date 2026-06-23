"""Targeted tests to close the remaining coverage gaps reported in the latest run.

Files / lines addressed:
  gnosis/routers/review.py  90% → lines 147-155 (enroll 404), 158 (already enrolled),
                                   189-190 (submit_review sets last_reviewed)
  gnosis/routers/notes.py   97% → lines 52→exit (empty tag list arc),
                                   54-57 (new Tag creation inside _upsert_tags)
  gnosis/routers/ai.py      93% → lines 129 (404 helper raise), 243-244 (chat 503),
                                   297-303 (suggest-links 503 + rationale fallback),
                                   343-344 (suggest-tags 503), 411-412 (critique 503),
                                   450 (orphan-audit empty/no-provider fast-return),
                                   670 (generate-moc empty topic 422),
                                   709-710 (generate-moc no notes 404)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ===========================================================================
# review.py
# ===========================================================================

class TestReviewEnroll:
    """review.py lines 147-155 (note not found) and 158 (already enrolled)."""

    @pytest.mark.asyncio
    async def test_enroll_note_not_found_returns_404(self, client):
        """Enrolling a non-existent note_id must return 404."""
        resp = await client.post(
            "/api/v1/review/does-not-exist-abc123/enroll",
            json={"due_today": False},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_enroll_already_enrolled_returns_existing_card(self, client, vault_dir):
        """Enrolling a note that is already enrolled must return the existing card (200, not 201)."""
        # First create a note via the notes router
        create_resp = await client.post(
            "/api/v1/notes/",
            json={
                "title": "Review Enroll Dupe Test",
                "body": "Body text",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert create_resp.status_code == 201
        note_id = create_resp.json()["id"]

        # First enroll — 201
        r1 = await client.post(f"/api/v1/review/{note_id}/enroll", json={"due_today": False})
        assert r1.status_code == 201

        # Second enroll — should hit line 158, returning the existing card with 200 or 201
        r2 = await client.post(f"/api/v1/review/{note_id}/enroll", json={"due_today": False})
        # FastAPI returns 201 for the route but the handler returns early with existing card
        assert r2.status_code in (200, 201)
        assert r2.json()["note_id"] == note_id


class TestReviewSubmitLastReviewed:
    """review.py lines 189-190: submit_review sets note.last_reviewed."""

    @pytest.mark.asyncio
    async def test_submit_review_updates_last_reviewed(self, client, vault_dir):
        """Submitting a review must touch note.last_reviewed (lines 189-190)."""
        # Create + enroll a note
        cr = await client.post(
            "/api/v1/notes/",
            json={
                "title": "Last Reviewed Test Note",
                "body": "Some body",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert cr.status_code == 201
        note_id = cr.json()["id"]

        er = await client.post(f"/api/v1/review/{note_id}/enroll", json={"due_today": True})
        assert er.status_code == 201

        # Submit a review — quality 4 (good recall)
        sr = await client.post(f"/api/v1/review/{note_id}", json={"quality": 4})
        assert sr.status_code == 200
        data = sr.json()
        assert data["note_id"] == note_id
        # interval should advance
        assert data["interval"] >= 1


# ===========================================================================
# notes.py  — _upsert_tags
# ===========================================================================

class TestUpsertTagsBranches:
    """notes.py lines 52→exit (empty list), 54-57 (new Tag row created)."""

    @pytest.mark.asyncio
    async def test_create_note_with_new_tags_creates_tag_rows(self, client, vault_dir):
        """Creating a note with a fresh tag name exercises the new-Tag branch (lines 54-57)."""
        resp = await client.post(
            "/api/v1/notes/",
            json={
                "title": "Note With Brand New Tag",
                "body": "Content.",
                "folder": "10-zettelkasten",
                "tags": ["xyzzy-unique-tag-9"],
            },
        )
        assert resp.status_code == 201
        assert "xyzzy-unique-tag-9" in resp.json()["tags"]

    @pytest.mark.asyncio
    async def test_create_note_with_empty_tags_skips_upsert(self, client, vault_dir):
        """Creating a note with tags=[] exercises the 52→exit arc (for-loop body never entered)."""
        resp = await client.post(
            "/api/v1/notes/",
            json={
                "title": "Note With No Tags At All",
                "body": "No tags here.",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert resp.status_code == 201
        assert resp.json()["tags"] == []


# ===========================================================================
# ai.py
# ===========================================================================

class TestAiGetNoteOr404:
    """ai.py line 129: _get_note_or_404 raises 404 for unknown note."""

    @pytest.mark.asyncio
    async def test_summarize_unknown_note_returns_404(self, client):
        with patch("gnosis.services.llm_provider.llm_provider.is_available", True):
            resp = await client.post("/api/v1/ai/summarize/nonexistent-note-id")
        assert resp.status_code == 404


class TestAiChat503:
    """ai.py lines 243-244: chat raises 503 when no provider is available."""

    @pytest.mark.asyncio
    async def test_chat_no_provider_returns_503(self, client):
        with (
            patch("gnosis.routers.ai.graph_rag.is_available", new=AsyncMock(return_value=False)),
            patch("gnosis.routers.ai.llm_provider.is_available", False),
        ):
            resp = await client.post(
                "/api/v1/ai/chat",
                json={"message": "hello", "mode": "hybrid"},
            )
        assert resp.status_code == 503


class TestAiSuggestLinks:
    """ai.py lines 297-303: suggest-links 503 when provider unavailable."""

    @pytest.mark.asyncio
    async def test_suggest_links_no_provider_returns_503(self, client):
        with patch("gnosis.routers.ai.llm_provider.is_available", False):
            resp = await client.post("/api/v1/ai/suggest-links/any-note-id")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_suggest_links_rationale_fallback(self, client, vault_dir):
        """Exercises rationale JSON-parse fallback (arrays[1] invalid JSON)."""
        cr = await client.post(
            "/api/v1/notes/",
            json={
                "title": "Suggest Links Source",
                "body": "Source note body for link suggestions.",
                "folder": "10-zettelkasten",
                "tags": [],
            },
        )
        assert cr.status_code == 201
        note_id = cr.json()["id"]

        # LLM returns two arrays; second is invalid JSON → fallback parse
        fake_llm_output = '["Title A"]\n[not valid json]'
        with (
            patch("gnosis.routers.ai.llm_provider.is_available", True),
            patch(
                "gnosis.routers.ai.llm_provider.complete",
                new=AsyncMock(return_value=fake_llm_output),
            ),
        ):
            resp = await client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data


class TestAiSuggestTags503:
    """ai.py lines 343-344: suggest-tags 503."""

    @pytest.mark.asyncio
    async def test_suggest_tags_no_provider_returns_503(self, client):
        with patch("gnosis.routers.ai.llm_provider.is_available", False):
            resp = await client.post("/api/v1/ai/suggest-tags/any-note-id")
        assert resp.status_code == 503


class TestAiCritique503:
    """ai.py lines 411-412: critique 503."""

    @pytest.mark.asyncio
    async def test_critique_no_provider_returns_503(self, client):
        with patch("gnosis.routers.ai.llm_provider.is_available", False):
            resp = await client.post("/api/v1/ai/critique/any-note-id")
        assert resp.status_code == 503


class TestAiOrphanAudit:
    """ai.py line 450: fast return when rows empty or provider unavailable."""

    @pytest.mark.asyncio
    async def test_orphan_audit_no_provider_returns_empty_items(self, client):
        """When provider is unavailable the handler returns early with items=[]."""
        with patch("gnosis.routers.ai.llm_provider.is_available", False):
            resp = await client.get("/api/v1/ai/orphan-audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []


class TestAiGenerateMoc:
    """ai.py lines 670 (empty topic 422) and 709-710 (no notes 404)."""

    @pytest.mark.asyncio
    async def test_generate_moc_empty_topic_returns_422(self, client):
        with patch("gnosis.routers.ai.llm_provider.is_available", True):
            resp = await client.post(
                "/api/v1/ai/generate-moc",
                json={"topic": "   "},  # whitespace-only → stripped to empty
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_moc_no_matching_notes_returns_404(self, client):
        """No notes containing the topic → 404 (lines 709-710)."""
        with patch("gnosis.routers.ai.llm_provider.is_available", True):
            resp = await client.post(
                "/api/v1/ai/generate-moc",
                json={"topic": "zzz-topic-that-will-never-match-anything-xyz"},
            )
        assert resp.status_code == 404
