"""Tests for database.py — engine, session factory, init_db."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# get_engine
# ---------------------------------------------------------------------------

def test_get_engine_returns_engine():
    from gnosis import database as db_module
    # Reset so we get a fresh creation path
    original = db_module._engine
    db_module._engine = None
    try:
        engine = db_module.get_engine()
        assert engine is not None
        # Second call returns cached instance
        engine2 = db_module.get_engine()
        assert engine is engine2
    finally:
        db_module._engine = original


# ---------------------------------------------------------------------------
# get_session_factory
# ---------------------------------------------------------------------------

def test_get_session_factory_returns_factory():
    from gnosis import database as db_module
    original = db_module._session_factory
    db_module._session_factory = None
    try:
        factory = db_module.get_session_factory()
        assert factory is not None
        factory2 = db_module.get_session_factory()
        assert factory is factory2
    finally:
        db_module._session_factory = original


# ---------------------------------------------------------------------------
# _AsyncSessionLocalProxy
# ---------------------------------------------------------------------------

def test_async_session_local_proxy_callable():
    from gnosis.database import AsyncSessionLocal
    # __call__ should return something (a session context manager)
    session = AsyncSessionLocal()
    assert session is not None


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_init_db_creates_vault_dirs(tmp_path):
    from gnosis import config

    settings = config.get_settings()
    settings.vault_path = str(tmp_path)

    mock_conn = AsyncMock()
    mock_conn.run_sync = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_engine = MagicMock()
    mock_engine.begin = MagicMock(return_value=mock_ctx)

    with patch("gnosis.database.get_engine", return_value=mock_engine):
        from gnosis.database import init_db
        await init_db()

    # All standard vault folders should have been created
    assert (tmp_path / "00-inbox").exists()
    assert (tmp_path / "10-zettelkasten").exists()
    assert (tmp_path / "50-archive").exists()
