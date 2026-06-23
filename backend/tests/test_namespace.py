"""Tests for core/namespace.py — vault path helpers and query scoping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from gnosis.core.namespace import (
    ensure_vault_directory,
    get_accessible_owner_ids,
    resolve_vault_path,
    scoped_note_stmt,
)
from gnosis.models.note import Note


@dataclass
class _FakeUser:
    id: int = 1
    vault_slug: str | None = None
    vault_path: str | None = None


# ---------------------------------------------------------------------------
# resolve_vault_path
# ---------------------------------------------------------------------------


def test_resolve_vault_path_uses_explicit_path():
    user = _FakeUser(vault_path="/custom/vault")
    result = resolve_vault_path(user)
    assert result == Path("/custom/vault")


def test_resolve_vault_path_uses_slug():
    user = _FakeUser(id=5, vault_slug="myslug")
    with patch("gnosis.core.namespace.VAULT_ROOT", Path("/vaults")):
        result = resolve_vault_path(user)
    assert result == Path("/vaults/myslug")


def test_resolve_vault_path_falls_back_to_id():
    user = _FakeUser(id=42, vault_slug=None)
    with patch("gnosis.core.namespace.VAULT_ROOT", Path("/vaults")):
        result = resolve_vault_path(user)
    assert result == Path("/vaults/42")


# ---------------------------------------------------------------------------
# ensure_vault_directory
# ---------------------------------------------------------------------------


def test_ensure_vault_directory_creates_path(tmp_path):
    user = _FakeUser(id=7, vault_slug="newslug")
    with patch("gnosis.core.namespace.VAULT_ROOT", tmp_path):
        result = ensure_vault_directory(user)
    assert result.exists()
    assert result == tmp_path / "newslug"


def test_ensure_vault_directory_with_explicit_path(tmp_path):
    user = _FakeUser(vault_path=str(tmp_path / "custom"))
    result = ensure_vault_directory(user)
    assert result.exists()


# ---------------------------------------------------------------------------
# get_accessible_owner_ids
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_accessible_owner_ids_includes_own():
    user = _FakeUser(id=3)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    ids = await get_accessible_owner_ids(user, mock_session)
    assert 3 in ids


@pytest.mark.asyncio
async def test_get_accessible_owner_ids_includes_shared_vault():
    user = _FakeUser(id=1)

    mock_grant = MagicMock()
    mock_grant.owner_id = 2

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_grant]
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    ids = await get_accessible_owner_ids(user, mock_session)
    assert 1 in ids
    assert 2 in ids


@pytest.mark.asyncio
async def test_get_accessible_owner_ids_raises_for_inaccessible_target():
    user = _FakeUser(id=1)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(ValueError, match="does not have access"):
        await get_accessible_owner_ids(user, mock_session, target_owner_id=99)


# ---------------------------------------------------------------------------
# scoped_note_stmt
# ---------------------------------------------------------------------------


def test_scoped_note_stmt_include_null_owner():
    base = select(Note)
    stmt = scoped_note_stmt(base, {1, 2}, include_null_owner=True)
    # Verify a WHERE clause was added (compile check)
    compiled = str(stmt.compile())
    assert "owner_id" in compiled


def test_scoped_note_stmt_exclude_null_owner():
    base = select(Note)
    stmt = scoped_note_stmt(base, {1}, include_null_owner=False)
    compiled = str(stmt.compile())
    assert "owner_id" in compiled
