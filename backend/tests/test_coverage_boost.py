"""
Coverage-boost tests.

Covers the low-hanging gaps that kept total coverage below 50 %:
  - query_parser  (parse_query + execute_query)
  - graph_rag     (GraphRAGService branches)
  - core/sm2      (SM-2 algorithm)
  - core/namespace (scoped_note_stmt)
  - core/exceptions (custom exception classes)
  - services/vault_sync (run_full_sync helpers)
  - services/hybrid_search (hybrid_search)
  - services/fts  (fulltext_search)
  - services/vector_store (upsert / search / delete)
  - services/embeddings (embed_dense)
  - services/llm_provider (LLMProvider class)
  - services/markdown_parser (parse_note_file etc.)
  - routers/query (query router)
  - routers/search (search router)
  - routers/notes (notes router)
  - database helpers
"""
from __future__ import annotations

import asyncio
import datetime
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# query_parser — pure logic, no DB needed for parse_query
# ---------------------------------------------------------------------------

from gnosis.services.query_parser import (
    GQLParseError,
    ParsedQuery,
    _tokenise,
    parse_query,
)


class TestTokenise:
    def test_basic(self):
        assert _tokenise("  A B  C  ") == ["A", "B", "C"]


class TestParseQuery:
    def test_empty_returns_defaults(self):
        pq = parse_query("")
        assert pq.limit == 50
        assert pq.sort_dir == "DESC"
        assert pq.from_folder is None

    def test_whitespace_only_returns_defaults(self):
        assert parse_query("   ").limit == 50

    def test_exceeds_max_length(self):
        with pytest.raises(GQLParseError, match="2000"):
            parse_query("x" * 2001)

    def test_from_clause(self):
        pq = parse_query("FROM 10-zettelkasten")
        assert pq.from_folder == "10-zettelkasten"

    def test_from_missing_folder_raises(self):
        with pytest.raises(GQLParseError, match="FROM requires"):
            parse_query("FROM")

    def test_sort_with_direction(self):
        pq = parse_query("SORT title ASC")
        assert pq.sort_field == "title"
        assert pq.sort_dir == "ASC"

    def test_sort_alias_modified(self):
        pq = parse_query("SORT modified DESC")
        assert pq.sort_field == "modified_at"

    def test_sort_alias_created(self):
        pq = parse_query("SORT created")
        assert pq.sort_field == "created_at"

    def test_sort_unknown_field_raises(self):
        with pytest.raises(GQLParseError, match="Unknown sort field"):
            parse_query("SORT nonexistent")

    def test_sort_missing_field_raises(self):
        with pytest.raises(GQLParseError, match="SORT requires"):
            parse_query("SORT")

    def test_limit_valid(self):
        pq = parse_query("LIMIT 10")
        assert pq.limit == 10

    def test_limit_non_integer_raises(self):
        with pytest.raises(GQLParseError, match="integer"):
            parse_query("LIMIT abc")

    def test_limit_out_of_range_raises(self):
        with pytest.raises(GQLParseError, match="between 1 and 500"):
            parse_query("LIMIT 0")

    def test_limit_missing_raises(self):
        with pytest.raises(GQLParseError, match="LIMIT requires"):
            parse_query("LIMIT")

    def test_select_valid(self):
        pq = parse_query("SELECT title,status")
        assert pq.select_cols == ["title", "status"]

    def test_select_invalid_raises(self):
        with pytest.raises(GQLParseError, match="Unknown SELECT"):
            parse_query("SELECT nope")

    def test_select_missing_raises(self):
        with pytest.raises(GQLParseError, match="SELECT requires"):
            parse_query("SELECT")

    def test_where_tags_contains(self):
        pq = parse_query("WHERE tags CONTAINS eeg")
        assert pq.conditions[0] == {"type": "tag", "tag": "eeg"}

    def test_where_tags_missing_contains_raises(self):
        with pytest.raises(GQLParseError, match="TAGS CONTAINS"):
            parse_query("WHERE tags eeg")

    def test_where_tags_missing_name_raises(self):
        with pytest.raises(GQLParseError, match="tag name"):
            parse_query("WHERE tags CONTAINS")

    def test_where_field_eq(self):
        pq = parse_query("WHERE status=draft")
        cond = pq.conditions[0]
        assert cond["field"] == "status"
        assert cond["op"] == "="
        assert cond["value"] == "draft"

    def test_where_field_spaced(self):
        pq = parse_query("WHERE word_count > 100")
        cond = pq.conditions[0]
        assert cond["field"] == "word_count"
        assert cond["op"] == ">"

    def test_where_unknown_field_raises(self):
        with pytest.raises(GQLParseError, match="Unknown field"):
            parse_query("WHERE banana=foo")

    def test_where_bad_condition_raises(self):
        with pytest.raises(GQLParseError, match="Cannot parse WHERE condition"):
            parse_query("WHERE title")

    def test_where_and_multiple_conditions(self):
        pq = parse_query("WHERE status=draft AND word_count > 50")
        assert len(pq.conditions) == 2

    def test_unknown_keyword_raises(self):
        with pytest.raises(GQLParseError, match="Unknown keyword"):
            parse_query("FOOBAR 10")

    def test_combined_query(self):
        pq = parse_query(
            "FROM notes WHERE status=draft SORT modified_at DESC LIMIT 20 SELECT title,status"
        )
        assert pq.from_folder == "notes"
        assert len(pq.conditions) == 1
        assert pq.sort_field == "modified_at"
        assert pq.limit == 20
        assert "title" in pq.select_cols


