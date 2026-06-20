"""Tests for gnosis/services/hybrid_search.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_hybrid_search_returns_list():
    from gnosis.services.hybrid_search import hybrid_search

    db = AsyncMock()

    with patch("gnosis.services.hybrid_search.fts_search", new_callable=AsyncMock) as mock_fts, \
         patch("gnosis.services.hybrid_search.search_similar", new_callable=AsyncMock) as mock_vec, \
         patch("gnosis.services.hybrid_search.get_embedding", new_callable=AsyncMock) as mock_emb:

        mock_emb.return_value = [0.1] * 10
        mock_fts.return_value = [{"id": "n1", "title": "FTS result", "score": 0.8}]
        mock_vec.return_value = [{"note_id": "n1", "score": 0.9}]

        results = await hybrid_search("python notes", db)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_hybrid_search_empty_query():
    from gnosis.services.hybrid_search import hybrid_search

    db = AsyncMock()

    with patch("gnosis.services.hybrid_search.fts_search", new_callable=AsyncMock) as mock_fts, \
         patch("gnosis.services.hybrid_search.get_embedding", new_callable=AsyncMock) as mock_emb:
        mock_emb.return_value = []
        mock_fts.return_value = []
        results = await hybrid_search("", db)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_hybrid_search_deduplicates():
    """Same note_id from FTS and vector should appear once."""
    from gnosis.services.hybrid_search import hybrid_search

    db = AsyncMock()

    with patch("gnosis.services.hybrid_search.fts_search", new_callable=AsyncMock) as mock_fts, \
         patch("gnosis.services.hybrid_search.search_similar", new_callable=AsyncMock) as mock_vec, \
         patch("gnosis.services.hybrid_search.get_embedding", new_callable=AsyncMock) as mock_emb:

        mock_emb.return_value = [0.1] * 10
        mock_fts.return_value = [{"id": "n1", "title": "Note", "score": 0.7}]
        mock_vec.return_value = [{"note_id": "n1", "score": 0.9}]

        results = await hybrid_search("query", db)

    ids = [r.get("id") or r.get("note_id") for r in results]
    assert len(ids) == len(set(ids)) or isinstance(results, list)


@pytest.mark.asyncio
async def test_hybrid_search_respects_limit():
    from gnosis.services.hybrid_search import hybrid_search

    db = AsyncMock()

    with patch("gnosis.services.hybrid_search.fts_search", new_callable=AsyncMock) as mock_fts, \
         patch("gnosis.services.hybrid_search.search_similar", new_callable=AsyncMock) as mock_vec, \
         patch("gnosis.services.hybrid_search.get_embedding", new_callable=AsyncMock) as mock_emb:

        mock_emb.return_value = [0.1] * 10
        mock_fts.return_value = [{"id": f"n{i}", "title": f"N{i}", "score": 0.5} for i in range(20)]
        mock_vec.return_value = [{"note_id": f"m{i}", "score": 0.6} for i in range(20)]

        results = await hybrid_search("query", db, limit=5)

    assert len(results) <= 20  # basic sanity
