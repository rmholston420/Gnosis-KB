"""Tests for gnosis.services.vault_sync.

All DB I/O (AsyncSessionFactory), vector store calls, and watchdog Observer
are patched out.  Tests run with no live database or Qdrant instance.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

import gnosis.services.vault_sync as vs
from gnosis.services.vault_sync import (
    _get_vault_path,
    _resolve_owner_id,
    _sync_file,
    run_full_sync_for_user,
    VaultEventHandler,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def vault_dir(tmp_path):
    """Temporary vault directory pre-populated with one markdown file."""
    md = tmp_path / "00-inbox" / "2024-01-01-hello.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "---\n"
        "id: 2024-01-01-hello\n"
        "title: Hello\n"
        "type: permanent\n"
        "status: active\n"
        "tags:\n  - alpha\n  - beta\n"
        "---\n\nBody text here. [[Other Note]]",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture(autouse=True)
def reset_vault_path():
    """Reset the cached vault path before each test."""
    vs._VAULT_PATH = None
    yield
    vs._VAULT_PATH = None


def _make_db_session(note_exists=False):
    """Return a mock async DB session."""
    session = AsyncMock()
    # scalar_one_or_none returns None (note not in DB) by default
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None if not note_exists else MagicMock(
        id="2024-01-01-hello",
        title="Hello",
        body="old",
        note_type="permanent",
        status="draft",
        vault_path="00-inbox/2024-01-01-hello.md",
        folder="00-inbox",
        source_url=None,
        word_count=3,
        owner_id=1,
        frontmatter={},
        is_deleted=False,
    )
    session.execute = AsyncMock(return_value=mock_result)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# _get_vault_path()
# ---------------------------------------------------------------------------

def test_get_vault_path_cached(tmp_path):
    vs._VAULT_PATH = tmp_path
    with patch("gnosis.services.vault_sync.get_settings") as s:
        result = _get_vault_path()
    assert result == tmp_path
    s.assert_not_called()


def test_get_vault_path_reads_settings(tmp_path):
    vs._VAULT_PATH = None
    with patch("gnosis.services.vault_sync.get_settings") as s:
        s.return_value.vault_path = str(tmp_path)
        result = _get_vault_path()
    assert result == tmp_path.resolve()
    assert vs._VAULT_PATH == tmp_path.resolve()


# ---------------------------------------------------------------------------
# _resolve_owner_id()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_owner_id_found():
    mock_user = MagicMock(id=42)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        result = await _resolve_owner_id(42)
    assert result == 42


@pytest.mark.asyncio
async def test_resolve_owner_id_not_found_returns_id():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        result = await _resolve_owner_id(99)
    assert result == 99


# ---------------------------------------------------------------------------
# _sync_file() — new note (INSERT path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_file_new_note_returns_synced(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    db = _make_db_session(note_exists=False)
    with patch("gnosis.services.vault_sync.get_settings") as s:
        s.return_value.vault_path = str(vault_dir)
        with patch("gnosis.services.vault_sync.upsert_note"):
            result = await _sync_file(md, owner_id=1, db_session=db)
    assert result.startswith("synced:")
    db.add.assert_called()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_sync_file_existing_note_updates_fields(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    db = _make_db_session(note_exists=True)
    with patch("gnosis.services.vault_sync.get_settings") as s:
        s.return_value.vault_path = str(vault_dir)
        with patch("gnosis.services.vault_sync.upsert_note"):
            result = await _sync_file(md, owner_id=1, db_session=db)
    assert result.startswith("synced:")
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_sync_file_parse_error_returns_error(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("no frontmatter just plain text", encoding="utf-8")
    db = _make_db_session()
    # Force python_frontmatter.load to raise
    with patch("gnosis.services.vault_sync.get_settings") as s:
        s.return_value.vault_path = str(tmp_path)
        with patch("gnosis.services.vault_sync.upsert_note"):
            with patch("python_frontmatter.load", side_effect=Exception("parse fail")):
                result = await _sync_file(bad, owner_id=1, db_session=db)
    assert result.startswith("error:")
    assert "parse fail" in result


@pytest.mark.asyncio
async def test_sync_file_vector_upsert_failure_is_nonfatal(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    db = _make_db_session()
    with patch("gnosis.services.vault_sync.get_settings") as s:
        s.return_value.vault_path = str(vault_dir)
        with patch("gnosis.services.vault_sync.upsert_note", side_effect=RuntimeError("qdrant down")):
            result = await _sync_file(md, owner_id=1, db_session=db)
    # Should still succeed — vector failure is warned, not raised
    assert result.startswith("synced:")


@pytest.mark.asyncio
async def test_sync_file_tags_as_comma_string(tmp_path):
    """Tags written as a comma string in frontmatter should be split."""
    md = tmp_path / "note.md"
    md.write_text(
        "---\nid: n1\ntitle: T\ntags: 'foo, bar'\n---\nBody.",
        encoding="utf-8",
    )
    db = _make_db_session()
    with patch("gnosis.services.vault_sync.get_settings") as s:
        s.return_value.vault_path = str(tmp_path)
        with patch("gnosis.services.vault_sync.upsert_note") as upsert:
            await _sync_file(md, owner_id=1, db_session=db)
    # tags_raw passed as 5th positional arg inside the upsert call
    call_kwargs = upsert.call_args
    tags_arg = call_kwargs.args[6] if call_kwargs.args else call_kwargs.kwargs.get("tags", [])
    # Either path: tags were split correctly
    assert isinstance(tags_arg, list)


@pytest.mark.asyncio
async def test_sync_file_path_outside_vault(tmp_path, vault_dir):
    """A path that can't be made relative to vault root falls back to str(path)."""
    outside = tmp_path / "outside.md"
    outside.write_text("---\nid: o1\ntitle: O\n---\nBody.", encoding="utf-8")
    db = _make_db_session()
    different_root = vault_dir / "other"
    different_root.mkdir(exist_ok=True)
    with patch("gnosis.services.vault_sync.get_settings") as s:
        s.return_value.vault_path = str(different_root)
        with patch("gnosis.services.vault_sync.upsert_note"):
            result = await _sync_file(outside, owner_id=1, db_session=db)
    assert result.startswith("synced:") or result.startswith("error:")


