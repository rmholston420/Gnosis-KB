"""
Tests for /api/v1/users endpoints — additional scenarios beyond
test_users_router_coverage.py.

Uses synchronous TestClient (not AsyncClient) with async generator session
override so coverage.py's tracer is active.  All user fixtures are real
SQLAlchemy User instances so UserProfile.model_validate() succeeds.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_session
from gnosis.models.user import User
from gnosis.routers.users import router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(user_id: int = 1, superuser: bool = False, **kw) -> User:
    u = User(
        email=kw.get("email", "alice@example.com"),
        hashed_password="hashed",
        full_name=kw.get("full_name", "Alice"),
        vault_slug=kw.get("vault_slug", "alice"),
        vault_path=kw.get("vault_path", "/vaults/alice"),
        vault_display_name=kw.get("vault_display_name", "Alice's Vault"),
        is_superuser=superuser,
        is_active=True,
    )
    u.id = user_id
    return u


def _make_app(user: User, session_mock: AsyncMock | None = None):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    if session_mock is None:
        session_mock = AsyncMock()
        empty = MagicMock()
        empty.scalar_one_or_none.return_value = None
        empty.scalars.return_value.all.return_value = []
        session_mock.execute = AsyncMock(return_value=empty)
        session_mock.commit = AsyncMock()
        session_mock.refresh = AsyncMock(side_effect=lambda obj: None)
        session_mock.add = MagicMock()

    async def _override_session():
        yield session_mock

    async def _override_user():
        return user

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[require_user] = _override_user
    return app, session_mock


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------

def test_get_me_profile_email():
    user = _make_user()
    app, _ = _make_app(user)
    with TestClient(app, raise_server_exceptions=True) as c:
        r = c.get("/api/v1/users/me")
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


# ---------------------------------------------------------------------------
# PATCH /users/me  — slug conflict 409
# ---------------------------------------------------------------------------

def test_patch_me_slug_conflict_returns_409():
    user = _make_user()
    session = AsyncMock()
    other = _make_user(user_id=99, email="bob@example.com")
    conflict = MagicMock()
    conflict.scalar_one_or_none.return_value = other
    session.execute = AsyncMock(return_value=conflict)
    app, _ = _make_app(user, session)
    with TestClient(app) as c:
        r = c.patch("/api/v1/users/me", json={"vault_slug": "taken-slug"})
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /users/me/vaults/invite
# ---------------------------------------------------------------------------

def test_invite_unknown_user_returns_404():
    user = _make_user()
    app, _ = _make_app(user)
    with TestClient(app) as c:
        r = c.post(
            "/api/v1/users/me/vaults/invite",
            json={"member_email": "ghost@example.com", "permission": "read"},
        )
    assert r.status_code == 404


def test_invite_self_returns_422():
    user = _make_user()
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user  # same user returned
    session.execute = AsyncMock(return_value=result)
    app, _ = _make_app(user, session)
    with TestClient(app) as c:
        r = c.post(
            "/api/v1/users/me/vaults/invite",
            json={"member_email": user.email, "permission": "read"},
        )
    assert r.status_code == 422


def test_invite_invalid_permission_returns_422():
    user = _make_user()
    app, _ = _make_app(user)
    with TestClient(app) as c:
        r = c.post(
            "/api/v1/users/me/vaults/invite",
            json={"member_email": "bob@example.com", "permission": "admin"},
        )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /users/me/vaults
# ---------------------------------------------------------------------------

def test_list_my_vaults_empty():
    user = _make_user()
    app, _ = _make_app(user)
    with TestClient(app, raise_server_exceptions=True) as c:
        r = c.get("/api/v1/users/me/vaults")
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# PATCH /users/me/vaults/{grant_id}
# ---------------------------------------------------------------------------

def test_update_grant_invalid_permission_422():
    user = _make_user()
    app, _ = _make_app(user)
    with TestClient(app) as c:
        r = c.patch("/api/v1/users/me/vaults/1", json={"permission": "owner"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /users/me/vaults/{grant_id}
# ---------------------------------------------------------------------------

def test_revoke_grant_not_found():
    user = _make_user()
    app, _ = _make_app(user)
    with TestClient(app, raise_server_exceptions=True) as c:
        r = c.delete("/api/v1/users/me/vaults/9999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /users/ — superuser create with vault slug
# ---------------------------------------------------------------------------

def test_create_user_with_vault_slug_201():
    """Exercises lines 222-243 with full create path including vault_slug."""
    user = _make_user(user_id=1, superuser=True)
    session = AsyncMock()
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=empty)
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 99) or None)
    app, _ = _make_app(user, session)
    with patch("gnosis.routers.users.get_password_hash", return_value="hashed"):
        with TestClient(app, raise_server_exceptions=True) as c:
            r = c.post(
                "/api/v1/users/",
                json={
                    "email": "newuser@example.com",
                    "password": "securepass",
                    "vault_slug": "new-vault",
                },
            )
    assert r.status_code == 201
    assert r.json()["email"] == "newuser@example.com"


# ---------------------------------------------------------------------------
# PATCH /users/me — vault_path as superuser (line 150-151)
# ---------------------------------------------------------------------------

def test_patch_me_vault_path_superuser_200():
    """line 150-151: superuser sets explicit vault_path."""
    user = _make_user(user_id=1, superuser=True)
    app, _ = _make_app(user)
    with patch("gnosis.routers.users.ensure_vault_directory"):
        with TestClient(app, raise_server_exceptions=True) as c:
            r = c.patch("/api/v1/users/me", json={"vault_path": "/custom/path"})
    assert r.status_code == 200
