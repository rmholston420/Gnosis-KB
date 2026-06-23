"""
test_coverage_gaps2.py

Surgical second-pass tests targeting every line/arc still uncovered after
test_final_gaps.py:

  gnosis/config.py              line 82     get_settings env-override
  gnosis/database.py            line 66     _AsyncSessionLocalProxy.__call__
  gnosis/routers/admin.py       line 95     reindex_vault OSError path
  gnosis/routers/ai.py          lines/arcs:
                                  129       summarize_note — LLM unavailable 503
                                  138->142  _parse_json_list bracket+invalid JSON
                                  211->221  suggest_links — no arrays in raw
                                  215->221  suggest_links — first array invalid JSON
                                  243-244   suggest_links — second array invalid JSON
                                  297-303   set_model — Ollama not available 400
                                  343-344   critique_note — no JSON braces in raw
                                  411-412   orphan_audit — no JSON array in raw
                                  450       daily_review — notes exist but LLM unavailable
                                  467->483  daily_review — valid JSON path
                                  481-482   daily_review — brace+invalid JSON
                                  634-635   ingest_note — exception → 500
                                  670       _LIGHTRAG_AVAILABLE_CHECK — ImportError
                                  709-710   generate_moc — JSON decode error in sections
  gnosis/routers/export.py      line 237    export_note_pdf — note not found 404
  gnosis/routers/notes.py       52->exit, 54-57   list_notes — body_snippet truncation
  gnosis/routers/review.py      146-154,157,188-189  review session edge cases
"""
from __future__ import annotations

import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_note(client, note_id: str, title: str, body: str = "Test body.") -> str:
    resp = await client.post(
        "/api/v1/notes/",
        json={"id": note_id, "title": title, "body": body, "folder": "00-inbox"},
    )
    assert resp.status_code in (200, 201), f"note creation failed {resp.status_code}: {resp.text}"
    return note_id


async def _create_review_card(client, note_id: str) -> None:
    """Seed a ReviewCard for *note_id* via POST /api/v1/review/."""
    resp = await client.post("/api/v1/review/", json={"note_id": note_id})
    assert resp.status_code in (200, 201, 409), (
        f"review card creation failed {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# gnosis/config.py  line 82 — get_settings env override path
# ---------------------------------------------------------------------------

class TestConfigEnvOverride:
    def test_get_settings_reads_env(self, monkeypatch):
        """Force get_settings() to construct a fresh Settings from env vars."""
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-32-characters-long")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/gnosis_test")

        # Clear the lru_cache so Settings is rebuilt from the env vars we set.
        from gnosis.config import get_settings
        get_settings.cache_clear()
        try:
            s = get_settings()
            assert s.secret_key == "test-secret-key-32-characters-long"
        finally:
            get_settings.cache_clear()


# ---------------------------------------------------------------------------
# gnosis/database.py  line 66 — _AsyncSessionLocalProxy.__call__
# ---------------------------------------------------------------------------

class TestAsyncSessionLocalProxyCall:
    def test_call_delegates_to_factory(self):
        from gnosis.database import AsyncSessionLocal
        fake_session = MagicMock()
        fake_factory = MagicMock(return_value=fake_session)
        with patch("gnosis.database.get_session_factory", return_value=fake_factory):
            result = AsyncSessionLocal()
        fake_factory.assert_called_once()
        assert result is fake_session


# ---------------------------------------------------------------------------
# gnosis/routers/admin.py  line 95 — reindex_vault OSError path
# ---------------------------------------------------------------------------

class TestAdminReindexOsError:
    async def test_reindex_raises_oserror(self, async_client):
        with patch(
            "gnosis.routers.admin.run_full_vault_reindex",
            side_effect=OSError("disk full"),
        ):
            resp = await async_client.post("/api/v1/admin/reindex")
        assert resp.status_code == 500
        assert "disk full" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  line 129
