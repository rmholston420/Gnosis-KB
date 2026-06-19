"""Graph-related Pydantic schemas."""

from typing import Any

from pydantic import BaseModel


class GraphNode(BaseModel):
    """Represents a note node in the graph."""

    id: str
    title: str
    note_type: str
    status: str
    folder: str
    word_count: int
    tag_count: int
    incoming_link_count: int
    outgoing_link_count: int


class GraphEdge(BaseModel):
    """Represents a directional link in the graph."""

    source: str
    target: str
    link_text: str
    link_type: str = "wikilink"


class GraphData(BaseModel):
    """Complete graph snapshot."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


class PathResult(BaseModel):
    """Result of a shortest-path query."""

    from_id: str
    to_id: str
    path: list[str]
    length: int
    exists: bool


class ClusterResult(BaseModel):
    """Result of community detection."""

    cluster_id: int
    node_ids: list[str]
    size: int


class GraphStats(BaseModel):
    """Summary statistics for the knowledge graph."""

    total_notes: int
    total_links: int
    orphan_count: int
    avg_degree: float
    density: float
    most_connected: list[dict[str, Any]]