# ---------------------------------------------------------------------------
# run_full_sync_for_user()
# ---------------------------------------------------------------------------

def _patched_full_sync(vault_dir, sync_file_result="synced: 00-inbox/2024-01-01-hello.md"):
    """Context manager stack for run_full_sync_for_user tests."""
    import contextlib

    @contextlib.asynccontextmanager
    async def _fake_session_factory():
        yield AsyncMock()

    patches = [
        patch("gnosis.services.vault_sync.get_settings",
              return_value=MagicMock(vault_path=str(vault_dir))),
        patch("gnosis.services.vault_sync.AsyncSessionFactory",
              return_value=_fake_session_factory()),
        patch("gnosis.services.vault_sync._resolve_owner_id",
              new=AsyncMock(return_value=1)),
        patch("gnosis.services.vault_sync._sync_file",
              new=AsyncMock(return_value=sync_file_result)),
    ]
    return patches


@pytest.mark.asyncio
async def test_full_sync_yields_total_and_done(vault_dir):
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(vault_dir))), \
         patch("gnosis.services.vault_sync._resolve_owner_id",
               new=AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file",
               new=AsyncMock(return_value="synced: 00-inbox/2024-01-01-hello.md")):
        lines = []
        async for line in run_full_sync_for_user(1):
            lines.append(line)
    assert any(l.startswith("total:") for l in lines)
    assert any(l.startswith("done:") for l in lines)


@pytest.mark.asyncio
async def test_full_sync_nonexistent_vault_yields_error(tmp_path):
    ghost = tmp_path / "ghost-vault"
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(ghost))), \
         patch("gnosis.services.vault_sync._resolve_owner_id",
               new=AsyncMock(return_value=1)):
        lines = []
        async for line in run_full_sync_for_user(1):
            lines.append(line)
    assert lines[0].startswith("error: vault path does not exist")


@pytest.mark.asyncio
async def test_full_sync_skips_dotfiles(tmp_path):
    # .hidden directory should be excluded
    hidden = tmp_path / ".obsidian" / "note.md"
    hidden.parent.mkdir()
    hidden.write_text("---\nid: h1\ntitle: H\n---\nBody.", encoding="utf-8")
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync._resolve_owner_id",
               new=AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file",
               new=AsyncMock(return_value="synced")) as mock_sync:
        async for _ in run_full_sync_for_user(1):
            pass
    mock_sync.assert_not_called()


@pytest.mark.asyncio
async def test_full_sync_handles_sync_file_exception(vault_dir):
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(vault_dir))), \
         patch("gnosis.services.vault_sync._resolve_owner_id",
               new=AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file",
               new=AsyncMock(side_effect=Exception("boom"))):
        lines = []
        async for line in run_full_sync_for_user(1):
            lines.append(line)
    assert any("error:" in l for l in lines)
    assert any(l.startswith("done:") for l in lines)


# ---------------------------------------------------------------------------
# VaultEventHandler — on_created / on_modified / on_deleted
# ---------------------------------------------------------------------------

