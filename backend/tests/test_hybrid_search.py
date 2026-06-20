"""Unit tests for gnosis/services/hybrid_search.py.

Patches vector_store and fts so no external services are needed.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _fake_vector_results():
    return [
        {"id": "note-1", "score": 0.9, "title": "Alpha", "folder": "10"},
        {"id": "note-2", "score": 0.7, "title": "Beta", "folder": "20"},
    ]


def _fake_fts_results():
    return [
        {"id": "note-1", "rank": -0.5, "title": "Alpha"},
        {"id": "note-3", "rank": -1.0, "title": "Gamma"},
    ]


@pytest.mark.asyncio
async def test_hybrid_search_merges_results():
    from gnosis.services.hybrid_search import hybrid_search

    with patch("gnosis.services.hybrid_search.search_notes", new=AsyncMock(return_value=_fake_vector_results())), \
         patch("gnosis.services.hybrid_search.fts_search", new=AsyncMock(return_value=_fake_fts_results())):
        results = await hybrid_search("test query", db=MagicMock(), limit=10)

    ids = [r["id"] for r in results]
    # note-1 appears in both — should be present once
    assert ids.count("note-1") == 1
    # All three unique notes should be present
    assert set(ids) >= {"note-1", "note-2", "note-3"}


@pytest.mark.asyncio
async def test_hybrid_search_respects_limit():
    from gnosis.services.hybrid_search import hybrid_search

    with patch("gnosis.services.hybrid_search.search_notes", new=AsyncMock(return_value=_fake_vector_results())), \
         patch("gnosis.services.hybrid_search.fts_search", new=AsyncMock(return_value=_fake_fts_results())):
        results = await hybrid_search("q", db=MagicMock(), limit=2)

    assert len(results) <= 2


@pytest.mark.asyncio
async def test_hybrid_search_empty_results():
    from gnosis.services.hybrid_search import hybrid_search

    with patch("gnosis.services.hybrid_search.search_notes", new=AsyncMock(return_value=[])), \
         patch("gnosis.services.hybrid_search.fts_search", new=AsyncMock(return_value=[])):
        results = await hybrid_search("q", db=MagicMock(), limit=10)

    assert results == []
