"""Tests for health router."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ping(client: AsyncClient) -> None:
    """Liveness probe always returns 200."""
    resp = await client.get("/api/v1/health/ping")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pong"


@pytest.mark.asyncio
async def test_health_keys(client: AsyncClient) -> None:
    """Readiness probe returns expected top-level keys."""
    resp = await client.get("/api/v1/health/")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("status", "uptime_seconds", "checks", "version"):
        assert key in body
