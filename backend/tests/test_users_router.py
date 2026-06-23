"""
Tests for /api/v1/users endpoints.

All DB calls are mocked so no real database is needed.

Critical: _make_user() returns a real User SQLAlchemy instance, NOT a
MagicMock. UserProfile uses model_validate(obj, from_attributes=True) which
calls Pydantic's int/str validators on the actual attribute values. A
MagicMock satisfies attribute access but fails int/str validation, causing
a 422/500 before line 128 executes. A real User instance with typed fields
passes validation correctly.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from gnosis.models.user import User
from gnosis.routers.users import router
from gnosis.database import get_session


# ---------------------------------------------------------------------------
# App / client fixtures
# ---------------------------------------------------------------------------

def _make_user(*, is_superuser: bool = False, **kw) -> User:
    """Return a real User ORM instance with typed attributes.

    MagicMock cannot be used here because UserProfile.model_validate() runs
    Pydantic field validators (int, str, bool) on each attribute value.
    A MagicMock passes attribute access but the returned MagicMock objects
    fail int('MagicMock') validation, raising ValidationError -> HTTP 500.
    """
    u = User(
        email=kw.get("email", "alice@example.com"),
        hashed_password="hashed",
        full_name=kw.get("full_name", "Alice"),
        vault_slug=kw.get("vault_slug", "alice"),
        vault_path=kw.get("vault_path", "/vaults/alice"),
        vault_display_name=kw.get("vault_display_name", "Alice's Vault"),
        is_superuser=is_superuser,
        is_active=True,
    )
    u.id = kw.get("id", 1)
    return u


def _make_app(current_user: User):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda obj: None)
    mock_session.add = MagicMock()

    app.dependency_overrides[get_session] = lambda: mock_session

    from gnosis.core.auth import require_user
    async def _auth():
        return current_user
    app.dependency_overrides[require_user] = _auth

    return app, mock_session


@pytest.fixture()
def normal_user() -> User:
    return _make_user()


@pytest.fixture()
def super_user() -> User:
    return _make_user(is_superuser=True, id=2, email="admin@example.com")


# ---------------------------------------------------------------------------
# GET /users/me  (line 128)
# ---------------------------------------------------------------------------

async def test_get_me_returns_profile(normal_user):
    app, _ = _make_app(normal_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["vault_slug"] == "alice"


# ---------------------------------------------------------------------------
# PATCH /users/me  (line 134+)
# ---------------------------------------------------------------------------

async def test_patch_me_updates_full_name(normal_user):
    app, mock_session = _make_app(normal_user)
    async def _refresh(obj):
        pass
    mock_session.refresh.side_effect = _refresh

    with patch("gnosis.routers.users.ensure_vault_directory"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch("/api/v1/users/me", json={"full_name": "Alice Smith"})
    assert resp.status_code == 200


async def test_patch_me_invalid_slug_returns_422(normal_user):
    app, _ = _make_app(normal_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch("/api/v1/users/me", json={"vault_slug": "!invalid!"})
    assert resp.status_code == 422


async def test_patch_me_vault_path_non_superuser_returns_403(normal_user):
    app, _ = _make_app(normal_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch("/api/v1/users/me", json={"vault_path": "/custom"})
    assert resp.status_code == 403


async def test_patch_me_slug_conflict_returns_409(normal_user):
    app, mock_session = _make_app(normal_user)
    other = _make_user(id=99, email="bob@example.com")
    conflict_result = MagicMock()
    conflict_result.scalar_one_or_none.return_value = other
    mock_session.execute = AsyncMock(return_value=conflict_result)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch("/api/v1/users/me", json={"vault_slug": "taken-slug"})
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# GET /users/me/vaults
# ---------------------------------------------------------------------------

async def test_list_my_vaults_returns_empty(normal_user):
    app, _ = _make_app(normal_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/users/me/vaults")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# POST /users/me/vaults/invite
# ---------------------------------------------------------------------------

async def test_invite_invalid_permission_returns_422(normal_user):
    app, _ = _make_app(normal_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/users/me/vaults/invite",
            json={"member_email": "bob@example.com", "permission": "admin"},
        )
    assert resp.status_code == 422


async def test_invite_unknown_user_returns_404(normal_user):
    app, _ = _make_app(normal_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/users/me/vaults/invite",
            json={"member_email": "ghost@example.com", "permission": "read"},
        )
    assert resp.status_code == 404


async def test_invite_self_returns_422(normal_user):
    app, mock_session = _make_app(normal_user)
    member_result = MagicMock()
    member_result.scalar_one_or_none.return_value = normal_user
    mock_session.execute = AsyncMock(return_value=member_result)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/users/me/vaults/invite",
            json={"member_email": normal_user.email, "permission": "read"},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /users/me/vaults/{grant_id}
# ---------------------------------------------------------------------------

async def test_update_grant_invalid_permission(normal_user):
    app, _ = _make_app(normal_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            "/api/v1/users/me/vaults/1",
            json={"permission": "superadmin"},
        )
    assert resp.status_code == 422


async def test_update_grant_not_found_returns_404(normal_user):
    app, _ = _make_app(normal_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            "/api/v1/users/me/vaults/9999",
            json={"permission": "write"},
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /users/me/vaults/{grant_id}
# ---------------------------------------------------------------------------

async def test_revoke_grant_not_found_returns_404(normal_user):
    app, _ = _make_app(normal_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete("/api/v1/users/me/vaults/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /users/  — superuser only  (lines 222-243)
# ---------------------------------------------------------------------------

async def test_list_users_non_superuser_returns_403(normal_user):
    app, _ = _make_app(normal_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/users/")
    assert resp.status_code == 403


async def test_list_users_superuser_returns_200(super_user):
    app, _ = _make_app(super_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/users/")
    assert resp.status_code == 200
    assert "users" in resp.json()


# ---------------------------------------------------------------------------
# POST /users/  — create user, superuser only
# ---------------------------------------------------------------------------

async def test_create_user_non_superuser_returns_403(normal_user):
    app, _ = _make_app(normal_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/users/",
            json={"email": "new@example.com", "password": "securepass"},
        )
    assert resp.status_code == 403


async def test_create_user_duplicate_email_returns_409(super_user):
    app, mock_session = _make_app(super_user)
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = super_user
    mock_session.execute = AsyncMock(return_value=existing_result)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/users/",
            json={"email": "alice@example.com", "password": "securepass"},
        )
    assert resp.status_code == 409


async def test_create_user_success_returns_201(super_user):
    app, mock_session = _make_app(super_user)
    mock_session.refresh.side_effect = lambda obj: None

    with patch("gnosis.routers.users.get_password_hash", return_value="hashed"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/users/",
                json={"email": "new@example.com", "password": "securepass"},
            )
    assert resp.status_code == 201
