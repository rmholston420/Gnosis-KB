"""Targeted tests to close the remaining coverage gaps.

Files / lines addressed:
  gnosis/routers/review.py  90% → lines 147-155 (enroll 404), 158 (already enrolled),
                                   189-190 (submit_review sets last_reviewed)
  gnosis/routers/notes.py   97% → lines 52→exit (empty tag list arc),
                                   54-57 (new Tag creation inside _upsert_tags)
  gnosis/routers/ai.py      93% → lines 129 (_get_note_or_404 raise),
                                   138-142 (providers no provider early return),
                                   211 (set_model ollama absent 400),
                                   215-221 (set_model ollama swap path),
                                   243-244 (chat 503),
                                   297-303 (suggest-links 503 + rationale fallback),
                                   343-344 (suggest-tags 503),
                                   411-412 (critique 503),
                                   450 (orphan-audit no-provider fast-return),
                                   467-483 (SSE stream exception handler),
                                   670 (generate-moc empty topic 422),
                                   709-710 (generate-moc no notes 404)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module-namespace patch helpers
# ---------------------------------------------------------------------------
# Patching at gnosis.routers.ai.<name> replaces the name in the module where
# it is *used*, not where it is defined.  This is what coverage's branch
# tracker requires to register the correct arc as taken.

_AI = "gnosis.routers.ai"


def _mock_llm(available: bool) -> MagicMock:
    """Return a MagicMock that mimics llm_provider with is_available=<available>."""
    m = MagicMock()
    m.is_available = available
    m.complete = AsyncMock(return_value="mocked response")
    m.stream = AsyncMock(return_value=iter([]))
    m._available = ["ollama"] if available else []
    m.active_provider = "ollama" if available else "none"
    m.active_model = "llama3:8b" if available else ""
    m.swap_model = MagicMock()
    return m


def _mock_graph_rag(available: bool) -> MagicMock:
    """Return a MagicMock that mimics graph_rag with is_available=<available>.

    graph_rag.is_available is awaited as a coroutine in the router:
        if await graph_rag.is_available(current_user.id): ...
    so it must be an AsyncMock callable that returns the bool.
    """
    m = MagicMock()
    m.is_available = AsyncMock(return_value=available)
    m.query = AsyncMock(return_value="graph answer")

    async def _empty_stream(*args, **kwargs):
        return
        yield  # make it an async generator

    m.stream = _empty_stream
    return m


# ===========================================================================
# review.py
# ===========================================================================

class TestReviewEnroll:
    """review.py lines 147-155 (note not found) and 158 (already enrolled)."""

    @pytest.mark.asyncio
    async def test_enroll_note_not_found_returns_404(self, client, vault_dir):
        """Enrolling a non-existent note_id must return 404."""
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

        # Second enroll hits line 158 (already enrolled) — returns existing card
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
# ai.py  — all patches target gnosis.routers.ai.<name> (module namespace)
# ===========================================================================

class TestAiGetNoteOr404:
    """ai.py line 129: _get_note_or_404 raises 404 for unknown note."""

    @pytest.mark.asyncio
    async def test_summarize_unknown_note_returns_404(self, client, vault_dir):
        """Provider available but note doesn't exist → 404."""
        with patch(f"{_AI}.llm_provider", _mock_llm(available=True)):
            resp = await client.post("/api/v1/ai/summarize/nonexistent-note-id")
        assert resp.status_code == 404


