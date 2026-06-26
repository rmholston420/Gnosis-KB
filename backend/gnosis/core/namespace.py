"""Namespace helpers for multi-user vault isolation.

All note queries that touch the database MUST go through one of:
  - ``scoped_note_stmt()`` -- returns a Select with owner filter applied
  - ``get_accessible_user_ids()`` -- set of user IDs readable by current_user

This keeps the isolation logic in one place rather than scattered across routers.

Synthetic guest (id=0)
----------------------
When ``AUTH_REQUIRED=false`` and the DB has no real users yet, auth.py
returns a synthetic ``User(id=0)``.  ``get_accessible_owner_ids`` treats
``id=0`` as a signal to return the empty set, and ``scoped_note_stmt``
treats an empty owner_ids as "no filter" (returns all notes).  Together
this makes the app fully usable on a fresh install without any DB seed.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.models.note import Note
from gnosis.models.shared_vault import SharedVaultMember
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

#: Sentinel id used by the synthetic guest returned when AUTH_REQUIRED=false
#: and no real users exist.  Must match the value in gnosis/core/auth.py.
_GUEST_ID = 0


async def get_accessible_owner_ids(
    current_user: User,
    session: AsyncSession,
    target_owner_id: int | None = None,
) -> set[int]:
    """Return the set of user IDs whose notes *current_user* may read.

    Always includes the current user's own ID.
    Also includes any vault where an active SharedVaultMember grant exists.

    If *target_owner_id* is given, additionally verify the current user
    has access to that specific owner's vault (raises ValueError if not).

    Special case
    ------------
    When *current_user* is the synthetic guest (id=0, created when
    AUTH_REQUIRED=false and the DB has no real users), this function returns
    the **empty set** ``set()``.  ``scoped_note_stmt`` treats an empty set as
    "no owner filter" so all notes are visible — correct for local single-user
    mode before any accounts are created.
    """
    # Synthetic guest: skip all DB queries and return empty set so that
    # scoped_note_stmt falls through to the "no filter" branch below.
    if current_user.id == _GUEST_ID:
        return set()

    from gnosis.models.shared_vault import SharedVault  # local to avoid circular

    accessible: set[int] = {current_user.id}

    result = await session.execute(
        select(SharedVault)
        .join(
            SharedVaultMember,
            SharedVaultMember.vault_id == SharedVault.id,
        )
        .where(
            SharedVaultMember.member_id == current_user.id,
        )
    )
    for vault in result.scalars().all():
        accessible.add(vault.owner_id)

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

    Empty *owner_ids* (synthetic guest or unscoped query)
    -------------------------------------------------------
    When *owner_ids* is empty, no owner filter is applied at all — all notes
    are returned regardless of ``owner_id``.  This is the correct behaviour
    for local single-user mode (AUTH_REQUIRED=false, no real users seeded).
    """
    if not owner_ids:
        # No owner filter — return all notes (local single-user mode).
        return base_stmt

    if include_null_owner:
        from sqlalchemy import or_

        return base_stmt.where(
            or_(
                Note.owner_id.in_(owner_ids),
                Note.owner_id.is_(None),
            )
        )
    return base_stmt.where(Note.owner_id.in_(owner_ids))
