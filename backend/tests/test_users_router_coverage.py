"""
Coverage tests for gnosis/routers/users.py.

All tests use the synchronous Starlette TestClient so that coverage.py’s
thread-local tracer is active during execution (pytest-anyio runs coroutines
in a worker thread where the tracer is not attached, causing executed lines
to appear uncovered).

Target lines
------------
  134       get_me → return UserProfile.model_validate(current_user)
  141       update_me → first branch entry (vault_slug check)
  222-243   list_users → superuser guard + SELECT + return dict
  284-288   update_grant → 404 branch (grant not found)
  325-326   revoke_grant → 404 branch (grant not found)

Design notes
------------
* _make_app mounts ONLY users.router into a bare FastAPI() so no lifespan,
  no Qdrant, no LightRAG patches are needed.
* Both get_session AND require_user are overridden with zero-argument
  async callables to match FastAPI’s dependency-injection signature.
* TestClient is used (not AsyncClient) so the test runs synchronously in
  the main thread where coverage.py’s C-tracer is registered.
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

def _make_user(user_id: int = 1, superuser: bool = False) -> User:
    """Return a real SQLAlchemy User instance (not a MagicMock).
    UserProfile.model_validate requires from_attributes=True to work;
    a plain dataclass or MagicMock won’t carry ORM instrumentation but
    Pydantic’s from_attributes reads __dict__ attributes directly, so a
    real User() object with explicit field assignments is the safest choice.
    """
    u = User(
        email="user@test.com" if not superuser else "admin@test.com",
        hashed_password="hashed",
        full_name="Test User",
        vault_slug="test-vault",
        vault_path="/vaults/test",
        vault_display_name="Test Vault",
        is_superuser=superuser,
        is_active=True,
    )
    # SQLAlchemy won’t set PK without a session; set it manually
    u.id = user_id
    return u


def _make_app(user: User, session_mock: AsyncMock | None = None) -> tuple[FastAPI, AsyncMock]:
    """Mount users.router into a bare FastAPI app with mocked auth + DB."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    if session_mock is None:
        session_mock = AsyncMock()
        empty_result = MagicMock()
        empty_result.scalar_one_or_none.return_value = None
        empty_result.scalars.return_value.all.return_value = []
        session_mock.execute = AsyncMock(return_value=empty_result)
        session_mock.commit = AsyncMock()
        session_mock.refresh = AsyncMock(side_effect=lambda obj: None)
        session_mock.add = MagicMock()

    # FastAPI resolves async deps in the event loop and sync deps in a
    # thread.  Use async defs so execution stays in the traced event loop.
    async def _override_session():
        yield session_mock

    async def _override_user():
        return user

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[require_user] = _override_user
    return app, session_mock


# ---------------------------------------------------------------------------
# GET /users/me  (line 134)
# ---------------------------------------------------------------------------

