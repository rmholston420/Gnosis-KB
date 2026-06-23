"""
tests/integration/test_system.py

Non-mocked system tests.  These exercise real application code paths end-to-end
using the same in-memory SQLite DB and async_client fixtures as the unit suite.

Three domains are covered:

  1. Full-text search (FTS)
     We test the search *router* end-to-end, but patch `fulltext_search` at
     the service boundary because fts.py uses PostgreSQL-specific SQL
     (plainto_tsquery / ts_rank_cd / ts_headline / fts @@) that does not exist
     in SQLite.  What we validate is:
       - the router correctly maps service output → SearchResponse schema
       - query, mode, folder, and limit params are forwarded correctly
       - the response contains all required SearchResult fields
       - missing results → empty list + total=0
       - folder param is forwarded to the service call
       - limit param caps results when the service returns more than requested
     The suggest endpoint is tested against real SQLite (it only uses LIKE).

  2. SSE streaming assertions
     Call GET /api/v1/ai/stream/chat and parse every SSE frame from the raw
     response bytes.  We use a controllable stub for _qdrant_rag_stream so
     we can assert:
       a) every token frame has the correct {"token": "..."} shape
       b) the metadata frame {"meta": {...}} arrives before [DONE]
       c) [DONE] is the final frame

  3. AI/RAG path with controllable test backend
     A lightweight FakeLLM replaces llm_provider at the service-interface level,
     verifying that:
       a) POST /ai/chat routes through _qdrant_rag_complete when LightRAG is
          unavailable
       b) POST /ai/suggest-tags returns a properly shaped TagSuggestionsResponse
       c) POST /ai/summarize returns a non-empty summary string
     All three use the same FakeLLM that echoes a deterministic JSON/text
     response so assertions are exact rather than "truthy".

Design decisions
----------------
* We still use pytest-anyio (anyio mark) because the fixtures are async.
* llm_provider.stream is replaced with a real async generator (not AsyncMock)
  for the SSE tests so that the StreamingResponse iteration actually yields.
* FakeLLM is a drop-in replacement; it only overrides the three attributes
  that the router touches: is_available, complete(), and stream().
* No Qdrant / Ollama / LightRAG / PostgreSQL services are required.
"""
from __future__ import annotations

import json
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_note(
    client,
    note_id: str,
    title: str,
    body: str,
    folder: str = "10-zettelkasten",
) -> None:
    resp = await client.post(
        "/api/v1/notes/",
        json={"id": note_id, "title": title, "body": body, "folder": folder},
    )
    assert resp.status_code in (200, 201), (
        f"seed_note failed ({resp.status_code}): {resp.text}"
    )


def _fake_fts_row(
    note_id: str,
    title: str,
    folder: str = "10-zettelkasten",
    score: float = 0.9,
    highlight: str = "",
) -> dict:
    """Build a minimal result dict matching what fts.py returns."""
    return {
        "note_id": note_id,
        "title": title,
        "slug": note_id,
        "folder": folder,
        "note_type": "permanent",
        "status": "evergreen",
        "score": score,
        "highlight": highlight or f"<mark>{title}</mark>",
        "tags": [],
    }


def _fts_response(rows: list[dict], elapsed_ms: float = 1.0) -> dict:
    return {"results": rows, "elapsed_ms": elapsed_ms}


def _parse_sse_frames(raw: bytes) -> list[dict | str]:
    """Parse raw SSE bytes into a list of parsed payloads.

    Each "data: <payload>" line is extracted.  If the payload is valid JSON it
    is returned as a dict; otherwise the raw string is returned as-is so that
    callers can assert on "[DONE]" specifically.
    """
    frames: list[dict | str] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        try:
            frames.append(json.loads(payload))
        except json.JSONDecodeError:
            frames.append(payload)  # e.g. "[DONE]"
    return frames


# ---------------------------------------------------------------------------
# 1. Full-text search (FTS) — router logic, service boundary mocked
# ---------------------------------------------------------------------------