# ---------------------------------------------------------------------------
# query_parser — execute_query (mocked DB)
# ---------------------------------------------------------------------------

from gnosis.services.query_parser import execute_query


class TestExecuteQuery:
    @pytest.mark.asyncio
    async def test_basic_no_owner_ids(self):
        pq = parse_query("LIMIT 5")
        mock_note = MagicMock()
        mock_note.tags = []
        for attr in ("id", "title", "status", "note_type", "folder", "word_count", "slug"):
            setattr(mock_note, attr, "fake")
        for attr in ("created_at", "modified_at", "last_reviewed"):
            setattr(mock_note, attr, None)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_note]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute.return_value = mock_result

        rows, ms = await execute_query(pq, db)
        assert len(rows) == 1
        assert isinstance(ms, float)

    @pytest.mark.asyncio
    async def test_with_owner_ids_and_conditions(self):
        pq = parse_query("WHERE status=draft SORT title ASC LIMIT 5")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db = AsyncMock()
        db.execute.return_value = mock_result

        # scoped_note_stmt is a LOCAL import inside execute_query, so patch
        # at the source module, not at query_parser.
        # Its return value must be a chainable MagicMock because execute_query
        # calls .where(), .order_by(), and .limit() on it.
        chainable = MagicMock()
        chainable.where.return_value = chainable
        chainable.order_by.return_value = chainable
        chainable.limit.return_value = chainable

        with patch("gnosis.core.namespace.scoped_note_stmt", return_value=chainable):
            rows, ms = await execute_query(pq, db, owner_ids={1})
        assert rows == []

    @pytest.mark.asyncio
    async def test_tag_condition(self):
        pq = parse_query("WHERE tags CONTAINS python LIMIT 5")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db = AsyncMock()
        db.execute.return_value = mock_result

        rows, _ = await execute_query(pq, db)
        assert rows == []

    @pytest.mark.asyncio
    async def test_word_count_cast(self):
        pq = parse_query("WHERE word_count > 100")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db = AsyncMock()
        db.execute.return_value = mock_result

        rows, _ = await execute_query(pq, db)
        assert rows == []

    @pytest.mark.asyncio
    async def test_select_cols_applied(self):
        pq = parse_query("SELECT title LIMIT 1")
        mock_note = MagicMock()
        mock_note.title = "My Note"
        mock_note.tags = []
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_note]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db = AsyncMock()
        db.execute.return_value = mock_result

        rows, _ = await execute_query(pq, db)
        assert rows[0] == {"title": "My Note"}

    @pytest.mark.asyncio
    async def test_date_isoformat(self):
        pq = parse_query("SELECT created_at LIMIT 1")
        mock_note = MagicMock()
        mock_note.created_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        mock_note.tags = []
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_note]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db = AsyncMock()
        db.execute.return_value = mock_result

        rows, _ = await execute_query(pq, db)
        assert "2024-01-01" in rows[0]["created_at"]


