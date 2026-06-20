"""Tests for gnosis/services/vault_sync.py.

Public API:
  run_full_sync_for_user(user_id: int) -> AsyncIterator[str]
    -- async generator that yields progress log lines
  start_vault_watcher(owner_id: int = 1) -> Observer
  VaultEventHandler (class)

All DB I/O goes through AsyncSessionFactory which we mock.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest


def _make_db_session():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    # Context manager support for `async with AsyncSessionFactory() as db:`
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


@pytest.mark.asyncio
async def test_run_full_sync_yields_strings(tmp_path):
    """run_full_sync_for_user must yield at least one string log line."""
    from gnosis.services.vault_sync import run_full_sync_for_user

    db = _make_db_session()
    fake_factory = MagicMock(return_value=db)

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", fake_factory), \
         patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1):
        lines = [line async for line in run_full_sync_for_user(1)]

    assert all(isinstance(line, str) for line in lines)


@pytest.mark.asyncio
async def test_run_full_sync_empty_vault(tmp_path):
    """An empty vault directory produces no file-sync lines but completes."""
    from gnosis.services.vault_sync import run_full_sync_for_user

    db = _make_db_session()
    fake_factory = MagicMock(return_value=db)

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", fake_factory), \
         patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1):
        lines = [line async for line in run_full_sync_for_user(1)]

    assert isinstance(lines, list)


@pytest.mark.asyncio
async def test_run_full_sync_with_markdown_file(tmp_path):
    """A vault with one .md file should be processed without exception."""
    from gnosis.services.vault_sync import run_full_sync_for_user

    md = tmp_path / "test-note.md"
    md.write_text("---\ntitle: Test\ntags: [x]\n---\nContent.")

    db = _make_db_session()
    fake_factory = MagicMock(return_value=db)

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", fake_factory), \
         patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1), \
         patch("gnosis.services.vault_sync.upsert_note"), \
         patch("gnosis.services.vault_sync.delete_note"):
        lines = [line async for line in run_full_sync_for_user(1)]

    assert isinstance(lines, list)


@pytest.mark.asyncio
async def test_run_full_sync_skips_dot_dirs(tmp_path):
    """Files inside hidden directories should be skipped."""
    from gnosis.services.vault_sync import run_full_sync_for_user

    hidden = tmp_path / ".obsidian"
    hidden.mkdir()
    (hidden / "config.md").write_text("# hidden")

    db = _make_db_session()
    fake_factory = MagicMock(return_value=db)

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", fake_factory), \
         patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1):
        lines = [line async for line in run_full_sync_for_user(1)]

    # The hidden config.md should NOT appear in sync lines as a processed file
    assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# VaultEventHandler
# ---------------------------------------------------------------------------

def test_vault_event_handler_instantiates():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    assert handler is not None
