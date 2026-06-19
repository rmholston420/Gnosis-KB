"""Graph router — knowledge graph endpoints for visualization and traversal.

All endpoints return data formatted for react-force-graph-2d:
  { nodes: [{id, title, type, incomingLinkCount}], edges: [{source, target}] }

Namespace contract
------------------
Every endpoint is scoped to the calling user's accessible vault set via the
``get_vault_owner_ids`` dependency (honours ``X-Vault-Owner-Id`` header).
``_build_nx_graph`` accepts ``owner_ids`` and applies ``scoped_note_stmt``
so notes from inaccessible vaults never appear in any graph response.
Link edges whose *source* note is outside the accessible set are also
excluded, preventing indirect information leakage through edge metadata.
"""
from __future__ import annotations

from typing import Any

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import get_vault_owner_ids
from gnosis.core.namespace import scoped_note_stmt
from gnosis.database import get_db
from gnosis.models.link import Link
from gnosis.models.note import Note
from gnosis.schemas.graph import GraphData, GraphEdge, GraphNode, GraphStats

router = APIRouter(prefix="/graph", tags=["graph"])


async def _build_nx_graph(
    db: AsyncSession,
    owner_ids: set[int],
) -> tuple[nx.DiGraph, list[Note]]:
    """Load scoped notes + links from DB and build a NetworkX DiGraph.

    Only notes whose ``owner_id`` is in *owner_ids* (or is NULL for legacy
    data) are included.  Link edges whose *source* note is outside the
    accessible set are also excluded.
    """
    # Scoped note fetch
    note_stmt = scoped_note_stmt(
        select(Note).where(Note.is_deleted.is_(False)),
        owner_ids,
    )
    result = await db.execute(note_stmt)
    notes = result.scalars().all()
    accessible_ids = {n.id for n in notes}

    G: nx.DiGraph = nx.DiGraph()
    for note in notes:
        G.add_node(note.id, title=note.title, note_type=note.note_type)

    # Only include edges where BOTH endpoints are in the accessible set
    link_result = await db.execute(
        select(Link.source_id, Link.target_id).where(
            Link.source_id.in_(accessible_ids),
            Link.target_id.in_(accessible_ids),
        )
    )
    for source_id, target_id in link_result:
        G.add_edge(source_id, target_id)

    return G, list(notes)


@router.get("/", response_model=GraphData, summary="Full knowledge graph for visualization")
async def get_full_graph(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> GraphData:
    """Return all accessible notes as nodes and their wikilinks as directed edges."""
    G, notes = await _build_nx_graph(db, owner_ids)
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
    edges = [GraphEdge(source=u, target=v) for u, v in G.edges()]
    return GraphData(nodes=nodes, edges=edges)


@router.get("/neighborhood/{note_id}", response_model=GraphData, summary="Ego-graph: note + 1-hop neighbours")
async def get_neighborhood(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> GraphData:
    """Return the target note plus all notes directly linked to/from it.

    Returns HTTP 404 if the note is not found within the caller's accessible
    vaults (whether it doesn't exist or is simply inaccessible).
    """
    G, notes = await _build_nx_graph(db, owner_ids)
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
async def get_path(
    from_id: str,
    to_id: str,
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict[str, Any]:
    """Return the shortest directed path from *from_id* to *to_id*.

    Both nodes must be within the caller's accessible vaults; otherwise
    NetworkX raises NodeNotFound which is mapped to HTTP 404.
    """
    G, _ = await _build_nx_graph(db, owner_ids)
    try:
        path = nx.shortest_path(G, source=from_id, target=to_id)
        return {"path": path, "length": len(path) - 1}
    except nx.NetworkXNoPath:
        raise HTTPException(status_code=404, detail="No path found")
    except nx.NodeNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/clusters", summary="Community detection (Louvain)")
async def get_clusters(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict[str, Any]:
    """Detect note communities using the Louvain algorithm on the undirected projection.

    Only notes within the caller's accessible vaults contribute to the
    partition, so shared-vault members see a graph limited to their scope.
    """
    G, _ = await _build_nx_graph(db, owner_ids)
    undirected = G.to_undirected()
    try:
        import community as community_louvain  # python-louvain
        partition = community_louvain.best_partition(undirected)
    except ImportError:
        partition = {}
        for i, comp in enumerate(nx.connected_components(undirected)):
            for node in comp:
                partition[node] = i
    clusters: dict[int, list[str]] = {}
    for node, cluster_id in partition.items():
        clusters.setdefault(cluster_id, []).append(node)
    return {"clusters": clusters, "count": len(clusters)}


@router.get("/stats", response_model=GraphStats, summary="Graph statistics")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> GraphStats:
    """Return high-level graph metrics scoped to the caller's accessible vaults."""
    G, _ = await _build_nx_graph(db, owner_ids)
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
