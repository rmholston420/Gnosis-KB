"""Tests for health router.

These tests use the real async test client (conftest `client` fixture) which
does NOT mock external services (Qdrant, disk).  The readiness endpoint
(GET /health/) will return 503 when Qdrant is unreachable in CI, which is
the correct and expected behavior.

test_health_keys only verifies that the correct top-level keys are present
in the response body — it does not assert a specific HTTP status code so it
passes regardless of whether the CI environment has Qdrant running.
"""

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
    """Readiness probe returns expected top-level keys.

    Status code may be 200 (all OK) or 503 (any check degraded, e.g. Qdrant
    not running in CI).  This test only validates the response shape.
    """
    resp = await client.get("/api/v1/health/")
    assert resp.status_code in (200, 503)
    body = resp.json()
    for key in ("status", "uptime_seconds", "checks", "version"):
        assert key in body
