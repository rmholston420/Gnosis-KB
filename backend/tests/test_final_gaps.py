"""
test_final_gaps.py

Surgical tests for every remaining uncovered line/arc:

  gnosis/models/attachment.py    line 36   Attachment.__repr__
  gnosis/models/link.py          line 43   Link.__repr__
  gnosis/models/review.py        line 57   ReviewCard.__repr__
  gnosis/models/shared_vault.py  line 74   SharedVault.can_write
  gnosis/models/tag.py           line 39   Tag.__repr__
  gnosis/database.py             lines 66,83,86  _AsyncSessionLocalProxy.__call__/__aenter__/__aexit__
  gnosis/main.py                 lines 86-88     lifespan graph_rag.initialize warning path
  gnosis/routers/export.py       line 237  export_note_pdf note-not-found
  gnosis/routers/ingest.py       lines 143-144   _ai_enrich invalid-JSON fallback
  gnosis/routers/ai.py           arcs 138->142, 211->221, 215->221, 243-244,
                                       343-344, 467->483, 481-482, 534-535, 634-635

All HTTP tests use the `async_client` fixture from conftest.py.
"""
from __future__ import annotations

import sys
import types
from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# gnosis/models/tag.py  line 39 - Tag.__repr__
# ---------------------------------------------------------------------------

class TestTagRepr:
    def test_repr(self):
        from gnosis.models.tag import Tag
        t = Tag(name="buddhism")
        assert repr(t) == "<Tag name='buddhism'>"


# ---------------------------------------------------------------------------
# gnosis/models/link.py  line 43 - Link.__repr__
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
# gnosis/models/review.py  line 57 - ReviewCard.__repr__
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
# gnosis/models/shared_vault.py  line 74 - SharedVault.can_write property
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
# gnosis/models/attachment.py  line 36 - Attachment.__repr__
# ---------------------------------------------------------------------------

class TestAttachmentRepr:
    def test_repr(self):
        from gnosis.models.attachment import Attachment
        a = Attachment(
            note_id="note-001",
            filename="photo.jpg",
            original_filename="photo.jpg",
            file_path="/vault/attachments/photo.jpg",
        )
        r = repr(a)
        assert "photo.jpg" in r
        assert "Attachment" in r


# ---------------------------------------------------------------------------
# gnosis/database.py  lines 66, 83, 86
# _AsyncSessionLocalProxy.__call__ / __aenter__ / __aexit__
# ---------------------------------------------------------------------------

class TestAsyncSessionLocalProxy:
    def test_call_returns_session(self):
        """__call__ (line 66): AsyncSessionLocal() delegates to get_session_factory()()."""
        from gnosis.database import AsyncSessionLocal

        fake_session = MagicMock()
        fake_factory = MagicMock(return_value=fake_session)

        with patch("gnosis.database.get_session_factory", return_value=fake_factory):
            result = AsyncSessionLocal()

        fake_factory.assert_called_once()
        assert result is fake_session

    @pytest.mark.anyio
    async def test_aenter_aexit(self):
        """__aenter__ (line 83) and __aexit__ (line 86): async context manager path."""
        from gnosis.database import AsyncSessionLocal

        fake_session = MagicMock()
        fake_factory = MagicMock()
        fake_factory.__aenter__ = AsyncMock(return_value=fake_session)
        fake_factory.__aexit__ = AsyncMock(return_value=False)

        with patch("gnosis.database.get_session_factory", return_value=fake_factory):
            async with AsyncSessionLocal as session:
                assert session is fake_session

        fake_factory.__aenter__.assert_called_once()
        fake_factory.__aexit__.assert_called_once()


# ---------------------------------------------------------------------------
# gnosis/main.py  lines 86-88
# lifespan: graph_rag.initialize(user_id=1) raises -> logger.warning fires.
#
# The key technique: engine.begin() must return a real async context manager.
# We build one via @asynccontextmanager so that `async with engine.begin() as
# conn` works correctly -- setting __aenter__/__aexit__ as instance attributes
# on a MagicMock does NOT work because Python's async protocol looks them up
# on the *type*, not the instance.
# ---------------------------------------------------------------------------

