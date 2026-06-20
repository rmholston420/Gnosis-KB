"""Tests for the /api/v1/graph/* endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_graph_empty(client):
    """GET /graph/ returns empty nodes + edges lists when DB has no notes."""
    resp = await client.get("/api/v1/graph/")
    assert resp.status_code == 200
    body = resp.json()
    assert "nodes" in body
    assert "edges" in body
    assert body["nodes"] == []
    assert body["edges"] == []


@pytest.mark.asyncio
async def test_graph_stats(client):
    """GET /graph/stats returns the expected aggregate keys.

    Key names are defined by the /stats router response:
      node_count, link_count, orphan_count, max_degree, avg_degree
    'link_count' is the canonical name (matches graph.py docstring).
    """
    resp = await client.get("/api/v1/graph/stats")
    assert resp.status_code == 200
    body = resp.json()
    for key in ["node_count", "link_count", "orphan_count", "max_degree"]:
        assert key in body, f"Expected key '{key}' missing from /graph/stats response: {body}"