# summarize_note — LLM not available → 503
# ---------------------------------------------------------------------------

class TestSummarizeNoteLlmUnavailable:
    async def test_summarize_503_when_no_llm(self, async_client):
        note_id = await _create_note(async_client, "sum-nollm-001", "Summarize No LLM")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = False
            resp = await async_client.post(f"/api/v1/ai/summarize/{note_id}")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  138->142
# _parse_json_list — bracket matched but body is invalid JSON → line-split fallback
# ---------------------------------------------------------------------------

class TestParseJsonListBracketInvalidJson:
    def test_bracket_invalid_json_falls_back_to_lines(self):
        from gnosis.routers.ai import _parse_json_list
        raw = "Here are items: [not: valid, json] and more text after"
        result = _parse_json_list(raw)
        # Falls through to the line-split path — must return a list
        assert isinstance(result, list)

    def test_valid_json_list_returned_directly(self):
        from gnosis.routers.ai import _parse_json_list
        assert _parse_json_list('["a", "b"]') == ["a", "b"]

    def test_no_bracket_returns_line_split(self):
        from gnosis.routers.ai import _parse_json_list
        result = _parse_json_list("- alpha\n- beta\n- gamma")
        assert "alpha" in result and "beta" in result


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  arcs 211->221, 215->221, 243-244
# suggest_links edge cases
# ---------------------------------------------------------------------------

