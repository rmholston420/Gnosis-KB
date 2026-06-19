"""Graph router — knowledge graph endpoints for visualization and traversal.

All endpoints return data formatted for react-force-graph-2d:
  { nodes: [{id, title, type, incomingLinkCount}], edges: [{source, target}] }
"""
from __future__ import annotations

import json
from typing import Any

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.database import get_db
from gnosis.models.note import Note
from gnosis.schemas.graph import GraphData, GraphEdge, GraphNode, GraphStats

router = APIRouter(prefix="/graph", tags=["graph"])


async def _build_nx_graph(db: AsyncSession) -> tuple[nx.DiGraph, list[Note]]:
    """Load all notes + links from DB and build a NetworkX DiGraph."""
    result = await db.execute(
        select(Note).where(Note.is_deleted == False)  # noqa: E712
    )
    notes = result.scalars().all()
    G: nx.DiGraph = nx.DiGraph()
    for note in notes:
        G.add_node(note.id, title=note.title, note_type=note.note_type)

    rows = await db.execute(text("SELECT source_id, target_id FROM links"))
    for source_id, target_id in rows:
        G.add_edge(source_id, target_id)

    return G, list(notes)


@router.get("/", response_model=GraphData, summary="Full knowledge graph for visualization")
async def get_full_graph(db: AsyncSession = Depends(get_db)) -> GraphData:
    """Return all notes as nodes and all wikilinks as directed edges."""
    G, notes = await _build_nx_graph(db)
    in_degree = dict(G.in_degree())
    nodes = [
        GraphNode(
            id=n.id,
            title=n.title,
            note_type=n.note_type,
            status=getattr(n, "status", "draft"),
            folder=getattr(n, "folder", ""),
            incoming_link_count=in_degree.get(n.id, 0),
        )
        for n in notes
    ]
    edges = [
        GraphEdge(source=u, target=v)
        for u, v in G.edges()
    ]
    return GraphData(nodes=nodes, edges=edges)


@router.get("/neighborhood/{note_id}", response_model=GraphData, summary="Ego-graph: note + 1-hop neighbours")
async def get_neighborhood(note_id: str, db: AsyncSession = Depends(get_db)) -> GraphData:
    """Return the target note plus all notes directly linked to/from it."""
    G, notes = await _build_nx_graph(db)
    if note_id not in G:
        raise HTTPException(status_code=404, detail="Note not found in graph")
    note_map = {n.id: n for n in notes}
    neighbours = set(G.predecessors(note_id)) | set(G.successors(note_id)) | {note_id}
    sub = G.subgraph(neighbours)
    in_degree = dict(sub.in_degree())
    nodes = [
        GraphNode(
            id=nid,
            title=note_map[nid].title if nid in note_map else nid,
            note_type=note_map[nid].note_type if nid in note_map else "unknown",
            status=getattr(note_map.get(nid), "status", "draft"),
            folder=getattr(note_map.get(nid), "folder", ""),
            incoming_link_count=in_degree.get(nid, 0),
        )
        for nid in sub.nodes()
    ]
    edges = [GraphEdge(source=u, target=v) for u, v in sub.edges()]
    return GraphData(nodes=nodes, edges=edges)


@router.get("/path/{from_id}/{to_id}", summary="Shortest path between two notes")
async def get_path(from_id: str, to_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return the shortest directed path from *from_id* to *to_id* as an ordered list of note IDs."""
    G, _ = await _build_nx_graph(db)
    try:
        path = nx.shortest_path(G, source=from_id, target=to_id)
        return {"path": path, "length": len(path) - 1}
    except nx.NetworkXNoPath:
        raise HTTPException(status_code=404, detail="No path found")
    except nx.NodeNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/clusters", summary="Community detection (Louvain)")
async def get_clusters(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Detect note communities using the Louvain algorithm on the undirected projection."""
    G, _ = await _build_nx_graph(db)
    undirected = G.to_undirected()
    try:
        import community as community_louvain  # python-louvain
        partition = community_louvain.best_partition(undirected)
    except ImportError:
        # Fallback to connected components if python-louvain not installed
        partition = {}
        for i, comp in enumerate(nx.connected_components(undirected)):
            for node in comp:
                partition[node] = i
    clusters: dict[int, list[str]] = {}
    for node, cluster_id in partition.items():
        clusters.setdefault(cluster_id, []).append(node)
    return {"clusters": clusters, "count": len(clusters)}


@router.get("/stats", response_model=GraphStats, summary="Graph statistics")
async def get_stats(db: AsyncSession = Depends(get_db)) -> GraphStats:
    """Return high-level graph metrics: node count, edge count, density, orphan count."""
    G, _ = await _build_nx_graph(db)
    orphans = [n for n in G.nodes() if G.in_degree(n) == 0 and G.out_degree(n) == 0]
    density = nx.density(G) if len(G.nodes()) > 1 else 0.0
    avg_degree = (
        sum(dict(G.degree()).values()) / len(G.nodes()) if len(G.nodes()) > 0 else 0.0
    )
    return GraphStats(
        node_count=G.number_of_nodes(),
        edge_count=G.number_of_edges(),
        density=round(density, 6),
        avg_degree=round(avg_degree, 3),
        orphan_count=len(orphans),
    )
