"""Pydantic schemas for graph visualization and traversal."""

from typing import Any, Optional

from pydantic import BaseModel


class GraphNode(BaseModel):
    """A node in the knowledge graph (= a note)."""

    id: str
    title: str
    note_type: str
    status: str
    folder: str
    word_count: int
    tag_count: int
    incoming_link_count: int
    outgoing_link_count: int
    tags: list[str] = []


class GraphEdge(BaseModel):
    """A directed edge between two notes (= a wikilink)."""

    source: str
    target: str
    link_text: str
    link_type: str


class GraphData(BaseModel):
    """Full graph data for frontend visualization."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphStats(BaseModel):
    """Summary statistics for the knowledge graph."""

    total_notes: int
    total_links: int
    orphan_count: int
    avg_degree: float
    density: float
    most_connected: list[dict[str, Any]]


class ClusterResult(BaseModel):
    """A detected community/cluster in the graph."""

    cluster_id: int
    node_ids: list[str]
    size: int
    label: Optional[str] = None  # AI-generated label (future)


class PathResult(BaseModel):
    """Shortest path between two notes."""

    from_id: str
    to_id: str
    path: list[str]  # List of note IDs from source to target
    length: int
    exists: bool
