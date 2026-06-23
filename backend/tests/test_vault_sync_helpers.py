"""
Unit tests for vault_sync.py pure-Python helpers.

All I/O (DB, filesystem) is mocked so tests run without a real vault or DB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _get_vault_path (module-level cache)
# ---------------------------------------------------------------------------


def test_get_vault_path_returns_resolved_path(tmp_path):
    from gnosis.services import vault_sync

    vault_sync._VAULT_PATH = None  # reset module cache
    with patch("gnosis.services.vault_sync.get_settings") as mock_settings:
        mock_settings.return_value.vault_path = str(tmp_path)
        result = vault_sync._get_vault_path()

    assert result == tmp_path.resolve()
    vault_sync._VAULT_PATH = None  # clean up


def test_get_vault_path_caches_result(tmp_path):
    from gnosis.services import vault_sync

    vault_sync._VAULT_PATH = None
    with patch("gnosis.services.vault_sync.get_settings") as mock_settings:
        mock_settings.return_value.vault_path = str(tmp_path)
        first = vault_sync._get_vault_path()
        second = vault_sync._get_vault_path()
        assert first is second  # same cached object
        assert mock_settings.call_count == 1  # called only once
    vault_sync._VAULT_PATH = None


# ---------------------------------------------------------------------------
# run_full_sync_for_user — missing vault path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_run_full_sync_missing_vault_yields_error(tmp_path):
    nonexistent = tmp_path / "does_not_exist"

    from gnosis.services import vault_sync

    vault_sync._VAULT_PATH = None

    with (
        patch("gnosis.services.vault_sync.get_settings") as mock_settings,
        patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)),
    ):
        mock_settings.return_value.vault_path = str(nonexistent)
        lines = [line async for line in vault_sync.run_full_sync_for_user(1)]

    assert any("error" in line.lower() for line in lines)
    vault_sync._VAULT_PATH = None


# ---------------------------------------------------------------------------
# run_full_sync_for_user — empty vault (no .md files)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_run_full_sync_empty_vault(tmp_path):
    from gnosis.services import vault_sync

    vault_sync._VAULT_PATH = None

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("gnosis.services.vault_sync.get_settings") as mock_settings,
        patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)),
        patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_db),
    ):
        mock_settings.return_value.vault_path = str(tmp_path)
        lines = [line async for line in vault_sync.run_full_sync_for_user(1)]

    assert any(line.startswith("total: 0") for line in lines)
    assert any(line.startswith("done:") for line in lines)
    vault_sync._VAULT_PATH = None


# ---------------------------------------------------------------------------
# run_full_sync_for_user — filters dot directories
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_run_full_sync_skips_dot_dirs(tmp_path):
    dot_dir = tmp_path / ".obsidian"
    dot_dir.mkdir()
    (dot_dir / "plugin.md").write_text("---\ntitle: hidden\n---\n")

    normal_dir = tmp_path / "notes"
    normal_dir.mkdir()
    (normal_dir / "visible.md").write_text("---\ntitle: Visible\n---\nHello")

    from gnosis.services import vault_sync

    vault_sync._VAULT_PATH = None

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=None)

    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_execute_result)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    with (
        patch("gnosis.services.vault_sync.get_settings") as mock_settings,
        patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)),
        patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_db),
        patch("gnosis.services.vault_sync.upsert_note"),
    ):
        mock_settings.return_value.vault_path = str(tmp_path)
        lines = [line async for line in vault_sync.run_full_sync_for_user(1)]

    # Only 1 md file should be counted (the one in notes/, not .obsidian/)
    total_line = next(l for l in lines if l.startswith("total:"))
    assert total_line == "total: 1"
    vault_sync._VAULT_PATH = None


# ---------------------------------------------------------------------------
# VaultEventHandler — ignores directories and non-.md files
# ---------------------------------------------------------------------------


def test_vault_event_handler_ignores_directories():
    from gnosis.services.vault_sync import VaultEventHandler

    handler = VaultEventHandler(owner_id=1)
    event = MagicMock()
    event.is_directory = True
    event.src_path = "/vault/somedir"

    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_created(event)
        handler.on_modified(event)
        handler.on_deleted(event)

    mock_dispatch.assert_not_called()


def test_vault_event_handler_ignores_non_md():
    from gnosis.services.vault_sync import VaultEventHandler

    handler = VaultEventHandler(owner_id=1)
    event = MagicMock()
    event.is_directory = False
    event.src_path = "/vault/image.png"

    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_created(event)
        handler.on_modified(event)
        handler.on_deleted(event)

    mock_dispatch.assert_not_called()


def test_vault_event_handler_dispatches_md_create():
    from gnosis.services.vault_sync import VaultEventHandler

    handler = VaultEventHandler(owner_id=1)
    event = MagicMock()
    event.is_directory = False
    event.src_path = "/vault/new-note.md"

    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_created(event)

    mock_dispatch.assert_called_once()


def test_vault_event_handler_dispatches_md_delete():
    from gnosis.services.vault_sync import VaultEventHandler

    handler = VaultEventHandler(owner_id=1)
    event = MagicMock()
    event.is_directory = False
    event.src_path = "/vault/old-note.md"

    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_deleted(event)

    mock_dispatch.assert_called_once()


# ---------------------------------------------------------------------------
# VaultEventHandler._dispatch_coroutine — loop not running branch
# ---------------------------------------------------------------------------


def test_dispatch_coroutine_handles_exception_gracefully():
    from gnosis.services.vault_sync import VaultEventHandler

    handler = VaultEventHandler(owner_id=1)

    async def _dummy():
        pass

    # Should not raise even if loop shenanigans occur
    with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
        try:
            handler._dispatch_coroutine(_dummy())
        except Exception:
            pytest.fail("_dispatch_coroutine raised an unexpected exception")
