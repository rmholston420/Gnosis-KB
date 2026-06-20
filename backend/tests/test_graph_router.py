"""Unit tests for gnosis/routers/graph.py — no DB, no HTTP client.

Calls handler functions directly with mocked AsyncSession and owner_ids.

Key implementation notes
------------------------
- get_path: issues TWO queries (notes first, links second) and returns
  {"path": [{"id": ..., "label": ...}, ...]} — NOT a flat list of strings.
- get_graph_stats: issues TWO queries and counts len(notes) / len(links)
  — does NOT use scalar_one().
- get_clusters: issues ONE query and groups by note.folder.
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


def _sess_seq(*row_lists):
    """Session whose successive execute() calls return successive row lists.

    Each entry in row_lists is the list of ORM objects returned by
    .scalars().unique().all() (for notes) or .scalars().all() (for links).
    The same list is wired to both accessor chains so handlers can use either.
    """
    lists = list(row_lists)
    call = [0]
    async def _exec(stmt, *a, **kw):
        rows = lists[min(call[0], len(lists) - 1)]
        call[0] += 1
        r = MagicMock()
        r.scalars.return_value.unique.return_value.all.return_value = rows
        r.scalars.return_value.all.return_value = rows
        return r
    sess = AsyncMock()
    sess.execute = _exec
    return sess


# ---------------------------------------------------------------------------
# GET /graph/  — full graph
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_full_graph_empty():
    sess = _sess_seq([], [])  # notes=[], links=[]
    result = await get_full_graph(db=sess, owner_ids={1})
    assert result == {"nodes": [], "edges": []}


@pytest.mark.asyncio
async def test_get_full_graph_nodes_and_edges():
    notes = [_note("n1"), _note("n2")]
    links = [_link("n1", "n2")]
    sess = _sess_seq(notes, links)
    result = await get_full_graph(db=sess, owner_ids={1})
    assert len(result["nodes"]) == 2
    assert len(result["edges"]) == 1
    assert result["edges"][0]["source"] == "n1"


# ---------------------------------------------------------------------------
# GET /graph/neighborhood/{note_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_neighborhood_no_links():
    sess = _sess_seq([], [])  # links=[], then notes=[]
    result = await get_neighborhood(note_id="n1", db=sess, owner_ids={1})
    assert result["nodes"] == []
    assert result["links"] == []


@pytest.mark.asyncio
async def test_get_neighborhood_with_links():
    n1 = _note("n1"); n2 = _note("n2")
    lnk = _link("n1", "n2")
    # get_neighborhood: 1st query=links, 2nd query=notes for neighbour ids
    sess = _sess_seq([lnk], [n1, n2])
    result = await get_neighborhood(note_id="n1", db=sess, owner_ids={1})
    assert len(result["links"]) == 1


# ---------------------------------------------------------------------------
# GET /graph/path/{from_id}/{to_id}
#
# get_path issues: 1st query = notes, 2nd query = links
# Returns {"path": [{"id": ..., "label": ...}, ...]}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_path_same_node():
    """Same source and target: BFS starts at from_id which is already 'visited'.

    The handler breaks immediately when current==to_id, so a single node
    in the notes list is sufficient.  The path reconstructed is [from_id].
    """
    n1 = _note("n1", title="Alpha")
    sess = _sess_seq([n1], [])  # notes=[n1], links=[]
    result = await get_path(from_id="n1", to_id="n1", db=sess, owner_ids={1})
    assert len(result["path"]) == 1
    assert result["path"][0]["id"] == "n1"


@pytest.mark.asyncio
async def test_get_path_no_path_raises_404():
    """No notes → from_id never in visited → 404."""
    sess = _sess_seq([], [])  # notes=[], links=[]
    with pytest.raises(HTTPException) as exc_info:
        await get_path(from_id="n1", to_id="n2", db=sess, owner_ids={1})
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_path_direct_link():
    """n1 → n2 via a single wikilink."""
    n1 = _note("n1", title="Alpha"); n2 = _note("n2", title="Beta")
    lnk = _link("n1", "n2")
    sess = _sess_seq([n1, n2], [lnk])  # notes first, links second
    result = await get_path(from_id="n1", to_id="n2", db=sess, owner_ids={1})
    path_ids = [step["id"] for step in result["path"]]
    assert "n1" in path_ids
    assert "n2" in path_ids


# ---------------------------------------------------------------------------
# GET /graph/clusters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_clusters_empty():
    sess = _sess_seq([])  # notes=[]
    result = await get_clusters(db=sess, owner_ids={1})
    assert "clusters" in result
    assert result["clusters"] == []


@pytest.mark.asyncio
async def test_get_clusters_groups_by_folder():
    notes = [
        _note("n1", folder="00-inbox"),
        _note("n2", folder="00-inbox"),
        _note("n3", folder="10-zettelkasten"),
    ]
    sess = _sess_seq(notes)
    result = await get_clusters(db=sess, owner_ids={1})
    folders = {c["id"] for c in result["clusters"]}
    assert "00-inbox" in folders
    assert "10-zettelkasten" in folders
    inbox = next(c for c in result["clusters"] if c["id"] == "00-inbox")
    assert len(inbox["note_ids"]) == 2


# ---------------------------------------------------------------------------
# GET /graph/stats
#
# get_graph_stats: 1st query=notes, 2nd query=links
# Returns node_count=len(notes), link_count=len(links)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_graph_stats_empty():
    sess = _sess_seq([], [])  # notes=[], links=[]
    result = await get_graph_stats(db=sess, owner_ids={1})
    assert result["node_count"] == 0
    assert result["link_count"] == 0


@pytest.mark.asyncio
async def test_get_graph_stats_values():
    notes = [_note(f"n{i}") for i in range(10)]
    links = [_link(f"n{i}", f"n{i+1}") for i in range(5)]
    sess = _sess_seq(notes, links)
    result = await get_graph_stats(db=sess, owner_ids={1})
    assert result["node_count"] == 10
    assert result["link_count"] == 5


@pytest.mark.asyncio
async def test_get_graph_stats_orphan_count():
    """Notes with no links count as orphans."""
    notes = [_note("n1"), _note("n2"), _note("n3")]
    links = [_link("n1", "n2")]  # n3 has no links → orphan
    sess = _sess_seq(notes, links)
    result = await get_graph_stats(db=sess, owner_ids={1})
    assert result["orphan_count"] == 1
    assert result["max_degree"] == 1