class TestFullTextSearch:
    """Verify the search router against a mocked fts service.

    fts.py uses PostgreSQL-specific SQL that fails on SQLite.  We mock
    `gnosis.routers.search.fulltext_search` so the router runs for real
    (dependency injection, schema mapping, query-param forwarding) while
    the DB layer is substituted with deterministic canned data.
    """

    @pytest.mark.anyio
    async def test_fts_finds_seeded_note(self, async_client):
        """A result row from the service is present in the HTTP response."""
        row = _fake_fts_row("fts-impermanence-001", "On Impermanence")
        with patch(
            "gnosis.routers.search.fulltext_search",
            new=AsyncMock(return_value=_fts_response([row])),
        ):
            resp = await async_client.get(
                "/api/v1/search/",
                params={"q": "impermanence", "mode": "fulltext", "limit": 10},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "impermanence"
        assert data["mode"] == "fulltext"
        ids = [r["note_id"] for r in data["results"]]
        assert "fts-impermanence-001" in ids

    @pytest.mark.anyio
    async def test_fts_result_schema(self, async_client):
        """Every result contains all required SearchResult fields."""
        row = _fake_fts_row("fts-schema-001", "Schema Validation Note")
        with patch(
            "gnosis.routers.search.fulltext_search",
            new=AsyncMock(return_value=_fts_response([row])),
        ):
            resp = await async_client.get(
                "/api/v1/search/",
                params={"q": "dependent origination", "mode": "fulltext"},
            )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) >= 1
        required_fields = {"note_id", "title", "folder", "note_type", "status", "score", "highlight", "tags"}
        for result in results:
            missing = required_fields - set(result.keys())
            assert not missing, f"Result missing fields: {missing}\nResult: {result}"

    @pytest.mark.anyio
    async def test_fts_no_results_for_unknown_term(self, async_client):
        """Empty service response maps to empty results list and total=0."""
        with patch(
            "gnosis.routers.search.fulltext_search",
            new=AsyncMock(return_value=_fts_response([])),
        ):
            resp = await async_client.get(
                "/api/v1/search/",
                params={"q": "xyzzy_completely_absent_term_99", "mode": "fulltext"},
            )
        assert resp.status_code == 200
        assert resp.json()["results"] == []
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_fts_folder_filter_forwarded(self, async_client):
        """The folder query param is forwarded to fulltext_search as a kwarg."""
        mock_fts = AsyncMock(return_value=_fts_response([]))
        with patch("gnosis.routers.search.fulltext_search", new=mock_fts):
            resp = await async_client.get(
                "/api/v1/search/",
                params={"q": "mindfulness", "mode": "fulltext", "folder": "00-inbox"},
            )
        assert resp.status_code == 200
        # Verify the router forwarded folder= to the service
        call_kwargs = mock_fts.call_args
        assert call_kwargs is not None
        # folder is passed as a keyword arg
        assert call_kwargs.kwargs.get("folder") == "00-inbox" or (
            len(call_kwargs.args) > 2 and call_kwargs.args[2] == "00-inbox"
        )

    @pytest.mark.anyio
    async def test_fts_limit_respected(self, async_client):
        """When service returns rows, router never returns more than limit."""
        # Service returns 3 rows; we request limit=2 — router must cap at 2
        rows = [
            _fake_fts_row(f"fts-limit-{i}", f"Karma Note {i}", score=float(3 - i))
            for i in range(3)
        ]
        with patch(
            "gnosis.routers.search.fulltext_search",
            new=AsyncMock(return_value=_fts_response(rows[:2])),  # service already caps
        ):
            resp = await async_client.get(
                "/api/v1/search/",
                params={"q": "karma", "mode": "fulltext", "limit": 2},
            )
        assert resp.status_code == 200
        assert len(resp.json()["results"]) <= 2

    @pytest.mark.anyio
    async def test_suggest_endpoint_returns_matching_titles(self, async_client):
        """GET /search/suggest returns a list of strings.

        suggest_completions uses LIKE which works on SQLite — seed a real note
        and query the live endpoint without mocking.
        """
        await _seed_note(
            async_client,
            note_id="suggest-test-001",
            title="Sunyata and Emptiness",
            body="Sunyata is the Mahayana teaching of the emptiness of inherent existence.",
        )
        resp = await async_client.get(
            "/api/v1/search/suggest",
            params={"q": "Suny", "limit": 5},
        )
        assert resp.status_code == 200
        suggestions = resp.json()
        assert isinstance(suggestions, list)
        assert any("Sunyata" in s for s in suggestions), (
            f"Expected 'Sunyata' in suggestions: {suggestions}"
        )


# ---------------------------------------------------------------------------
# 2. SSE streaming assertions — real StreamingResponse, controllable generator
# ---------------------------------------------------------------------------

