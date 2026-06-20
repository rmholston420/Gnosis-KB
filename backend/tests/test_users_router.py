"""Unit tests for gnosis/routers/users.py — no DB, no HTTP client.

Strategy: patch get_session / require_user / get_current_user dependencies
and call the route handler functions directly as async coroutines.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from gnosis.routers.users import (
    UserProfile,
    UpdateMeRequest,
    InviteRequest,
    UpdateGrantRequest,
    CreateUserRequest,
    get_me,
    update_me,
    list_users,
    create_user,
    invite_to_vault,
    update_grant,
    revoke_grant,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(id=1, email="a@b.com", full_name="Alice", vault_slug="alice",
          vault_path=None, vault_display_name=None, is_superuser=False, is_active=True):
    u = MagicMock()
    u.id = id; u.email = email; u.full_name = full_name
    u.vault_slug = vault_slug; u.vault_path = vault_path
    u.vault_display_name = vault_display_name
    u.is_superuser = is_superuser; u.is_active = is_active
    return u


def _session(scalar=None, scalars=None):
    sess = AsyncMock()
    r = MagicMock()
    r.scalar_one_or_none.return_value = scalar
    r.scalars.return_value.all.return_value = scalars or []
    sess.execute = AsyncMock(return_value=r)
    sess.commit = AsyncMock()
    sess.refresh = AsyncMock()
    sess.add = MagicMock()
    return sess


# ---------------------------------------------------------------------------
# UserProfile schema — Pydantic v2 ConfigDict
# ---------------------------------------------------------------------------

def test_user_profile_from_attributes():
    """ConfigDict(from_attributes=True) replaced class Config."""
    u = _user()
    profile = UserProfile.model_validate(u)
    assert profile.email == "a@b.com"
    assert profile.is_superuser is False


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_me_returns_profile():
    u = _user(id=7, email="z@z.com")
    result = await get_me(current_user=u)
    assert result.id == 7
    assert result.email == "z@z.com"


# ---------------------------------------------------------------------------
# PATCH /users/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_me_full_name():
    u = _user()
    sess = _session(scalar=None)  # no slug conflict
    req = UpdateMeRequest(full_name="Bob")
    with patch("gnosis.routers.users.ensure_vault_directory"):
        result = await update_me(req=req, session=sess, current_user=u)
    assert u.full_name == "Bob"
    sess.commit.assert_awaited()


@pytest.mark.asyncio
async def test_update_me_invalid_slug_raises_422():
    u = _user()
    sess = _session()
    req = UpdateMeRequest(vault_slug="AB")
    with pytest.raises(HTTPException) as exc_info:
        await update_me(req=req, session=sess, current_user=u)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_update_me_duplicate_slug_raises_409():
    u = _user(id=1)
    other = _user(id=2, vault_slug="taken")
    sess = _session(scalar=other)
    req = UpdateMeRequest(vault_slug="taken")
    with pytest.raises(HTTPException) as exc_info:
        await update_me(req=req, session=sess, current_user=u)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_update_me_vault_path_non_superuser_raises_403():
    u = _user(is_superuser=False)
    sess = _session()
    req = UpdateMeRequest(vault_path="/tmp/v")
    with pytest.raises(HTTPException) as exc_info:
        await update_me(req=req, session=sess, current_user=u)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_update_me_vault_path_superuser_ok():
    u = _user(is_superuser=True)
    sess = _session(scalar=None)
    req = UpdateMeRequest(vault_path="/data/vault")
    with patch("gnosis.routers.users.ensure_vault_directory"):
        await update_me(req=req, session=sess, current_user=u)
    assert u.vault_path == "/data/vault"


@pytest.mark.asyncio
async def test_update_me_ensure_vault_oserror_is_swallowed():
    u = _user()
    sess = _session(scalar=None)
    req = UpdateMeRequest(full_name="X")
    with patch("gnosis.routers.users.ensure_vault_directory", side_effect=OSError("no perm")):
        result = await update_me(req=req, session=sess, current_user=u)
    assert result is not None  # no raise


# ---------------------------------------------------------------------------
# GET /users/  — superuser only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_users_non_superuser_raises_403():
    u = _user(is_superuser=False)
    with pytest.raises(HTTPException) as exc_info:
        await list_users(page=1, page_size=50, session=_session(), current_user=u)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_list_users_superuser_returns_list():
    u = _user(is_superuser=True)
    users = [_user(id=i) for i in range(3)]
    sess = _session(scalars=users)
    result = await list_users(page=1, page_size=50, session=sess, current_user=u)
    assert "users" in result
    assert len(result["users"]) == 3


# ---------------------------------------------------------------------------
# POST /users/  — superuser only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_user_non_superuser_raises_403():
    u = _user(is_superuser=False)
    req = CreateUserRequest(email="x@x.com", password="password1")
    with pytest.raises(HTTPException) as exc_info:
        await create_user(req=req, session=_session(), current_user=u)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_create_user_duplicate_raises_409():
    u = _user(is_superuser=True)
    req = CreateUserRequest(email="exists@x.com", password="password1")
    sess = _session(scalar=_user(email="exists@x.com"))
    with pytest.raises(HTTPException) as exc_info:
        await create_user(req=req, session=sess, current_user=u)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_create_user_superuser_creates_ok():
    u = _user(is_superuser=True)
    new_user = _user(id=99, email="new@x.com")
    sess = _session(scalar=None)
    sess.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 99) or None)
    req = CreateUserRequest(email="new@x.com", password="password1")
    with patch("gnosis.routers.users.get_password_hash", return_value="hashed"):
        result = await create_user(req=req, session=sess, current_user=u)
    sess.commit.assert_awaited()


# ---------------------------------------------------------------------------
# POST /me/vaults/invite
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invite_invalid_permission_raises_422():
    u = _user(id=1)
    req = InviteRequest(member_email="b@b.com", permission="admin")
    with pytest.raises(HTTPException) as exc_info:
        await invite_to_vault(req=req, session=_session(), current_user=u)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_invite_self_raises_422():
    u = _user(id=1, email="a@b.com")
    req = InviteRequest(member_email="a@b.com", permission="read")
    # session returns the same user (same id)
    sess = _session(scalar=u)
    with pytest.raises(HTTPException) as exc_info:
        await invite_to_vault(req=req, session=sess, current_user=u)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_invite_user_not_found_raises_404():
    u = _user(id=1)
    req = InviteRequest(member_email="ghost@x.com", permission="read")
    sess = _session(scalar=None)
    with pytest.raises(HTTPException) as exc_info:
        await invite_to_vault(req=req, session=sess, current_user=u)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /me/vaults/{grant_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_grant_invalid_permission_raises_422():
    u = _user(id=1)
    req = UpdateGrantRequest(permission="owner")
    with pytest.raises(HTTPException) as exc_info:
        await update_grant(grant_id=1, req=req, session=_session(), current_user=u)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_update_grant_not_found_raises_404():
    u = _user(id=1)
    req = UpdateGrantRequest(permission="write")
    sess = _session(scalar=None)
    with pytest.raises(HTTPException) as exc_info:
        await update_grant(grant_id=99, req=req, session=sess, current_user=u)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_grant_ok():
    u = _user(id=1)
    grant = MagicMock(id=5, owner_id=1, member_id=2,
                      permission="read", is_active=True, accepted_at=None)
    grant.member = MagicMock(email="b@b.com")
    sess = _session(scalar=grant)
    req = UpdateGrantRequest(permission="write")
    result = await update_grant(grant_id=5, req=req, session=sess, current_user=u)
    assert grant.permission == "write"
    sess.commit.assert_awaited()


# ---------------------------------------------------------------------------
# DELETE /me/vaults/{grant_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoke_grant_not_found_raises_404():
    u = _user(id=1)
    sess = _session(scalar=None)
    with pytest.raises(HTTPException) as exc_info:
        await revoke_grant(grant_id=99, session=sess, current_user=u)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_revoke_grant_sets_inactive():
    u = _user(id=1)
    grant = MagicMock(id=3, is_active=True)
    sess = _session(scalar=grant)
    await revoke_grant(grant_id=3, session=sess, current_user=u)
    assert grant.is_active is False
    sess.commit.assert_awaited()