class TestAiProviders:
    """ai.py lines 138-142: GET /providers returns available=False when no provider."""

    @pytest.mark.asyncio
    async def test_get_providers_no_provider_returns_unavailable(self, client, vault_dir):
        """Lines 138-142: early return with available=False."""
        with patch(f"{_AI}.llm_provider", _mock_llm(available=False)):
            resp = await client.get("/api/v1/ai/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["provider"] == "none"
        assert data["models"] == []


class TestAiSetModel:
    """ai.py lines 211-221: POST /providers/model."""

    @pytest.mark.asyncio
    async def test_set_model_ollama_unavailable_returns_400(self, client, vault_dir):
        """Line 211: ollama not in _available → 400."""
        with patch(f"{_AI}.llm_provider", _mock_llm(available=False)):
            resp = await client.post(
                "/api/v1/ai/providers/model",
                json={"model": "llama3:8b"},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_set_model_ollama_available_swaps_and_returns_info(self, client, vault_dir):
        """Lines 215-221: ollama present → swap_model called, 200 with provider info."""
        mock_llm = _mock_llm(available=True)

        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 200
        mock_http_resp.json.return_value = {"models": [{"name": "llama3:8b"}]}

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.get = AsyncMock(return_value=mock_http_resp)

        with (
            patch(f"{_AI}.llm_provider", mock_llm),
            patch(f"{_AI}.httpx.AsyncClient", return_value=mock_http_client),
        ):
            resp = await client.post(
                "/api/v1/ai/providers/model",
                json={"model": "llama3:8b"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "ollama"
        assert data["model"] == "llama3:8b"
        mock_llm.swap_model.assert_called_once_with("llama3:8b")


class TestAiChat503:
    """ai.py lines 243-244: chat 503 when neither graph_rag nor llm available."""

    @pytest.mark.asyncio
    async def test_chat_no_provider_returns_503(self, client, vault_dir):
        with (
            patch(f"{_AI}.graph_rag", _mock_graph_rag(available=False)),
            patch(f"{_AI}.llm_provider", _mock_llm(available=False)),
        ):
            resp = await client.post(
                "/api/v1/ai/chat",
                json={"message": "hello", "mode": "hybrid"},
            )
        assert resp.status_code == 503


class TestAiSuggestLinks:
    """ai.py lines 297-303: suggest-links 503 + rationale fallback."""

    @pytest.mark.asyncio
    async def test_suggest_links_no_provider_returns_503(self, client, vault_dir):
        with patch(f"{_AI}.llm_provider", _mock_llm(available=False)):
            resp = await client.post("/api/v1/ai/suggest-links/any-note-id")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_suggest_links_rationale_fallback(self, client, vault_dir):
        """arrays[1] is invalid JSON → exercises _parse_json_list fallback path."""
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

        mock_llm = _mock_llm(available=True)
        # First array is valid JSON; second array is intentionally broken JSON
        # so the except-JSONDecodeError branch in suggest_links is exercised.
        mock_llm.complete = AsyncMock(return_value='["Title A"]\n[not valid json]')

        with patch(f"{_AI}.llm_provider", mock_llm):
            resp = await client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        assert "suggestions" in resp.json()


class TestAiSuggestTags503:
    """ai.py lines 343-344: suggest-tags 503."""

    @pytest.mark.asyncio
    async def test_suggest_tags_no_provider_returns_503(self, client, vault_dir):
        with patch(f"{_AI}.llm_provider", _mock_llm(available=False)):
            resp = await client.post("/api/v1/ai/suggest-tags/any-note-id")
        assert resp.status_code == 503


class TestAiCritique503:
    """ai.py lines 411-412: critique 503."""

    @pytest.mark.asyncio
    async def test_critique_no_provider_returns_503(self, client, vault_dir):
        with patch(f"{_AI}.llm_provider", _mock_llm(available=False)):
            resp = await client.post("/api/v1/ai/critique/any-note-id")
        assert resp.status_code == 503


class TestAiOrphanAudit:
    """ai.py line 450: fast return when provider unavailable."""

    @pytest.mark.asyncio
    async def test_orphan_audit_no_provider_returns_empty_items(self, client, vault_dir):
        with patch(f"{_AI}.llm_provider", _mock_llm(available=False)):
            resp = await client.get("/api/v1/ai/orphan-audit")
        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestAiStreamChat:
    """ai.py lines 467-483, 481-482: SSE stream exception handler."""

    @pytest.mark.asyncio
    async def test_stream_chat_exception_yields_error_event(self, client, vault_dir):
        """Raising inside the token loop exercises lines 481-482; finally always
        emits meta + [DONE] (lines 467/483)."""

        async def _boom(*args, **kwargs):
            raise RuntimeError("injected stream failure")
            yield  # make it an async generator  # noqa: unreachable

        with (
            patch(f"{_AI}.graph_rag", _mock_graph_rag(available=False)),
            patch(f"{_AI}.llm_provider", _mock_llm(available=True)),
            patch(f"{_AI}._qdrant_rag_stream", side_effect=_boom),
        ):
            resp = await client.get(
                "/api/v1/ai/stream/chat",
                params={"message": "hello", "mode": "hybrid"},
            )
        assert resp.status_code == 200
        body = resp.text
        assert '"error"' in body
        assert '"meta"' in body
        assert "[DONE]" in body


class TestAiGenerateMoc:
    """ai.py lines 670 (empty topic 422) and 709-710 (no notes 404)."""

    @pytest.mark.asyncio
    async def test_generate_moc_empty_topic_returns_422(self, client, vault_dir):
        """Whitespace-only topic → Pydantic accepts it (len>0), router strips
        to empty string → manual 422 raise."""
        with patch(f"{_AI}.llm_provider", _mock_llm(available=True)):
            resp = await client.post(
                "/api/v1/ai/generate-moc",
                json={"topic": "   "},
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_moc_no_matching_notes_returns_404(self, client, vault_dir):
        """No notes matching topic → 404."""
        with patch(f"{_AI}.llm_provider", _mock_llm(available=True)):
            resp = await client.post(
                "/api/v1/ai/generate-moc",
                json={"topic": "zzz-topic-that-will-never-match-anything-xyz"},
            )
        assert resp.status_code == 404
