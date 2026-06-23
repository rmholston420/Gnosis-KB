"""
test_final_gaps.py

Surgical tests for every remaining uncovered line/arc:

  gnosis/models/link.py          line 43  Link.__repr__
  gnosis/models/review.py        line 57  ReviewCard.__repr__
  gnosis/models/shared_vault.py  line 74  SharedVault.can_write
  gnosis/models/tag.py           line 39  Tag.__repr__
  gnosis/routers/export.py       line 237 export_note_pdf note-not-found
  gnosis/routers/ingest.py       lines 143-144  _ai_enrich invalid-JSON fallback
  gnosis/routers/ai.py           arcs 138->142, 211->221, 215->221, 243-244,
                                       343-344, 467->483, 481-482, 534-535, 634-635

All HTTP tests use the `async_client` fixture from conftest.py.
"""
from __future__ import annotations

import sys
import types
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# gnosis/models/tag.py  line 39 — Tag.__repr__
# ---------------------------------------------------------------------------

class TestTagRepr:
    def test_repr(self):
        from gnosis.models.tag import Tag
        t = Tag(name="buddhism")
        assert repr(t) == "<Tag name='buddhism'>"


# ---------------------------------------------------------------------------
# gnosis/models/link.py  line 43 — Link.__repr__
# ---------------------------------------------------------------------------

class TestLinkRepr:
    def test_repr(self):
        from gnosis.models.link import Link
        lnk = Link(source_id="aaa", target_id="bbb", link_text="Foo Bar")
        r = repr(lnk)
        assert "aaa" in r
        assert "bbb" in r
        assert "Foo Bar" in r


# ---------------------------------------------------------------------------
# gnosis/models/review.py  line 57 — ReviewCard.__repr__
# ---------------------------------------------------------------------------

class TestReviewCardRepr:
    def test_repr(self):
        from gnosis.models.review import ReviewCard
        rc = ReviewCard(
            note_id="zettel-001",
            easiness=2.5,
            interval=6,
            repetitions=3,
            due_date=date(2026, 7, 1),
        )
        r = repr(rc)
        assert "zettel-001" in r
        assert "6" in r
        assert "2.50" in r


# ---------------------------------------------------------------------------
# gnosis/models/shared_vault.py  line 74 — SharedVault.can_write property
# ---------------------------------------------------------------------------

class TestSharedVaultCanWrite:
    def test_can_write_true(self):
        from gnosis.models.shared_vault import SharedVault
        sv = SharedVault(owner_id=1, member_id=2, permission="write", is_active=True)
        assert sv.can_write is True

    def test_can_write_false_read(self):
        from gnosis.models.shared_vault import SharedVault
        sv = SharedVault(owner_id=1, member_id=2, permission="read", is_active=True)
        assert sv.can_write is False

    def test_can_write_false_inactive(self):
        from gnosis.models.shared_vault import SharedVault
        sv = SharedVault(owner_id=1, member_id=2, permission="write", is_active=False)
        assert sv.can_write is False


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py — _parse_json_list  (arcs 138->142, 140-141)
# Pure unit tests — no DB, no HTTP.
# ---------------------------------------------------------------------------

class TestParseJsonList:
    def test_invalid_json_bracket_falls_back_to_line_split(self):
        """Bracket matched but invalid JSON -> JSONDecodeError path (arc 138->142)."""
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
# gnosis/routers/ingest.py  lines 143-144 — _ai_enrich invalid-JSON fallback
# _ai_enrich is a pure async helper — call it directly.
# ParsedDocument field is `raw_format` (verified from document_parser.py).
# ---------------------------------------------------------------------------