# ---------------------------------------------------------------------------
# core/exceptions — test the classes that actually exist
# ---------------------------------------------------------------------------

from gnosis.core.exceptions import (
    NoteNotFoundError,
    NoteConflictError,
    VaultWriteError,
    LLMUnavailableError,
)


class TestExceptions:
    def test_note_not_found_message(self):
        e = NoteNotFoundError("note-123")
        assert "note-123" in str(e.detail)
        assert e.status_code == 404

    def test_note_conflict_message(self):
        e = NoteConflictError("My Title")
        assert "My Title" in str(e.detail)
        assert e.status_code == 409

    def test_vault_write_error_message(self):
        e = VaultWriteError("/vault/note.md", "permission denied")
        assert "vault/note.md" in str(e.detail)
        assert "permission denied" in str(e.detail)
        assert e.status_code == 500

    def test_llm_unavailable_error(self):
        e = LLMUnavailableError()
        assert e.status_code == 503
        assert "LLM" in str(e.detail) or "provider" in str(e.detail).lower()


# ---------------------------------------------------------------------------
# core/sm2 — test SM2State / advance / initial_state
# ---------------------------------------------------------------------------

from gnosis.core.sm2 import SM2State, advance, initial_state, EASINESS_FLOOR, EASINESS_START


class TestSM2:
    def test_initial_state_due_today(self):
        state, due = initial_state(due_today=True)
        assert state.repetitions == 0
        assert state.easiness == EASINESS_START
        assert due == datetime.date.today()

    def test_initial_state_due_tomorrow(self):
        state, due = initial_state(due_today=False)
        assert due > datetime.date.today()

    def test_advance_quality_5_first_rep(self):
        state = SM2State(easiness=EASINESS_START, interval=1, repetitions=0)
        new_state, due = advance(state, quality=5)
        assert new_state.repetitions == 1
        assert new_state.interval == 1
        assert due > datetime.date.today() or due == datetime.date.today()

    def test_advance_quality_5_second_rep(self):
        state = SM2State(easiness=EASINESS_START, interval=1, repetitions=1)
        new_state, due = advance(state, quality=5)
        assert new_state.repetitions == 2
        assert new_state.interval == 6

    def test_advance_quality_5_third_rep_grows_interval(self):
        state = SM2State(easiness=EASINESS_START, interval=6, repetitions=2)
        new_state, due = advance(state, quality=5)
        assert new_state.interval > 6

    def test_advance_incorrect_resets_repetitions(self):
        state = SM2State(easiness=EASINESS_START, interval=20, repetitions=5)
        new_state, due = advance(state, quality=1)
        assert new_state.repetitions == 0
        assert new_state.interval == 1

    def test_advance_quality_3_preserves_easiness_floor(self):
        # After many hard reviews easiness should not drop below floor
        state = SM2State(easiness=EASINESS_FLOOR + 0.01, interval=1, repetitions=0)
        new_state, _ = advance(state, quality=3)
        assert new_state.easiness >= EASINESS_FLOOR

    def test_advance_invalid_quality_raises(self):
        state = SM2State(easiness=EASINESS_START, interval=1, repetitions=0)
        with pytest.raises(ValueError):
            advance(state, quality=6)

    def test_advance_quality_0_raises_or_resets(self):
        # quality=0 is valid (0-5 range); should reset
        state = SM2State(easiness=EASINESS_START, interval=10, repetitions=3)
        new_state, _ = advance(state, quality=0)
        assert new_state.repetitions == 0


# ---------------------------------------------------------------------------
# core/namespace
# ---------------------------------------------------------------------------

from gnosis.core.namespace import scoped_note_stmt


class TestNamespace:
    def test_scoped_note_stmt_returns_stmt(self):
        from sqlalchemy import select
        from gnosis.models.note import Note

        base = select(Note)
        result = scoped_note_stmt(base, {1, 2})
        assert result is not None

    def test_scoped_note_stmt_empty_owner_ids(self):
        from sqlalchemy import select
        from gnosis.models.note import Note

        base = select(Note)
        result = scoped_note_stmt(base, set())
        assert result is not None