class TestMainLifespanWarning:
    @pytest.mark.anyio
    async def test_lifespan_graphrag_init_warning(self):
        """When graph_rag.initialize raises, lifespan logs a warning and continues."""
        from gnosis.main import lifespan
        from fastapi import FastAPI

        app = FastAPI()

        # Build a fake async connection whose run_sync is awaitable
        fake_conn = MagicMock()
        fake_conn.run_sync = AsyncMock()

        # Build a proper async context manager for engine.begin()
        @asynccontextmanager
        async def _fake_begin():
            yield fake_conn

        fake_engine = MagicMock()
        fake_engine.begin = _fake_begin

        # Observer for vault watcher shutdown
        mock_obs = MagicMock()

        with (
            patch("gnosis.main.get_engine", return_value=fake_engine),
            patch("gnosis.main.llm_provider") as mock_llm,
            patch("gnosis.main.ensure_collection"),
            patch("gnosis.main.start_vault_watcher", new=AsyncMock(return_value=mock_obs)),
            patch("gnosis.main.graph_rag") as mock_rag,
        ):
            mock_llm.initialize = AsyncMock()
            # graph_rag.initialize raises -> except branch -> logger.warning (lines 86-88)
            mock_rag.initialize = AsyncMock(side_effect=RuntimeError("no ollama"))

            gen = lifespan(app)
            await gen.__anext__()      # startup: hits except -> logger.warning
            try:
                await gen.__anext__()  # shutdown (after yield)
            except StopAsyncIteration:
                pass

        mock_rag.initialize.assert_called_once_with(user_id=1)
        mock_obs.stop.assert_called_once()
        mock_obs.join.assert_called_once()


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py - _parse_json_list  (arcs 138->142, 140-141)
# Pure unit tests - no DB, no HTTP.
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
# gnosis/routers/ingest.py  lines 143-144 - _ai_enrich invalid-JSON fallback
# ---------------------------------------------------------------------------

class TestAiEnrichInvalidJson:
    @pytest.mark.anyio
    async def test_ai_enrich_brace_match_invalid_json_fallback(self):
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
# gnosis/routers/export.py  line 237 - PDF export note-not-found
# ---------------------------------------------------------------------------

class TestExportPdfNotFound:
    @pytest.mark.anyio
    async def test_export_pdf_note_not_found(self, async_client):
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
# Helper
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
# gnosis/routers/ai.py - suggest_links  (arcs 211->221, 215->221, 243-244)
# ---------------------------------------------------------------------------

class TestSuggestLinksEdgeCases:
    @pytest.mark.anyio
    async def test_suggest_links_no_brackets(self, async_client):
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
        note_id = await _create_note(async_client, "sl-bad-first", "SL Bad First Array")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="[Note Alpha, Note Beta, Note Gamma]"
            )
            resp = await async_client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        assert isinstance(resp.json()["suggestions"], list)
        assert resp.json()["rationale"] == []

    @pytest.mark.anyio
    async def test_suggest_links_invalid_rationale_json(self, async_client):
        note_id = await _create_note(async_client, "sl-bad-rationale", "SL Bad Rationale")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='["Note A", "Note B"] then [not: valid json at all]'
            )
            resp = await async_client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        assert "Note A" in resp.json()["suggestions"]
        assert isinstance(resp.json()["rationale"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py - critique_note  (arc 343-344)
# ---------------------------------------------------------------------------

class TestCritiqueEdgeCases:
    @pytest.mark.anyio
    async def test_critique_no_json(self, async_client):
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
        note_id = await _create_note(async_client, "crit-bad-json", "Critique Bad JSON")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="{atomicity: good, connectivity: moderate - not valid JSON}"
            )
            resp = await async_client.post(f"/api/v1/ai/critique/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["atomicity"], str)
        assert len(data["atomicity"]) > 0
        assert data["connectivity"] == ""
        assert data["overall"] == ""


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py - orphan_audit  (lines 411-412)
# ---------------------------------------------------------------------------

class TestOrphanAuditJsonDecodeError:
    @pytest.mark.anyio
    async def test_orphan_audit_invalid_json(self, async_client):
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="[{note_id: 'x', title: bad, suggestions: []}]"
            )
            resp = await async_client.get("/api/v1/ai/orphan-audit?limit=5")
        assert resp.status_code == 200
        assert isinstance(resp.json()["items"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py - daily_review  (arcs 467->483, 481-482)
# ---------------------------------------------------------------------------

class TestDailyReviewEdgeCases:
    @pytest.mark.anyio
    async def test_daily_review_no_notes_today(self, async_client):
        resp = await async_client.post("/api/v1/ai/daily-review")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["summary"], str)
        assert isinstance(data["action_items"], list)

    @pytest.mark.anyio
    async def test_daily_review_invalid_json(self, async_client):
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
# gnosis/routers/ai.py - stream_chat SSE exception path  (arcs 534-535)
# ---------------------------------------------------------------------------

class TestStreamChatException:
    @pytest.mark.anyio
    async def test_stream_chat_sse_exception_path(self, async_client):
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
# gnosis/routers/ai.py - ingest_note LightRAG exception  (arcs 634-635)
# ---------------------------------------------------------------------------

class TestIngestNoteException:
    @pytest.mark.anyio
    async def test_ingest_note_lightrag_raises(self, async_client):
        note_id = await _create_note(async_client, "ingest-exc-001", "Ingest Exception Note")
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai._LIGHTRAG_AVAILABLE_CHECK") as mock_check,
        ):
            mock_check.return_value = True
            mock_rag.ingest_note = AsyncMock(side_effect=RuntimeError("lightrag down"))
            resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")
        assert resp.status_code == 500
        assert "lightrag down" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py - generate_moc json-decode fallback  (lines 709-710)
# ---------------------------------------------------------------------------

class TestGenerateMocJsonDecodeFallback:
    @pytest.mark.anyio
    async def test_generate_moc_invalid_json_sections(self, async_client):
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