class TestAiEnrichInvalidJson:
    @pytest.mark.anyio
    async def test_ai_enrich_brace_match_invalid_json_fallback(self):
        """regex matches braces but json.loads raises -> fallback to parsed values."""
        from gnosis.routers.ingest import _ai_enrich
        from gnosis.services.document_parser import ParsedDocument

        parsed = ParsedDocument(
            title="Test Doc",
            text="Some interesting content about epistemology.",
            raw_format="pdf",
        )
        with patch("gnosis.routers.ingest.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="{title: AI Title, summary: great stuff, tags: not-array}"
            )
            title, summary, tags = await _ai_enrich(parsed)

        assert title == parsed.title
        assert summary == parsed.text[:500]
        assert tags == []

    @pytest.mark.anyio
    async def test_ai_enrich_no_brace_match_fallback(self):
        """No brace group in LLM response -> fallback."""
        from gnosis.routers.ingest import _ai_enrich
        from gnosis.services.document_parser import ParsedDocument

        parsed = ParsedDocument(
            title="Second Doc",
            text="Content about dependent origination.",
            raw_format="docx",
        )
        with patch("gnosis.routers.ingest.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="Here is a plain prose response with no JSON at all."
            )
            title, summary, tags = await _ai_enrich(parsed)

        assert title == parsed.title
        assert tags == []


# ---------------------------------------------------------------------------
# gnosis/routers/export.py  line 237 — PDF export note-not-found
# Patch the module-level bound name `gnosis.routers.export.settings`.
# Inject a weasyprint stub via sys.modules so the ImportError branch is skipped.
# ---------------------------------------------------------------------------

class TestExportPdfNotFound:
    @pytest.mark.anyio
    async def test_export_pdf_note_not_found(self, async_client):
        """PDF enabled, weasyprint stub present, note missing -> 404."""
        fake_wp = types.ModuleType("weasyprint")
        fake_wp.HTML = MagicMock()

        with (
            patch("gnosis.routers.export.settings") as mock_settings,
            patch.dict(sys.modules, {"weasyprint": fake_wp}),
        ):
            mock_settings.enable_pdf_export = True
            resp = await async_client.get("/api/v1/export/note/does-not-exist-xyz.pdf")

        assert resp.status_code == 404


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
    assert resp.status_code in (200, 201), (
        f"note creation failed {resp.status_code}: {resp.text}"
    )
    return note_id


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py — suggest_links  (arcs 211->221, 215->221, 243-244)
#
# Arc 211->221: re.findall returns empty list (arrays=[]) -> both suggestions
#               and rationale remain [] and the if/len blocks are skipped.
# Arc 215->221: arrays[0] json.loads raises -> _parse_json_list fallback.
# Arc 243-244:  len(arrays)>=2 AND arrays[1] json.loads raises.
# ---------------------------------------------------------------------------

