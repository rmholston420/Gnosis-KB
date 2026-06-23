"""
Direct coroutine-level unit tests for gnosis/routers/users.py.

asyncio_mode = "auto" in pyproject.toml means pytest-asyncio auto-collects
all async def test_* functions. The @pytest.mark.asyncio marker is not only
unnecessary but actively harmful in auto mode: it can cause tests to be
collected twice or skipped entirely. All markers are removed here.

Target lines in users.py
-------------------------
  128     get_me -> return UserProfile.model_validate(current_user)
  134     update_me function body entry
  222-243 list_users body (superuser guard + SELECT + return)
  284-288 update_grant -> grant-not-found 404 branch
  325-326 revoke_grant -> grant-not-found 404 branch
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from gnosis.models.user import User
from gnosis.routers.users import (
    CreateUserRequest,
    UpdateGrantRequest,
    UpdateMeRequest,
    create_user,
    get_me,
    list_users,
    revoke_grant,
    update_grant,
    update_me,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(superuser: bool = False) -> User:
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
    u.id = 1 if not superuser else 2
    return u


def _session(result_value=None) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = result_value
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda obj: None)
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# get_me  (line 128)
# ---------------------------------------------------------------------------

async def test_get_me_direct():
    user = _user()
    result = await get_me(current_user=user)
    assert result.email == "user@test.com"
    assert result.vault_slug == "test-vault"
    assert result.is_superuser is False


async def test_get_me_superuser_direct():
    user = _user(superuser=True)
    result = await get_me(current_user=user)
    assert result.is_superuser is True


# ---------------------------------------------------------------------------
# update_me  (lines 134+)
# ---------------------------------------------------------------------------

async def test_update_me_full_name_direct():
    user = _user()
    session = _session()
    req = UpdateMeRequest(full_name="New Name")
    with patch("gnosis.routers.users.ensure_vault_directory"):
        result = await update_me(req=req, session=session, current_user=user)
    assert result.full_name == "New Name"


async def test_update_me_invalid_slug_raises_422():
    user = _user()
    session = _session()
    req = UpdateMeRequest(vault_slug="X")
    with pytest.raises(HTTPException) as exc_info:
        await update_me(req=req, session=session, current_user=user)
    assert exc_info.value.status_code == 422


async def test_update_me_slug_conflict_raises_409():
    other = _user()
    other.id = 99
    user = _user()
    session = _session(result_value=other)
    req = UpdateMeRequest(vault_slug="taken-slug")
    with pytest.raises(HTTPException) as exc_info:
        await update_me(req=req, session=session, current_user=user)
    assert exc_info.value.status_code == 409


async def test_update_me_vault_path_non_superuser_raises_403():
    user = _user(superuser=False)
    session = _session()
    req = UpdateMeRequest(vault_path="/override")
    with pytest.raises(HTTPException) as exc_info:
        await update_me(req=req, session=session, current_user=user)
    assert exc_info.value.status_code == 403


async def test_update_me_vault_path_superuser_ok():
    user = _user(superuser=True)
    session = _session()
    req = UpdateMeRequest(vault_path="/custom/path")
    with patch("gnosis.routers.users.ensure_vault_directory"):
        result = await update_me(req=req, session=session, current_user=user)
    assert result.vault_path == "/custom/path"


# ---------------------------------------------------------------------------
# list_users  (lines 222-243)
# ---------------------------------------------------------------------------

async def test_list_users_non_superuser_raises_403():
    user = _user(superuser=False)
    session = _session()
    with pytest.raises(HTTPException) as exc_info:
        await list_users(page=1, page_size=50, session=session, current_user=user)
    assert exc_info.value.status_code == 403


async def test_list_users_superuser_returns_dict():
    user = _user(superuser=True)
    session = _session()
    result = await list_users(page=1, page_size=50, session=session, current_user=user)
    assert "users" in result
    assert result["page"] == 1
    assert result["page_size"] == 50
    assert isinstance(result["users"], list)


async def test_list_users_page_2():
    user = _user(superuser=True)
    session = _session()
    result = await list_users(page=2, page_size=10, session=session, current_user=user)
    assert result["page"] == 2
    assert result["page_size"] == 10


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

async def test_create_user_non_superuser_raises_403():
    user = _user(superuser=False)
    session = _session()
    req = CreateUserRequest(email="x@x.com", password="12345678")
    with pytest.raises(HTTPException) as exc_info:
        await create_user(req=req, session=session, current_user=user)
    assert exc_info.value.status_code == 403


async def test_create_user_duplicate_raises_409():
    user = _user(superuser=True)
    existing = _user()
    session = _session(result_value=existing)
    req = CreateUserRequest(email="user@test.com", password="12345678")
    with pytest.raises(HTTPException) as exc_info:
        await create_user(req=req, session=session, current_user=user)
    assert exc_info.value.status_code == 409


async def test_create_user_superuser_success():
    user = _user(superuser=True)
    session = _session(result_value=None)
    session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 42) or None)
    req = CreateUserRequest(email="new@example.com", password="12345678")
    with patch("gnosis.routers.users.get_password_hash", return_value="hashed"):
        result = await create_user(req=req, session=session, current_user=user)
    assert result["email"] == "new@example.com"


# ---------------------------------------------------------------------------
# update_grant  (lines 284-288)
# ---------------------------------------------------------------------------

async def test_update_grant_not_found_raises_404():
    user = _user()
    session = _session(result_value=None)
    req = UpdateGrantRequest(permission="write")
    with pytest.raises(HTTPException) as exc_info:
        await update_grant(grant_id=9999, req=req, session=session, current_user=user)
    assert exc_info.value.status_code == 404
    assert "Grant not found" in exc_info.value.detail


async def test_update_grant_invalid_permission_raises_422():
    user = _user()
    session = _session()
    req = UpdateGrantRequest(permission="owner")
    with pytest.raises(HTTPException) as exc_info:
        await update_grant(grant_id=1, req=req, session=session, current_user=user)
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# revoke_grant  (lines 325-326)
# ---------------------------------------------------------------------------

async def test_revoke_grant_not_found_raises_404():
    user = _user()
    session = _session(result_value=None)
    with pytest.raises(HTTPException) as exc_info:
        await revoke_grant(grant_id=9999, session=session, current_user=user)
    assert exc_info.value.status_code == 404
    assert "Grant not found" in exc_info.value.detail