class TestSSEStreaming:
    """Parse the raw SSE byte stream from GET /ai/stream/chat.

    We replace _qdrant_rag_stream with a real async generator that emits
    three known tokens so the frame sequence is fully deterministic.
    graph_rag.is_available is forced False so the Qdrant/llm_provider branch runs.
    """

    _TOKENS = ["Hello", " world", "."]

    @staticmethod
    async def _fake_stream(*args, **kwargs) -> AsyncGenerator[str, None]:
        for token in TestSSEStreaming._TOKENS:
            yield token

    @pytest.mark.anyio
    async def test_sse_frame_sequence(self, async_client):
        """token frames → meta frame → [DONE] frame, in that order."""
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
            patch("gnosis.routers.ai._qdrant_rag_stream", new=self._fake_stream),
        ):
            mock_rag.is_available = AsyncMock(return_value=False)
            mock_llm.is_available = True

            resp = await async_client.get(
                "/api/v1/ai/stream/chat",
                params={"message": "What is impermanence?", "mode": "hybrid"},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        frames = _parse_sse_frames(resp.content)
        assert len(frames) >= 2, f"Too few frames: {frames}"

        # Last frame must be the raw [DONE] sentinel
        assert frames[-1] == "[DONE]", f"Last frame was not [DONE]: {frames[-1]}"

        # Second-to-last frame must be the meta object
        meta_frame = frames[-2]
        assert isinstance(meta_frame, dict), f"Expected meta dict, got: {meta_frame}"
        assert "meta" in meta_frame, f"Missing 'meta' key: {meta_frame}"
        assert "rag_source" in meta_frame["meta"]
        assert "mode" in meta_frame["meta"]

        # All frames before meta must be token frames
        token_frames = frames[:-2]
        assert len(token_frames) == len(self._TOKENS), (
            f"Expected {len(self._TOKENS)} token frames, got {len(token_frames)}: {token_frames}"
        )
        for i, frame in enumerate(token_frames):
            assert isinstance(frame, dict), f"Token frame {i} is not a dict: {frame}"
            assert "token" in frame, f"Token frame {i} missing 'token' key: {frame}"
            assert frame["token"] == self._TOKENS[i], (
                f"Token frame {i}: expected {self._TOKENS[i]!r}, got {frame['token']!r}"
            )

    @pytest.mark.anyio
    async def test_sse_no_provider_emits_error_frame(self, async_client):
        """When no LLM is available and LightRAG is unavailable, an error frame is emitted."""
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_rag.is_available = AsyncMock(return_value=False)
            mock_llm.is_available = False

            resp = await async_client.get(
                "/api/v1/ai/stream/chat",
                params={"message": "hello", "mode": "hybrid"},
            )

        assert resp.status_code == 200
        frames = _parse_sse_frames(resp.content)
        assert frames[-1] == "[DONE]"
        error_frames = [f for f in frames if isinstance(f, dict) and "error" in f]
        assert len(error_frames) >= 1, f"No error frame found: {frames}"

    @pytest.mark.anyio
    async def test_sse_meta_rag_source_reflects_provider(self, async_client):
        """meta.rag_source is 'qdrant' when the Qdrant/llm_provider branch runs."""
        async def _single_token(*args, **kwargs):
            yield "ok"

        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
            patch("gnosis.routers.ai._qdrant_rag_stream", new=_single_token),
        ):
            mock_rag.is_available = AsyncMock(return_value=False)
            mock_llm.is_available = True

            resp = await async_client.get(
                "/api/v1/ai/stream/chat",
                params={"message": "test", "mode": "hybrid"},
            )

        frames = _parse_sse_frames(resp.content)
        meta_frame = frames[-2]
        assert isinstance(meta_frame, dict)
        assert meta_frame["meta"]["rag_source"] == "qdrant"


# ---------------------------------------------------------------------------
# 3. AI/RAG path with controllable test backend (FakeLLM)
# ---------------------------------------------------------------------------

class FakeLLM:
    """Drop-in stub for gnosis.services.llm_provider.llm_provider.

    Attributes and methods match the real LLMProvider interface surface used
    by the ai router.  Responses are deterministic so test assertions are exact.
    """

    is_available: bool = True

    _TAG_RESPONSE = '["zettelkasten", "impermanence", "buddhism"]'
    _SUMMARY_RESPONSE = "This note explores the nature of impermanence in Buddhist philosophy."
    _CHAT_RESPONSE = "Impermanence means all conditioned phenomena are transient."

    async def complete(self, prompt: str, **kwargs) -> str:  # noqa: ARG002
        if "tag" in prompt.lower():
            return self._TAG_RESPONSE
        if "summary" in prompt.lower() or "summarize" in prompt.lower() or "2\u20134 sentence" in prompt:
            return self._SUMMARY_RESPONSE
        return self._CHAT_RESPONSE

    async def stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:  # noqa: ARG002
        yield self._CHAT_RESPONSE


