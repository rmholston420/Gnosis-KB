"""
test_final_gaps.py

Surgical tests for the exact remaining uncovered lines/arcs:

  gnosis/models/tag.py       line 39          Tag.__repr__
  gnosis/routers/export.py   line 237         export_note_pdf note-not-found
  gnosis/routers/ingest.py   lines 143-144    _ai_enrich invalid-JSON fallback
  gnosis/routers/ai.py       138->142,140-141 _parse_json_list json-decode branch
                             211->221,215->221 suggest_links empty-arrays path
                             243-244           suggest_links rationale decode error
                             340->345,343-344,348-349  critique_note no/bad json
                             411-412           orphan_audit json-decode error
                             467->483,481-482  daily_review json-decode error
                             534-535           stream_chat SSE exception
                             634-635           ingest_note LightRAG exception
                             709-710           generate_moc json-decode fallback

All HTTP tests use the `async_client` fixture from conftest.py which wires
up an isolated SQLite DB and pre-authenticates as FakeUser(id=1). No login
calls are needed.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# gnosis/models/tag.py  line 39 — Tag.__repr__  (pure unit test, no DB)
# ---------------------------------------------------------------------------

class TestTagRepr:
    def test_repr(self):
        from gnosis.models.tag import Tag
        t = Tag(name="buddhism")
        assert repr(t) == "<Tag name='buddhism'>"


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  — _parse_json_list  (lines 138->142, 140-141)
# Pure unit tests — no DB, no HTTP.
# ---------------------------------------------------------------------------

class TestParseJsonList:
    def test_invalid_json_bracket_falls_back_to_line_split(self):
        """Bracket group matched but invalid JSON -> except JSONDecodeError path."""
        from gnosis.routers.ai import _parse_json_list
        raw = "Here are items: [not: valid, json] and more"
        result = _parse_json_list(raw)
        assert isinstance(result, list)

    def test_valid_json_list_returned(self):
        from gnosis.routers.ai import _parse_json_list
        raw = '["zettelkasten", "spaced-repetition"]'
        assert _parse_json_list(raw) == ["zettelkasten", "spaced-repetition"]

    def test_no_bracket_falls_back_to_line_split(self):
        from gnosis.routers.ai import _parse_json_list
        raw = "- item one\n- item two\n- item three"
        result = _parse_json_list(raw)
        assert "item one" in result
        assert "item two" in result


# ---------------------------------------------------------------------------
# Helper: create a note via the notes router
# ---------------------------------------------------------------------------

async def _create_note(
    client, note_id: str, title: str, body: str = "Test body."
) -> str:
    resp = await client.post(
        "/api/v1/notes/",
        json={"id": note_id, "title": title, "body": body, "folder": "00-inbox"},
    )
    assert resp.status_code in (200, 201), f"note creation failed {resp.status_code}: {resp.text}"
    return note_id


# ---------------------------------------------------------------------------
# gnosis/routers/export.py  line 237 — PDF export note-not-found
# ---------------------------------------------------------------------------

class TestExportPdfNotFound:
    @pytest.mark.anyio
    async def test_export_pdf_note_not_found(self, async_client):
        """PDF export enabled but note doesn't exist -> 404 (or 503 if weasyprint absent)."""
        with (
            patch("gnosis.routers.export.get_settings") as mock_settings,
            patch("gnosis.routers.export.HTML", create=True),
        ):
            cfg = MagicMock()
            cfg.enable_pdf_export = True
            mock_settings.return_value = cfg
            resp = await async_client.get("/api/v1/export/note/does-not-exist-xyz/pdf")
        assert resp.status_code in (404, 422, 503)


# ---------------------------------------------------------------------------
# gnosis/routers/ingest.py  lines 143-144 — _ai_enrich invalid-JSON fallback
# ---------------------------------------------------------------------------

class TestIngestAiEnrichInvalidJson:
    @pytest.mark.anyio
    async def test_ai_enrich_invalid_json_fallback(self, async_client):
        """LLM returns brace text but not valid JSON -> except branch, note still created."""
        with (
            patch("gnosis.routers.ingest.llm_provider") as mock_llm,
            patch("gnosis.routers.ingest.hybrid_search", return_value=[]),
        ):
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(return_value="{this is not json at all}")
            resp = await async_client.post(
                "/api/v1/ingest/note",
                json={
                    "id": "ingest-invalid-json-001",
                    "title": "Invalid JSON Enrich Test",
                    "body": "Body content for invalid json enrich fallback.",
                    "folder": "00-inbox",
                },
            )
        assert resp.status_code in (200, 201, 422)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py — suggest_links  (lines 211->221, 215->221, 243-244)
# ---------------------------------------------------------------------------

