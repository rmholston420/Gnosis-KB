"""Unit tests for gnosis/routers/auth.py.

Covers: login (happy + wrong password + unknown user),
register (happy + duplicate email), me endpoint.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _user(uid=1, email="user@example.com", hashed="hashed"):
    u = MagicMock()
    u.id = uid
    u.email = email
    u.hashed_password = hashed
    u.full_name = "Test User"
    return u


def _db_scalar(obj):
    result = MagicMock()
    result.scalar_one_or_none.return_value = obj
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _form(username="user@example.com", password="secret"):
    f = MagicMock()
    f.username = username
    f.password = password
    return f


# ---------------------------------------------------------------------------
# POST /auth/token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_returns_token_on_valid_credentials():
    from gnosis.routers.auth import login

    user = _user()
    db = _db_scalar(user)

    with (
        patch("gnosis.routers.auth.verify_password", return_value=True),
        patch("gnosis.routers.auth.create_access_token", return_value="jwt-token"),
    ):
        result = await login(
            request=MagicMock(), response=MagicMock(),
            form=_form(), db=db,
        )
    assert result.access_token == "jwt-token"


@pytest.mark.asyncio
async def test_login_returns_401_on_wrong_password():
    from fastapi import HTTPException
    from gnosis.routers.auth import login

    user = _user()
    db = _db_scalar(user)

    with (
        patch("gnosis.routers.auth.verify_password", return_value=False),
        pytest.raises(HTTPException) as exc_info,
    ):
        await login(
            request=MagicMock(), response=MagicMock(),
            form=_form(password="wrong"), db=db,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_returns_401_on_unknown_user():
    from fastapi import HTTPException
    from gnosis.routers.auth import login

    db = _db_scalar(None)  # no user found

    with pytest.raises(HTTPException) as exc_info:
        await login(
            request=MagicMock(), response=MagicMock(),
            form=_form(), db=db,
        )
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_creates_new_user():
    from gnosis.routers.auth import register
    from gnosis.schemas.auth import UserCreate

    db = _db_scalar(None)  # no existing user
    new_user = _user()
    db.refresh = AsyncMock(side_effect=lambda u: None)

    with patch("gnosis.routers.auth.get_password_hash", return_value="hashed_pw"):
        result = await register(
            request=MagicMock(), response=MagicMock(),
            payload=UserCreate(email="new@example.com", password="pass123", full_name="New User"),
            db=db,
        )
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_returns_400_on_duplicate_email():
    from fastapi import HTTPException
    from gnosis.routers.auth import register
    from gnosis.schemas.auth import UserCreate

    db = _db_scalar(_user())  # existing user found

    with pytest.raises(HTTPException) as exc_info:
        await register(
            request=MagicMock(), response=MagicMock(),
            payload=UserCreate(email="user@example.com", password="pass", full_name="Dup"),
            db=db,
        )
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_me_returns_current_user():
    from gnosis.routers.auth import me

    user = _user()
    result = await me(current=user)
    assert result.id == 1