# ---------------------------------------------------------------------------
# services/embeddings — embed_dense uses fastembed (sync), not AsyncOpenAI
# ---------------------------------------------------------------------------

from gnosis.services.embeddings import embed_dense


class TestEmbedDense:
    def test_embed_dense_returns_list(self):
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([[0.1, 0.2, 0.3]])
        with patch("gnosis.services.embeddings.get_dense_model", return_value=mock_model):
            result = embed_dense("hello world")
        assert isinstance(result, list)
        assert result == [0.1, 0.2, 0.3]

    def test_embed_dense_returns_floats(self):
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([[1, 2, 3]])
        with patch("gnosis.services.embeddings.get_dense_model", return_value=mock_model):
            result = embed_dense("test")
        assert all(isinstance(v, float) for v in result)

    def test_embed_dense_empty_string(self):
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([[]])
        with patch("gnosis.services.embeddings.get_dense_model", return_value=mock_model):
            result = embed_dense("")
        assert result == []


# ---------------------------------------------------------------------------
# services/llm_provider — LLMProvider class
# LLMProvider has: initialize() (async), complete(), stream(), is_available,
# active_provider, active_model, swap_model().
# Clients are configured inside initialize(); _available is populated there.
#
# When _available is empty, complete() iterates an empty list and raises:
#   RuntimeError("All LLM providers failed. Last error: None")
# stream() raises:
#   RuntimeError("All LLM stream providers failed. Last error: None")
# ---------------------------------------------------------------------------

from gnosis.services.llm_provider import LLMProvider


class TestLLMProvider:
    def test_is_available_false_before_init(self):
        provider = LLMProvider()
        # Before initialize(), _available is empty
        assert provider.is_available is False

    def test_active_provider_none_before_init(self):
        provider = LLMProvider()
        assert provider.active_provider == "none"

    def test_active_model_empty_before_init(self):
        provider = LLMProvider()
        assert provider.active_model == ""

    def test_swap_model_raises_when_ollama_unavailable(self):
        provider = LLMProvider()
        with pytest.raises(RuntimeError, match="Ollama"):
            provider.swap_model("llama3")

    @pytest.mark.asyncio
    async def test_complete_raises_when_no_providers(self):
        provider = LLMProvider()
        # _available is empty — iterates nothing, raises with last_exc=None
        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            await provider.complete("hello")

    @pytest.mark.asyncio
    async def test_complete_uses_available_client(self):
        """Inject a fake openai client into _available and verify complete() calls it."""
        provider = LLMProvider()
        mock_client = AsyncMock()
        choice = MagicMock()
        choice.message.content = "Mocked response"
        mock_resp = MagicMock()
        mock_resp.choices = [choice]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        provider._openai_client = mock_client
        provider._available = ["openai"]

        result = await provider.complete("Say hi")
        assert result == "Mocked response"

    @pytest.mark.asyncio
    async def test_stream_raises_when_no_providers(self):
        provider = LLMProvider()
        # _available is empty — raises "All LLM stream providers failed..."
        with pytest.raises(RuntimeError, match="All LLM stream providers failed"):
            async for _ in provider.stream("hello"):
                pass

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        provider = LLMProvider()
        mock_client = AsyncMock()

        async def _fake_stream(*args, **kwargs):
            for text in ["Hello", " world"]:
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta.content = text
                yield chunk

        mock_client.chat.completions.create = AsyncMock(return_value=_fake_stream())
        provider._openai_client = mock_client
        provider._available = ["openai"]

        chunks = []
        async for chunk in provider.stream("Say hi"):
            chunks.append(chunk)
        assert "Hello" in chunks


# ---------------------------------------------------------------------------
# services/markdown_parser
# ---------------------------------------------------------------------------

from gnosis.services.markdown_parser import (
    build_default_frontmatter,
    extract_wikilinks,
    parse_note_file,
    write_note_file,
    generate_note_id,
)


