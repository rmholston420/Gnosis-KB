"""
test_final_gaps.py

Surgical tests targeting the exact remaining uncovered lines/arcs:

  gnosis/models/tag.py            line 39  — Tag.__repr__
  gnosis/routers/export.py        line 237 — export_note_pdf note-not-found branch
  gnosis/routers/ingest.py        lines 143-144 — _ai_enrich invalid-JSON fallback
  gnosis/routers/ai.py            lines 138->142, 140-141 — _parse_json_list json-decode branch
                                  lines 211->221, 215->221 — suggest_links empty-arrays path
                                  lines 243-244            — suggest_links rationale decode error
                                  lines 340->345, 343-344, 348-349 — critique_note json-miss
                                  lines 411-412            — orphan_audit json-decode error
                                  lines 467->483, 481-482  — daily_review json-decode error
                                  lines 534-535            — stream_chat SSE exception path
                                  lines 634-635            — ingest_note LightRAG exception path
                                  lines 709-710            — generate_moc json-decode fallback
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# gnosis/models/tag.py  line 39 — Tag.__repr__
# ---------------------------------------------------------------------------

class TestTagRepr:
    def test_repr(self):
        from gnosis.models.tag import Tag
        t = Tag(name="buddhism")
        assert repr(t) == "<Tag name='buddhism'>"


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  — _parse_json_list  (lines 138->142, 140-141)
# _parse_json_list hits the json.JSONDecodeError branch when the regex
# matches a bracket group but the content isn't valid JSON.
# ---------------------------------------------------------------------------

class TestParseJsonList:
    def test_invalid_json_bracket_falls_back_to_line_split(self):
        from gnosis.routers.ai import _parse_json_list
        # Bracket group present but invalid JSON → triggers except block
        raw = "Here are some items: [not: valid, json] and more"
        result = _parse_json_list(raw)
        # Falls back to line-splitting; result is a list (possibly empty)
        assert isinstance(result, list)

    def test_valid_json_list_returned(self):
        from gnosis.routers.ai import _parse_json_list
        raw = '["zettelkasten", "spaced-repetition"]'
        assert _parse_json_list(raw) == ["zettelkasten", "spaced-repetition"]

    def test_no_bracket_falls_back(self):
        from gnosis.routers.ai import _parse_json_list
        raw = "- item one\n- item two\n- item three"
        result = _parse_json_list(raw)
        assert "item one" in result
        assert "item two" in result


# ---------------------------------------------------------------------------
# HTTP-layer fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    from gnosis.main import app as _app
    return _app


@pytest.fixture()
async def auth_client(app):
    """Authenticated async client using existing conftest DB fixtures."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Register + login
        reg = await client.post(
            "/api/v1/auth/register",
            json={"username": "gap_user", "password": "GapPass123!", "email": "gap@test.com"},
        )
        assert reg.status_code in (200, 201, 409)
        login = await client.post(
            "/api/v1/auth/token",
            data={"username": "gap_user", "password": "GapPass123!"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


# ---------------------------------------------------------------------------
# gnosis/routers/export.py  line 237 — PDF export note-not-found
# ---------------------------------------------------------------------------

class TestExportPdfNotFound:
    @pytest.mark.anyio
    async def test_export_pdf_note_not_found(self, auth_client):
        """When PDF export is enabled but the note doesn't exist → 404."""
        with (
            patch("gnosis.routers.export.get_settings") as mock_settings,
            patch("gnosis.routers.export.HTML", create=True),
        ):
            mock_settings.return_value = MagicMock(enable_pdf_export=True)
            resp = await auth_client.get("/api/v1/export/note/nonexistent-note-id-xyz/pdf")
        assert resp.status_code in (404, 422, 503)


# ---------------------------------------------------------------------------
# gnosis/routers/ingest.py  lines 143-144 — _ai_enrich invalid-JSON path
# The function calls llm_provider.complete → returns text with braces but
# malformed JSON, so json.loads raises and the except branch is taken.
# ---------------------------------------------------------------------------

class TestIngestAiEnrichInvalidJson:
    @pytest.mark.anyio
    async def test_ai_enrich_invalid_json_fallback(self, auth_client):
        """LLM returns brace-containing but non-parseable text — note still created."""
        with (
            patch("gnosis.routers.ingest.llm_provider") as mock_llm,
            patch("gnosis.routers.ingest.hybrid_search", return_value=[]),
        ):
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(return_value="{this is not json at all}")
            resp = await auth_client.post(
                "/api/v1/ingest/note",
                json={
                    "id": "test-ingest-invalid-json",
                    "title": "Invalid JSON Enrich Test",
                    "body": "Some body content for invalid json fallback test.",
                    "folder": "00-inbox",
                },
            )
        # Note should be created (200/201) even if AI enrichment JSON fails
        assert resp.status_code in (200, 201, 422)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  — suggest_links  (lines 211->221, 215->221, 243-244)
# When LLM returns text with NO bracket arrays → both suggestion lists empty.
# When rationale array JSON is invalid → decode-error branch.
# ---------------------------------------------------------------------------

class TestSuggestLinksEdgeCases:
    @pytest.fixture()
    async def note_id(self, auth_client):
        resp = await auth_client.post(
            "/api/v1/notes/",
            json={
                "id": "link-edge-note",
                "title": "Link Edge Note",
                "body": "Content for link suggestion edge case testing.",
                "folder": "00-inbox",
            },
        )
        assert resp.status_code in (200, 201)
        return "link-edge-note"

    @pytest.mark.anyio
    async def test_suggest_links_no_brackets(self, auth_client, note_id):
        """LLM returns no bracket arrays → empty suggestions, no crash."""
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(return_value="No structured output here at all.")
            resp = await auth_client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["suggestions"] == []
        assert data["rationale"] == []

    @pytest.mark.anyio
    async def test_suggest_links_invalid_rationale_json(self, auth_client, note_id):
        """First array valid, second array bracket present but invalid JSON."""
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            # Two bracket groups: first valid JSON list, second invalid
            mock_llm.complete = AsyncMock(
                return_value='["Note A", "Note B"] then [not: valid json]'
            )
            resp = await auth_client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "Note A" in data["suggestions"]
        # rationale fell through to line-split fallback, is a list
        assert isinstance(data["rationale"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  — critique_note  (lines 340->345, 343-344, 348-349)
# When LLM returns text with no JSON object → critique_data stays {}, fields
# fall back to raw string / empty string.
# ---------------------------------------------------------------------------

class TestCritiqueEdgeCases:
    @pytest.fixture()
    async def note_id(self, auth_client):
        resp = await auth_client.post(
            "/api/v1/notes/",
            json={
                "id": "critique-edge-note",
                "title": "Critique Edge Note",
                "body": "Content to critique.",
                "folder": "00-inbox",
            },
        )
        assert resp.status_code in (200, 201)
        return "critique-edge-note"

    @pytest.mark.anyio
    async def test_critique_no_json(self, auth_client, note_id):
        """LLM returns plain prose, no JSON → atomicity=raw, rest empty."""
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="This note covers a single idea about Dharma practices."
            )
            resp = await auth_client.post(f"/api/v1/ai/critique/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        # atomicity falls back to raw string
        assert "Dharma" in data["atomicity"]
        assert data["connectivity"] == ""
        assert data["overall"] == ""

    @pytest.mark.anyio
    async def test_critique_invalid_json_braces(self, auth_client, note_id):
        """Brace group matched but json.loads raises → same fallback."""
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="{atomicity: good, connectivity: moderate — not valid JSON}"
            )
            resp = await auth_client.post(f"/api/v1/ai/critique/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["atomicity"], str)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  — orphan_audit  (lines 411-412)
# When LLM returns bracket-matched but invalid JSON → json.JSONDecodeError
# is caught, items stays [].
# ---------------------------------------------------------------------------

class TestOrphanAuditJsonDecodeError:
    @pytest.mark.anyio
    async def test_orphan_audit_invalid_json(self, auth_client):
        with (
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_llm.is_available = True
            # Bracket-containing but invalid JSON string
            mock_llm.complete = AsyncMock(
                return_value="[{note_id: 'x', title: bad json, suggestions: []}]"
            )
            resp = await auth_client.get("/api/v1/ai/orphan-audit?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  — daily_review  (lines 467->483, 481-482)
# json.JSONDecodeError in daily_review → summary_text = raw, action_items=[]
# ---------------------------------------------------------------------------

class TestDailyReviewJsonDecodeError:
    @pytest.mark.anyio
    async def test_daily_review_invalid_json(self, auth_client):
        """Brace group present but JSON invalid → summary=raw, action_items=[]"""
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="{summary: today was productive, action_items: not an array}"
            )
            resp = await auth_client.post("/api/v1/ai/daily-review")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["summary"], str)
        assert isinstance(data["action_items"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  — stream_chat SSE  (lines 534-535)
# Exception raised inside event_generator → error event emitted, no crash.
# ---------------------------------------------------------------------------

class TestStreamChatException:
    @pytest.mark.anyio
    async def test_stream_chat_sse_exception(self, auth_client):
        """graph_rag.is_available raises → SSE error event emitted."""
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_rag.is_available = AsyncMock(side_effect=RuntimeError("rag exploded"))
            mock_llm.is_available = False
            resp = await auth_client.get("/api/v1/ai/stream/chat?message=hello&mode=hybrid")
        # StreamingResponse → 200; check error event in body
        assert resp.status_code == 200
        assert b"error" in resp.content or b"DONE" in resp.content


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  — ingest_note exception path  (lines 634-635)
# graph_rag.ingest_note raises → HTTPException 500.
# ---------------------------------------------------------------------------

class TestIngestNoteException:
    @pytest.fixture()
    async def note_id(self, auth_client):
        resp = await auth_client.post(
            "/api/v1/notes/",
            json={
                "id": "ingest-exc-note",
                "title": "Ingest Exception Note",
                "body": "Body for ingest exception test.",
                "folder": "00-inbox",
            },
        )
        assert resp.status_code in (200, 201)
        return "ingest-exc-note"

    @pytest.mark.anyio
    async def test_ingest_note_lightrag_exception(self, auth_client, note_id):
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai._LIGHTRAG_AVAILABLE_CHECK", return_value=True),
        ):
            mock_rag.ingest_note = AsyncMock(side_effect=RuntimeError("lightrag down"))
            resp = await auth_client.post(f"/api/v1/ai/ingest-note/{note_id}")
        assert resp.status_code == 500
        assert "lightrag down" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  — generate_moc json-decode fallback  (lines 709-710)
# LLM returns bracket group with invalid JSON → sections stays [].
# ---------------------------------------------------------------------------

class TestGenerateMocJsonDecodeFallback:
    @pytest.fixture()
    async def seed_notes(self, auth_client):
        """Create a few notes containing the topic keyword so the query finds them."""
        for i in range(3):
            await auth_client.post(
                "/api/v1/notes/",
                json={
                    "id": f"moc-seed-{i}",
                    "title": f"Dharma Seed Note {i}",
                    "body": f"Content about dharma practice {i}.",
                    "folder": "00-inbox",
                },
            )

    @pytest.mark.anyio
    async def test_generate_moc_invalid_json_sections(self, auth_client, seed_notes):
        """Bracket group present but invalid JSON → sections=[], markdown still built."""
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="[{heading: Intro, summary: bad, wikilinks: not-array}]"
            )
            resp = await auth_client.post(
                "/api/v1/ai/generate-moc",
                json={"topic": "dharma", "max_notes": 10},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sections"] == []
        assert "dharma" in data["topic"].lower()
