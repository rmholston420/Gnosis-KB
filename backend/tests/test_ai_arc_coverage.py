"""
test_ai_arc_coverage.py

Pure unit tests targeting uncovered arcs in gnosis/routers/ai.py:

  138→142   _parse_json_list  — if match: is False (no bracket in input)
  211→221   suggest_links     — re.findall returns [] (no arrays)
  215→221   suggest_links     — exactly one array (len < 2, skip rationale)
  243–244   suggest_links     — second array present but json.loads raises
  467→483   daily_review      — json_match found but json.loads raises
  481–482   daily_review      — except: summary=raw, action_items=[]
  534–535   stream_chat       — exception inside event_generator
  634–635   ingest_note       — graph_rag.ingest_note raises → HTTP 500
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared note factory
# ---------------------------------------------------------------------------

def _note(
    note_id="n1",
    title="Test Note",
    body="Body content.",
    folder="10-zettelkasten",
    note_type="evergreen",
    status="active",
    owner_id: int = 1,
):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.folder = folder
    n.note_type = note_type
    n.status = status
    n.is_deleted = False
    n.owner_id = owner_id
    n.created_at = datetime.now(UTC)
    return n


# ===========================================================================
# Arc 138→142  _parse_json_list
#
# Line 138: `if match:` — two arcs:
#   138→139  match is truthy  (bracket found)  — covered by existing tag tests
#   138→142  match is falsy   (NO bracket)     — this is the missing arc
# ===========================================================================

class TestParseJsonListNoBracket:
    def test_no_bracket_in_input_skips_to_line_split(self):
        """Arc 138→142: re.search returns None (no '[' in text).
        Falls directly to line-split path."""
        from gnosis.routers.ai import _parse_json_list

        # Absolutely no bracket characters — regex cannot match
        raw = "zettelkasten spaced repetition atomic notes"
        result = _parse_json_list(raw)
        assert isinstance(result, list)
        # Line-split returns the single non-empty line
        assert len(result) == 1
        assert "zettelkasten" in result[0]

    def test_no_bracket_multiline_returns_all_lines(self):
        """Multiple lines, no brackets — each becomes a list item."""
        from gnosis.routers.ai import _parse_json_list

        raw = "impermanence\ncognitive load\nspaced repetition"
        result = _parse_json_list(raw)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_bracket_that_fails_json_decode_falls_to_linesplit(self):
        """Bracket IS found but json.loads raises — falls through to line-split."""
        from gnosis.routers.ai import _parse_json_list

        raw = "[key: value, unquoted: thing]"
        result = _parse_json_list(raw)
        assert isinstance(result, list)


# ===========================================================================
# Arc 211→221, 215→221, 243–244  suggest_links
#
# Root cause of prior failures: _get_note_or_404 calls session.execute once
# internally.  suggest_links then calls session.execute again for candidates.
# The _make_db helper must supply enough side_effect entries:
#   entry 0 — consumed by _get_note_or_404 (note lookup)
#   entry 1 — consumed by suggest_links itself (candidate query)
#
# We bypass _get_note_or_404 entirely by patching it, so session.execute
# only needs one entry: the candidate result.
# ===========================================================================

class TestSuggestLinksArcs:
    """Patch _get_note_or_404 directly so session.execute is only called
    once (for the candidate SELECT), making mock setup trivial."""

    def _make_db(self, candidates=None):
        cand_result = MagicMock()
        cand_result.all.return_value = candidates or []
        db = AsyncMock()
        db.execute = AsyncMock(return_value=cand_result)
        return db

    @pytest.mark.asyncio
    async def test_arc_211_to_221_no_arrays_in_llm_response(self):
        """Arc 211→221: re.findall returns [] — if arrays: is False."""
        from gnosis.routers.ai import suggest_links

        note = _note("sl-a", "Source Note", "some body text")
        db = self._make_db()

        with (
            patch("gnosis.routers.ai._get_note_or_404", new=AsyncMock(return_value=note)),
            patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_llm.is_available = True
            # No brackets at all — re.findall returns []
            mock_llm.complete = AsyncMock(
                return_value="I suggest Note Alpha and Note Beta as links."
            )
            result = await suggest_links("sl-a", session=db, owner_ids={1})

        assert result.note_id == "sl-a"
        assert result.suggestions == []
        assert result.rationale == []

    @pytest.mark.asyncio
    async def test_arc_215_to_221_one_array_no_rationale(self):
        """Arc 215→221: len(arrays) == 1 — if len(arrays) >= 2: is False."""
        from gnosis.routers.ai import suggest_links

        note = _note("sl-b", "Source Note B", "body")
        db = self._make_db()

        with (
            patch("gnosis.routers.ai._get_note_or_404", new=AsyncMock(return_value=note)),
            patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_llm.is_available = True
            # Exactly one JSON array — no second array for rationale
            mock_llm.complete = AsyncMock(
                return_value='["Note Alpha", "Note Beta"]'
            )
            result = await suggest_links("sl-b", session=db, owner_ids={1})

        assert result.note_id == "sl-b"
        assert "Note Alpha" in result.suggestions
        assert result.rationale == []

    @pytest.mark.asyncio
    async def test_arc_243_244_second_array_invalid_json(self):
        """Arc 243–244: arrays[1] exists but json.loads raises → _parse_json_list."""
        from gnosis.routers.ai import suggest_links

        note = _note("sl-c", "Source Note C", "body")
        db = self._make_db()

        with (
            patch("gnosis.routers.ai._get_note_or_404", new=AsyncMock(return_value=note)),
            patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_llm.is_available = True
            # Two arrays: first is valid JSON, second has unquoted values
            mock_llm.complete = AsyncMock(
                return_value='["Note Alpha", "Note Beta"] [Because A, Because B]'
            )
            result = await suggest_links("sl-c", session=db, owner_ids={1})

        assert result.note_id == "sl-c"
        assert "Note Alpha" in result.suggestions
        assert isinstance(result.rationale, list)


# ===========================================================================
# Arc 467→483 / 481–482  daily_review
#
# daily_review calls session.execute once (for the inbox note SELECT).
# The result mock must expose .scalars().all() returning notes.
# scoped_note_stmt is patched to pass through the statement unchanged.
# The LLM returns a string with braces that json.loads rejects.
# ===========================================================================

class TestDailyReviewJsonDecodeError:
    @pytest.mark.asyncio
    async def test_json_match_found_but_decode_fails(self):
        """Arc 467→483 / 481-482: braces present, json.loads raises,
        except sets summary_text = raw and action_items = []."""
        from gnosis.routers.ai import daily_review

        notes = [_note("dr-x", "Inbox Note", "content", folder="00-inbox")]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = notes
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result_mock)

        # Contains braces so re.search matches, but json.loads rejects
        invalid_json = "{summary: Today was productive, action_items: [Process inbox]}"

        with (
            patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(return_value=invalid_json)
            result = await daily_review(session=db, owner_ids={1})

        assert result.summary == invalid_json
        assert result.action_items == []
        assert result.inbox_note_count == 1

    @pytest.mark.asyncio
    async def test_single_quoted_json_fails_decode(self):
        """Single-quoted keys match braces regex but fail json.loads."""
        from gnosis.routers.ai import daily_review

        notes = [
            _note("dr-y", "Note Y", "body", folder="00-inbox"),
            _note("dr-z", "Note Z", "body", folder="00-inbox"),
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = notes
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result_mock)

        raw = "{'summary': 'good day', 'action_items': ['a', 'b']}"

        with (
            patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(return_value=raw)
            result = await daily_review(session=db, owner_ids={1})

        assert result.summary == raw
        assert result.action_items == []
        assert result.inbox_note_count == 2


# ===========================================================================
# Arc 534–535  stream_chat — exception inside event_generator
#
# The patch context MUST remain active while draining body_iterator —
# StreamingResponse is lazy and executes the generator on iteration.
# ===========================================================================

class TestStreamChatExceptionArc:
    @pytest.mark.asyncio
    async def test_exception_in_is_available_emits_error_sse(self):
        """graph_rag.is_available raises → except branch emits error SSE."""
        from gnosis.routers.ai import stream_chat

        user = MagicMock()
        user.id = 42

        mock_rag = MagicMock()
        mock_rag.is_available = AsyncMock(side_effect=RuntimeError("graph exploded"))

        with (
            patch("gnosis.routers.ai.graph_rag", mock_rag),
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_llm.is_available = False
            response = await stream_chat(
                message="test",
                mode="hybrid",
                session=AsyncMock(),
                current_user=user,
                owner_ids={42},
            )
            chunks: list[str] = []
            async for chunk in response.body_iterator:
                chunks.append(chunk if isinstance(chunk, str) else chunk.decode())

        full = "".join(chunks)
        assert '"error"' in full, f"Expected error event: {full!r}"
        assert "graph exploded" in full, f"Expected exc message: {full!r}"
        assert "[DONE]" in full, f"Expected [DONE]: {full!r}"

    @pytest.mark.asyncio
    async def test_exception_during_qdrant_stream_iteration(self):
        """Exception mid-stream in _qdrant_rag_stream hits the except arc."""
        from gnosis.routers.ai import stream_chat

        user = MagicMock()
        user.id = 7

        mock_rag = MagicMock()
        mock_rag.is_available = AsyncMock(return_value=False)

        async def _stream_that_raises(*args, **kwargs):
            yield "first-token"
            raise ValueError("qdrant down mid-stream")

        with (
            patch("gnosis.routers.ai.graph_rag", mock_rag),
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
            patch("gnosis.routers.ai._qdrant_rag_stream", _stream_that_raises),
        ):
            mock_llm.is_available = True
            response = await stream_chat(
                message="crash me",
                mode="hybrid",
                session=AsyncMock(),
                current_user=user,
                owner_ids={7},
            )
            chunks: list[str] = []
            async for chunk in response.body_iterator:
                chunks.append(chunk if isinstance(chunk, str) else chunk.decode())

        full = "".join(chunks)
        assert "first-token" in full, f"Expected first token: {full!r}"
        assert '"error"' in full, f"Expected error event: {full!r}"
        assert "qdrant down mid-stream" in full, f"Expected exc message: {full!r}"
        assert "[DONE]" in full, f"Expected [DONE]: {full!r}"


# ===========================================================================
# Arc 634–635  ingest_note — graph_rag.ingest_note raises → HTTP 500
#
# Patch _get_note_or_404 to bypass its session.execute call entirely.
# Patch _LIGHTRAG_AVAILABLE_CHECK as a plain lambda returning True so
# `not _LIGHTRAG_AVAILABLE_CHECK()` evaluates to False (proceeds to try).
# graph_rag.ingest_note raises → except raises HTTPException(500).
# ===========================================================================

class TestIngestNoteExceptionArc:
    @pytest.mark.asyncio
    async def test_ingest_note_raises_http_500_on_runtime_error(self):
        from fastapi import HTTPException

        from gnosis.routers.ai import ingest_note

        note = _note("ing-err", "Error Note", "content", owner_id=3)
        user = MagicMock()
        user.id = 3

        fake_graph = MagicMock()
        fake_graph.ingest_note = AsyncMock(
            side_effect=RuntimeError("lightrag index failure")
        )

        with (
            patch("gnosis.routers.ai._get_note_or_404", new=AsyncMock(return_value=note)),
            patch("gnosis.routers.ai.graph_rag", fake_graph),
            # Use a plain lambda so _LIGHTRAG_AVAILABLE_CHECK() returns True
            patch("gnosis.routers.ai._LIGHTRAG_AVAILABLE_CHECK", new=lambda: True),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await ingest_note(
                    "ing-err",
                    session=AsyncMock(),
                    current_user=user,
                    owner_ids={3},
                )

        assert exc_info.value.status_code == 500
        assert "lightrag index failure" in exc_info.value.detail
        assert "LightRAG ingest failed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_ingest_note_raises_http_500_on_value_error(self):
        from fastapi import HTTPException

        from gnosis.routers.ai import ingest_note

        note = _note("ing-err2", "Error Note 2", "content", owner_id=5)
        user = MagicMock()
        user.id = 5

        fake_graph = MagicMock()
        fake_graph.ingest_note = AsyncMock(
            side_effect=ValueError("unexpected graph state")
        )

        with (
            patch("gnosis.routers.ai._get_note_or_404", new=AsyncMock(return_value=note)),
            patch("gnosis.routers.ai.graph_rag", fake_graph),
            patch("gnosis.routers.ai._LIGHTRAG_AVAILABLE_CHECK", new=lambda: True),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await ingest_note(
                    "ing-err2",
                    session=AsyncMock(),
                    current_user=user,
                    owner_ids={5},
                )

        assert exc_info.value.status_code == 500
        assert "unexpected graph state" in exc_info.value.detail
        assert "LightRAG ingest failed" in exc_info.value.detail