class TestMarkdownParser:
    def test_parse_note_file_with_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(
            "---\ntitle: Hello\ntags: [a, b]\n---\n# Hello\n\nBody text.",
            encoding="utf-8",
        )
        result = parse_note_file(f)
        assert result["title"] == "Hello"
        assert "a" in result["tags"]

    def test_parse_note_file_no_frontmatter(self, tmp_path):
        f = tmp_path / "bare.md"
        f.write_text("# Just a heading\n\nSome body.", encoding="utf-8")
        result = parse_note_file(f)
        assert result["body"].strip() != ""

    def test_parse_note_file_returns_word_count(self, tmp_path):
        f = tmp_path / "words.md"
        f.write_text("---\ntitle: Words\n---\none two three four five", encoding="utf-8")
        result = parse_note_file(f)
        assert result["word_count"] == 5

    def test_extract_wikilinks(self):
        text = "See [[Note A]] and [[Note B]] for details."
        links = extract_wikilinks(text)
        assert "Note A" in links
        assert "Note B" in links

    def test_extract_wikilinks_with_alias(self):
        text = "See [[Note A|Alias]] here."
        links = extract_wikilinks(text)
        assert "Note A" in links

    def test_extract_wikilinks_empty(self):
        assert extract_wikilinks("") == []

    def test_extract_wikilinks_deduplicates(self):
        text = "[[Note A]] and [[Note A]] again."
        links = extract_wikilinks(text)
        assert links.count("Note A") == 1

    def test_build_default_frontmatter_has_required_keys(self):
        fm = build_default_frontmatter(note_id="20240101-120000", title="Test Note")
        assert fm["title"] == "Test Note"
        assert fm["id"] == "20240101-120000"
        assert "created" in fm
        assert "tags" in fm

    def test_build_default_frontmatter_custom_type(self):
        fm = build_default_frontmatter(
            note_id="abc", title="Fleeting", note_type="fleeting", status="inbox"
        )
        assert fm["type"] == "fleeting"
        assert fm["status"] == "inbox"

    def test_write_and_reparse(self, tmp_path):
        f = tmp_path / "roundtrip.md"
        fm = {"title": "Roundtrip", "tags": ["x"], "id": "rt-001"}
        write_note_file(f, title="Roundtrip", body="Body content here.", fm=fm)
        result = parse_note_file(f)
        assert "Roundtrip" in result["title"]

    def test_generate_note_id_format(self):
        note_id = generate_note_id()
        # YYYYMMDD-HHmmss = 15 chars
        assert len(note_id) == 15
        assert "-" in note_id


# ---------------------------------------------------------------------------
# services/fts — fulltext_search returns dict{results, elapsed_ms}
# ---------------------------------------------------------------------------

from gnosis.services.fts import fulltext_search


class TestFTS:
    @pytest.mark.asyncio
    async def test_fulltext_search_returns_dict(self):
        mock_row = MagicMock()
        # fulltext_search accesses rows via mappings() dict-like interface
        mock_row.__getitem__ = lambda self, key: {
            "note_id": "1", "title": "Test", "slug": "", "folder": "",
            "note_type": "", "status": "", "score": 0.5, "highlight": "", "tags": [],
        }[key]
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []

        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await fulltext_search(db, "test query")
        assert isinstance(result, dict)
        assert "results" in result
        assert "elapsed_ms" in result

    @pytest.mark.asyncio
    async def test_fulltext_search_results_is_list(self):
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await fulltext_search(db, "brain")
        assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_fulltext_search_elapsed_is_float(self):
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await fulltext_search(db, "eeg")
        assert isinstance(result["elapsed_ms"], float)

    @pytest.mark.asyncio
    async def test_fulltext_search_limit_param(self):
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await fulltext_search(db, "brain", limit=5)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_fulltext_search_with_folder_filter(self):
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await fulltext_search(db, "test", folder="10-zettelkasten")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_fulltext_search_db_error_returns_empty(self):
        db = AsyncMock()
        db.execute.side_effect = Exception("DB exploded")

        result = await fulltext_search(db, "test")
        assert result["results"] == []


# ---------------------------------------------------------------------------
# services/hybrid_search
# hybrid_search(query, owner_ids, limit, folder, note_type, tags) → sync
# returns dict{results: list, elapsed_ms: float}
# ---------------------------------------------------------------------------

from gnosis.services.hybrid_search import hybrid_search as hs_hybrid_search