class TestSuggestLinksEdgeCases:
    async def test_no_arrays_in_raw_returns_empty(self, async_client):
        """arc 211->221: re.findall finds no [...] — suggestions and rationale are []."""
        note_id = await _create_note(async_client, "sl-no-arr-001", "SL No Arrays")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(return_value="No structured output at all.")
            resp = await async_client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["suggestions"] == []
        assert data["rationale"] == []

    async def test_first_array_invalid_json_uses_parse_fallback(self, async_client):
        """arc 215->221: arrays[0] is invalid JSON → _parse_json_list fallback."""
        note_id = await _create_note(async_client, "sl-bad-arr-001", "SL Bad First Array")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="[Note Alpha, Note Beta, Note Gamma]"
            )
            resp = await async_client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        assert isinstance(resp.json()["suggestions"], list)

    async def test_second_array_invalid_json_rationale_empty(self, async_client):
        """arcs 243-244: arrays[1] is invalid JSON → rationale uses _parse_json_list."""
        note_id = await _create_note(async_client, "sl-bad-rat-001", "SL Bad Rationale")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='["Note A", "Note B"] and then [bad: rationale json here]'
            )
            resp = await async_client.post(f"/api/v1/ai/suggest-links/{note_id}")
        assert resp.status_code == 200
        assert "Note A" in resp.json()["suggestions"]
        assert isinstance(resp.json()["rationale"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  lines 297-303
# set_model — Ollama not an available provider → 400
# ---------------------------------------------------------------------------

class TestSetModelOllamaUnavailable:
    async def test_set_model_400_when_ollama_unavailable(self, async_client):
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm._available = {}  # Ollama not in available providers
            resp = await async_client.post(
                "/api/v1/ai/providers/model", json={"model": "llama3"}
            )
        assert resp.status_code == 400
        assert "Ollama" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  lines 343-344
# critique_note — no JSON braces at all in raw response → fallback path
# ---------------------------------------------------------------------------

class TestCritiqueNoteNoBraces:
    async def test_critique_plain_text_no_json(self, async_client):
        """json_match is None → critique_data stays {} → atomicity=raw, rest empty."""
        note_id = await _create_note(async_client, "crit-plain-001", "Critique Plain Text")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="This note covers a single idea about dependent origination."
            )
            resp = await async_client.post(f"/api/v1/ai/critique/{note_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "dependent origination" in data["atomicity"]
        assert data["connectivity"] == ""
        assert data["overall"] == ""


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  lines 411-412
# orphan_audit — LLM returns text with no JSON array → items stays []
# ---------------------------------------------------------------------------

class TestOrphanAuditNoJsonArray:
    async def test_orphan_audit_plain_prose_response(self, async_client):
        """json_match is None → items stays [] → OrphanAuditResponse with empty items."""
        # Create an unlinked note so orphan_audit has rows to feed to the LLM
        await _create_note(async_client, "orphan-plain-001", "Orphan Plain Prose")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="These notes could link to epistemology and philosophy of mind."
            )
            resp = await async_client.get("/api/v1/ai/orphan-audit?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  line 450
# daily_review — notes exist today but LLM is unavailable → early return
# ---------------------------------------------------------------------------

class TestDailyReviewNotesButNoLlm:
    async def test_daily_review_early_return_no_llm(self, async_client):
        """Branch: notes exist but llm_provider.is_available is False → early return."""
        import datetime
        today = datetime.date.today().isoformat()
        note_id = f"dr-nollm-{today.replace('-', '')}"
        await async_client.post(
            "/api/v1/notes/",
            json={
                "id": note_id,
                "title": "Daily Review No LLM",
                "body": "Content about impermanence.",
                "folder": "00-inbox",
            },
        )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = False
            resp = await async_client.post("/api/v1/ai/daily-review")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == "No inbox notes today."
        assert data["action_items"] == []


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  arcs 467->483  (valid JSON path)
# daily_review — LLM returns valid JSON with summary + action_items
# ---------------------------------------------------------------------------

class TestDailyReviewValidJson:
    async def test_daily_review_parses_json_response(self, async_client):
        import datetime
        today = datetime.date.today().isoformat()
        note_id = f"dr-json-{today.replace('-', '')}"
        await async_client.post(
            "/api/v1/notes/",
            json={
                "id": note_id,
                "title": "Daily Review JSON Note",
                "body": "Captured insight about the nature of mind.",
                "folder": "00-inbox",
            },
        )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='{"summary": "Today was productive.", '
                             '"action_items": ["Process inbox", "Link notes"]}'
            )
            resp = await async_client.post("/api/v1/ai/daily-review")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == "Today was productive."
        assert "Process inbox" in data["action_items"]


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  arcs 481-482
# daily_review — brace-match succeeds but JSON is invalid → summary stays as raw
# ---------------------------------------------------------------------------

class TestDailyReviewInvalidJson:
    async def test_daily_review_invalid_json_fallback(self, async_client):
        import datetime
        today = datetime.date.today().isoformat()
        note_id = f"dr-badjson-{today.replace('-', '')}"
        await async_client.post(
            "/api/v1/notes/",
            json={
                "id": note_id,
                "title": "Daily Review Bad JSON",
                "body": "Studying the aggregates today.",
                "folder": "00-inbox",
            },
        )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="{summary: great day, action_items: not-an-array}"
            )
            resp = await async_client.post("/api/v1/ai/daily-review")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["summary"], str)
        assert isinstance(data["action_items"], list)


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  arcs 634-635
# ingest_note — graph_rag.ingest_note raises → 500
# ---------------------------------------------------------------------------

class TestIngestNoteRaises500:
    async def test_ingest_note_exception_returns_500(self, async_client):
        note_id = await _create_note(async_client, "ing-exc-501", "Ingest Raises")
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai._LIGHTRAG_AVAILABLE_CHECK", return_value=True),
        ):
            mock_rag.ingest_note = AsyncMock(side_effect=RuntimeError("lightrag exploded"))
            resp = await async_client.post(f"/api/v1/ai/ingest-note/{note_id}")
        assert resp.status_code == 500
        assert "lightrag exploded" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  line 670
# _LIGHTRAG_AVAILABLE_CHECK — ImportError path returns False
# ---------------------------------------------------------------------------

