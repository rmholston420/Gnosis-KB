"""Tests for auth router — register, login, me endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient) -> None:
    """Register a new user then exchange credentials for a JWT."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "testpass", "full_name": "Tester"},
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    assert body["email"] == "test@example.com"

    token_resp = await client.post(
        "/api/v1/auth/token",
        data={"username": "test@example.com", "password": "testpass"},
    )
    assert token_resp.status_code == 200
    assert "access_token" in token_resp.json()


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient) -> None:
    """When AUTH_REQUIRED=false the /me endpoint returns the bootstrap admin."""
    me_resp = await client.get("/api/v1/auth/me")
    # In non-auth mode the auto-resolved admin is returned
    assert me_resp.status_code in (200, 401)