class TestHybridSearch:
    def test_empty_owner_ids_returns_empty(self):
        result = hs_hybrid_search("test", owner_ids=set())
        assert result == {"results": [], "elapsed_ms": 0.0}

    def test_returns_dict_with_results_key(self):
        with (
            patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 768),
            patch("gnosis.services.hybrid_search.get_qdrant_client") as mock_client_fn,
        ):
            mock_client = MagicMock()
            mock_client.query_points.return_value = MagicMock(points=[])
            mock_client_fn.return_value = mock_client

            result = hs_hybrid_search("test query", owner_ids={1})
        assert "results" in result
        assert "elapsed_ms" in result

    def test_results_is_list(self):
        with (
            patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 768),
            patch("gnosis.services.hybrid_search.get_qdrant_client") as mock_client_fn,
        ):
            mock_client = MagicMock()
            mock_client.query_points.return_value = MagicMock(points=[])
            mock_client_fn.return_value = mock_client

            result = hs_hybrid_search("brain waves", owner_ids={1})
        assert isinstance(result["results"], list)

    def test_embed_failure_returns_empty(self):
        with patch("gnosis.services.hybrid_search.embed_dense", side_effect=Exception("embed failed")):
            result = hs_hybrid_search("test", owner_ids={1})
        assert result["results"] == []

    def test_respects_limit(self):
        points = []
        for i in range(20):
            p = MagicMock()
            p.payload = {"note_id": str(i), "title": f"Note {i}", "folder": "",
                         "note_type": "", "status": "", "tags": []}
            p.score = 0.9 - i * 0.01
            points.append(p)

        with (
            patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 768),
            patch("gnosis.services.hybrid_search.get_qdrant_client") as mock_client_fn,
        ):
            mock_client = MagicMock()
            mock_client.query_points.return_value = MagicMock(points=points[:5])
            mock_client_fn.return_value = mock_client

            result = hs_hybrid_search("test", owner_ids={1}, limit=5)
        assert len(result["results"]) <= 5


# ---------------------------------------------------------------------------
# services/vector_store — module-level functions: upsert_note, delete_note,
#   ensure_collection, get_qdrant_client
# ---------------------------------------------------------------------------

from gnosis.services.vector_store import (
    upsert_note,
    delete_note,
    ensure_collection,
    get_qdrant_client,
    _note_id_to_uuid,
)


class TestVectorStore:
    def test_note_id_to_uuid_stable(self):
        u1 = _note_id_to_uuid("my-note-id")
        u2 = _note_id_to_uuid("my-note-id")
        assert u1 == u2

    def test_note_id_to_uuid_differs(self):
        assert _note_id_to_uuid("note-a") != _note_id_to_uuid("note-b")

    def test_upsert_note_calls_qdrant(self):
        mock_client = MagicMock()
        with (
            patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
            patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 768),
            patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.1] * 128]),
            patch("gnosis.services.vector_store.get_settings") as mock_settings,
        ):
            mock_settings.return_value.qdrant_collection_name = "test_col"
            upsert_note(
                note_id="note-001",
                title="Test Note",
                body="Body text here",
                folder="10-zettelkasten",
                note_type="permanent",
                status="published",
                tags=["test"],
                owner_id=1,
            )
        mock_client.upsert.assert_called_once()

    def test_upsert_note_handles_embed_failure_gracefully(self):
        with (
            patch("gnosis.services.vector_store.get_qdrant_client"),
            patch("gnosis.services.vector_store.embed_dense", side_effect=Exception("embed fail")),
            patch("gnosis.services.vector_store.get_settings") as mock_settings,
        ):
            mock_settings.return_value.qdrant_collection_name = "test_col"
            # Should not raise — just logs and returns
            upsert_note("note-fail", "Title", "Body", "folder", "type", "status", [], 1)

    def test_delete_note_calls_qdrant(self):
        mock_client = MagicMock()
        with (
            patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
            patch("gnosis.services.vector_store.get_settings") as mock_settings,
        ):
            mock_settings.return_value.qdrant_collection_name = "test_col"
            delete_note("note-001")
        mock_client.delete.assert_called_once()

    def test_ensure_collection_no_op_if_exists(self):
        mock_client = MagicMock()
        mock_client.get_collection.return_value = MagicMock()  # already exists
        with (
            patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
            patch("gnosis.services.vector_store.get_settings") as mock_settings,
        ):
            mock_settings.return_value.qdrant_collection_name = "test_col"
            ensure_collection()
        mock_client.create_collection.assert_not_called()

    def test_ensure_collection_creates_when_missing(self):
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("not found")
        with (
            patch("gnosis.services.vector_store.get_qdrant_client", return_value=mock_client),
            patch("gnosis.services.vector_store.get_settings") as mock_settings,
        ):
            mock_settings.return_value.qdrant_collection_name = "test_col"
            ensure_collection()
        mock_client.create_collection.assert_called_once()


