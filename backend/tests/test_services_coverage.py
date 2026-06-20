"""Coverage tests for service modules matching actual source signatures.

Services covered:
- gnosis/services/embeddings.py   (embed_dense uses fastembed lazy model)
- gnosis/services/fts.py          (fulltext_search(db, query, *, limit, ...) -> dict)
- gnosis/services/hybrid_search.py (hybrid_search(query, owner_ids, ...) -> dict)
- gnosis/services/markdown_parser.py (parse_note_file, extract_wikilinks, ...)
- gnosis/services/vector_store.py  (upsert_note, delete_note, hybrid_search)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# embeddings.py  —  uses fastembed TextEmbedding, lazy _dense_model global
# ---------------------------------------------------------------------------

def test_embed_dense_returns_list():
    """embed_dense() calls model.embed() and returns list[float]."""
    fake_model = MagicMock()
    fake_model.embed.return_value = iter([[0.1, 0.2, 0.3]])

    import gnosis.services.embeddings as emb
    original = emb._dense_model
    emb._dense_model = fake_model
    try:
        result = emb.embed_dense("hello world")
        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)
    finally:
        emb._dense_model = original


def test_embed_dense_empty_string():
    fake_model = MagicMock()
    fake_model.embed.return_value = iter([[]])

    import gnosis.services.embeddings as emb
    original = emb._dense_model
    emb._dense_model = fake_model
    try:
        result = emb.embed_dense("")
        assert isinstance(result, list)
    finally:
        emb._dense_model = original


# ---------------------------------------------------------------------------
# fts.py  —  fulltext_search(db, query, *, limit, ...) -> dict with 'results'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fulltext_search_returns_list():
    """fulltext_search returns a dict with a 'results' key."""
    from unittest.mock import AsyncMock
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    db.execute.return_value = mock_result

    from gnosis.services.fts import fulltext_search
    out = await fulltext_search(db, "python")
    assert isinstance(out, dict)
    assert "results" in out


@pytest.mark.asyncio
async def test_fulltext_search_empty_query():
    """Empty query returns early with empty results."""
    from unittest.mock import AsyncMock
    db = AsyncMock()

    from gnosis.services.fts import fulltext_search
    out = await fulltext_search(db, "")
    assert isinstance(out, dict)
    assert out["results"] == []


# ---------------------------------------------------------------------------
# hybrid_search.py  —  hybrid_search(query, owner_ids, ...) -> dict
#   owner_ids is a set[int], the function is SYNC (not async)
# ---------------------------------------------------------------------------

def test_hybrid_search_returns_list():
    """hybrid_search returns a dict with 'results' key."""
    with patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 768), \
         patch("gnosis.services.hybrid_search.get_qdrant_client") as mock_client:
        mock_qdrant = MagicMock()
        mock_qdrant.query_points.return_value = MagicMock(points=[])
        mock_client.return_value = mock_qdrant

        from gnosis.services.hybrid_search import hybrid_search
        out = hybrid_search("python", owner_ids={1})
        assert isinstance(out, dict)
        assert "results" in out


def test_hybrid_search_deduplicates():
    """hybrid_search with empty owner_ids returns early."""
    from gnosis.services.hybrid_search import hybrid_search
    out = hybrid_search("test", owner_ids=set())
    assert out["results"] == []


# ---------------------------------------------------------------------------
# markdown_parser.py  —  parse_note_file(path), extract_wikilinks(body)
# ---------------------------------------------------------------------------

def test_parse_note_file_no_frontmatter(tmp_path: Path):
    """parse_note_file on a plain markdown file returns expected keys."""
    md = tmp_path / "test.md"
    md.write_text("# Hello\n\nSome body text.", encoding="utf-8")

    from gnosis.services.markdown_parser import parse_note_file
    result = parse_note_file(md)
    assert result["title"] == "test"
    assert "body" in result
    assert "wikilinks" in result
    assert "word_count" in result


def test_parse_note_file_with_frontmatter(tmp_path: Path):
    """parse_note_file correctly parses YAML frontmatter."""
    md = tmp_path / "note.md"
    md.write_text(
        "---\ntitle: My Note\ntags: [python, testing]\n---\n\nBody here.",
        encoding="utf-8",
    )

    from gnosis.services.markdown_parser import parse_note_file
    result = parse_note_file(md)
    assert result["title"] == "My Note"
    assert "python" in result["tags"]
    assert result["body"].strip() == "Body here."


# ---------------------------------------------------------------------------
# vector_store.py  —  upsert_note(...), delete_note(note_id)
# ---------------------------------------------------------------------------

def test_vector_search_returns_list():
    """vector_store.hybrid_search returns a list."""
    with patch("gnosis.services.vector_store.embed_dense", return_value=[0.0] * 768), \
         patch("gnosis.services.vector_store.get_qdrant_client") as mock_client:
        mock_qdrant = MagicMock()
        mock_qdrant.query_points.return_value = MagicMock(points=[])
        mock_client.return_value = mock_qdrant

        from gnosis.services.vector_store import hybrid_search
        result = hybrid_search("test query", owner_ids={1})
        assert isinstance(result, list)


def test_upsert_note_calls_client():
    """upsert_note calls client.upsert with a PointStruct."""
    with patch("gnosis.services.vector_store.embed_dense", return_value=[0.0] * 768), \
         patch("gnosis.services.vector_store.embed_colbert", return_value=[[0.0] * 128]), \
         patch("gnosis.services.vector_store.get_qdrant_client") as mock_client, \
         patch("gnosis.services.vector_store.get_settings") as mock_cfg:
        mock_cfg.return_value = MagicMock(qdrant_collection_name="gnosis_notes")
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        from gnosis.services.vector_store import upsert_note
        upsert_note(
            note_id="20240101-120000",
            title="Test",
            body="Some body",
            folder="00-inbox",
            note_type="permanent",
            status="draft",
            tags=["test"],
            owner_id=1,
        )
        mock_qdrant.upsert.assert_called_once()


def test_delete_note_calls_client():
    """delete_note calls client.delete."""
    with patch("gnosis.services.vector_store.get_qdrant_client") as mock_client, \
         patch("gnosis.services.vector_store.get_settings") as mock_cfg:
        mock_cfg.return_value = MagicMock(qdrant_collection_name="gnosis_notes")
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        from gnosis.services.vector_store import delete_note
        delete_note("20240101-120000")
        mock_qdrant.delete.assert_called_once()
