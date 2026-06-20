"""Graph router.

Endpoints
---------
- GET /graph/           — full wikilink graph (nodes + edges)
- GET /graph/neighborhood/{note_id} — 1-hop neighbourhood
- GET /graph/path/{from_id}/{to_id}  — shortest link path
- GET /graph/clusters    — community/cluster membership
- GET /graph/stats       — aggregate graph statistics
- GET /graph/lightrag    — LightRAG entities + relations as D3 nodes/links
- GET /graph/entities    — flat LightRAG entity list (for sidebar panel)

Response key conventions
------------------------
- Full graph (GET /)  : {"nodes": [...], "edges": [...]}  ← test_graph_empty asserts
- Stats (GET /stats) : {"node_count": ..., "link_count": ..., ...}  ← test_graph_stats asserts
- Neighbourhood/LightRAG: {"nodes": [...], "links": [...]}  (D3 convention, no test asserts)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import get_vault_owner_ids
from gnosis.core.namespace import scoped_note_stmt
from gnosis.database import get_db
from gnosis.models.link import Link
from gnosis.models.note import Note

router = APIRouter(prefix="/graph", tags=["graph"])


# ---------------------------------------------------------------------------
# Helper types
# ---------------------------------------------------------------------------


def _node(note: Note) -> dict[str, Any]:
    return {
        "id": note.id,
        "label": note.title,
        "folder": note.folder,
        "note_type": note.note_type,
    }


def _link(link: Link) -> dict[str, Any]:
    return {
        "source": link.source_id,
        "target": link.target_id,
        "link_type": link.link_type,
    }


# ---------------------------------------------------------------------------
# Full graph
# ---------------------------------------------------------------------------


@router.get("/", summary="Full wikilink graph")
async def get_full_graph(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict[str, Any]:
    result = await db.execute(
        scoped_note_stmt(
            select(Note).where(Note.is_deleted.is_(False)),
            owner_ids,
        )
    )
    notes = result.scalars().unique().all()
    note_ids = {n.id for n in notes}

    links_result = await db.execute(
        select(Link).where(
            Link.source_id.in_(note_ids),
            Link.target_id.in_(note_ids),
        )
    )
    links = links_result.scalars().all()

    # Key names: "nodes" + "edges" — test_graph_empty asserts both present.
    return {
        "nodes": [_node(n) for n in notes],
        "edges": [_link(lnk) for lnk in links],
    }


# ---------------------------------------------------------------------------
# Neighbourhood
# ---------------------------------------------------------------------------


@router.get("/neighborhood/{note_id}", summary="1-hop neighbourhood")
async def get_neighborhood(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict[str, Any]:
    links_result = await db.execute(
        select(Link).where(
            (Link.source_id == note_id) | (Link.target_id == note_id)
        )
    )
    links = links_result.scalars().all()
    neighbour_ids = {lnk.source_id for lnk in links} | {lnk.target_id for lnk in links} | {note_id}

    result = await db.execute(
        scoped_note_stmt(
            select(Note).where(Note.id.in_(neighbour_ids), Note.is_deleted.is_(False)),
            owner_ids,
        )
    )
    notes = result.scalars().unique().all()
    present_ids = {n.id for n in notes}
    visible_links = [
        lnk for lnk in links
        if lnk.source_id in present_ids and lnk.target_id in present_ids
    ]
    # Keep "links" here (D3 convention) — no test asserts this key name.
    return {"nodes": [_node(n) for n in notes], "links": [_link(lnk) for lnk in visible_links]}


# ---------------------------------------------------------------------------
# Shortest path
# ---------------------------------------------------------------------------


@router.get("/path/{from_id}/{to_id}", summary="Shortest link path")
async def get_path(
    from_id: str,
    to_id: str,
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict[str, Any]:
    result = await db.execute(
        scoped_note_stmt(
            select(Note).where(Note.is_deleted.is_(False)),
            owner_ids,
        )
    )
    notes = result.scalars().unique().all()
    note_ids = {n.id for n in notes}

    links_result = await db.execute(
        select(Link).where(
            Link.source_id.in_(note_ids),
            Link.target_id.in_(note_ids),
        )
    )
    links = links_result.scalars().all()

    # BFS
    from collections import deque
    adj: dict[str, list[str]] = {n.id: [] for n in notes}
    for lnk in links:
        adj.setdefault(lnk.source_id, []).append(lnk.target_id)
        adj.setdefault(lnk.target_id, []).append(lnk.source_id)

    visited: dict[str, str | None] = {from_id: None}
    queue: deque[str] = deque([from_id])
    while queue:
        current = queue.popleft()
        if current == to_id:
            break
        for nb in adj.get(current, []):
            if nb not in visited:
                visited[nb] = current
                queue.append(nb)

    if to_id not in visited:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No path found between the two notes.",
        )

    path: list[str] = []
    node: str | None = to_id
    while node is not None:
        path.append(node)
        node = visited.get(node)
    path.reverse()

    note_map = {n.id: n for n in notes}
    return {"path": [{"id": nid, "label": note_map[nid].title} for nid in path if nid in note_map]}


# ---------------------------------------------------------------------------
# Clusters
# ---------------------------------------------------------------------------


@router.get("/clusters", summary="Community cluster membership")
async def get_clusters(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict[str, Any]:
    """
    Simple folder-based clustering as a fast proxy for community detection.
    Returns a list of clusters, each with an id, label, and list of note ids.
    """
    result = await db.execute(
        scoped_note_stmt(
            select(Note).where(Note.is_deleted.is_(False)),
            owner_ids,
        )
    )
    notes = result.scalars().unique().all()

    clusters: dict[str, list[str]] = {}
    for n in notes:
        key = n.folder or "Uncategorised"
        clusters.setdefault(key, []).append(n.id)

    return {
        "clusters": [
            {"id": folder, "label": folder, "note_ids": ids}
            for folder, ids in clusters.items()
        ]
    }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", summary="Aggregate graph statistics")
async def get_graph_stats(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict[str, Any]:
    result = await db.execute(
        scoped_note_stmt(
            select(Note).where(Note.is_deleted.is_(False)),
            owner_ids,
        )
    )
    notes = result.scalars().unique().all()
    note_ids = {n.id for n in notes}

    links_result = await db.execute(
        select(Link).where(
            Link.source_id.in_(note_ids),
            Link.target_id.in_(note_ids),
        )
    )
    links = links_result.scalars().all()

    # Degree map
    degree: dict[str, int] = {n.id: 0 for n in notes}
    for lnk in links:
        degree[lnk.source_id] = degree.get(lnk.source_id, 0) + 1
        degree[lnk.target_id] = degree.get(lnk.target_id, 0) + 1

    orphan_count = sum(1 for v in degree.values() if v == 0)
    max_degree = max(degree.values(), default=0)

    # Key names match test_graph_stats assertions:
    # "node_count", "link_count", "orphan_count", "max_degree"
    return {
        "node_count": len(notes),
        "link_count": len(links),
        "orphan_count": orphan_count,
        "max_degree": max_degree,
        "avg_degree": round(sum(degree.values()) / len(degree), 2) if degree else 0,
    }


# ---------------------------------------------------------------------------
# LightRAG knowledge graph export
# ---------------------------------------------------------------------------


@router.get("/lightrag", summary="LightRAG entities + relations for D3 visualisation")
async def get_lightrag_graph(
    owner_ids: set[int] = Depends(get_vault_owner_ids),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Export LightRAG's entity/relation graph for the frontend D3 Knowledge
    Graph tab.  Entities are coloured by concept cluster.

    Falls back gracefully when LightRAG is not initialised: returns an empty
    graph so the frontend tab renders a friendly empty state rather than
    crashing.
    """
    try:
        from gnosis.services.graph_rag import graph_rag  # lazy import
    except ImportError:
        return {"nodes": [], "links": [], "source": "lightrag", "error": "LightRAG not installed"}

    try:
        data = await graph_rag.export_graph(list(owner_ids))
    except Exception as exc:  # noqa: BLE001
        # LightRAG may not be initialised yet — return empty graph gracefully
        return {
            "nodes": [],
            "links": [],
            "source": "lightrag",
            "error": str(exc),
        }

    return {
        "nodes": data.get("nodes", []),
        "links": data.get("links", []),
        "source": "lightrag",
    }


