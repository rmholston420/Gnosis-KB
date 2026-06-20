"""Unit tests for gnosis/core/auth.py.

Covers: verify_password, get_password_hash, create_access_token,
get_current_user (auth_required=True: valid token, bad token, user not found;
auth_required=False: returns first active user),
require_user (None raises 401),
get_vault_owner_ids (no header, own-vault header, invalid header, no-grant header).
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def test_get_password_hash_and_verify():
    from gnosis.core.auth import get_password_hash, verify_password
    hashed = get_password_hash("mysecret")
    assert verify_password("mysecret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_access_token_encodes_user_id():
    from gnosis.core.auth import create_access_token, TokenData
    from jose import jwt
    from gnosis.config import settings
    token = create_access_token(TokenData(user_id=42, email="u@example.com"))
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert payload["sub"] == "42"
    assert payload["email"] == "u@example.com"


def test_create_access_token_custom_expiry():
    from gnosis.core.auth import create_access_token, TokenData
    token = create_access_token(TokenData(user_id=1, email="a@b.com"), expires_delta=timedelta(hours=1))
    assert token


# ---------------------------------------------------------------------------
# get_current_user — auth_required=True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_current_user_returns_user_on_valid_token():
    from gnosis.core.auth import get_current_user, create_access_token, TokenData
    from gnosis.config import settings as real_settings

    user = MagicMock()
    user.id = 7
    user.is_active = True
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    token = create_access_token(TokenData(user_id=7, email="u@example.com"))

    with patch("gnosis.core.auth.settings") as mock_settings:
        mock_settings.auth_required = True
        mock_settings.secret_key = real_settings.secret_key
        result = await get_current_user(token=token, db=db)
    assert result.id == 7


@pytest.mark.asyncio
async def test_get_current_user_raises_401_on_bad_token():
    from fastapi import HTTPException
    from gnosis.core.auth import get_current_user

    db = AsyncMock()
    with patch("gnosis.core.auth.settings") as mock_settings:
        mock_settings.auth_required = True
        mock_settings.secret_key = "test-secret"
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="not.a.valid.jwt", db=db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_raises_401_when_no_token():
    from fastapi import HTTPException
    from gnosis.core.auth import get_current_user

    db = AsyncMock()
    with patch("gnosis.core.auth.settings") as mock_settings:
        mock_settings.auth_required = True
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=None, db=db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_raises_401_when_user_not_found():
    from fastapi import HTTPException
    from gnosis.core.auth import get_current_user, create_access_token, TokenData
    from gnosis.config import settings as real_settings

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    token = create_access_token(TokenData(user_id=99, email="ghost@example.com"))

    with patch("gnosis.core.auth.settings") as mock_settings:
        mock_settings.auth_required = True
        mock_settings.secret_key = real_settings.secret_key
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_auth_not_required_returns_first_user():
    from gnosis.core.auth import get_current_user

    user = MagicMock()
    user.id = 1
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    with patch("gnosis.core.auth.settings") as mock_settings:
        mock_settings.auth_required = False
        result = await get_current_user(token=None, db=db)
    assert result.id == 1


# ---------------------------------------------------------------------------
# require_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_user_raises_401_when_none():
    from fastapi import HTTPException
    from gnosis.core.auth import require_user

    with pytest.raises(HTTPException) as exc_info:
        await require_user(current=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_user_returns_user_when_present():
    from gnosis.core.auth import require_user

    user = MagicMock()
    user.id = 5
    result = await require_user(current=user)
    assert result.id == 5


# ---------------------------------------------------------------------------
# get_vault_owner_ids
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_vault_owner_ids_no_header_returns_accessible():
    """When X-Vault-Owner-Id header is absent, delegate to get_accessible_owner_ids."""
    from gnosis.core.auth import get_vault_owner_ids

    user = MagicMock()
    user.id = 1
    request = MagicMock()
    request.headers.get.return_value = None
    db = AsyncMock()

    # get_accessible_owner_ids is imported locally inside get_vault_owner_ids
    # from gnosis.core.namespace — patch it there.
    with patch("gnosis.core.namespace.get_accessible_owner_ids", new=AsyncMock(return_value={1, 2})):
        import importlib
        import gnosis.core.auth as _auth
        # Force the lazy import inside the function to pick up our patch
        import gnosis.core.namespace as _ns
        original = _ns.get_accessible_owner_ids
        _ns.get_accessible_owner_ids = AsyncMock(return_value={1, 2})
        try:
            result = await get_vault_owner_ids(request=request, current_user=user, db=db)
        finally:
            _ns.get_accessible_owner_ids = original

    assert 1 in result


@pytest.mark.asyncio
async def test_get_vault_owner_ids_own_vault_header_returns_self():
    """When header equals own user.id, return {user.id} without DB call."""
    from gnosis.core.auth import get_vault_owner_ids

    user = MagicMock()
    user.id = 3
    request = MagicMock()
    request.headers.get.return_value = "3"
    db = AsyncMock()

    result = await get_vault_owner_ids(request=request, current_user=user, db=db)
    assert result == {3}


@pytest.mark.asyncio
async def test_get_vault_owner_ids_invalid_header_returns_400():
    """Non-integer header value raises HTTP 400."""
    from fastapi import HTTPException
    from gnosis.core.auth import get_vault_owner_ids

    user = MagicMock()
    user.id = 1
    request = MagicMock()
    request.headers.get.return_value = "not-an-int"
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await get_vault_owner_ids(request=request, current_user=user, db=db)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_vault_owner_ids_no_grant_returns_403():
    """When get_accessible_owner_ids raises ValueError, HTTP 403 is raised."""
    from fastapi import HTTPException
    from gnosis.core.auth import get_vault_owner_ids

    user = MagicMock()
    user.id = 1
    request = MagicMock()
    request.headers.get.return_value = "99"  # different vault, no grant
    db = AsyncMock()

    import gnosis.core.namespace as _ns
    original = _ns.get_accessible_owner_ids
    _ns.get_accessible_owner_ids = AsyncMock(side_effect=ValueError("no grant"))
    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_vault_owner_ids(request=request, current_user=user, db=db)
        assert exc_info.value.status_code == 403
    finally:
        _ns.get_accessible_owner_ids = original
