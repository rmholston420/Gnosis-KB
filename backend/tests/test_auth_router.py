"""Tests for gnosis/routers/auth.py — login, register, me endpoints.

Calls handler coroutines directly after monkeypatching the db.execute result.
slowapi's @auth_limit decorator wraps the function but still exposes the
original coroutine via the closure — we extract it with inspect rather than
reloading the module.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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


def _form(username="u@example.com", password="secret"):
    f = MagicMock()
    f.username = username
    f.password = password
    return f


def _req():
    return MagicMock()


def _get_handler(decorated_fn):
    """Return the underlying coroutine from a slowapi-decorated handler.

    slowapi wraps with functools.wraps so __wrapped__ is set on the inner
    function.  Walk the chain until we find a plain coroutinefunction.
    """
    import inspect

    fn = decorated_fn
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    if inspect.iscoroutinefunction(fn):
        return fn
    # Fallback: call as-is (will raise if still wrapped)
    return decorated_fn


# ---------------------------------------------------------------------------
# POST /auth/token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_valid_credentials_returns_token():
    from gnosis.core.auth import get_password_hash
    from gnosis.routers.auth import login

    user = MagicMock()
    user.id = 1
    user.email = "u@example.com"
    user.hashed_password = get_password_hash("secret")

    handler = _get_handler(login)
    token = await handler(_req(), MagicMock(), _form(), _make_db(user=user))
    assert token.access_token


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401():
    from fastapi import HTTPException

    from gnosis.core.auth import get_password_hash
    from gnosis.routers.auth import login

    user = MagicMock()
    user.id = 1
    user.email = "u@example.com"
    user.hashed_password = get_password_hash("correct")

    handler = _get_handler(login)
    with pytest.raises(HTTPException) as exc:
        await handler(_req(), MagicMock(), _form(password="wrong"), _make_db(user=user))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user_returns_401():
    from fastapi import HTTPException

    from gnosis.routers.auth import login

    handler = _get_handler(login)
    with pytest.raises(HTTPException) as exc:
        await handler(_req(), MagicMock(), _form(), _make_db(user=None))
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_new_user_calls_commit():
    from gnosis.routers.auth import register

    db = _make_db(user=None)
    payload = MagicMock()
    payload.email = "new@example.com"
    payload.password = "pass1234"
    payload.full_name = "New User"

    handler = _get_handler(register)
    await handler(_req(), MagicMock(), payload, db)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_400():
    from fastapi import HTTPException

    from gnosis.routers.auth import register

    existing = MagicMock()
    db = _make_db(user=existing)
    payload = MagicMock()
    payload.email = "dup@example.com"
    payload.password = "pass"
    payload.full_name = "Dup"

    handler = _get_handler(register)
    with pytest.raises(HTTPException) as exc:
        await handler(_req(), MagicMock(), payload, db)
    assert exc.value.status_code == 400


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