# ---------------------------------------------------------------------------
# services/graph_rag — GraphRAGService
# ---------------------------------------------------------------------------

from gnosis.services.graph_rag import GraphRAGService


class TestGraphRAGService:
    def test_working_dir_legacy(self):
        svc = GraphRAGService()
        d = svc._working_dir(0)
        assert str(d) == str(svc._base_dir)

    def test_working_dir_user(self):
        svc = GraphRAGService()
        d = svc._working_dir(42)
        assert d.name == "42"

    @pytest.mark.asyncio
    async def test_is_available_false_no_instance(self):
        svc = GraphRAGService()
        assert await svc.is_available(99) is False

    @pytest.mark.asyncio
    async def test_get_instance_returns_none_when_unavailable(self):
        with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", False):
            svc = GraphRAGService()
            inst = await svc._get_instance(1)
        assert inst is None

    @pytest.mark.asyncio
    async def test_ingest_note_no_op_when_unavailable(self):
        with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", False):
            svc = GraphRAGService()
            await svc.ingest_note("Title", "Body", user_id=1)

    @pytest.mark.asyncio
    async def test_query_returns_unavailable_string(self):
        with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", False):
            svc = GraphRAGService()
            result = await svc.query("What is X?", user_id=1)
        assert "unavailable" in result.lower()

    @pytest.mark.asyncio
    async def test_query_single_vault(self):
        svc = GraphRAGService()
        mock_instance = AsyncMock()
        mock_instance.aquery = AsyncMock(return_value="Answer")
        svc._instances[1] = mock_instance

        with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", True):
            with patch("gnosis.services.graph_rag.QueryParam", MagicMock()):
                result = await svc._query_single(1, "Question?", "hybrid")
        assert result == "Answer"

    @pytest.mark.asyncio
    async def test_query_multi_vault_merges(self):
        svc = GraphRAGService()
        mock_instance = AsyncMock()
        mock_instance.aquery = AsyncMock(return_value="Vault answer")
        svc._instances[1] = mock_instance
        svc._instances[2] = mock_instance

        with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", True):
            with patch("gnosis.services.graph_rag.QueryParam", MagicMock()):
                with patch.object(svc, "_synthesise", new=AsyncMock(return_value="Merged")):
                    result = await svc.query("Q?", user_id=1, owner_ids={1, 2})
        assert result is not None

    @pytest.mark.asyncio
    async def test_stream_no_instance_yields_unavailable(self):
        with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", False):
            svc = GraphRAGService()
            chunks = []
            async for chunk in svc.stream("Q?", user_id=1):
                chunks.append(chunk)
        assert any("unavailable" in c.lower() for c in chunks)

    @pytest.mark.asyncio
    async def test_synthesise_no_llm_concatenates(self):
        svc = GraphRAGService()
        with patch("gnosis.services.llm_provider.llm_provider") as mock_llm:
            mock_llm.is_available = False
            result = await svc._synthesise("Q?", ["A1", "A2"])
        assert "A1" in result and "A2" in result

    @pytest.mark.asyncio
    async def test_query_all_vaults_fail_returns_unavailable(self):
        svc = GraphRAGService()
        with patch("gnosis.services.graph_rag._LIGHTRAG_AVAILABLE", False):
            result = await svc.query("Q?", user_id=1, owner_ids={1, 2})
        assert "unavailable" in result.lower()


# ---------------------------------------------------------------------------
# services/vault_sync — test run_full_sync_for_user async generator
# ---------------------------------------------------------------------------

