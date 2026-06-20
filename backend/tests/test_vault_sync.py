"""Tests for gnosis/services/vault_sync.py.

Public API:
  run_full_sync_for_user(user_id: int) -> AsyncIterator[str]
  start_vault_watcher(owner_id: int = 1) -> Observer
  VaultEventHandler (class)

_sync_file imports python_frontmatter and slugify at call-time; the
easiest way to get coverage without a live DB is to patch _sync_file
itself for structural tests and test it directly with deep mocks for
unit tests.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest


def _make_db_session():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    result.scalar_one_or_none.return_value = None
    result.mappings.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


# ---------------------------------------------------------------------------
# run_full_sync_for_user — structural tests (empty vault)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_full_sync_yields_strings(tmp_path):
    from gnosis.services.vault_sync import run_full_sync_for_user
    db = _make_db_session()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=db), \
         patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1):
        lines = [line async for line in run_full_sync_for_user(1)]
    assert all(isinstance(line, str) for line in lines)


@pytest.mark.asyncio
async def test_run_full_sync_empty_vault(tmp_path):
    from gnosis.services.vault_sync import run_full_sync_for_user
    db = _make_db_session()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=db), \
         patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1):
        lines = [line async for line in run_full_sync_for_user(1)]
    # Should yield "total: 0" and a "done:" line
    assert any("total" in line for line in lines)
    assert any("done" in line for line in lines)


@pytest.mark.asyncio
async def test_run_full_sync_missing_vault_yields_error():
    """If the vault path doesn't exist, yields an error line."""
    from gnosis.services.vault_sync import run_full_sync_for_user
    missing = Path("/tmp/nonexistent_vault_abc123")
    with patch("gnosis.services.vault_sync._get_vault_path", return_value=missing), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1):
        lines = [line async for line in run_full_sync_for_user(1)]
    assert any("error" in line for line in lines)


@pytest.mark.asyncio
async def test_run_full_sync_skips_dot_dirs(tmp_path):
    from gnosis.services.vault_sync import run_full_sync_for_user
    hidden = tmp_path / ".obsidian"
    hidden.mkdir()
    (hidden / "config.md").write_text("# hidden")
    db = _make_db_session()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=db), \
         patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1):
        lines = [line async for line in run_full_sync_for_user(1)]
    # The .obsidian file should NOT appear as synced
    assert not any(".obsidian" in line and "synced" in line for line in lines)


@pytest.mark.asyncio
async def test_run_full_sync_with_markdown_file(tmp_path):
    """A vault with one .md file: _sync_file is patched to return a log line."""
    from gnosis.services.vault_sync import run_full_sync_for_user
    md = tmp_path / "test-note.md"
    md.write_text("---\ntitle: Test\n---\nContent.")
    db = _make_db_session()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=db), \
         patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1), \
         patch("gnosis.services.vault_sync._sync_file", new_callable=AsyncMock, return_value="synced: test-note.md"):
        lines = [line async for line in run_full_sync_for_user(1)]
    assert any("synced" in line for line in lines)


@pytest.mark.asyncio
async def test_run_full_sync_exception_in_sync_file_yields_error_line(tmp_path):
    """If _sync_file raises, the generator yields an error line and continues."""
    from gnosis.services.vault_sync import run_full_sync_for_user
    md = tmp_path / "bad-note.md"
    md.write_text("content")
    db = _make_db_session()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=db), \
         patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1), \
         patch("gnosis.services.vault_sync._sync_file", new_callable=AsyncMock, side_effect=RuntimeError("parse failed")):
        lines = [line async for line in run_full_sync_for_user(1)]
    assert any("error" in line for line in lines)


@pytest.mark.asyncio
async def test_run_full_sync_done_line_includes_user_id(tmp_path):
    from gnosis.services.vault_sync import run_full_sync_for_user
    db = _make_db_session()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=db), \
         patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=42):
        lines = [line async for line in run_full_sync_for_user(42)]
    assert any("42" in line for line in lines)


# ---------------------------------------------------------------------------
# VaultEventHandler
# ---------------------------------------------------------------------------

def test_vault_event_handler_instantiates():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    assert handler is not None
    assert handler._owner_id == 1


def test_vault_event_handler_ignores_directories():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    evt = MagicMock()
    evt.is_directory = True
    evt.src_path = "/vault/some_dir"
    # Should not dispatch anything
    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_created(evt)
        mock_dispatch.assert_not_called()


def test_vault_event_handler_ignores_non_md_files():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    evt = MagicMock()
    evt.is_directory = False
    evt.src_path = "/vault/image.png"
    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_created(evt)
        mock_dispatch.assert_not_called()


def test_vault_event_handler_dispatches_on_md_created():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    evt = MagicMock()
    evt.is_directory = False
    evt.src_path = "/vault/note.md"
    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_created(evt)
        mock_dispatch.assert_called_once()


def test_vault_event_handler_dispatches_on_md_modified():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    evt = MagicMock()
    evt.is_directory = False
    evt.src_path = "/vault/note.md"
    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_modified(evt)
        mock_dispatch.assert_called_once()


def test_vault_event_handler_dispatches_on_md_deleted():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    evt = MagicMock()
    evt.is_directory = False
    evt.src_path = "/vault/note.md"
    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_deleted(evt)
        mock_dispatch.assert_called_once()
