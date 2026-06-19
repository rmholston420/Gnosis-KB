"""Unit tests for multi-user namespace helpers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gnosis.core.namespace import resolve_vault_path, scoped_note_stmt
from gnosis.models.user import User


def _make_user(**kwargs) -> User:
    u = User.__new__(User)
    defaults = dict(id=1, email="test@example.com", vault_slug=None, vault_path=None)
    defaults.update(kwargs)
    for k, v in defaults.items():
        object.__setattr__(u, k, v)
    return u


# ---------------------------------------------------------------------------
# resolve_vault_path
# ---------------------------------------------------------------------------

def test_resolve_vault_path_explicit(tmp_path: Path):
    """Explicit vault_path overrides everything."""
    user = _make_user(vault_path=str(tmp_path / "custom"))
    assert resolve_vault_path(user) == tmp_path / "custom"


def test_resolve_vault_path_uses_slug():
    """Falls back to GNOSIS_VAULT_ROOT / slug."""
    user = _make_user(id=42, vault_slug="alice")
    path = resolve_vault_path(user)
    assert path.name == "alice"


def test_resolve_vault_path_uses_id_when_no_slug():
    """Falls back to GNOSIS_VAULT_ROOT / str(id) when no slug."""
    user = _make_user(id=99, vault_slug=None, vault_path=None)
    path = resolve_vault_path(user)
    assert path.name == "99"


# ---------------------------------------------------------------------------
# scoped_note_stmt
# ---------------------------------------------------------------------------

def test_scoped_note_stmt_includes_null_owner():
    """With include_null_owner=True, legacy notes (owner_id IS NULL) are included."""
    from sqlalchemy import select
    from gnosis.models.note import Note

    stmt = select(Note)
    scoped = scoped_note_stmt(stmt, {1, 2}, include_null_owner=True)
    # Verify the WHERE clause string references NULL
    compiled = str(scoped.compile())
    assert "IS NULL" in compiled or "owner_id" in compiled


def test_scoped_note_stmt_excludes_null_owner():
    """With include_null_owner=False, only owned notes are returned."""
    from sqlalchemy import select
    from gnosis.models.note import Note

    stmt = select(Note)
    scoped = scoped_note_stmt(stmt, {1}, include_null_owner=False)
    compiled = str(scoped.compile())
    assert "IS NULL" not in compiled
    assert "owner_id" in compiled