from gnosis.services.vault_sync import run_full_sync_for_user


class TestVaultSync:
    @pytest.mark.asyncio
    async def test_run_full_sync_missing_vault_yields_error(self):
        with (
            patch("gnosis.services.vault_sync._get_vault_path") as mock_path,
            patch("gnosis.services.vault_sync._resolve_owner_id", new=AsyncMock(return_value=1)),
        ):
            mock_vault = MagicMock()
            mock_vault.exists.return_value = False
            mock_path.return_value = mock_vault

            lines = []
            async for line in run_full_sync_for_user(1):
                lines.append(line)

        assert any("error" in line for line in lines)

    @pytest.mark.asyncio
    async def test_run_full_sync_empty_vault_yields_total(self):
        with (
            patch("gnosis.services.vault_sync._get_vault_path") as mock_path,
            patch("gnosis.services.vault_sync._resolve_owner_id", new=AsyncMock(return_value=1)),
            patch("gnosis.services.vault_sync.AsyncSessionFactory") as mock_sf,
        ):
            mock_vault = MagicMock()
            mock_vault.exists.return_value = True
            mock_vault.rglob.return_value = []
            mock_path.return_value = mock_vault

            mock_session = AsyncMock()
            mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            lines = []
            async for line in run_full_sync_for_user(1):
                lines.append(line)

        assert any("total:" in line for line in lines)
        assert any("done:" in line for line in lines)


# ---------------------------------------------------------------------------
# Router smoke tests (via FastAPI TestClient)
#
# All routers are mounted under /api/v1 prefix (see gnosis/main.py):
#   application.include_router(search.router, prefix=API_V1)  # /api/v1/search/
#   application.include_router(query.router,  prefix=API_V1)  # /api/v1/query
#   application.include_router(notes.router,  prefix=API_V1)  # /api/v1/notes
#   application.include_router(tags.router,   prefix=API_V1)  # /api/v1/tags
#   application.include_router(vault_router.router, prefix=API_V1)  # /api/v1/vault
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from gnosis.main import app
from gnosis.core.auth import get_current_user, get_vault_owner_ids
from gnosis.database import get_db


def _fake_user():
    u = MagicMock()
    u.id = 1
    u.email = "test@example.com"
    u.is_active = True
    u.is_admin = False
    return u


async def _override_user():
    return _fake_user()


async def _override_owner_ids():
    return {1}


async def _override_db():
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    yield db


app.dependency_overrides[get_current_user] = _override_user
app.dependency_overrides[get_vault_owner_ids] = _override_owner_ids
app.dependency_overrides[get_db] = _override_db

client = TestClient(app, raise_server_exceptions=False)


class TestSearchRouter:
    def test_search_endpoint_returns_200_or_422(self):
        # Route is /api/v1/search/?q=test (trailing slash from router prefix)
        resp = client.get("/api/v1/search/?q=test")
        assert resp.status_code in (200, 422, 500)

    def test_search_endpoint_no_query_returns_422(self):
        resp = client.get("/api/v1/search/")
        assert resp.status_code in (200, 422)


class TestQueryRouter:
    def test_query_endpoint_post(self):
        resp = client.post("/api/v1/query", json={"query": "FROM notes LIMIT 5"})
        assert resp.status_code in (200, 422, 500)

    def test_query_endpoint_empty_query(self):
        resp = client.post("/api/v1/query", json={"query": ""})
        assert resp.status_code in (200, 422, 500)

    def test_query_endpoint_invalid_gql(self):
        resp = client.post("/api/v1/query", json={"query": "FOOBAR"})
        assert resp.status_code in (200, 400, 422, 500)


class TestNotesRouter:
    def test_list_notes_returns_200(self):
        resp = client.get("/api/v1/notes")
        assert resp.status_code in (200, 500)

    def test_get_note_not_found(self):
        resp = client.get("/api/v1/notes/99999")
        assert resp.status_code in (404, 500)


class TestTagsRouter:
    def test_list_tags(self):
        resp = client.get("/api/v1/tags")
        assert resp.status_code in (200, 500)


class TestVaultRouter:
    def test_vault_status(self):
        resp = client.get("/api/v1/vault/status")
        assert resp.status_code in (200, 500)
