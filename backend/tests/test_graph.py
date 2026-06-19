"""Tests for graph router."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_graph_empty(client: AsyncClient) -> None:
    """Graph endpoint returns valid structure even when no notes exist."""
    resp = await client.get("/api/v1/graph/")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data and "edges" in data


@pytest.mark.asyncio
async def test_graph_stats(client: AsyncClient) -> None:
    """Stats endpoint returns expected keys."""
    resp = await client.get("/api/v1/graph/stats")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("node_count", "edge_count", "density", "avg_degree", "orphan_count"):
        assert key in body


@pytest.mark.asyncio
async def test_graph_path_not_found(client: AsyncClient) -> None:
    """Path endpoint returns 404 when nodes do not exist."""
    resp = await client.get("/api/v1/graph/path/nonexistent-a/nonexistent-b")
    assert resp.status_code == 404
