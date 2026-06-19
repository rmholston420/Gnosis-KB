"""Graph router — knowledge graph traversal and visualization."""

from typing import Any

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.database import get_db
from gnosis.models.link import Link
from gnosis.models.note import Note
from gnosis.schemas.graph import (
    ClusterResult,
    GraphData,
    GraphEdge,
    GraphNode,
    GraphStats,
    PathResult,
)

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


async def _build_nx_graph(db: AsyncSession) -> nx.DiGraph:
    """Build a NetworkX DiGraph from the links table."""
    g: nx.DiGraph = nx.DiGraph()

    notes_result = await db.execute(
        select(Note.id, Note.title).where(Note.is_deleted.is_(False))
    )
    for row in notes_result:
        g.add_node(row.id, title=row.title)

    links_result = await db.execute(select(Link.source_id, Link.target_id))
    for row in links_result:
        g.add_edge(row.source_id, row.target_id)

    return g


@router.get("/", response_model=GraphData, summary="Full knowledge graph")
async def get_full_graph(db: AsyncSession = Depends(get_db)) -> GraphData:
    """Return the full graph (all notes + wikilinks) for visualization.

    Returns:
        GraphData with nodes and edges lists.
    """
    notes_result = await db.execute(
        select(Note).where(Note.is_deleted.is_(False))
    )
    notes = notes_result.scalars().all()

    # Compute incoming link counts
    in_count_result = await db.execute(
        select(Link.target_id, func.count(Link.id).label("cnt"))
        .group_by(Link.target_id)
    )
    in_counts: dict[str, int] = {row.target_id: row.cnt for row in in_count_result}
    out_count_result = await db.execute(
        select(Link.source_id, func.count(Link.id).label("cnt"))
        .group_by(Link.source_id)
    )
    out_counts: dict[str, int] = {row.source_id: row.cnt for row in out_count_result}

    nodes = [
        GraphNode(
            id=n.id,
            title=n.title,
            note_type=n.note_type,
            status=n.status,
            folder=n.folder,
            word_count=n.word_count,
            tag_count=len(n.frontmatter.get("tags", [])) if n.frontmatter else 0,
            incoming_link_count=in_counts.get(n.id, 0),
            outgoing_link_count=out_counts.get(n.id, 0),
        )
        for n in notes
    ]

    links_result = await db.execute(select(Link))
    edges = [
        GraphEdge(
            source=lnk.source_id,
            target=lnk.target_id,
            link_text=lnk.link_text,
            link_type=lnk.link_type,
        )
        for lnk in links_result.scalars().all()
    ]

    return GraphData(nodes=nodes, edges=edges)


@router.get("/neighborhood/{note_id}", response_model=GraphData, summary="Ego graph")
async def get_neighborhood(
    note_id: str, db: AsyncSession = Depends(get_db)
) -> GraphData:
    """Return the ego-graph: the given note plus all 1-hop neighbors.

    Args:
        note_id: The central note ID.
        db: Database session.

    Returns:
        GraphData with the note and its immediate neighbors.
    """
    g = await _build_nx_graph(db)
    if note_id not in g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note {note_id} not found in graph")

    ego = nx.ego_graph(g, note_id, radius=1)
    neighbor_ids = set(ego.nodes())

    notes_result = await db.execute(
        select(Note).where(Note.id.in_(list(neighbor_ids)), Note.is_deleted.is_(False))
    )
    notes = notes_result.scalars().all()
    nodes = [
        GraphNode(
            id=n.id, title=n.title, note_type=n.note_type, status=n.status,
            folder=n.folder, word_count=n.word_count, tag_count=0,
            incoming_link_count=0, outgoing_link_count=0,
        )
        for n in notes
    ]

    links_result = await db.execute(
        select(Link).where(
            Link.source_id.in_(list(neighbor_ids)),
            Link.target_id.in_(list(neighbor_ids)),
        )
    )
    edges = [
        GraphEdge(source=lnk.source_id, target=lnk.target_id, link_text=lnk.link_text, link_type=lnk.link_type)
        for lnk in links_result.scalars().all()
    ]
    return GraphData(nodes=nodes, edges=edges)


@router.get("/path/{from_id}/{to_id}", response_model=PathResult, summary="Shortest path between notes")
async def get_path(
    from_id: str, to_id: str, db: AsyncSession = Depends(get_db)
) -> PathResult:
    """Find the shortest path between two notes using NetworkX.

    Args:
        from_id: Source note ID.
        to_id: Target note ID.
        db: Database session.

    Returns:
        PathResult with path list and length.
    """
    g = await _build_nx_graph(db)
    try:
        path = nx.shortest_path(g, from_id, to_id)
        return PathResult(from_id=from_id, to_id=to_id, path=path, length=len(path) - 1, exists=True)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return PathResult(from_id=from_id, to_id=to_id, path=[], length=0, exists=False)


@router.get("/clusters", response_model=list[ClusterResult], summary="Community detection")
async def get_clusters(db: AsyncSession = Depends(get_db)) -> list[ClusterResult]:
    """Detect note communities using NetworkX Louvain algorithm.

    Returns:
        List of ClusterResult, each with cluster_id, node_ids, and size.
    """
    g = await _build_nx_graph(db)
    undirected = g.to_undirected()
    if len(undirected.nodes) == 0:
        return []

    communities = nx.community.louvain_communities(undirected, seed=42)
    return [
        ClusterResult(cluster_id=i, node_ids=list(community), size=len(community))
        for i, community in enumerate(communities)
    ]


@router.get("/stats", response_model=GraphStats, summary="Graph statistics")
async def get_graph_stats(db: AsyncSession = Depends(get_db)) -> GraphStats:
    """Return summary statistics for the knowledge graph.

    Returns:
        GraphStats: node count, edge count, orphans, density, avg degree, top nodes.
    """
    g = await _build_nx_graph(db)

    n = g.number_of_nodes()
    e = g.number_of_edges()
    density = nx.density(g) if n > 1 else 0.0
    avg_degree = (2 * e / n) if n > 0 else 0.0

    orphan_count = sum(1 for node in g.nodes() if g.degree(node) == 0)

    degree_sorted = sorted(g.degree(), key=lambda x: x[1], reverse=True)[:10]
    most_connected = [
        {"note_id": node_id, "degree": deg, "title": g.nodes[node_id].get("title", "")}
        for node_id, deg in degree_sorted
    ]

    return GraphStats(
        total_notes=n,
        total_links=e,
        orphan_count=orphan_count,
        avg_degree=avg_degree,
        density=density,
        most_connected=most_connected,
    )
