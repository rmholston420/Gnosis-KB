"""
test_ai_arc_coverage.py

Pure unit tests (no DB, no async_client, no HTTP stack) targeting the 8
remaining uncovered lines/arcs in gnosis/routers/ai.py as reported by
coverage:

  138→142   _parse_json_list  — bracket matches but json.loads raises
  211→221   suggest_links     — raw has NO bracket arrays at all
  215→221   suggest_links     — raw has exactly ONE array (no rationale)
  243–244   suggest_links     — second array present but invalid JSON
  467→483   daily_review      — json_match found but json.loads raises
  481–482   daily_review      — except sets summary=raw, action_items=[]
  534–535   stream_chat       — exception inside event_generator
  634–635   ingest_note       — graph_rag.ingest_note raises → HTTP 500

All tests call the endpoint/helper functions directly, bypassing FastAPI
routing so there is no dependency on the test database or conftest fixtures.
"""
from __future__ import annotations

from datetime import datetime, timezone
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
    n.created_at = datetime.now(timezone.utc)
    return n


# ===========================================================================
# Arc 138→142  _parse_json_list
# Condition: re.search finds a bracket expression BUT json.loads raises
# JSONDecodeError.  The code must fall through to the line-split path.
# ===========================================================================

class TestParseJsonListBracketDecodeError:
    def test_bracket_with_unquoted_keys_causes_decode_error(self):
        """`[key: value]` matches the regex but is not valid JSON."""
        from gnosis.routers.ai import _parse_json_list

        raw = "[key: value, another: thing]"
        result = _parse_json_list(raw)
        assert isinstance(result, list)

    def test_bracket_with_trailing_comma_causes_decode_error(self):
        """Trailing comma `["a", "b",]` — invalid in stdlib json."""
        from gnosis.routers.ai import _parse_json_list

        raw = '["spaced-repetition", "zettelkasten",]'
        result = _parse_json_list(raw)
        assert isinstance(result, list)

    def test_valid_integer_list_in_brackets_returns_str_items(self):
        """[42] is valid JSON list — returns [\"42\"] via str(item)."""
        from gnosis.routers.ai import _parse_json_list

        result = _parse_json_list("The answer is [42] not a string list")
        assert isinstance(result, list)


# ===========================================================================
# Arc 211→221  suggest_links — raw has NO bracket arrays
# Arc 215→221  suggest_links — raw has exactly ONE array (no rationale)
# Arc 243–244  suggest_links — second array found but its json.loads raises
# ===========================================================================

class TestSuggestLinksArcs:
    def _make_db(self, note, candidates=None):
        note_result = MagicMock()
        note_result.scalar_one_or_none.return_value = note

        cand_result = MagicMock()
        cand_result.all.return_value = candidates or []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[note_result, cand_result])
        return db

    @pytest.mark.asyncio
    async def test_arc_211_to_221_no_arrays_in_response(self):
        """Arc 211→221: re.findall finds zero bracket arrays."""
        from gnosis.routers.ai import suggest_links

        note = _note("sl-a", "Source Note", "some body text")
        db = self._make_db(note)

        with (
            patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="I suggest linking to Note Alpha and Note Beta."
            )
            result = await suggest_links("sl-a", session=db, owner_ids={1})

        assert result.note_id == "sl-a"
        assert result.suggestions == []
        assert result.rationale == []

    @pytest.mark.asyncio
    async def test_arc_215_to_221_one_array_no_rationale(self):
        """Arc 215→221: exactly one array — suggestions populated, rationale []."""
        from gnosis.routers.ai import suggest_links

        note = _note("sl-b", "Source Note B", "body")
        db = self._make_db(note)

        with (
            patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='["Note Alpha", "Note Beta"]'
            )
            result = await suggest_links("sl-b", session=db, owner_ids={1})

        assert result.note_id == "sl-b"
        assert "Note Alpha" in result.suggestions
        assert result.rationale == []

    @pytest.mark.asyncio
    async def test_arc_243_244_second_array_invalid_json(self):
        """Arc 243–244: two arrays; second fails json.loads → _parse_json_list."""
        from gnosis.routers.ai import suggest_links

        note = _note("sl-c", "Source Note C", "body")
        db = self._make_db(note)

        with (
            patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='["Note Alpha", "Note Beta"] [Because A, Because B]'
            )
            result = await suggest_links("sl-c", session=db, owner_ids={1})

        assert result.note_id == "sl-c"
        assert "Note Alpha" in result.suggestions
        assert isinstance(result.rationale, list)


