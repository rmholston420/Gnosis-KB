"""Coverage tests for gnosis/routers/users.py.

Key notes:
- Router uses `require_user` (not `get_current_user`) for most auth.
- Router uses `get_session` (not `get_db`) for its DB dependency.
- UserProfile requires: id, email, full_name, vault_slug, vault_path,
  vault_display_name, is_superuser.
- No auth router here — login/register live in gnosis/routers/auth.py.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_session
from gnosis.models.user import User
from gnosis.routers.users import router


def _make_user(user_id: int = 1, superuser: bool = False) -> User:
    return User(
        id=user_id,
        email="user@test.com",
        hashed_password="hashed",
        full_name="Test User",
        vault_slug="test-vault",
        vault_path="/vaults/test",
        vault_display_name="Test Vault",
        is_superuser=superuser,
        is_active=True,
    )


def _make_app(session_mock: AsyncMock, user: User | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    _user = user or _make_user()

    async def _session():
        yield session_mock

    async def _require_user():
        return _user

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[require_user] = _require_user
    return app


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------

def test_get_me_returns_200():
    session = AsyncMock()
    client = TestClient(_make_app(session))
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user@test.com"
    assert data["vault_slug"] == "test-vault"


# ---------------------------------------------------------------------------
# PATCH /users/me
# ---------------------------------------------------------------------------

def test_update_me_full_name():
    """PATCH /users/me updates full_name and returns 200."""
    user = _make_user()
    session = AsyncMock()
    session.refresh = AsyncMock()

    with patch("gnosis.routers.users.ensure_vault_directory"):
        client = TestClient(_make_app(session, user))
        resp = client.patch("/api/v1/users/me", json={"full_name": "New Name"})
    assert resp.status_code == 200


def test_update_me_invalid_slug_returns_422():
    """PATCH /users/me with an invalid slug returns 422."""
    session = AsyncMock()
    client = TestClient(_make_app(session))
    resp = client.patch("/api/v1/users/me", json={"vault_slug": "AB"})
    assert resp.status_code == 422


def test_update_me_valid_slug():
    """PATCH /users/me with valid slug succeeds."""
    user = _make_user()
    session = AsyncMock()
    # Uniqueness check returns None (no conflict)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    session.refresh = AsyncMock()

    with patch("gnosis.routers.users.ensure_vault_directory"):
        client = TestClient(_make_app(session, user))
        resp = client.patch("/api/v1/users/me", json={"vault_slug": "my-vault"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /users/me/vaults
# ---------------------------------------------------------------------------

def test_list_my_vaults_returns_200():
    """GET /users/me/vaults returns 200 and a list."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    client = TestClient(_make_app(session))
    resp = client.get("/api/v1/users/me/vaults")
    assert resp.status_code == 200
    assert resp.json() == []