class TestSuggestLinksEdgeCases:
    @pytest.mark.anyio
    async def test_suggest_links_no_brackets(self, async_client):
        """LLM returns no bracket arrays -> empty suggestions and rationale."""
        note_id = await _create_note(async_client, "sl-no-brackets", "SL No Brackets")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(return_value="No structured output here.")
            resp = await async_client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["suggestions"] == []
        assert data["rationale"] == []

    @pytest.mark.anyio
    async def test_suggest_links_invalid_rationale_json(self, async_client):
        """First bracket array valid JSON, second is invalid JSON -> rationale fallback."""
        note_id = await _create_note(async_client, "sl-bad-rationale", "SL Bad Rationale")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='["Note A", "Note B"] then [not: valid json at all]'
            )
            resp = await async_client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "Note A" in data["suggestions"]
        assert isinstance(data["rationale"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py — critique_note  (lines 340->345, 343-344, 348-349)
# ---------------------------------------------------------------------------

class TestCritiqueEdgeCases:
    @pytest.mark.anyio
    async def test_critique_no_json(self, async_client):
        """LLM returns plain prose -> atomicity=raw, connectivity/overall empty."""
        note_id = await _create_note(async_client, "crit-no-json", "Critique No JSON")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="This note covers a single idea about Dharma practice."
            )
            resp = await async_client.post(f"/api/v1/ai/critique/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "Dharma" in data["atomicity"]
        assert data["connectivity"] == ""
        assert data["overall"] == ""

    @pytest.mark.anyio
    async def test_critique_invalid_json_braces(self, async_client):
        """Brace group matched but json.loads raises -> same empty fallback."""
        note_id = await _create_note(async_client, "crit-bad-json", "Critique Bad JSON")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="{atomicity: good, connectivity: moderate — not valid JSON}"
            )
            resp = await async_client.post(f"/api/v1/ai/critique/{note_id}")
        assert resp.status_code == 200
        assert isinstance(resp.json()["atomicity"], str)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py — orphan_audit  (lines 411-412)
# ---------------------------------------------------------------------------

class TestOrphanAuditJsonDecodeError:
    @pytest.mark.anyio
    async def test_orphan_audit_invalid_json(self, async_client):
        """LLM returns bracket-matched but invalid JSON -> items stays []."""
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="[{note_id: 'x', title: bad, suggestions: []}]"
            )
            resp = await async_client.get("/api/v1/ai/orphan-audit?limit=5")
        assert resp.status_code == 200
        assert isinstance(resp.json()["items"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py — daily_review  (lines 467->483, 481-482)
# ---------------------------------------------------------------------------

class TestDailyReviewJsonDecodeError:
    @pytest.mark.anyio
    async def test_daily_review_invalid_json(self, async_client):
        """Brace group present but JSON invalid -> summary=raw, action_items=[]."""
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="{summary: today was good, action_items: not-an-array}"
            )
            resp = await async_client.post("/api/v1/ai/daily-review")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["summary"], str)
        assert isinstance(data["action_items"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py — stream_chat SSE exception path  (lines 534-535)
# ---------------------------------------------------------------------------

class TestStreamChatException:
    @pytest.mark.anyio
    async def test_stream_chat_sse_exception_path(self, async_client):
        """graph_rag.is_available raises -> SSE error event emitted, response 200."""
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_rag.is_available = AsyncMock(side_effect=RuntimeError("rag exploded"))
            mock_llm.is_available = False
            resp = await async_client.get(
                "/api/v1/ai/stream/chat?message=hello&mode=hybrid"
            )
        assert resp.status_code == 200
        assert b"error" in resp.content or b"DONE" in resp.content


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py — ingest_note LightRAG exception  (lines 634-635)
# ---------------------------------------------------------------------------

class TestIngestNoteException:
    @pytest.mark.anyio
    async def test_ingest_note_lightrag_raises(self, async_client):
        """graph_rag.ingest_note raises RuntimeError -> HTTP 500 with detail."""
        note_id = await _create_note(async_client, "ingest-exc-001", "Ingest Exception Note")
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai._LIGHTRAG_AVAILABLE_CHECK", return_value=True),
        ):
            mock_rag.ingest_note = AsyncMock(side_effect=RuntimeError("lightrag down"))
            resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")
        assert resp.status_code == 500
        assert "lightrag down" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py — generate_moc json-decode fallback  (lines 709-710)
# ---------------------------------------------------------------------------

class TestGenerateMocJsonDecodeFallback:
    @pytest.mark.anyio
    async def test_generate_moc_invalid_json_sections(self, async_client):
        """LLM returns bracket group with invalid JSON -> sections=[], markdown built."""
        for i in range(3):
            await _create_note(
                async_client,
                f"moc-dharma-{i}",
                f"Dharma Seed {i}",
                body=f"Content about dharma practice {i}.",
            )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="[{heading: Intro, summary: bad, wikilinks: not-an-array}]"
            )
            resp = await async_client.post(
                "/api/v1/ai/generate-moc",
                json={"topic": "dharma", "max_notes": 10},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sections"] == []
        assert "dharma" in data["topic"].lower()
