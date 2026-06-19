"""
Users Router — /api/v1/users

Endpoints:
  GET  /me                     — Current user profile + vault info
  PATCH /me                    — Update vault slug, display name, vault_path
  GET  /me/vaults              — Vaults shared with the current user
  POST /me/vaults/invite       — Grant another user access to own vault
  DELETE /me/vaults/{grant_id} — Revoke a share grant
  PATCH /me/vaults/{grant_id}  — Change permission level on a grant
  GET  /                       — List all users (superuser only)
  POST /                       — Create a new user (superuser only)
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field

from gnosis.core.auth import get_current_user, get_password_hash, require_user
from gnosis.core.namespace import ensure_vault_directory
from gnosis.database import get_session
from gnosis.models.shared_vault import SharedVault
from gnosis.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,78}[a-z0-9]$")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    id: int
    email: str
    full_name: str | None
    vault_slug: str | None
    vault_path: str | None
    vault_display_name: str | None
    is_superuser: bool

    class Config:
        from_attributes = True


class UpdateMeRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    vault_slug: str | None = Field(default=None, max_length=80)
    vault_display_name: str | None = Field(default=None, max_length=200)
    vault_path: str | None = Field(
        default=None,
        description="Override absolute filesystem path for vault (admin use only)",
    )


class InviteRequest(BaseModel):
    member_email: EmailStr = Field(description="Email of the user to invite")
    permission: str = Field(
        default="read",
        description="'read' or 'write'",
    )


class UpdateGrantRequest(BaseModel):
    permission: str = Field(description="'read' or 'write'")


class SharedVaultGrant(BaseModel):
    id: int
    owner_id: int
    owner_email: str
    owner_vault_display_name: str | None
    member_id: int
    member_email: str
    permission: str
    is_active: bool
    accepted_at: str | None


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    vault_slug: str | None = None
    is_superuser: bool = False


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserProfile, summary="Current user profile")
async def get_me(
    current_user: User = Depends(require_user),
) -> UserProfile:
    return UserProfile.model_validate(current_user)


# ---------------------------------------------------------------------------
# PATCH /users/me
# ---------------------------------------------------------------------------

@router.patch("/me", response_model=UserProfile, summary="Update profile and vault settings")
async def update_me(
    req: UpdateMeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_user),
) -> UserProfile:
    if req.vault_slug is not None:
        slug = req.vault_slug.lower().strip()
        if not _SLUG_RE.match(slug):
            raise HTTPException(
                status_code=422,
                detail="vault_slug must be 3-80 lowercase alphanumeric / dash / underscore characters",
            )
        # Uniqueness check
        existing = await session.execute(
            select(User).where(User.vault_slug == slug, User.id != current_user.id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail=f"Vault slug '{slug}' is already taken")
        current_user.vault_slug = slug

    if req.full_name is not None:
        current_user.full_name = req.full_name

    if req.vault_display_name is not None:
        current_user.vault_display_name = req.vault_display_name

    if req.vault_path is not None:
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=403, detail="Only superusers may set an explicit vault_path"
            )
        current_user.vault_path = req.vault_path

    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)

    # Ensure vault directory exists after slug/path update
    try:
        ensure_vault_directory(current_user)
    except OSError as exc:
        logger.warning("Could not create vault directory: %s", exc)

    return UserProfile.model_validate(current_user)


# ---------------------------------------------------------------------------
# GET /users/me/vaults  — grants current user has received
# ---------------------------------------------------------------------------

@router.get(
    "/me/vaults",
    response_model=list[SharedVaultGrant],
    summary="Vaults shared with the current user",
)
async def list_my_vaults(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_user),
) -> list[SharedVaultGrant]:
    """Return all active vaults this user has been invited to."""
    result = await session.execute(
        select(SharedVault).where(
            SharedVault.member_id == current_user.id,
            SharedVault.is_active.is_(True),
        )
    )
    grants = result.scalars().all()
    return [
        SharedVaultGrant(
            id=g.id,
            owner_id=g.owner_id,
            owner_email=g.owner.email,
            owner_vault_display_name=g.owner.vault_display_name,
            member_id=g.member_id,
            member_email=g.member.email,
            permission=g.permission,
            is_active=g.is_active,
            accepted_at=g.accepted_at.isoformat() if g.accepted_at else None,
        )
        for g in grants
    ]


# ---------------------------------------------------------------------------
# POST /users/me/vaults/invite
# ---------------------------------------------------------------------------

@router.post(
    "/me/vaults/invite",
    response_model=SharedVaultGrant,
    status_code=status.HTTP_201_CREATED,
    summary="Share your vault with another user",
)
async def invite_to_vault(
    req: InviteRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_user),
) -> SharedVaultGrant:
    if req.permission not in ("read", "write"):
        raise HTTPException(status_code=422, detail="permission must be 'read' or 'write'")

    # Resolve invitee
    result = await session.execute(
        select(User).where(User.email == req.member_email, User.is_active.is_(True))
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail=f"No active user with email {req.member_email}")
    if member.id == current_user.id:
        raise HTTPException(status_code=422, detail="You cannot share your vault with yourself")

    # Idempotent upsert
    existing_result = await session.execute(
        select(SharedVault).where(
            SharedVault.owner_id == current_user.id,
            SharedVault.member_id == member.id,
        )
    )
    grant = existing_result.scalar_one_or_none()
    if grant is not None:
        grant.permission = req.permission
        grant.is_active = True
    else:
        grant = SharedVault(
            owner_id=current_user.id,
            member_id=member.id,
            permission=req.permission,
        )
        session.add(grant)

    await session.commit()
    await session.refresh(grant)

    return SharedVaultGrant(
        id=grant.id,
        owner_id=grant.owner_id,
        owner_email=current_user.email,
        owner_vault_display_name=current_user.vault_display_name,
        member_id=grant.member_id,
        member_email=member.email,
        permission=grant.permission,
        is_active=grant.is_active,
        accepted_at=grant.accepted_at.isoformat() if grant.accepted_at else None,
    )


# ---------------------------------------------------------------------------
# PATCH /users/me/vaults/{grant_id}  — change permission
# ---------------------------------------------------------------------------

@router.patch(
    "/me/vaults/{grant_id}",
    response_model=SharedVaultGrant,
    summary="Update permission level on a share grant",
)
async def update_grant(
    grant_id: int,
    req: UpdateGrantRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_user),
) -> SharedVaultGrant:
    if req.permission not in ("read", "write"):
        raise HTTPException(status_code=422, detail="permission must be 'read' or 'write'")

    result = await session.execute(
        select(SharedVault).where(
            SharedVault.id == grant_id,
            SharedVault.owner_id == current_user.id,
        )
    )
    grant = result.scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=404, detail="Grant not found")

    grant.permission = req.permission
    await session.commit()
    await session.refresh(grant)

    return SharedVaultGrant(
        id=grant.id,
        owner_id=grant.owner_id,
        owner_email=current_user.email,
        owner_vault_display_name=current_user.vault_display_name,
        member_id=grant.member_id,
        member_email=grant.member.email,
        permission=grant.permission,
        is_active=grant.is_active,
        accepted_at=grant.accepted_at.isoformat() if grant.accepted_at else None,
    )


# ---------------------------------------------------------------------------
# DELETE /users/me/vaults/{grant_id}  — revoke access
# ---------------------------------------------------------------------------

@router.delete(
    "/me/vaults/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a vault share grant",
)
async def revoke_grant(
    grant_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_user),
) -> None:
    result = await session.execute(
        select(SharedVault).where(
            SharedVault.id == grant_id,
            SharedVault.owner_id == current_user.id,
        )
    )
    grant = result.scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=404, detail="Grant not found")

    grant.is_active = False
    await session.commit()


# ---------------------------------------------------------------------------
# POST /users/me/vaults/{grant_id}/accept  — member accepts invite
# ---------------------------------------------------------------------------

@router.post(
    "/me/vaults/{grant_id}/accept",
    response_model=SharedVaultGrant,
    summary="Accept a vault share invitation",
)
async def accept_invite(
    grant_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_user),
) -> SharedVaultGrant:
    from datetime import datetime, timezone

    result = await session.execute(
        select(SharedVault).where(
            SharedVault.id == grant_id,
            SharedVault.member_id == current_user.id,
            SharedVault.is_active.is_(True),
        )
    )
    grant = result.scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=404, detail="Invite not found")

    grant.accepted_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(grant)

    return SharedVaultGrant(
        id=grant.id,
        owner_id=grant.owner_id,
        owner_email=grant.owner.email,
        owner_vault_display_name=grant.owner.vault_display_name,
        member_id=grant.member_id,
        member_email=grant.member.email,
        permission=grant.permission,
        is_active=grant.is_active,
        accepted_at=grant.accepted_at.isoformat() if grant.accepted_at else None,
    )


# ---------------------------------------------------------------------------
# GET /users  — superuser only
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[UserProfile], summary="List all users (superuser only)")
async def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_user),
) -> list[UserProfile]:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")

    offset = (page - 1) * per_page
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(per_page)
    )
    users = result.scalars().all()
    return [UserProfile.model_validate(u) for u in users]


# ---------------------------------------------------------------------------
# POST /users  — superuser only
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (superuser only)",
)
async def create_user(
    req: CreateUserRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_user),
) -> UserProfile:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")

    existing = await session.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    slug = req.vault_slug or req.email.split("@")[0].lower()
    user = User(
        email=req.email,
        hashed_password=get_password_hash(req.password),
        full_name=req.full_name,
        vault_slug=slug,
        is_superuser=req.is_superuser,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    try:
        ensure_vault_directory(user)
    except OSError as exc:
        logger.warning("Could not create vault directory for new user: %s", exc)

    return UserProfile.model_validate(user)
