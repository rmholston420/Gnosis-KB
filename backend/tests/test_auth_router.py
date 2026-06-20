"""Tests for gnosis/routers/auth.py — login, register, me endpoints.

Uses the existing `async_client` + `auth_headers` fixtures from conftest.py
so the full ASGI stack is exercised (including slowapi) without fighting the
rate-limit decorator directly.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# POST /auth/token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_valid_credentials_returns_token(async_client, test_user):
    """Valid email+password returns a bearer token."""
    resp = await async_client.post(
        "/api/v1/auth/token",
        data={"username": test_user["email"], "password": test_user["password"]},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(async_client, test_user):
    resp = await async_client.post(
        "/api/v1/auth/token",
        data={"username": test_user["email"], "password": "totally_wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user_returns_401(async_client):
    resp = await async_client.post(
        "/api/v1/auth/token",
        data={"username": "nobody@nowhere.com", "password": "irrelevant"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_new_user_returns_201(async_client):
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "brand_new@example.com", "password": "pass1234", "full_name": "Brand New"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "brand_new@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_400(async_client, test_user):
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": test_user["email"], "password": "whatever", "full_name": "Dup"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_me_returns_current_user(async_client, auth_headers):
    resp = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
