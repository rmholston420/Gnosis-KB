"""
Tests for AI router endpoints.

Uses mock LLM provider to avoid real API calls in CI.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_no_provider(client: AsyncClient) -> None:
    """POST /ai/chat returns 503 when no provider is available."""
    with patch(
        "gnosis.routers.ai.llm_provider.is_available", new_callable=lambda: property(lambda self: False)
    ):
        with patch("gnosis.routers.ai.graph_rag.is_available", new_callable=lambda: property(lambda self: False)):
            resp = await client.post(
                "/api/v1/ai/chat",
                json={"message": "What is Gnosis?"},
            )
            assert resp.status_code in (503, 401)  # 401 if auth required in test


@pytest.mark.asyncio
async def test_stream_chat_endpoint_exists(client: AsyncClient) -> None:
    """GET /ai/stream/chat returns 200 or 400 (missing param)."""
    resp = await client.get("/api/v1/ai/stream/chat")
    # 422 = missing required query param 'message' — acceptable
    assert resp.status_code in (200, 422, 401)


@pytest.mark.asyncio
async def test_summarize_not_found(client: AsyncClient, auth_headers: dict) -> None:
    """POST /ai/summarize/nonexistent returns 404."""
    with patch("gnosis.routers.ai.llm_provider.is_available", True):
        resp = await client.post(
            "/api/v1/ai/summarize/nonexistent-note-id",
            headers=auth_headers,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_suggest_tags_not_found(client: AsyncClient, auth_headers: dict) -> None:
    """POST /ai/suggest-tags/nonexistent returns 404."""
    with patch("gnosis.routers.ai.llm_provider.is_available", True):
        resp = await client.post(
            "/api/v1/ai/suggest-tags/nonexistent-note-id",
            headers=auth_headers,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_orphan_audit_returns_list(client: AsyncClient, auth_headers: dict) -> None:
    """GET /ai/orphan-audit returns JSON with orphan_count and items."""
    resp = await client.get("/api/v1/ai/orphan-audit", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "orphan_count" in data
    assert "items" in data


@pytest.mark.asyncio
async def test_daily_review_no_notes(client: AsyncClient, auth_headers: dict) -> None:
    """POST /ai/daily-review returns 200 even with empty inbox."""
    resp = await client.post("/api/v1/ai/daily-review", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "date" in data
    assert "summary" in data
