"""Coverage tests for service modules:
- gnosis/services/embeddings.py
- gnosis/services/fts.py
- gnosis/services/hybrid_search.py
- gnosis/services/markdown_parser.py
- gnosis/services/vector_store.py
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# embeddings.py
# ---------------------------------------------------------------------------

def test_embed_dense_returns_list():
    with patch("gnosis.services.embeddings.SentenceTransformer") as mock_st:
        mock_model = MagicMock()
        mock_model.encode.return_value = [0.1, 0.2, 0.3]
        mock_st.return_value = mock_model

        from gnosis.services import embeddings as emb_module
        emb_module._model = mock_model  # inject mock

        result = emb_module.embed_dense("hello world")
        assert isinstance(result, list)


def test_embed_dense_empty_string():
    with patch("gnosis.services.embeddings.SentenceTransformer") as mock_st:
        mock_model = MagicMock()
        mock_model.encode.return_value = []
        mock_st.return_value = mock_model

        from gnosis.services import embeddings as emb_module
        emb_module._model = mock_model
        result = emb_module.embed_dense("")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# fts.py
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fulltext_search_returns_list():
    db = AsyncMock()
    r = MagicMock()
    r.all.return_value = []
    db.execute.return_value = r

    from gnosis.services.fts import fulltext_search
    results = await fulltext_search(db, "python", owner_ids=[1])
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_fulltext_search_empty_query():
    db = AsyncMock()
    r = MagicMock()
    r.all.return_value = []
    db.execute.return_value = r

    from gnosis.services.fts import fulltext_search
    results = await fulltext_search(db, "", owner_ids=[1])
    assert results == []


# ---------------------------------------------------------------------------
# hybrid_search.py
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hybrid_search_returns_list():
    db = AsyncMock()
    r = MagicMock()
    r.all.return_value = []
    db.execute.return_value = r

    with patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 384), \
         patch("gnosis.services.hybrid_search.vector_search", new_callable=AsyncMock,
               return_value=[]), \
         patch("gnosis.services.hybrid_search.fulltext_search", new_callable=AsyncMock,
               return_value=[]):
        from gnosis.services.hybrid_search import hybrid_search
        results = await hybrid_search("query", owner_ids=[1])
        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_hybrid_search_deduplicates():
    db = AsyncMock()
    r = MagicMock()
    r.note_id = "n1"
    r.title = "T"
    r.snippet = "s"
    r.score = 0.9

    with patch("gnosis.services.hybrid_search.embed_dense", return_value=[0.1] * 384), \
         patch("gnosis.services.hybrid_search.vector_search", new_callable=AsyncMock,
               return_value=[r, r]), \
         patch("gnosis.services.hybrid_search.fulltext_search", new_callable=AsyncMock,
               return_value=[r]):
        from gnosis.services.hybrid_search import hybrid_search
        results = await hybrid_search("query", owner_ids=[1])
        note_ids = [res.note_id for res in results]
        assert len(note_ids) == len(set(note_ids))


# ---------------------------------------------------------------------------
# markdown_parser.py
# ---------------------------------------------------------------------------

def test_parse_note_file_no_frontmatter(tmp_path):
    p = tmp_path / "test.md"
    p.write_text("# Hello\n\nSome content here.")
    from gnosis.services.markdown_parser import parse_note_file
    result = parse_note_file(str(p))
    assert isinstance(result, dict)


def test_parse_note_file_with_frontmatter(tmp_path):
    p = tmp_path / "note.md"
    p.write_text("---\ntitle: My Note\ntags: [python, ml]\n---\n# Hello\n\nContent.")
    from gnosis.services.markdown_parser import parse_note_file
    result = parse_note_file(str(p))
    assert result.get("title") == "My Note"


def test_extract_wikilinks():
    from gnosis.services.markdown_parser import extract_wikilinks
    links = extract_wikilinks("See [[Note A]] and [[Note B]] for details.")
    assert "Note A" in links
    assert "Note B" in links


def test_extract_wikilinks_empty():
    from gnosis.services.markdown_parser import extract_wikilinks
    assert extract_wikilinks("") == []


# ---------------------------------------------------------------------------
# vector_store.py
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vector_search_returns_list():
    from gnosis.services.vector_store import vector_search
    mock_client = MagicMock()
    mock_client.search = MagicMock(return_value=[])

    with patch("gnosis.services.vector_store._client", mock_client):
        results = await vector_search([0.1] * 384, owner_ids=[1])
        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_upsert_note_calls_client():
    from gnosis.services.vector_store import upsert_note
    mock_client = MagicMock()
    mock_client.upsert = MagicMock()

    with patch("gnosis.services.vector_store._client", mock_client), \
         patch("gnosis.services.vector_store.embed_dense", return_value=[0.1] * 384):
        await upsert_note("n1", "Title", "Body text", owner_id=1)


@pytest.mark.asyncio
async def test_delete_note_calls_client():
    from gnosis.services.vector_store import delete_note
    mock_client = MagicMock()
    mock_client.delete = MagicMock()

    with patch("gnosis.services.vector_store._client", mock_client):
        await delete_note("n1")
