"""Coverage tests for gnosis/routers/users.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.users import router


def _make_app(db_mock: AsyncMock, user_id: int = 1) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    user = User(id=user_id, email="u@test.com", hashed_password="x")

    async def _db():
        yield db_mock

    async def _user():
        return user

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[require_user] = _user
    return app


def _user_obj(user_id=1, email="u@test.com"):
    u = MagicMock(spec=User)
    u.id = user_id
    u.email = email
    u.hashed_password = "hashed"
    u.created_at = datetime.now(timezone.utc)
    u.is_active = True
    return u


def _scalar_one(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalars.return_value.first.return_value = value
    return r


# GET /users/me
def test_get_me_returns_200():
    db = AsyncMock()
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "u@test.com"


# POST /users/register
def test_register_new_user():
    db = AsyncMock()
    db.execute.return_value = _scalar_one(None)  # no existing user
    new_user = _user_obj()
    db.refresh = AsyncMock(side_effect=lambda u: (
        setattr(u, 'id', 1) or
        setattr(u, 'email', 'new@test.com') or
        setattr(u, 'created_at', datetime.now(timezone.utc)) or
        setattr(u, 'is_active', True)
    ))
    db.add = MagicMock()
    db.commit = AsyncMock()

    with patch("gnosis.routers.users.pwd_context") as mock_pwd:
        mock_pwd.hash.return_value = "hashed_pw"
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/users/register",
                           json={"email": "new@test.com", "password": "secret123"})
    assert resp.status_code in (200, 201)


def test_register_existing_user_returns_400():
    db = AsyncMock()
    db.execute.return_value = _scalar_one(_user_obj())  # user exists
    client = TestClient(_make_app(db))
    resp = client.post("/api/v1/users/register",
                       json={"email": "u@test.com", "password": "secret"})
    assert resp.status_code == 400


# POST /users/login
def test_login_wrong_email_returns_401():
    db = AsyncMock()
    db.execute.return_value = _scalar_one(None)
    client = TestClient(_make_app(db))
    resp = client.post("/api/v1/users/login",
                       json={"email": "wrong@test.com", "password": "pw"})
    assert resp.status_code == 401


def test_login_wrong_password_returns_401():
    db = AsyncMock()
    db.execute.return_value = _scalar_one(_user_obj())
    with patch("gnosis.routers.users.pwd_context") as mock_pwd:
        mock_pwd.verify.return_value = False
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/users/login",
                           json={"email": "u@test.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_success_returns_token():
    db = AsyncMock()
    u = _user_obj()
    db.execute.return_value = _scalar_one(u)
    with patch("gnosis.routers.users.pwd_context") as mock_pwd, \
         patch("gnosis.routers.users.create_access_token", return_value="tok123"):
        mock_pwd.verify.return_value = True
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/users/login",
                           json={"email": "u@test.com", "password": "correct"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


# PATCH /users/me
def test_update_me_returns_200():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda u: None)
    client = TestClient(_make_app(db))
    resp = client.patch("/api/v1/users/me", json={"email": "newemail@test.com"})
    assert resp.status_code == 200


# DELETE /users/me
def test_delete_me_returns_204():
    db = AsyncMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    client = TestClient(_make_app(db))
    resp = client.delete("/api/v1/users/me")
    assert resp.status_code == 204
