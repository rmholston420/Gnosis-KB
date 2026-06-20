"""Tests for gnosis/routers/auth.py — login, register, me endpoints.

Existing test_auth.py covers the happy-path JWT flow via the full ASGI stack.
These tests call the handler functions directly to hit the remaining branches
(duplicate email, bad credentials) without standing up the full app.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_db(user=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _make_form(username="user@example.com", password="secret"):
    form = MagicMock()
    form.username = username
    form.password = password
    return form


# ---------------------------------------------------------------------------
# POST /auth/token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_returns_token_on_valid_credentials():
    from gnosis.routers.auth import login
    from gnosis.core.auth import get_password_hash

    user = MagicMock()
    user.id = 1
    user.email = "user@example.com"
    user.hashed_password = get_password_hash("secret")

    db = _make_db(user=user)
    form = _make_form()
    request = MagicMock()
    response = MagicMock()

    # Bypass the @auth_limit decorator
    with patch("gnosis.routers.auth.auth_limit", lambda f: f):
        from gnosis.routers import auth as auth_mod
        # Call the underlying coroutine directly
        token = await auth_mod.login.__wrapped__(request, response, form, db) \
            if hasattr(auth_mod.login, "__wrapped__") \
            else await auth_mod.login(request, response, form, db)
    assert token.access_token


@pytest.mark.asyncio
async def test_login_raises_401_on_wrong_password():
    from fastapi import HTTPException
    from gnosis.routers.auth import login
    from gnosis.core.auth import get_password_hash

    user = MagicMock()
    user.id = 1
    user.email = "user@example.com"
    user.hashed_password = get_password_hash("correct")

    db = _make_db(user=user)
    form = _make_form(password="wrong")
    request = MagicMock()
    response = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await login(request, response, form, db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_raises_401_when_user_not_found():
    from fastapi import HTTPException
    from gnosis.routers.auth import login

    db = _make_db(user=None)
    form = _make_form()
    request = MagicMock()
    response = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await login(request, response, form, db)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_creates_new_user():
    from gnosis.routers.auth import register

    db = _make_db(user=None)  # no existing user

    new_user = MagicMock()
    new_user.id = 5
    new_user.email = "new@example.com"
    db.refresh = AsyncMock(side_effect=lambda u: None)

    payload = MagicMock()
    payload.email = "new@example.com"
    payload.password = "pass1234"
    payload.full_name = "New User"
    request = MagicMock()
    response = MagicMock()

    # The handler returns the User ORM object after refresh; mock the DB
    # so the returned object is the one add() received
    created_user = None

    def capture_add(u):
        nonlocal created_user
        created_user = u

    db.add = capture_add
    result = await register(request, response, payload, db)
    # Should reach db.commit without raising
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_raises_400_on_duplicate_email():
    from fastapi import HTTPException
    from gnosis.routers.auth import register

    existing = MagicMock()
    db = _make_db(user=existing)  # existing user found

    payload = MagicMock()
    payload.email = "existing@example.com"
    payload.password = "pass"
    payload.full_name = "Dup"
    request = MagicMock()
    response = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await register(request, response, payload, db)
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_me_returns_current_user():
    from gnosis.routers.auth import me

    user = MagicMock()
    user.id = 3
    result = await me(current=user)
    assert result.id == 3
