"""Unit tests for gnosis/services/vault_sync.py.

Avoid importing heavy deps (watchdog, AsyncSessionFactory, DB models).
Focus on:
  - WIKILINK_RE regex
  - _get_vault_path()
  - VaultEventHandler (event dispatch logic, no real loop)
  - run_full_sync_for_user (vault-not-found path)
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# WIKILINK_RE
# ---------------------------------------------------------------------------

def test_wikilink_re_matches_simple_link():
    from gnosis.services.vault_sync import WIKILINK_RE
    assert WIKILINK_RE.findall("See [[My Note]]") == ["My Note"]


def test_wikilink_re_matches_multiple():
    from gnosis.services.vault_sync import WIKILINK_RE
    assert WIKILINK_RE.findall("[[A]] and [[B]]") == ["A", "B"]


def test_wikilink_re_no_match():
    from gnosis.services.vault_sync import WIKILINK_RE
    assert WIKILINK_RE.findall("No wikilinks here.") == []


# ---------------------------------------------------------------------------
# _get_vault_path
# ---------------------------------------------------------------------------

def test_get_vault_path_returns_resolved_path():
    import gnosis.services.vault_sync as vs
    vs._VAULT_PATH = None  # reset cache
    with patch("gnosis.services.vault_sync.get_settings") as mock_settings:
        mock_settings.return_value.vault_path = "/tmp/vault"
        p = vs._get_vault_path()
    assert isinstance(p, Path)
    vs._VAULT_PATH = None  # reset after test


def test_get_vault_path_is_cached():
    import gnosis.services.vault_sync as vs
    vs._VAULT_PATH = Path("/cached")
    p = vs._get_vault_path()
    assert p == Path("/cached")
    vs._VAULT_PATH = None


# ---------------------------------------------------------------------------
# VaultEventHandler — on_created / on_modified / on_deleted routing
# ---------------------------------------------------------------------------

def _fake_event(src_path, is_directory=False):
    ev = MagicMock()
    ev.src_path = src_path
    ev.is_directory = is_directory
    return ev


def test_on_created_ignores_directory():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_created(_fake_event("/vault/dir", is_directory=True))
    mock_dispatch.assert_not_called()


def test_on_created_ignores_non_md_file():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_created(_fake_event("/vault/image.png"))
    mock_dispatch.assert_not_called()


def test_on_created_dispatches_md_file():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_created(_fake_event("/vault/note.md"))
    mock_dispatch.assert_called_once()


def test_on_modified_dispatches_md_file():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_modified(_fake_event("/vault/note.md"))
    mock_dispatch.assert_called_once()


def test_on_deleted_dispatches_md_file():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_deleted(_fake_event("/vault/note.md"))
    mock_dispatch.assert_called_once()


def test_on_deleted_ignores_non_md():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    with patch.object(handler, "_dispatch_coroutine") as mock_dispatch:
        handler.on_deleted(_fake_event("/vault/old.txt"))
    mock_dispatch.assert_not_called()


# ---------------------------------------------------------------------------
# VaultEventHandler._dispatch_coroutine — error swallowing
# ---------------------------------------------------------------------------

def test_dispatch_coroutine_swallows_error():
    """_dispatch_coroutine must not propagate exceptions."""
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)

    async def bad_coro():
        raise RuntimeError("boom")

    # Should not raise
    with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
        handler._dispatch_coroutine(bad_coro())


# ---------------------------------------------------------------------------
# run_full_sync_for_user — vault path missing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_full_sync_yields_error_when_vault_missing():
    from gnosis.services.vault_sync import run_full_sync_for_user
    import gnosis.services.vault_sync as vs

    vs._VAULT_PATH = Path("/nonexistent/vault/xyz")

    with patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)):
        lines = []
        async for line in run_full_sync_for_user(1):
            lines.append(line)

    vs._VAULT_PATH = None
    assert any("error" in line for line in lines)


@pytest.mark.asyncio
async def test_run_full_sync_yields_total_then_done(tmp_path):
    """With a real (empty) vault directory, yields 'total: 0' then 'done:'."""
    from gnosis.services.vault_sync import run_full_sync_for_user
    import gnosis.services.vault_sync as vs

    vs._VAULT_PATH = tmp_path  # empty dir — no .md files

    fake_session = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    with patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=fake_session):
        lines = []
        async for line in run_full_sync_for_user(1):
            lines.append(line)

    vs._VAULT_PATH = None
    assert lines[0] == "total: 0"
    assert lines[-1].startswith("done:")
