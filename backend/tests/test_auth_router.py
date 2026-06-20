"""Tests for gnosis/routers/auth.py — login, register, me endpoints.

The @auth_limit decorator (slowapi) requires a live Request with state.limiter
attached. We bypass it by importing and calling the underlying coroutine
functions directly after patching the limiter at module level.
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


def _make_request():
    """Minimal Request mock that satisfies slowapi key_func (get_remote_address)."""
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    # slowapi stores limiter on app.state
    req.app = MagicMock()
    req.app.state = MagicMock()
    req.app.state.limiter = MagicMock()
    req.state = MagicMock()
    return req


# Patch the limiter so @auth_limit becomes a no-op pass-through
_NOOP_LIMIT = lambda f: f  # noqa: E731


# ---------------------------------------------------------------------------
# POST /auth/token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_returns_token_on_valid_credentials():
    from gnosis.core.auth import get_password_hash

    user = MagicMock()
    user.id = 1
    user.email = "user@example.com"
    user.hashed_password = get_password_hash("secret")

    db = _make_db(user=user)
    form = _make_form()

    with patch("gnosis.routers.auth.auth_limit", _NOOP_LIMIT):
        # Re-import to pick up the patched decorator
        import importlib
        import gnosis.routers.auth as auth_mod
        importlib.reload(auth_mod)
        token = await auth_mod.login(_make_request(), MagicMock(), form, db)

    assert token.access_token


@pytest.mark.asyncio
async def test_login_raises_401_on_wrong_password():
    from fastapi import HTTPException
    from gnosis.core.auth import get_password_hash

    user = MagicMock()
    user.id = 1
    user.email = "user@example.com"
    user.hashed_password = get_password_hash("correct")

    db = _make_db(user=user)
    form = _make_form(password="wrong")

    with patch("gnosis.routers.auth.auth_limit", _NOOP_LIMIT):
        import importlib
        import gnosis.routers.auth as auth_mod
        importlib.reload(auth_mod)
        with pytest.raises(HTTPException) as exc_info:
            await auth_mod.login(_make_request(), MagicMock(), form, db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_raises_401_when_user_not_found():
    from fastapi import HTTPException

    db = _make_db(user=None)
    form = _make_form()

    with patch("gnosis.routers.auth.auth_limit", _NOOP_LIMIT):
        import importlib
        import gnosis.routers.auth as auth_mod
        importlib.reload(auth_mod)
        with pytest.raises(HTTPException) as exc_info:
            await auth_mod.login(_make_request(), MagicMock(), form, db)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_creates_new_user():
    db = _make_db(user=None)  # no existing user

    payload = MagicMock()
    payload.email = "new@example.com"
    payload.password = "pass1234"
    payload.full_name = "New User"

    with patch("gnosis.routers.auth.auth_limit", _NOOP_LIMIT):
        import importlib
        import gnosis.routers.auth as auth_mod
        importlib.reload(auth_mod)
        await auth_mod.register(_make_request(), MagicMock(), payload, db)

    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_raises_400_on_duplicate_email():
    from fastapi import HTTPException

    existing = MagicMock()
    db = _make_db(user=existing)  # existing user found

    payload = MagicMock()
    payload.email = "existing@example.com"
    payload.password = "pass"
    payload.full_name = "Dup"

    with patch("gnosis.routers.auth.auth_limit", _NOOP_LIMIT):
        import importlib
        import gnosis.routers.auth as auth_mod
        importlib.reload(auth_mod)
        with pytest.raises(HTTPException) as exc_info:
            await auth_mod.register(_make_request(), MagicMock(), payload, db)
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
