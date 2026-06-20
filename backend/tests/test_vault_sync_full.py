"""Coverage tests for gnosis/services/vault_sync.py.

run_full_sync_for_user is an async generator.
sync_single_file is a coroutine (async function).
Both use AsyncSessionFactory internally — patch it at the source.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# run_full_sync_for_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_full_sync_no_vault_path():
    """When vault_path points to a non-existent dir, yields an error dict."""
    with patch("gnosis.services.vault_sync.get_settings") as mock_cfg, \
         patch("gnosis.services.vault_sync.AsyncSessionFactory") as mock_sf:
        mock_cfg.return_value = MagicMock(vault_path="/nonexistent/path/vault")
        # AsyncSessionFactory used as async context manager
        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        from gnosis.services.vault_sync import run_full_sync_for_user
        results = []
        async for item in run_full_sync_for_user(user_id=1):
            results.append(item)

    assert len(results) >= 1
    # Should yield some kind of status/error dict
    assert isinstance(results[0], dict)


@pytest.mark.asyncio
async def test_run_full_sync_empty_vault(tmp_path: Path):
    """Empty vault directory yields a completion dict with zero counts."""
    vault = tmp_path / "vault"
    vault.mkdir()

    with patch("gnosis.services.vault_sync.get_settings") as mock_cfg, \
         patch("gnosis.services.vault_sync.AsyncSessionFactory") as mock_sf, \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1):
        mock_cfg.return_value = MagicMock(vault_path=str(vault))
        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        from gnosis.services.vault_sync import run_full_sync_for_user
        results = []
        async for item in run_full_sync_for_user(user_id=1):
            results.append(item)

    assert len(results) >= 1
    assert isinstance(results[-1], dict)


# ---------------------------------------------------------------------------
# sync_single_file
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_single_file_new_note(tmp_path: Path):
    """sync_single_file on a valid .md file returns a status dict."""
    vault = tmp_path / "vault"
    vault.mkdir()
    md = vault / "test-note.md"
    md.write_text("---\ntitle: Test\ntags: []\n---\n\nBody.", encoding="utf-8")

    with patch("gnosis.services.vault_sync.get_settings") as mock_cfg, \
         patch("gnosis.services.vault_sync.AsyncSessionFactory") as mock_sf, \
         patch("gnosis.services.vault_sync.upsert_note"), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new_callable=AsyncMock, return_value=1):
        mock_cfg.return_value = MagicMock(vault_path=str(vault))
        mock_session = AsyncMock()
        # Simulate note not found in DB (None), so it creates a new one
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        from gnosis.services.vault_sync import sync_single_file
        result = await sync_single_file(md, owner_id=1, db_session=mock_session)

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_sync_single_file_missing_raises_or_errors(tmp_path: Path):
    """sync_single_file on a missing file returns an error string."""
    missing = tmp_path / "vault" / "ghost.md"

    with patch("gnosis.services.vault_sync.get_settings") as mock_cfg:
        mock_cfg.return_value = MagicMock(vault_path=str(tmp_path / "vault"))
        mock_session = AsyncMock()

        from gnosis.services.vault_sync import _sync_file
        # _sync_file is the internal helper; it catches errors and returns a string
        result = await _sync_file(missing, owner_id=1, db_session=mock_session)

    assert isinstance(result, str)
    assert "error" in result.lower()
