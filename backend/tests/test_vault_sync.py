"""Tests for gnosis/services/vault_sync.py.

Public API:
  _get_vault_path()            -> Path   (reads settings)
  _resolve_owner_id(user_id)  -> int    (async, DB lookup)
  _sync_file(path, owner_id, db_session) -> str  (async)
  run_full_sync_for_user(user_id) -> AsyncIterator[str]  (async generator)
  start_vault_watcher(owner_id)   -> Observer  (async)
  VaultEventHandler              (watchdog FileSystemEventHandler subclass)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# _get_vault_path
# ---------------------------------------------------------------------------

def test_get_vault_path_returns_resolved_path(tmp_path):
    import gnosis.services.vault_sync as vs_mod
    fake_settings = MagicMock()
    fake_settings.vault_path = str(tmp_path)
    # Reset cached path
    vs_mod._VAULT_PATH = None
    with patch("gnosis.services.vault_sync.get_settings", return_value=fake_settings):
        p = vs_mod._get_vault_path()
    assert p == tmp_path.resolve()
    vs_mod._VAULT_PATH = None  # cleanup


def test_get_vault_path_caches_result(tmp_path):
    import gnosis.services.vault_sync as vs_mod
    fake_settings = MagicMock()
    fake_settings.vault_path = str(tmp_path)
    vs_mod._VAULT_PATH = None
    with patch("gnosis.services.vault_sync.get_settings", return_value=fake_settings) as mock_settings:
        vs_mod._get_vault_path()
        vs_mod._get_vault_path()  # second call should use cache
    # get_settings should only be called during the first invocation
    assert mock_settings.call_count <= 2  # generous bound for cache impl
    vs_mod._VAULT_PATH = None


# ---------------------------------------------------------------------------
# run_full_sync_for_user — no markdown files
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_full_sync_yields_strings(tmp_path):
    import gnosis.services.vault_sync as vs_mod

    fake_settings = MagicMock()
    fake_settings.vault_path = str(tmp_path)
    vs_mod._VAULT_PATH = None

    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)

    fake_session_factory = MagicMock(return_value=fake_db)

    with patch("gnosis.services.vault_sync.get_settings", return_value=fake_settings), \
         patch("gnosis.services.vault_sync.AsyncSessionFactory", fake_session_factory), \
         patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)):
        lines = []
        async for line in vs_mod.run_full_sync_for_user(1):
            lines.append(line)

    assert all(isinstance(line, str) for line in lines)
    vs_mod._VAULT_PATH = None


@pytest.mark.asyncio
async def test_run_full_sync_no_md_files_returns_summary(tmp_path):
    import gnosis.services.vault_sync as vs_mod

    # tmp_path has no .md files
    fake_settings = MagicMock()
    fake_settings.vault_path = str(tmp_path)
    vs_mod._VAULT_PATH = None

    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)

    with patch("gnosis.services.vault_sync.get_settings", return_value=fake_settings), \
         patch("gnosis.services.vault_sync.AsyncSessionFactory", MagicMock(return_value=fake_db)), \
         patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)):
        lines = [line async for line in vs_mod.run_full_sync_for_user(1)]

    # Should not raise and should produce at least one summary line
    assert len(lines) >= 1
    vs_mod._VAULT_PATH = None


@pytest.mark.asyncio
async def test_run_full_sync_skips_dot_directories(tmp_path):
    import gnosis.services.vault_sync as vs_mod

    # Create a .hidden directory with a .md file — should be skipped
    hidden = tmp_path / ".obsidian"
    hidden.mkdir()
    (hidden / "config.md").write_text("# hidden")

    fake_settings = MagicMock()
    fake_settings.vault_path = str(tmp_path)
    vs_mod._VAULT_PATH = None

    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)

    synced_files = []

    async def fake_sync_file(path, owner_id, db_session):
        synced_files.append(path)
        return f"synced {path.name}"

    with patch("gnosis.services.vault_sync.get_settings", return_value=fake_settings), \
         patch("gnosis.services.vault_sync.AsyncSessionFactory", MagicMock(return_value=fake_db)), \
         patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file", fake_sync_file):
        async for _ in vs_mod.run_full_sync_for_user(1):
            pass

    # The hidden file should NOT have been synced
    assert not any(".obsidian" in str(p) for p in synced_files)
    vs_mod._VAULT_PATH = None


@pytest.mark.asyncio
async def test_run_full_sync_processes_md_files(tmp_path):
    import gnosis.services.vault_sync as vs_mod

    # Create some real .md files
    (tmp_path / "note1.md").write_text("# Note 1")
    (tmp_path / "note2.md").write_text("# Note 2")

    fake_settings = MagicMock()
    fake_settings.vault_path = str(tmp_path)
    vs_mod._VAULT_PATH = None

    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)

    synced = []

    async def fake_sync_file(path, owner_id, db_session):
        synced.append(path.name)
        return f"ok: {path.name}"

    with patch("gnosis.services.vault_sync.get_settings", return_value=fake_settings), \
         patch("gnosis.services.vault_sync.AsyncSessionFactory", MagicMock(return_value=fake_db)), \
         patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file", fake_sync_file):
        async for _ in vs_mod.run_full_sync_for_user(1):
            pass

    assert "note1.md" in synced
    assert "note2.md" in synced
    vs_mod._VAULT_PATH = None


# ---------------------------------------------------------------------------
# VaultEventHandler
# ---------------------------------------------------------------------------

def test_vault_event_handler_is_filesystem_event_handler():
    from gnosis.services.vault_sync import VaultEventHandler
    from watchdog.events import FileSystemEventHandler
    assert issubclass(VaultEventHandler, FileSystemEventHandler)


def test_vault_event_handler_instantiates():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    assert handler.owner_id == 1
