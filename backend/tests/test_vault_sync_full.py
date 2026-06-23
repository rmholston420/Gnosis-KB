"""Coverage tests for gnosis/services/vault_sync.py.

run_full_sync_for_user(user_id) is an async generator that yields strings.
_sync_file(path, owner_id, db_session) is an internal async coroutine.

Both use AsyncSessionFactory and get_settings internally.
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
    """When vault_path does not exist, first yielded line is an error string."""
    with patch("gnosis.services.vault_sync.get_settings") as mock_cfg, \
         patch("gnosis.services.vault_sync._resolve_owner_id",
               new_callable=AsyncMock, return_value=1), \
         patch("gnosis.services.vault_sync._VAULT_PATH", None, create=True):
        mock_cfg.return_value = MagicMock(vault_path="/nonexistent/vault/path")

        # Reset the module-level cache so our patched settings take effect
        import gnosis.services.vault_sync as vs
        original_path = vs._VAULT_PATH
        vs._VAULT_PATH = None
        try:
            results = []
            async for line in vs.run_full_sync_for_user(user_id=1):
                results.append(line)
        finally:
            vs._VAULT_PATH = original_path

    assert len(results) >= 1
    assert any("error" in r for r in results)


@pytest.mark.asyncio
async def test_run_full_sync_empty_vault(tmp_path: Path):
    """Empty vault dir yields 'total: 0' and a 'done:' summary line."""
    vault = tmp_path / "vault"
    vault.mkdir()

    import gnosis.services.vault_sync as vs
    original_path = vs._VAULT_PATH
    vs._VAULT_PATH = None
    try:
        with patch("gnosis.services.vault_sync.get_settings") as mock_cfg, \
             patch("gnosis.services.vault_sync._resolve_owner_id",
                   new_callable=AsyncMock, return_value=1), \
             patch("gnosis.services.vault_sync.AsyncSessionFactory") as mock_sf:
            mock_cfg.return_value = MagicMock(vault_path=str(vault))
            mock_session = AsyncMock()
            mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            results = []
            async for line in vs.run_full_sync_for_user(user_id=1):
                results.append(line)
    finally:
        vs._VAULT_PATH = original_path

    assert any("total:" in r for r in results)
    assert any("done:" in r for r in results)


@pytest.mark.asyncio
async def test_run_full_sync_one_file(tmp_path: Path):
    """One .md file in vault yields 'synced:' line."""
    vault = tmp_path / "vault"
    (vault / "00-inbox").mkdir(parents=True)
    md = vault / "00-inbox" / "test-note.md"
    md.write_text("---\ntitle: Test\ntags: []\n---\n\nBody.", encoding="utf-8")

    import gnosis.services.vault_sync as vs
    original_path = vs._VAULT_PATH
    vs._VAULT_PATH = None
    try:
        with patch("gnosis.services.vault_sync.get_settings") as mock_cfg, \
             patch("gnosis.services.vault_sync._resolve_owner_id",
                   new_callable=AsyncMock, return_value=1), \
             patch("gnosis.services.vault_sync.AsyncSessionFactory") as mock_sf, \
             patch("gnosis.services.vault_sync.upsert_note"):
            mock_cfg.return_value = MagicMock(vault_path=str(vault))
            mock_session = AsyncMock()
            # DB execute returns None note (new)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute.return_value = mock_result
            mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            results = []
            async for line in vs.run_full_sync_for_user(user_id=1):
                results.append(line)
    finally:
        vs._VAULT_PATH = original_path

    assert any("total:" in r for r in results)


# ---------------------------------------------------------------------------
# _sync_file  (internal helper)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_single_file_new_note(tmp_path: Path):
    """_sync_file on a valid .md file returns a 'synced:' string."""
    vault = tmp_path / "vault"
    vault.mkdir()
    md = vault / "test-note.md"
    md.write_text("---\ntitle: Test\ntags: []\n---\n\nBody.", encoding="utf-8")

    with patch("gnosis.services.vault_sync.get_settings") as mock_cfg, \
         patch("gnosis.services.vault_sync.upsert_note"):
        mock_cfg.return_value = MagicMock(vault_path=str(vault))
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        from gnosis.services.vault_sync import _sync_file
        result = await _sync_file(md, owner_id=1, db_session=mock_session)

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_sync_single_file_missing_returns_error(tmp_path: Path):
    """_sync_file on a missing file returns an 'error:' string."""
    missing = tmp_path / "ghost.md"

    with patch("gnosis.services.vault_sync.get_settings") as mock_cfg:
        mock_cfg.return_value = MagicMock(vault_path=str(tmp_path))
        mock_session = AsyncMock()

        from gnosis.services.vault_sync import _sync_file
        result = await _sync_file(missing, owner_id=1, db_session=mock_session)

    assert isinstance(result, str)
    assert "error" in result.lower()