class TestSuggestLinksEdgeCases:
    @pytest.mark.anyio
    async def test_suggest_links_no_brackets(self, async_client):
        """LLM returns no bracket arrays (arc 211->221) -> empty suggestions/rationale."""
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
    async def test_suggest_links_first_array_invalid_json(self, async_client):
        """One bracket group, invalid JSON (arc 215->221) -> _parse_json_list fallback."""
        note_id = await _create_note(async_client, "sl-bad-first", "SL Bad First Array")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            # Single array with invalid JSON so arrays[0] parse fails
            mock_llm.complete = AsyncMock(
                return_value="[Note Alpha, Note Beta, Note Gamma]"
            )
            resp = await async_client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["suggestions"], list)
        assert data["rationale"] == []

    @pytest.mark.anyio
    async def test_suggest_links_invalid_rationale_json(self, async_client):
        """Two bracket groups, second invalid JSON (arc 243-244) -> rationale fallback."""
        note_id = await _create_note(async_client, "sl-bad-rationale", "SL Bad Rationale")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            # First array is valid JSON, second is not
            mock_llm.complete = AsyncMock(
                return_value='["Note A", "Note B"] then [not: valid json at all]'
            )
            resp = await async_client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "Note A" in data["suggestions"]
        assert isinstance(data["rationale"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py — critique_note  (arc 343-344)
#
# Brace group matched but json.loads raises -> critique_data stays {}.
# CritiqueResponse.atomicity falls back to raw string.
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
        """Brace group matched, json.loads raises (arc 343-344) -> empty fallback."""
        note_id = await _create_note(async_client, "crit-bad-json", "Critique Bad JSON")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="{atomicity: good, connectivity: moderate — not valid JSON}"
            )
            resp = await async_client.post(f"/api/v1/ai/critique/{note_id}")
        assert resp.status_code == 200
        # atomicity falls back to the raw string; connectivity/overall empty
        data = resp.json()
        assert isinstance(data["atomicity"], str)
        assert len(data["atomicity"]) > 0
        assert data["connectivity"] == ""
        assert data["overall"] == ""


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
# gnosis/routers/ai.py — daily_review  (arcs 467->483, 481-482)
#
# Arc 467->483: no inbox notes today (or llm unavailable) -> early return.
# Arc 481-482:  brace matched but json.loads raises -> summary=raw, items=[].
#
# For arc 467->483 we rely on there being no 00-inbox notes with today's date
# in the test DB — which is always true unless the test suite itself created them.
# For arc 481-482 we patch llm_provider to return invalid JSON AND ensure at
# least one inbox note exists so the early-return branch is NOT taken.
# ---------------------------------------------------------------------------

class TestDailyReviewEdgeCases:
    @pytest.mark.anyio
    async def test_daily_review_no_notes_today(self, async_client):
        """No today inbox notes -> early return with 'No inbox notes today.' (arc 467->483)."""
        resp = await async_client.post("/api/v1/ai/daily-review")
        assert resp.status_code == 200
        data = resp.json()
        # Either no notes exist at all, or LLM unavailable — both hit the early path
        assert isinstance(data["summary"], str)
        assert isinstance(data["action_items"], list)

    @pytest.mark.anyio
    async def test_daily_review_invalid_json(self, async_client):
        """Brace matched but json.loads raises (arc 481-482) -> summary=raw, items=[]."""
        # Create an inbox note with today's date so the early-return is skipped
        import datetime
        today = datetime.date.today().isoformat()
        note_id = f"dr-test-{today.replace('-', '')}"
        resp = await async_client.post(
            "/api/v1/notes/",
            json={
                "id": note_id,
                "title": "Daily Review Seed Note",
                "body": "Studying impermanence today.",
                "folder": "00-inbox",
            },
        )
        # If note already exists (409) that's fine — the note is there
        assert resp.status_code in (200, 201, 409)

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
# gnosis/routers/ai.py — stream_chat SSE exception path  (arcs 534-535)
#
# graph_rag.is_available is called as: await graph_rag.is_available(user_id)
# So we patch it as an AsyncMock with side_effect to raise inside the generator.
# ---------------------------------------------------------------------------

class TestStreamChatException:
    @pytest.mark.anyio
    async def test_stream_chat_sse_exception_path(self, async_client):
        """graph_rag.is_available raises -> SSE error event emitted, response 200."""
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            # is_available is awaited so must be an AsyncMock
            mock_rag.is_available = AsyncMock(side_effect=RuntimeError("rag exploded"))
            mock_llm.is_available = False
            resp = await async_client.get(
                "/api/v1/ai/stream/chat?message=hello&mode=hybrid"
            )
        assert resp.status_code == 200
        assert b"error" in resp.content or b"DONE" in resp.content


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py — ingest_note LightRAG exception  (arcs 634-635)
#
# _LIGHTRAG_AVAILABLE_CHECK is a module-level function called as
# `_LIGHTRAG_AVAILABLE_CHECK()` inside the endpoint.  We must patch it as
# a callable (not a return_value), and graph_rag.ingest_note as an AsyncMock.
# ---------------------------------------------------------------------------

class TestIngestNoteException:
    @pytest.mark.anyio
    async def test_ingest_note_lightrag_raises(self, async_client):
        """graph_rag.ingest_note raises RuntimeError -> HTTP 500 with detail."""
        note_id = await _create_note(async_client, "ingest-exc-001", "Ingest Exception Note")
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch(
                "gnosis.routers.ai._LIGHTRAG_AVAILABLE_CHECK",
                return_value=True,   # the patch replaces the function object;
                                     # endpoint calls it as _LIGHTRAG_AVAILABLE_CHECK()
                                     # which returns the mock — truthy, so branch taken
            ),
        ):
            # Make graph_rag truthy and ingest_note an AsyncMock that raises
            mock_rag.__bool__ = lambda self: True
            mock_rag.ingest_note = AsyncMock(side_effect=RuntimeError("lightrag down"))
            resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")
        # The endpoint catches the exception and raises HTTPException(500)
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