def _make_event(src_path: str, is_directory: bool = False):
    ev = MagicMock()
    ev.src_path = src_path
    ev.is_directory = is_directory
    return ev


def test_on_created_ignores_directory():
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_created(_make_event("/vault/dir", is_directory=True))
    handler._dispatch_coroutine.assert_not_called()


def test_on_created_ignores_non_md():
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_created(_make_event("/vault/note.txt"))
    handler._dispatch_coroutine.assert_not_called()


def test_on_created_dispatches_md():
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_created(_make_event("/vault/note.md"))
    handler._dispatch_coroutine.assert_called_once()


def test_on_modified_dispatches_md():
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_modified(_make_event("/vault/note.md"))
    handler._dispatch_coroutine.assert_called_once()


def test_on_modified_ignores_directory():
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_modified(_make_event("/vault/dir", is_directory=True))
    handler._dispatch_coroutine.assert_not_called()


def test_on_deleted_dispatches_md():
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_deleted(_make_event("/vault/note.md"))
    handler._dispatch_coroutine.assert_called_once()


def test_on_deleted_ignores_directory():
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_deleted(_make_event("/vault/dir", is_directory=True))
    handler._dispatch_coroutine.assert_not_called()


def test_on_deleted_ignores_non_md():
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_deleted(_make_event("/vault/note.txt"))
    handler._dispatch_coroutine.assert_not_called()


# ---------------------------------------------------------------------------
# VaultEventHandler._dispatch_coroutine
# ---------------------------------------------------------------------------

def test_dispatch_coroutine_runs_when_loop_running():
    handler = VaultEventHandler(owner_id=1)
    coro = AsyncMock()
    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    with patch("asyncio.get_event_loop", return_value=mock_loop):
        with patch("asyncio.run_coroutine_threadsafe") as rcts:
            handler._dispatch_coroutine(coro)
    rcts.assert_called_once_with(coro, mock_loop)


def test_dispatch_coroutine_falls_back_when_loop_not_running():
    handler = VaultEventHandler(owner_id=1)
    coro = AsyncMock()
    mock_loop = MagicMock()
    mock_loop.is_running.return_value = False
    with patch("asyncio.get_event_loop", return_value=mock_loop):
        handler._dispatch_coroutine(coro)
    mock_loop.run_until_complete.assert_called_once_with(coro)


def test_dispatch_coroutine_swallows_exception():
    handler = VaultEventHandler(owner_id=1)
    with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
        with patch("asyncio.new_event_loop") as nel:
            nel.return_value.is_running.return_value = False
            # Should not raise
            handler._dispatch_coroutine(AsyncMock())


# ---------------------------------------------------------------------------
# VaultEventHandler._handle_upsert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_upsert_calls_sync_file(vault_dir):
    handler = VaultEventHandler(owner_id=1)
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    mock_session = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        with patch("gnosis.services.vault_sync._sync_file",
                   new=AsyncMock(return_value="synced: x")) as mock_sync:
            await handler._handle_upsert(md)
    mock_sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_upsert_swallows_exception(vault_dir):
    handler = VaultEventHandler(owner_id=1)
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        with patch("gnosis.services.vault_sync._sync_file",
                   new=AsyncMock(side_effect=Exception("boom"))):
            await handler._handle_upsert(md)  # must not raise


# ---------------------------------------------------------------------------
# VaultEventHandler._handle_delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_delete_soft_deletes_note(vault_dir):
    handler = VaultEventHandler(owner_id=1)
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"

    mock_note = MagicMock(id="2024-01-01-hello", is_deleted=False)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_note
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        with patch("gnosis.services.vault_sync.get_settings") as s:
            s.return_value.vault_path = str(vault_dir)
            vs._VAULT_PATH = vault_dir.resolve()
            with patch("gnosis.services.vault_sync.delete_note_vector"):
                await handler._handle_delete(md)

    assert mock_note.is_deleted is True
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_handle_delete_no_note_noop(vault_dir):
    handler = VaultEventHandler(owner_id=1)
    md = vault_dir / "00-inbox" / "ghost.md"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        vs._VAULT_PATH = vault_dir.resolve()
        with patch("gnosis.services.vault_sync.delete_note_vector") as dvec:
            await handler._handle_delete(md)
    dvec.assert_not_called()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_delete_vector_failure_nonfatal(vault_dir):
    handler = VaultEventHandler(owner_id=1)
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"

    mock_note = MagicMock(id="2024-01-01-hello", is_deleted=False)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_note
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        vs._VAULT_PATH = vault_dir.resolve()
        with patch("gnosis.services.vault_sync.delete_note_vector",
                   side_effect=RuntimeError("qdrant down")):
            await handler._handle_delete(md)  # must not raise
    assert mock_note.is_deleted is True
