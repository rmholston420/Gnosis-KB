"""
Integration tests for gnosis/routers/graph.py.

Coverage targets (graph.py)
----------------------------
  171->170   get_path() – 404 when no path exists between two disconnected notes
  292-308    get_lightrag_graph() – graceful fallback when graph_rag.export_graph raises
  335-358    get_graph_entities() – graceful fallback + limit slicing

Patch note
----------
Both /lightrag and /entities do a lazy import *inside* the endpoint function::

    from gnosis.services.graph_rag import graph_rag   # <-- inside the function

That means there is no module-level name `graph_rag` in gnosis.routers.graph to
patch.  We must patch the singleton on its *source* module so the lazy import
picks up the mock:

    patch("gnosis.services.graph_rag.graph_rag", ...)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# get_path() → 404 when notes are disconnected  (line 171->170)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_path_404_when_no_connection(client):
    """Two notes with no wikilink between them → 404 Not Found."""
    r1 = await client.post("/api/v1/notes/", json={
        "title": "Note Alpha", "body": "No links here.", "folder": "10-zettelkasten"
    })
    r2 = await client.post("/api/v1/notes/", json={
        "title": "Note Beta", "body": "No links here either.", "folder": "10-zettelkasten"
    })
    assert r1.status_code == 201
    assert r2.status_code == 201
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    resp = await client.get(f"/api/v1/graph/path/{id1}/{id2}")
    assert resp.status_code == 404
    assert "No path found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# get_lightrag_graph() – export_graph raises → empty graph  (lines 292-308)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lightrag_graph_returns_empty_on_exception(client):
    """When graph_rag.export_graph raises, the endpoint returns an empty graph
    with the error message — no 500.

    Patch target: gnosis.services.graph_rag.graph_rag  (the singleton that
    the lazy import inside the endpoint function resolves to).
    """
    mock_rag = MagicMock()
    mock_rag.export_graph = AsyncMock(side_effect=RuntimeError("LightRAG not ready"))

    with patch("gnosis.services.graph_rag.graph_rag", mock_rag):
        resp = await client.get("/api/v1/graph/lightrag")

    assert resp.status_code == 200
    body = resp.json()
    assert body["nodes"] == []
    assert body["links"] == []
    assert body["source"] == "lightrag"
    assert "LightRAG not ready" in body["error"]


@pytest.mark.asyncio
async def test_lightrag_graph_returns_nodes_on_success(client):
    """Happy path: export_graph returns data → nodes/links forwarded to caller."""
    fake_data = {
        "nodes": [{"id": "e1", "label": "Impermanence"}],
        "links": [{"source": "e1", "target": "e1"}],
    }
    mock_rag = MagicMock()
    mock_rag.export_graph = AsyncMock(return_value=fake_data)

    with patch("gnosis.services.graph_rag.graph_rag", mock_rag):
        resp = await client.get("/api/v1/graph/lightrag")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["nodes"]) == 1
    assert body["nodes"][0]["label"] == "Impermanence"
    assert body["source"] == "lightrag"


# ---------------------------------------------------------------------------
# get_graph_entities() – graceful fallback + limit slicing  (lines 335-358)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_graph_entities_returns_empty_on_exception(client):
    """When export_graph raises, entities endpoint returns empty list without 500."""
    mock_rag = MagicMock()
    mock_rag.export_graph = AsyncMock(side_effect=RuntimeError("graph init failed"))

    with patch("gnosis.services.graph_rag.graph_rag", mock_rag):
        resp = await client.get("/api/v1/graph/entities")

    assert resp.status_code == 200
    body = resp.json()
    assert body["entities"] == []
    assert body["total"] == 0
    assert "graph init failed" in body["error"]


@pytest.mark.asyncio
async def test_graph_entities_limit_slicing(client):
    """Entities are sliced to the requested limit; total reflects all nodes."""
    many_nodes = [{"id": f"e{i}", "label": f"Entity {i}"} for i in range(50)]
    fake_data = {"nodes": many_nodes, "links": []}
    mock_rag = MagicMock()
    mock_rag.export_graph = AsyncMock(return_value=fake_data)

    with patch("gnosis.services.graph_rag.graph_rag", mock_rag):
        resp = await client.get("/api/v1/graph/entities?limit=10")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["entities"]) == 10
    assert body["total"] == 50


@pytest.mark.asyncio
async def test_graph_entities_full_shape(client):
    """Each entity carries all expected keys."""
    node = {
        "id": "n1",
        "label": "Buddha-nature",
        "description": "The innate capacity for awakening.",
        "cluster": "dharma",
        "source_note_ids": ["note-abc"],
    }
    mock_rag = MagicMock()
    mock_rag.export_graph = AsyncMock(return_value={"nodes": [node], "links": []})

    with patch("gnosis.services.graph_rag.graph_rag", mock_rag):
        resp = await client.get("/api/v1/graph/entities")

    assert resp.status_code == 200
    entity = resp.json()["entities"][0]
    assert entity["id"] == "n1"
    assert entity["label"] == "Buddha-nature"
    assert entity["description"] == "The innate capacity for awakening."
    assert entity["cluster"] == "dharma"
    assert entity["source_note_ids"] == ["note-abc"]
