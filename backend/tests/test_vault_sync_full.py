"""Coverage tests for gnosis/services/vault_sync.py."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _fake_note(note_id="n1", title="T", body="Body"):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.folder = "00-inbox"
    n.owner_id = 1
    n.tags = []
    return n


@pytest.mark.asyncio
async def test_run_full_sync_no_vault_path(tmp_path):
    with patch("gnosis.services.vault_sync.settings") as mock_settings:
        mock_settings.VAULT_PATH = str(tmp_path / "nonexistent")
        from gnosis.services.vault_sync import run_full_sync_for_user

        results = []
        async for chunk in run_full_sync_for_user(user_id=1):
            results.append(chunk)
        assert any(r.get("status") == "error" for r in results)


@pytest.mark.asyncio
async def test_run_full_sync_empty_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(return_value=None),
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    ))
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    with patch("gnosis.services.vault_sync.settings") as mock_settings, \
         patch("gnosis.services.vault_sync.AsyncSessionFactory") as mock_factory:
        mock_settings.VAULT_PATH = str(vault)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

        from gnosis.services.vault_sync import run_full_sync_for_user
        results = []
        async for chunk in run_full_sync_for_user(user_id=1):
            results.append(chunk)


@pytest.mark.asyncio
async def test_sync_single_file_new_note(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("---\ntitle: Test\n---\n# Test\n\nContent here.")

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(return_value=None)
    ))
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.refresh = AsyncMock(side_effect=lambda n: setattr(n, 'id', 'n-new'))

    with patch("gnosis.services.vault_sync.settings") as mock_settings, \
         patch("gnosis.services.vault_sync.upsert_note", new_callable=AsyncMock):
        mock_settings.VAULT_PATH = str(tmp_path)
        from gnosis.services.vault_sync import sync_single_file
        result = await sync_single_file(str(md_file), user_id=1, db=mock_db)
        assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_sync_single_file_missing_raises_or_errors(tmp_path):
    from gnosis.services.vault_sync import sync_single_file
    mock_db = AsyncMock()
    with patch("gnosis.services.vault_sync.settings") as mock_settings:
        mock_settings.VAULT_PATH = str(tmp_path)
        result = await sync_single_file("/nonexistent/path.md", user_id=1, db=mock_db)
        assert result.get("status") in ("error", "skipped")