class TestLightragAvailableCheckFalse:
    def test_returns_false_when_lightrag_not_installed(self):
        from gnosis.routers.ai import _LIGHTRAG_AVAILABLE_CHECK
        # Temporarily hide lightrag from sys.modules
        original = sys.modules.pop("lightrag", None)
        try:
            result = _LIGHTRAG_AVAILABLE_CHECK()
            assert result is False
        finally:
            if original is not None:
                sys.modules["lightrag"] = original


# ---------------------------------------------------------------------------
# gnosis/routers/ai.py  lines 709-710
# generate_moc — sections JSON decode error → sections=[]
# ---------------------------------------------------------------------------

class TestGenerateMocJsonDecodeError:
    async def test_generate_moc_invalid_json_sections(self, async_client):
        for i in range(3):
            await _create_note(
                async_client,
                f"moc-gaps2-{i}",
                f"Gaps2 Dharma Seed {i}",
                body=f"dharma content {i} about the three marks of existence.",
            )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="[{heading: no-quotes, summary: bad, wikilinks: not-array}]"
            )
            resp = await async_client.post(
                "/api/v1/ai/generate-moc",
                json={"topic": "dharma", "max_notes": 10},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sections"] == []
        assert "dharma" in data["topic"].lower()


# ---------------------------------------------------------------------------
# gnosis/routers/export.py  line 237
# export_note_pdf — note not found → 404
# ---------------------------------------------------------------------------

class TestExportPdfNoteNotFound:
    async def test_export_pdf_returns_404_for_missing_note(self, async_client):
        import types
        fake_wp = types.ModuleType("weasyprint")
        fake_wp.HTML = MagicMock()
        with (
            patch("gnosis.routers.export.settings") as mock_settings,
            patch.dict(sys.modules, {"weasyprint": fake_wp}),
        ):
            mock_settings.enable_pdf_export = True
            resp = await async_client.get("/api/v1/export/note/nonexistent-note-xyz.pdf")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# gnosis/routers/notes.py  lines 54-57  (body_snippet truncation)
# list_notes returns body_snippet truncated to 200 chars when body > 200 chars
# ---------------------------------------------------------------------------

class TestNoteBodySnippet:
    async def test_body_snippet_truncated_to_200(self, async_client):
        long_body = "A" * 300
        note_id = await _create_note(
            async_client, "snip-001", "Long Body Note", body=long_body
        )
        resp = await async_client.get("/api/v1/notes/")
        assert resp.status_code == 200
        items = resp.json()["items"] if "items" in resp.json() else resp.json()
        match = next((n for n in items if n["id"] == note_id), None)
        assert match is not None
        assert len(match.get("body_snippet", match.get("body", ""))) <= 200


# ---------------------------------------------------------------------------
# gnosis/routers/review.py  lines 146-154, 157
# submit_review — ReviewCard not found → 404
# ---------------------------------------------------------------------------

class TestSubmitReviewNotFound:
    async def test_submit_review_404_for_missing_card(self, async_client):
        resp = await async_client.post(
            "/api/v1/review/nonexistent-note-xyz/submit",
            json={"quality": 4},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# gnosis/routers/review.py  lines 188-189
# delete_review_card — ReviewCard not found → 404
# ---------------------------------------------------------------------------

class TestDeleteReviewCardNotFound:
    async def test_delete_review_card_404_for_missing(self, async_client):
        resp = await async_client.delete("/api/v1/review/nonexistent-note-xyz")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# gnosis/routers/review.py  lines 146-154  (full submit path)
# submit_review — happy path updates the card via SM-2
# ---------------------------------------------------------------------------

class TestSubmitReviewHappyPath:
    async def test_submit_review_updates_card(self, async_client):
        note_id = await _create_note(
            async_client, "rev-submit-001", "Review Submit Note"
        )
        await _create_review_card(async_client, note_id)
        resp = await async_client.post(
            f"/api/v1/review/{note_id}/submit",
            json={"quality": 4},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["note_id"] == note_id
        assert data["repetitions"] >= 1
