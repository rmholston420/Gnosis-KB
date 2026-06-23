"""Namespace helpers for multi-user vault isolation.

All note queries that touch the database MUST go through one of:
  - ``scoped_note_stmt()`` — returns a Select with owner filter applied
  - ``get_accessible_user_ids()`` — set of user IDs readable by current_user

This keeps the isolation logic in one place rather than scattered across routers.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.models.note import Note
from gnosis.models.shared_vault import SharedVault
from gnosis.models.user import User

# ---------------------------------------------------------------------------
# Vault path helpers
# ---------------------------------------------------------------------------

VAULT_ROOT = Path(os.environ.get("GNOSIS_VAULT_ROOT", "/vaults"))


def resolve_vault_path(user: User) -> Path:
    """Return the filesystem path for *user*'s vault root.

    Priority order:
    1. ``user.vault_path`` if explicitly set (absolute path override).
    2. ``GNOSIS_VAULT_ROOT / user.vault_slug`` if slug is set.
    3. ``GNOSIS_VAULT_ROOT / str(user.id)`` as a numeric fallback.
    """
    if user.vault_path:
        return Path(user.vault_path)
    slug = user.vault_slug or str(user.id)
    return VAULT_ROOT / slug


def ensure_vault_directory(user: User) -> Path:
    """Create the vault directory for *user* if it doesn't exist."""
    path = resolve_vault_path(user)
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Query scoping
# ---------------------------------------------------------------------------


async def get_accessible_owner_ids(
    current_user: User,
    session: AsyncSession,
    target_owner_id: int | None = None,
) -> set[int]:
    """Return the set of user IDs whose notes *current_user* may read.

    Always includes the current user's own ID.
    Also includes any vault where an active SharedVault grant exists.

    If *target_owner_id* is given, additionally verify the current user
    has access to that specific owner's vault (raises ValueError if not).
    """
    # Own vault is always accessible
    accessible: set[int] = {current_user.id}

    # Shared vaults this user has been granted access to
    result = await session.execute(
        select(SharedVault).where(
            SharedVault.member_id == current_user.id,
            SharedVault.is_active.is_(True),
            SharedVault.accepted_at.is_not(None),
        )
    )
    for grant in result.scalars().all():
        accessible.add(grant.owner_id)

    if target_owner_id is not None and target_owner_id not in accessible:
        raise ValueError(
            f"User {current_user.id} does not have access to vault owned by {target_owner_id}"
        )

    return accessible


def scoped_note_stmt(
    base_stmt: Select,
    owner_ids: set[int],
    *,
    include_null_owner: bool = True,
) -> Select:
    """Add a WHERE clause to *base_stmt* restricting to *owner_ids*.

    ``include_null_owner=True`` (default) also returns legacy notes where
    ``owner_id`` is NULL so existing data is visible before the migration
    backfill runs.
    """
    if include_null_owner:
        from sqlalchemy import or_

        return base_stmt.where(
            or_(
                Note.owner_id.in_(owner_ids),
                Note.owner_id.is_(None),
            )
        )
    return base_stmt.where(Note.owner_id.in_(owner_ids))