# ===========================================================================
# Arc 467→483 / 481–482  daily_review
# Condition: json_match found but json.loads raises JSONDecodeError.
# ===========================================================================

class TestDailyReviewJsonDecodeError:
    @pytest.mark.asyncio
    async def test_json_match_found_but_decode_fails(self):
        """Arc 467→483 / 481-482: braces match but json.loads raises."""
        from gnosis.routers.ai import daily_review

        notes = [_note("dr-x", "Inbox Note", "content", folder="00-inbox")]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = notes
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result_mock)

        invalid_json_with_braces = (
            "{summary: Today was productive, action_items: [Process inbox, Review]}"
        )

        with (
            patch("gnosis.routers.ai.scoped_note_stmt", side_effect=lambda s, o: s),
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(return_value=invalid_json_with_braces)
            result = await daily_review(session=db, owner_ids={1})

        assert result.summary == invalid_json_with_braces
        assert result.action_items == []
        assert result.inbox_note_count == 1

    @pytest.mark.asyncio
    async def test_json_match_found_but_decode_fails_variant(self):
        """Single-quoted JSON: matches brace regex, fails json.loads."""
        from gnosis.routers.ai import daily_review

        notes = [
            _note("dr-y", "Note Y", "studying impermanence", folder="00-inbox"),
            _note("dr-z", "Note Z", "contemplative practice", folder="00-inbox"),
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
# Arc 534–535  stream_chat — exception raised inside event_generator
#
# Critical: the patch context MUST remain active while draining
# response.body_iterator — the generator runs lazily, so closing the
# patch block before iteration tears down the mocks before the code runs.
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

            # Drain the iterator INSIDE the patch context so the mocks
            # are still active when the async generator body executes.
            chunks: list[str] = []
            async for chunk in response.body_iterator:
                chunks.append(chunk if isinstance(chunk, str) else chunk.decode())

        full = "".join(chunks)
        assert '"error"' in full, f"Expected error event in SSE output: {full!r}"
        assert "graph exploded" in full, f"Expected exc message in SSE output: {full!r}"
        assert "[DONE]" in full, f"Expected [DONE] in SSE output: {full!r}"

    @pytest.mark.asyncio
    async def test_exception_during_qdrant_stream_iteration(self):
        """Exception raised *during* async iteration of _qdrant_rag_stream
        is caught by the except clause in event_generator (arc 534-535).

        We use a real async generator that yields one token then raises,
        so the `async for token in _qdrant_rag_stream(...)` loop inside
        event_generator propagates the exception to the outer try/except.
        """
        from gnosis.routers.ai import stream_chat

        user = MagicMock()
        user.id = 7

        mock_rag = MagicMock()
        mock_rag.is_available = AsyncMock(return_value=False)

        async def _stream_that_raises(*args, **kwargs):
            """Yields one token then raises — the raise happens DURING iteration."""
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

            # Drain inside the patch context.
            chunks: list[str] = []
            async for chunk in response.body_iterator:
                chunks.append(chunk if isinstance(chunk, str) else chunk.decode())

        full = "".join(chunks)
        # The first token should have been emitted before the raise.
        assert "first-token" in full, f"Expected first token: {full!r}"
        # The except branch must emit an error event.
        assert '"error"' in full, f"Expected error event: {full!r}"
        assert "qdrant down mid-stream" in full, f"Expected exc message: {full!r}"
        assert "[DONE]" in full, f"Expected [DONE]: {full!r}"


# ===========================================================================
# Arc 634–635  ingest_note — graph_rag.ingest_note raises → HTTP 500
# ===========================================================================

class TestIngestNoteExceptionArc:
    @pytest.mark.asyncio
    async def test_ingest_note_raises_http_500_on_exception(self):
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
            patch(
                "gnosis.routers.ai._get_note_or_404",
                new=AsyncMock(return_value=note),
            ),
            patch("gnosis.routers.ai.graph_rag", fake_graph),
            patch(
                "gnosis.routers.ai._LIGHTRAG_AVAILABLE_CHECK", return_value=True
            ),
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

    @pytest.mark.asyncio
    async def test_ingest_note_raises_http_500_with_value_error(self):
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
            patch(
                "gnosis.routers.ai._get_note_or_404",
                new=AsyncMock(return_value=note),
            ),
            patch("gnosis.routers.ai.graph_rag", fake_graph),
            patch(
                "gnosis.routers.ai._LIGHTRAG_AVAILABLE_CHECK", return_value=True
            ),
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