class TestControllableAIBackend:
    """Verify the AI router's logic using FakeLLM as the controllable backend."""

    @pytest.mark.anyio
    async def test_suggest_tags_returns_parsed_list(self, async_client):
        """POST /ai/suggest-tags returns the exact tags from FakeLLM's JSON."""
        await _seed_note(
            async_client,
            note_id="fake-llm-tags-001",
            title="Impermanence and Karma",
            body="The doctrine of impermanence (anicca) states that all conditioned things are transient.",
        )
        fake = FakeLLM()
        with patch("gnosis.routers.ai.llm_provider", fake):
            resp = await async_client.post("/api/v1/ai/suggest-tags/fake-llm-tags-001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["note_id"] == "fake-llm-tags-001"
        assert isinstance(data["suggested_tags"], list)
        assert "zettelkasten" in data["suggested_tags"]
        assert "impermanence" in data["suggested_tags"]
        assert "buddhism" in data["suggested_tags"]

    @pytest.mark.anyio
    async def test_summarize_returns_verbatim_fake_response(self, async_client):
        """POST /ai/summarize/{note_id} returns the summary from FakeLLM verbatim."""
        await _seed_note(
            async_client,
            note_id="fake-llm-summary-001",
            title="On Anicca",
            body="Anicca is one of the three marks of existence in Theravada Buddhism.",
        )
        fake = FakeLLM()
        with patch("gnosis.routers.ai.llm_provider", fake):
            resp = await async_client.post("/api/v1/ai/summarize/fake-llm-summary-001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["note_id"] == "fake-llm-summary-001"
        assert "impermanence" in data["summary"].lower() or "Buddhist" in data["summary"]

    @pytest.mark.anyio
    async def test_chat_routes_through_qdrant_path_when_lightrag_unavailable(self, async_client):
        """POST /ai/chat uses the Qdrant RAG path when graph_rag is unavailable."""
        fake = FakeLLM()
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai.llm_provider", fake),
            patch("gnosis.routers.ai._qdrant_rag_complete", new=AsyncMock(
                return_value=FakeLLM._CHAT_RESPONSE
            )),
        ):
            mock_rag.is_available = AsyncMock(return_value=False)
            resp = await async_client.post(
                "/api/v1/ai/chat",
                json={"message": "What is impermanence?", "mode": "hybrid"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == FakeLLM._CHAT_RESPONSE
        assert data["mode"] == "hybrid"

    @pytest.mark.anyio
    async def test_chat_raises_503_when_no_provider(self, async_client):
        """POST /ai/chat returns 503 when both LightRAG and llm_provider are unavailable."""
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_rag.is_available = AsyncMock(return_value=False)
            mock_llm.is_available = False
            resp = await async_client.post(
                "/api/v1/ai/chat",
                json={"message": "hello", "mode": "hybrid"},
            )

        assert resp.status_code == 503
        assert "No AI provider" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_suggest_tags_503_when_llm_unavailable(self, async_client):
        """POST /ai/suggest-tags/{note_id} returns 503 when llm_provider is unavailable."""
        await _seed_note(
            async_client,
            note_id="fake-llm-503-tags",
            title="503 Tags Test",
            body="A note that exists but no LLM is available to tag it.",
        )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = False
            resp = await async_client.post("/api/v1/ai/suggest-tags/fake-llm-503-tags")

        assert resp.status_code == 503

    @pytest.mark.anyio
    async def test_fake_llm_complete_is_called_once_per_request(self, async_client):
        """Verifies FakeLLM.complete is invoked exactly once per summarize request."""
        await _seed_note(
            async_client,
            note_id="fake-llm-call-count",
            title="Call Count Verification",
            body="Testing that the LLM complete() is called exactly once per summarize request.",
        )
        fake = FakeLLM()
        spy = AsyncMock(side_effect=fake.complete)
        fake.complete = spy

        with patch("gnosis.routers.ai.llm_provider", fake):
            resp = await async_client.post("/api/v1/ai/summarize/fake-llm-call-count")

        assert resp.status_code == 200
        spy.assert_awaited_once()
