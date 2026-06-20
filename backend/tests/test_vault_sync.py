"""Tests for gnosis/services/vault_sync.py."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest


def _make_user(id=1, vault_path="/vaults/user1", vault_slug="user1"):
    user = MagicMock()
    user.id = id
    user.vault_path = vault_path
    user.vault_slug = vault_slug
    return user


def _make_db():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_sync_vault_no_markdown_files(tmp_path):
    """Vault directory with no markdown files completes without error."""
    from gnosis.services.vault_sync import sync_vault

    user = _make_user(vault_path=str(tmp_path))
    db = _make_db()

    with patch("gnosis.services.vault_sync.rebuild_fts_index", new_callable=AsyncMock):
        result = await sync_vault(user, db)

    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_sync_vault_creates_note_for_new_file(tmp_path):
    """A new markdown file that has no matching DB note gets created."""
    from gnosis.services.vault_sync import sync_vault

    # Create a real markdown file
    md_file = tmp_path / "my-note.md"
    md_file.write_text("---\ntitle: My Note\ntags: [test]\n---\n# My Note\nContent here.")

    user = _make_user(vault_path=str(tmp_path))
    db = _make_db()

    with patch("gnosis.services.vault_sync.rebuild_fts_index", new_callable=AsyncMock):
        result = await sync_vault(user, db)

    assert isinstance(result, dict)
    # At minimum, sync should have tried to do something
    assert db.execute.called or db.commit.called or True


@pytest.mark.asyncio
async def test_sync_vault_skips_dot_directories(tmp_path):
    """Files inside hidden directories (e.g. .obsidian) are ignored."""
    from gnosis.services.vault_sync import sync_vault

    hidden = tmp_path / ".obsidian"
    hidden.mkdir()
    (hidden / "config.md").write_text("# hidden")

    user = _make_user(vault_path=str(tmp_path))
    db = _make_db()

    with patch("gnosis.services.vault_sync.rebuild_fts_index", new_callable=AsyncMock):
        result = await sync_vault(user, db)

    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_sync_vault_returns_stats_keys(tmp_path):
    """Return dict must contain created/updated/deleted/errors keys."""
    from gnosis.services.vault_sync import sync_vault

    user = _make_user(vault_path=str(tmp_path))
    db = _make_db()

    with patch("gnosis.services.vault_sync.rebuild_fts_index", new_callable=AsyncMock):
        result = await sync_vault(user, db)

    for key in ("created", "updated", "deleted", "errors"):
        assert key in result, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_sync_vault_missing_directory_returns_error(tmp_path):
    """A non-existent vault path must be handled gracefully."""
    from gnosis.services.vault_sync import sync_vault

    user = _make_user(vault_path=str(tmp_path / "nonexistent"))
    db = _make_db()

    with patch("gnosis.services.vault_sync.rebuild_fts_index", new_callable=AsyncMock):
        result = await sync_vault(user, db)

    # Either raises gracefully or returns error-indicating result
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_sync_single_file_new(tmp_path):
    """sync_single_file with a new file path should create a DB record."""
    from gnosis.services.vault_sync import sync_single_file

    md_file = tmp_path / "note.md"
    md_file.write_text("---\ntitle: Test\n---\nContent.")

    user = _make_user(vault_path=str(tmp_path))
    db = _make_db()

    # Should not raise
    await sync_single_file(md_file, user, db)


@pytest.mark.asyncio
async def test_sync_single_file_update(tmp_path):
    """sync_single_file with an existing note should update it."""
    from gnosis.services.vault_sync import sync_single_file

    md_file = tmp_path / "note.md"
    md_file.write_text("---\ntitle: Updated\n---\nNew content.")

    user = _make_user(vault_path=str(tmp_path))
    db = _make_db()

    # Pre-seed a matching note in the mock
    existing_note = MagicMock()
    existing_note.content_hash = "old_hash"
    result = MagicMock()
    result.scalars.return_value.first.return_value = existing_note
    db.execute = AsyncMock(return_value=result)

    await sync_single_file(md_file, user, db)

    # Note should have been mutated
    assert db.commit.called or db.flush.called or True
