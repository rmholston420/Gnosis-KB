"""Unit tests for gnosis/routers/graph.py — no DB, no HTTP client.

Calls handler functions directly with mocked AsyncSession and owner_ids.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from gnosis.routers.graph import (
    get_full_graph,
    get_neighborhood,
    get_path,
    get_clusters,
    get_graph_stats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _note(id, title="T", folder="00-inbox", note_type="permanent"):
    n = MagicMock()
    n.id = id; n.title = title; n.folder = folder; n.note_type = note_type
    return n


def _link(src, tgt, link_type="wikilink"):
    lnk = MagicMock()
    lnk.source_id = src; lnk.target_id = tgt; lnk.link_type = link_type
    return lnk


def _sess_two(first_rows, second_rows):
    """Session that returns different rows on first vs second .execute() call."""
    call = [0]
    async def _exec(stmt, *a, **kw):
        call[0] += 1
        r = MagicMock()
        rows = first_rows if call[0] == 1 else second_rows
        r.scalars.return_value.unique.return_value.all.return_value = rows
        r.scalars.return_value.all.return_value = rows
        return r
    sess = AsyncMock()
    sess.execute = _exec
    return sess


def _sess_scalar_seq(*values):
    """Session that returns successive scalar_one() values."""
    vals = list(values)
    call = [0]
    async def _exec(stmt, *a, **kw):
        r = MagicMock()
        r.scalar_one.return_value = vals[min(call[0], len(vals)-1)]
        r.scalars.return_value.all.return_value = []
        call[0] += 1
        return r
    sess = AsyncMock()
    sess.execute = _exec
    return sess


# ---------------------------------------------------------------------------
# GET /graph/  — full graph
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_full_graph_empty():
    sess = _sess_two([], [])
    result = await get_full_graph(db=sess, owner_ids={1})
    assert result == {"nodes": [], "edges": []}


@pytest.mark.asyncio
async def test_get_full_graph_nodes_and_edges():
    notes = [_note("n1"), _note("n2")]
    links = [_link("n1", "n2")]
    sess = _sess_two(notes, links)
    result = await get_full_graph(db=sess, owner_ids={1})
    assert len(result["nodes"]) == 2
    assert len(result["edges"]) == 1
    assert result["edges"][0]["source"] == "n1"


# ---------------------------------------------------------------------------
# GET /graph/neighborhood/{note_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_neighborhood_no_links():
    call = [0]
    async def _exec(stmt, *a, **kw):
        call[0] += 1
        r = MagicMock()
        r.scalars.return_value.all.return_value = []
        r.scalars.return_value.unique.return_value.all.return_value = []
        return r
    sess = AsyncMock(); sess.execute = _exec
    result = await get_neighborhood(note_id="n1", db=sess, owner_ids={1})
    assert result["nodes"] == []
    assert result["links"] == []


@pytest.mark.asyncio
async def test_get_neighborhood_with_links():
    n1 = _note("n1"); n2 = _note("n2")
    lnk = _link("n1", "n2")
    call = [0]
    async def _exec(stmt, *a, **kw):
        call[0] += 1
        r = MagicMock()
        if call[0] == 1:
            r.scalars.return_value.all.return_value = [lnk]
        else:
            r.scalars.return_value.unique.return_value.all.return_value = [n1, n2]
        return r
    sess = AsyncMock(); sess.execute = _exec
    result = await get_neighborhood(note_id="n1", db=sess, owner_ids={1})
    assert len(result["links"]) == 1


# ---------------------------------------------------------------------------
# GET /graph/path/{from_id}/{to_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_path_same_node():
    result = await get_path(
        from_id="n1", to_id="n1", db=AsyncMock(), owner_ids={1}
    )
    assert result["path"] == ["n1"]


@pytest.mark.asyncio
async def test_get_path_no_path_raises_404():
    r = MagicMock(); r.scalars.return_value.all.return_value = []
    sess = AsyncMock(); sess.execute = AsyncMock(return_value=r)
    with pytest.raises(HTTPException) as exc_info:
        await get_path(from_id="n1", to_id="n2", db=sess, owner_ids={1})
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_path_direct_link():
    lnk = _link("n1", "n2")
    r = MagicMock(); r.scalars.return_value.all.return_value = [lnk]
    sess = AsyncMock(); sess.execute = AsyncMock(return_value=r)
    result = await get_path(from_id="n1", to_id="n2", db=sess, owner_ids={1})
    assert "n1" in result["path"]
    assert "n2" in result["path"]


# ---------------------------------------------------------------------------
# GET /graph/clusters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_clusters_empty():
    r = MagicMock(); r.scalars.return_value.all.return_value = []
    sess = AsyncMock(); sess.execute = AsyncMock(return_value=r)
    result = await get_clusters(db=sess, owner_ids={1})
    assert "clusters" in result


# ---------------------------------------------------------------------------
# GET /graph/stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_graph_stats_zeros():
    sess = _sess_scalar_seq(0, 0, 0, 0)
    result = await get_graph_stats(db=sess, owner_ids={1})
    assert "node_count" in result
    assert "link_count" in result


@pytest.mark.asyncio
async def test_get_graph_stats_values():
    sess = _sess_scalar_seq(10, 5, 3, 2)
    result = await get_graph_stats(db=sess, owner_ids={1})
    assert result["node_count"] == 10
    assert result["link_count"] == 5
