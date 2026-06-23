"""Pydantic schemas for graph endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class GraphNode(BaseModel):
    """A single note node in the graph."""

    id: str
    title: str
    note_type: str
    status: str
    folder: str
    incoming_link_count: int


class GraphEdge(BaseModel):
    """A directed wikilink edge between two notes."""

    source: str
    target: str


class GraphData(BaseModel):
    """Full graph payload consumed by react-force-graph-2d."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphStats(BaseModel):
    """High-level metrics about the knowledge graph."""

    node_count: int
    edge_count: int
    density: float
    avg_degree: float
    orphan_count: int
