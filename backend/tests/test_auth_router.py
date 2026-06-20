"""Integration tests for gnosis/routers/auth.py.

Auth endpoints are decorated with @auth_limit (slowapi) which requires a
real starlette.requests.Request object, so we use the async_client fixture
(HTTPX against the full ASGI app) rather than calling handlers directly.

Covers: POST /auth/token (valid + wrong password + unknown user),
POST /auth/register (new user + duplicate email), GET /auth/me.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# POST /auth/token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_returns_token_on_valid_credentials(async_client):
    """Valid credentials → 200 with access_token."""
    with patch("gnosis.routers.auth.get_password_hash", return_value="hashed"):
        await async_client.post(
            "/api/v1/auth/register",
            json={"email": "user@example.com", "password": "secret", "full_name": "Test"},
        )

    with (
        patch("gnosis.routers.auth.verify_password", return_value=True),
        patch("gnosis.routers.auth.create_access_token", return_value="jwt-token"),
    ):
        resp = await async_client.post(
            "/api/v1/auth/token",
            data={"username": "user@example.com", "password": "secret"},
        )
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "jwt-token"


@pytest.mark.asyncio
async def test_login_returns_401_on_wrong_password(async_client):
    """Known user but wrong password → 401."""
    with patch("gnosis.routers.auth.get_password_hash", return_value="hashed"):
        await async_client.post(
            "/api/v1/auth/register",
            json={"email": "pw@example.com", "password": "correct", "full_name": "PW"},
        )

    with patch("gnosis.routers.auth.verify_password", return_value=False):
        resp = await async_client.post(
            "/api/v1/auth/token",
            data={"username": "pw@example.com", "password": "wrong"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_returns_401_on_unknown_user(async_client):
    """Non-existent email → 401."""
    resp = await async_client.post(
        "/api/v1/auth/token",
        data={"username": "nobody@example.com", "password": "anything"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_creates_new_user(async_client):
    """Valid payload → 201 with user data."""
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "pass123", "full_name": "New User"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_register_returns_400_on_duplicate_email(async_client):
    """Registering the same email twice → 400."""
    payload = {"email": "dup@example.com", "password": "pass", "full_name": "Dup"}
    await async_client.post("/api/v1/auth/register", json=payload)
    resp = await async_client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_me_returns_current_user(async_client):
    """Authenticated GET /me → 200 with user fields."""
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