# ---------------------------------------------------------------------------
# LightRAG entity list  (Slice 16)
# ---------------------------------------------------------------------------


@router.get("/entities", summary="Flat LightRAG entity list for the sidebar panel")
async def get_graph_entities(
    limit: int = Query(default=100, ge=1, le=500, description="Max entities to return"),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
    db: AsyncSession = Depends(get_db),  # noqa: ARG001  kept for consistent dep injection
) -> dict[str, Any]:
    """
    Return a flat list of LightRAG entities for the GraphPage sidebar.

    Each entity has:
      id, label, description, cluster, source_note_ids

    Falls back gracefully when LightRAG is not initialised — returns an empty
    list so the frontend panel renders a friendly empty state.
    """
    try:
        from gnosis.services.graph_rag import graph_rag  # lazy import
    except ImportError:
        return {"entities": [], "total": 0, "error": "LightRAG not installed"}

    try:
        data = await graph_rag.export_graph(list(owner_ids))
    except Exception as exc:  # noqa: BLE001
        return {"entities": [], "total": 0, "error": str(exc)}

    nodes: list[dict[str, Any]] = data.get("nodes", [])

    entities = [
        {
            "id": n.get("id", ""),
            "label": n.get("label", ""),
            "description": n.get("description"),
            "cluster": n.get("cluster"),
            "source_note_ids": n.get("source_note_ids", []),
        }
        for n in nodes[:limit]
    ]

    return {"entities": entities, "total": len(nodes)}
