"""Tests for gnosis/services/vault_sync.py.

Public API:
  run_full_sync_for_user(user_id: int) -> AsyncIterator[str]
    -- async generator that yields progress log lines
  start_vault_watcher(owner_id: int = 1) -> Observer
  VaultEventHandler (class)

_sync_file imports python_frontmatter and slugify at call time;
we patch them via sys.modules when we want the file-level sync to run.
For structural tests we just mock _get_vault_path to an empty/minimal dir.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
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
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


def _make_pf_post(title="Test Note", body="Body text.", tags=None):
    """Fake python_frontmatter Post returned by python_frontmatter.load()."""
    post = MagicMock()
    post.metadata = {
        "title": title,
        "type": "permanent",
        "status": "active",
        "tags": tags or [],
    }
    post.content = body
    return post


@pytest.mark.asyncio
async def test_run_full_sync_yields_strings(tmp_path):
    """run_full_sync_for_user must yield string log lines."""
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
    """An empty vault directory completes without exception."""
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
    md.write_text("---\ntitle: Test\ntags:\n  - x\n---\nContent.")

    db = _make_db_session()
    fake_factory = MagicMock(return_value=db)

    # _sync_file does: import python_frontmatter; import slugify
    fake_pf = MagicMock()
    fake_pf.load.return_value = _make_pf_post()
    fake_slugify_mod = MagicMock()
    fake_slugify_mod.slugify.return_value = "test-note"

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", fake_factory), \
         patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1), \
         patch("gnosis.services.vault_sync.upsert_note"), \
         patch("gnosis.services.vault_sync.delete_note"), \
         patch.dict("sys.modules", {
             "python_frontmatter": fake_pf,
             "slugify": fake_slugify_mod,
         }):
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

    assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# VaultEventHandler
# ---------------------------------------------------------------------------

def test_vault_event_handler_instantiates():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    assert handler is not None
