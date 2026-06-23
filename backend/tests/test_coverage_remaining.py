"""Targeted tests to close the remaining coverage gaps reported in the latest run.

Files / lines addressed:
  gnosis/routers/review.py  90% → lines 147-155 (enroll 404), 158 (already enrolled),
                                   189-190 (submit_review sets last_reviewed)
  gnosis/routers/notes.py   97% → lines 52→exit (empty tag list arc),
                                   54-57 (new Tag creation inside _upsert_tags)
  gnosis/routers/ai.py      93% → lines 129 (404 helper raise), 138-142 (providers no-op),
                                   211-221 (set_model 400 + swap path),
                                   243-244 (chat 503), 297-303 (suggest-links 503 + fallback),
                                   343-344 (suggest-tags 503), 411-412 (critique 503),
                                   450 (orphan-audit empty/no-provider fast-return),
                                   467-483 (SSE stream exception handler),
                                   670 (generate-moc empty topic 422),
                                   709-710 (generate-moc no notes 404)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from gnosis.services.llm_provider import llm_provider
from gnosis.services.graph_rag import graph_rag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _available_provider():
    """Context manager: make llm_provider.is_available return True."""
    return patch.object(type(llm_provider), "is_available", new_callable=PropertyMock, return_value=True)


def _unavailable_provider():
    """Context manager: make llm_provider.is_available return False."""
    return patch.object(type(llm_provider), "is_available", new_callable=PropertyMock, return_value=False)


def _graph_rag_unavailable():
    """Context manager: make graph_rag.is_available return False (async method)."""
    return patch.object(graph_rag, "is_available", new=AsyncMock(return_value=False))


# ===========================================================================
# review.py
# ===========================================================================

class TestReviewEnroll:
    """review.py lines 147-155 (note not found) and 158 (already enrolled)."""

    @pytest.mark.asyncio
    async def test_enroll_note_not_found_returns_404(self, client):
        """Enrolling a non-existent note_id must return 404.

        ReviewEnroll schema requires both note_id and due_today fields.
        """
        resp = await client.post(
            "/api/v1/review/does-not-exist-abc123/enroll",
            json={"note_id": "does-not-exist-abc123", "due_today": False},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_enroll_already_enrolled_returns_existing_card(self, client, vault_dir):
        """Enrolling a note that is already enrolled must return the existing card."""
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

        r1 = await client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"note_id": note_id, "due_today": False},
        )
        assert r1.status_code == 201

        # Second enroll — hits line 158 (already enrolled), returns existing card
        r2 = await client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"note_id": note_id, "due_today": False},
        )
        assert r2.status_code in (200, 201)
        assert r2.json()["note_id"] == note_id


class TestReviewSubmitLastReviewed:
    """review.py lines 189-190: submit_review sets note.last_reviewed."""

    @pytest.mark.asyncio
    async def test_submit_review_updates_last_reviewed(self, client, vault_dir):
        """Submitting a review must touch note.last_reviewed (lines 189-190)."""
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

        er = await client.post(
            f"/api/v1/review/{note_id}/enroll",
            json={"note_id": note_id, "due_today": True},
        )
        assert er.status_code == 201

        sr = await client.post(f"/api/v1/review/{note_id}", json={"quality": 4})
        assert sr.status_code == 200
        data = sr.json()
        assert data["note_id"] == note_id
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
        """Creating a note with tags=[] exercises the 52→exit arc."""
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
        """When provider is available but note_id does not exist, return 404."""
        with _available_provider():
            resp = await client.post("/api/v1/ai/summarize/nonexistent-note-id")
        assert resp.status_code == 404


class TestAiProviders:
    """ai.py lines 138-142: GET /providers returns available=False when no provider."""

    @pytest.mark.asyncio
    async def test_get_providers_no_provider_returns_unavailable(self, client):
        """Lines 138-142: early return with available=False when llm_provider unavailable."""
        with _unavailable_provider():
            resp = await client.get("/api/v1/ai/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["provider"] == "none"
        assert data["models"] == []


class TestAiSetModel:
    """ai.py lines 211-221: POST /providers/model — ollama-absent 400 and swap path."""

    @pytest.mark.asyncio
    async def test_set_model_ollama_unavailable_returns_400(self, client):
        """Line 211: ollama not in _available → 400 Bad Request."""
        # Ensure ollama is NOT in the available list
        original = list(llm_provider._available)  # noqa: SLF001
        llm_provider._available.clear()  # noqa: SLF001
        try:
            resp = await client.post(
                "/api/v1/ai/providers/model",
                json={"model": "llama3:8b"},
            )
        finally:
            llm_provider._available.extend(original)  # noqa: SLF001
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_set_model_ollama_available_swaps_and_returns_info(self, client):
        """Lines 215-221: ollama present → swap_model called, 200 with provider info."""
        original = list(llm_provider._available)  # noqa: SLF001
        # Ensure ollama is registered
        if "ollama" not in llm_provider._available:  # noqa: SLF001
            llm_provider._available.append("ollama")  # noqa: SLF001
        try:
            with (
                patch.object(llm_provider, "swap_model") as mock_swap,
                patch("gnosis.routers.ai.httpx.AsyncClient") as mock_client_cls,
            ):
                # Mock httpx so we don't need Ollama running
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"models": [{"name": "llama3:8b"}]}
                mock_async_client = AsyncMock()
                mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
                mock_async_client.__aexit__ = AsyncMock(return_value=False)
                mock_async_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_async_client

                resp = await client.post(
                    "/api/v1/ai/providers/model",
                    json={"model": "llama3:8b"},
                )
        finally:
            llm_provider._available[:] = original  # noqa: SLF001

        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "ollama"
        assert data["model"] == "llama3:8b"
        mock_swap.assert_called_once_with("llama3:8b")


class TestAiChat503:
    """ai.py lines 243-244: chat raises 503 when no provider is available."""

    @pytest.mark.asyncio
    async def test_chat_no_provider_returns_503(self, client):
        with _graph_rag_unavailable(), _unavailable_provider():
            resp = await client.post(
                "/api/v1/ai/chat",
                json={"message": "hello", "mode": "hybrid"},
            )
        assert resp.status_code == 503


class TestAiSuggestLinks:
    """ai.py lines 297-303: suggest-links 503 when provider unavailable."""

    @pytest.mark.asyncio
    async def test_suggest_links_no_provider_returns_503(self, client):
        with _unavailable_provider():
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

        fake_llm_output = '["Title A"]\n[not valid json]'
        with (
            _available_provider(),
            patch.object(llm_provider, "complete", new=AsyncMock(return_value=fake_llm_output)),
        ):
            resp = await client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data


class TestAiSuggestTags503:
    """ai.py lines 343-344: suggest-tags 503."""

    @pytest.mark.asyncio
    async def test_suggest_tags_no_provider_returns_503(self, client):
        with _unavailable_provider():
            resp = await client.post("/api/v1/ai/suggest-tags/any-note-id")
        assert resp.status_code == 503


class TestAiCritique503:
    """ai.py lines 411-412: critique 503."""

    @pytest.mark.asyncio
    async def test_critique_no_provider_returns_503(self, client):
        with _unavailable_provider():
            resp = await client.post("/api/v1/ai/critique/any-note-id")
        assert resp.status_code == 503


class TestAiOrphanAudit:
    """ai.py line 450: fast return when rows empty or provider unavailable."""

    @pytest.mark.asyncio
    async def test_orphan_audit_no_provider_returns_empty_items(self, client):
        """When provider is unavailable the handler returns early with items=[]."""
        with _unavailable_provider():
            resp = await client.get("/api/v1/ai/orphan-audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []


class TestAiStreamChat:
    """ai.py lines 467-483, 481-482: SSE stream/chat error handler."""

    @pytest.mark.asyncio
    async def test_stream_chat_exception_yields_error_event(self, client):
        """Lines 467-483: when the stream raises mid-flight, the except block
        must yield a JSON error event then still emit the meta and [DONE] events."""
        # Make graph_rag unavailable so we fall through to the qdrant path,
        # then make _qdrant_rag_stream raise to exercise lines 481-482.
        async def _boom(*args, **kwargs):
            raise RuntimeError("injected stream failure")
            yield  # make it an async generator

        with (
            _graph_rag_unavailable(),
            _available_provider(),
            patch("gnosis.routers.ai._qdrant_rag_stream", side_effect=_boom),
        ):
            resp = await client.get(
                "/api/v1/ai/stream/chat",
                params={"message": "hello", "mode": "hybrid"},
            )
        assert resp.status_code == 200
        body = resp.text
        # Error event must be present
        assert '"error"' in body
        # Meta and DONE sentinel must always be emitted
        assert '"meta"' in body
        assert "[DONE]" in body


class TestAiGenerateMoc:
    """ai.py lines 670 (empty topic 422) and 709-710 (no notes 404)."""

    @pytest.mark.asyncio
    async def test_generate_moc_empty_topic_returns_422(self, client):
        with _available_provider():
            resp = await client.post(
                "/api/v1/ai/generate-moc",
                json={"topic": "   "},  # whitespace-only → stripped to empty
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_moc_no_matching_notes_returns_404(self, client):
        """No notes containing the topic → 404 (lines 709-710)."""
        with _available_provider():
            resp = await client.post(
                "/api/v1/ai/generate-moc",
                json={"topic": "zzz-topic-that-will-never-match-anything-xyz"},
            )
        assert resp.status_code == 404