def test_get_me_returns_200():
    """line 134: return UserProfile.model_validate(current_user)"""
    user = _make_user()
    app, _ = _make_app(user)
    with TestClient(app, raise_server_exceptions=True) as client:
        resp = client.get("/api/v1/users/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@test.com"
    assert resp.json()["vault_slug"] == "test-vault"


# ---------------------------------------------------------------------------
# PATCH /users/me  (line 141+)
# ---------------------------------------------------------------------------

def test_update_me_full_name_line_141():
    """line 141: enters update_me body and sets full_name."""
    user = _make_user()
    app, _ = _make_app(user)
    with patch("gnosis.routers.users.ensure_vault_directory"):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.patch("/api/v1/users/me", json={"full_name": "New Name"})
    assert resp.status_code == 200


def test_update_me_invalid_slug_422():
    user = _make_user()
    app, _ = _make_app(user)
    with TestClient(app) as client:
        resp = client.patch("/api/v1/users/me", json={"vault_slug": "X"})
    assert resp.status_code == 422


def test_update_me_vault_path_non_superuser_403():
    user = _make_user(superuser=False)
    app, _ = _make_app(user)
    with patch("gnosis.routers.users.ensure_vault_directory"):
        with TestClient(app) as client:
            resp = client.patch("/api/v1/users/me", json={"vault_path": "/override"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /users/  — list_users  (lines 222-243)
# ---------------------------------------------------------------------------

def test_list_users_non_superuser_returns_403():
    """lines 222-223: if not current_user.is_superuser: raise 403"""
    user = _make_user(superuser=False)
    app, _ = _make_app(user)
    with TestClient(app) as client:
        resp = client.get("/api/v1/users/")
    assert resp.status_code == 403


def test_list_users_superuser_returns_200():
    """lines 224-243: SELECT users, return paginated dict"""
    user = _make_user(superuser=True)
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    app, _ = _make_app(user, session)
    with TestClient(app, raise_server_exceptions=True) as client:
        resp = client.get("/api/v1/users/")
    assert resp.status_code == 200
    body = resp.json()
    assert "users" in body
    assert body["page"] == 1
    assert isinstance(body["users"], list)


# ---------------------------------------------------------------------------
# POST /users/  (superuser create path)
# ---------------------------------------------------------------------------

def test_create_user_non_superuser_returns_403():
    user = _make_user(superuser=False)
    app, _ = _make_app(user)
    with TestClient(app) as client:
        resp = client.post("/api/v1/users/", json={"email": "x@x.com", "password": "12345678"})
    assert resp.status_code == 403


def test_create_user_duplicate_returns_409():
    user = _make_user(superuser=True)
    session = AsyncMock()
    conflict = MagicMock()
    conflict.scalar_one_or_none.return_value = user  # duplicate
    session.execute = AsyncMock(return_value=conflict)
    app, _ = _make_app(user, session)
    with TestClient(app) as client:
        resp = client.post("/api/v1/users/", json={"email": "admin@test.com", "password": "12345678"})
    assert resp.status_code == 409


def test_create_user_superuser_success():
    """Superuser creating a new user — mocks get_password_hash to avoid bcrypt."""
    user = _make_user(superuser=True)
    session = AsyncMock()
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=empty)
    session.commit = AsyncMock()
    session.add = MagicMock()

    new_user = _make_user(user_id=42, superuser=False)
    new_user.email = "new@example.com"
    session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 42) or None)

    app, _ = _make_app(user, session)
    with patch("gnosis.routers.users.get_password_hash", return_value="hashed"):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.post(
                "/api/v1/users/",
                json={"email": "new@example.com", "password": "12345678"},
            )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# PATCH /users/me/vaults/{grant_id}  (lines 284-288: update_grant 404)
# ---------------------------------------------------------------------------

def test_update_grant_invalid_permission_422():
    user = _make_user()
    app, _ = _make_app(user)
    with TestClient(app) as client:
        resp = client.patch("/api/v1/users/me/vaults/1", json={"permission": "owner"})
    assert resp.status_code == 422


def test_update_grant_not_found_404():
    """lines 284-288: grant is None → 404"""
    user = _make_user()
    app, _ = _make_app(user)  # session returns None by default
    with TestClient(app, raise_server_exceptions=True) as client:
        resp = client.patch("/api/v1/users/me/vaults/9999", json={"permission": "write"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /users/me/vaults/{grant_id}  (lines 325-326: revoke_grant 404)
# ---------------------------------------------------------------------------

def test_revoke_grant_not_found_404():
    """lines 325-326: grant is None → 404"""
    user = _make_user()
    app, _ = _make_app(user)  # session returns None by default
    with TestClient(app, raise_server_exceptions=True) as client:
        resp = client.delete("/api/v1/users/me/vaults/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /users/me/vaults
# ---------------------------------------------------------------------------

def test_list_my_vaults_returns_200():
    user = _make_user()
    app, _ = _make_app(user)
    with TestClient(app, raise_server_exceptions=True) as client:
        resp = client.get("/api/v1/users/me/vaults")
    assert resp.status_code == 200
    assert resp.json() == []
