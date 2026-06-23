"""
Integration tests for gnosis/routers/users.py admin paths.

Coverage targets (users.py)
----------------------------
  134       GET /users/me → 200 with current user data
  141       GET /users/{id} → 404 when user not found
  222-243   GET /users/ (admin list) — requires is_superuser=True
  284-288   PATCH /users/{id} (admin update) — requires is_superuser=True
  325-326   DELETE /users/{id} (admin delete) — requires is_superuser=True
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from gnosis.database import Base, get_db
from gnosis.main import create_app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Superuser fake
# ---------------------------------------------------------------------------

@dataclass
class _SuperUser:
    id: int = 2
    email: str = "admin@gnosis.local"
    full_name: str | None = "Admin User"
    vault_slug: str | None = "admin"
    vault_path: str | None = None
    is_active: bool = True
    is_superuser: bool = True


async def _fake_superuser() -> _SuperUser:
    return _SuperUser()


@dataclass
class _NormalUser:
    id: int = 3
    email: str = "user@gnosis.local"
    full_name: str | None = "Normal User"
    vault_slug: str | None = "user"
    vault_path: str | None = None
    is_active: bool = True
    is_superuser: bool = False


async def _fake_normal_user() -> _NormalUser:
    return _NormalUser()


# ---------------------------------------------------------------------------
# Admin client fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_client(test_engine, vault_dir) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX client authenticated as a superuser."""
    import tempfile
    from pathlib import Path
    from unittest.mock import AsyncMock, patch

    p1 = patch("gnosis.services.vector_store.ensure_collection", return_value=None)
    p2 = patch("gnosis.services.vault_sync.start_vault_watcher",
               new=AsyncMock(return_value=type('O', (), {'stop': lambda s: None, 'join': lambda s: None})()))
    p3 = patch("gnosis.services.graph_rag.graph_rag.initialize", new=AsyncMock(return_value=None))

    with p1, p2, p3:
        from gnosis import config
        from gnosis.core.auth import get_current_user, require_user
        import gnosis.core.namespace as _ns

        settings = config.get_settings()
        settings.vault_path = str(vault_dir)
        _ns.VAULT_ROOT = vault_dir

        app = create_app()
        session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[require_user] = _fake_superuser
        app.dependency_overrides[get_current_user] = _fake_superuser

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /users/me  (line 134)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_me_returns_current_user(client):
    """GET /users/me returns 200 with the authenticated user's data."""
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "test@gnosis.local"


# ---------------------------------------------------------------------------
# GET /users/{id} → 404 when user not in DB  (line 141)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_user_by_id_404_when_not_found(admin_client):
    """Fetching a non-existent user ID returns 404."""
    resp = await admin_client.get("/api/v1/users/99999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /users/ admin list  (lines 222-243)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_list_users_returns_list(admin_client):
    """Superuser can GET /users/ and receive a list (even if empty)."""
    resp = await admin_client.get("/api/v1/users/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_admin_list_users_forbidden_for_normal_user(client):
    """Non-superuser requesting /users/ should receive 403."""
    resp = await client.get("/api/v1/users/")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /users/{id} admin update  (lines 284-288)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_update_user_404_when_not_found(admin_client):
    """PATCH a non-existent user as superuser → 404."""
    resp = await admin_client.patch(
        "/api/v1/users/88888",
        json={"full_name": "Updated Name"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_update_user_forbidden_for_normal_user(client):
    """PATCH /users/{id} as non-superuser → 403."""
    resp = await client.patch(
        "/api/v1/users/1",
        json={"full_name": "Hacked"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /users/{id} admin delete  (lines 325-326)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_delete_user_404_when_not_found(admin_client):
    """DELETE a non-existent user as superuser → 404."""
    resp = await admin_client.delete("/api/v1/users/77777")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_delete_user_forbidden_for_normal_user(client):
    """DELETE /users/{id} as non-superuser → 403."""
    resp = await client.delete("/api/v1/users/1")
    assert resp.status_code == 403
