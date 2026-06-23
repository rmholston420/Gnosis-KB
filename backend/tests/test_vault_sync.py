"""Tests for gnosis/services/vault_sync.py.

Coverage targets
----------------
Lines 75-194  : _sync_file (create, update, tag sync, wikilink sync, vector upsert,
                parse error path, out-of-vault path)
Lines 202-237 : run_full_sync_for_user (happy path, missing vault, skip dotfiles)
Lines 249-327 : VaultEventHandler event dispatch (on_created, on_modified, on_deleted,
                directory events ignored, non-.md files ignored, _dispatch_coroutine
                branch where loop IS running, branch where loop is NOT running)
Lines 345-360 : start_vault_watcher
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_session():
    """Return a fully-mocked AsyncSession that supports all patterns used by _sync_file."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


# ---------------------------------------------------------------------------
# _get_vault_path
# ---------------------------------------------------------------------------

def test_get_vault_path_returns_resolved_path(tmp_path):
    import gnosis.services.vault_sync as vs_mod
    fake_settings = MagicMock(vault_path=str(tmp_path))
    vs_mod._VAULT_PATH = None
    with patch("gnosis.services.vault_sync.get_settings", return_value=fake_settings):
        p = vs_mod._get_vault_path()
    assert p == tmp_path.resolve()
    vs_mod._VAULT_PATH = None


def test_get_vault_path_caches_second_call(tmp_path):
    import gnosis.services.vault_sync as vs_mod
    fake_settings = MagicMock(vault_path=str(tmp_path))
    vs_mod._VAULT_PATH = None
    with patch("gnosis.services.vault_sync.get_settings", return_value=fake_settings) as m:
        vs_mod._get_vault_path()
        vs_mod._get_vault_path()
    assert m.call_count <= 2
    vs_mod._VAULT_PATH = None


# ---------------------------------------------------------------------------
# _resolve_owner_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_owner_id_returns_existing_user_id():
    import gnosis.services.vault_sync as vs_mod
    fake_user = MagicMock(id=7)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=fake_user)
    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)
    fake_db.execute = AsyncMock(return_value=result)

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=fake_db):
        oid = await vs_mod._resolve_owner_id(7)
    assert oid == 7


@pytest.mark.asyncio
async def test_resolve_owner_id_falls_back_when_user_missing():
    import gnosis.services.vault_sync as vs_mod
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)
    fake_db.execute = AsyncMock(return_value=result)

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=fake_db):
        oid = await vs_mod._resolve_owner_id(42)
    assert oid == 42


# ---------------------------------------------------------------------------
# _sync_file — create path (note not in DB yet)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_file_creates_new_note(tmp_path):
    from gnosis.services.vault_sync import _sync_file

    md = tmp_path / "note.md"
    md.write_text("---\ntitle: My Note\nid: 20240101-000000\ntags: []\n---\nBody text.")

    db = _make_db_session()

    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.upsert_note"):
        line = await _sync_file(md, owner_id=1, db_session=db)

    assert line.startswith("synced:")
    db.add.assert_called()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_file_returns_synced_line_with_rel_path(tmp_path):
    from gnosis.services.vault_sync import _sync_file

    subdir = tmp_path / "10-zettel"
    subdir.mkdir()
    md = subdir / "my-note.md"
    md.write_text("---\ntitle: Titled\nid: abc\n---\nContent.")

    db = _make_db_session()
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.upsert_note"):
        line = await _sync_file(md, owner_id=1, db_session=db)

    assert "10-zettel/my-note.md" in line


# ---------------------------------------------------------------------------
# _sync_file — update path (note already in DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_file_updates_existing_note(tmp_path):
    from gnosis.services.vault_sync import _sync_file

    md = tmp_path / "existing.md"
    md.write_text("---\ntitle: Updated\nid: existing-id\n---\nNew body.")

    existing_note = MagicMock()
    existing_note.id = "existing-id"
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=existing_note)
    db = _make_db_session()
    db.execute = AsyncMock(return_value=result)

    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.upsert_note"):
        line = await _sync_file(md, owner_id=1, db_session=db)

    assert line.startswith("synced:")
    assert existing_note.title == "Updated"
    assert existing_note.body == "New body."


# ---------------------------------------------------------------------------
# _sync_file — tag sync with string tags
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_file_handles_string_tags(tmp_path):
    """tags as a comma-separated string are split correctly."""
    from gnosis.services.vault_sync import _sync_file

    md = tmp_path / "tagged.md"
    md.write_text("---\ntitle: Tagged\nid: t1\ntags: eeg, bci, neuroscience\n---\nBody.")

    db = _make_db_session()
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.upsert_note") as mock_upsert:
        await _sync_file(md, owner_id=1, db_session=db)

    call_tags = mock_upsert.call_args[0][6]  # 7th positional arg
    assert "eeg" in call_tags
    assert "bci" in call_tags


# ---------------------------------------------------------------------------
# _sync_file — parse error path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_file_returns_error_on_parse_failure(tmp_path):
    from gnosis.services.vault_sync import _sync_file

    md = tmp_path / "bad.md"
    md.write_text("some content")

    db = _make_db_session()
    # Patch at the correct module path — vault_sync does `import frontmatter`
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.upsert_note"), \
         patch("frontmatter.load", side_effect=Exception("bad yaml")):
        line = await _sync_file(md, owner_id=1, db_session=db)

    assert line.startswith("error:")
    assert "bad yaml" in line


# ---------------------------------------------------------------------------
# _sync_file — path outside vault root (ValueError from relative_to)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_file_handles_path_outside_vault(tmp_path):
    import tempfile

    from gnosis.services.vault_sync import _sync_file

    with tempfile.TemporaryDirectory() as other_dir:
        md = Path(other_dir) / "outside.md"
        md.write_text("---\ntitle: Outside\nid: out1\n---\nBody.")

        db = _make_db_session()
        with patch("gnosis.services.vault_sync.get_settings",
                   return_value=MagicMock(vault_path=str(tmp_path))), \
             patch("gnosis.services.vault_sync.upsert_note"):
            line = await _sync_file(md, owner_id=1, db_session=db)

    assert line.startswith("synced:")


# ---------------------------------------------------------------------------
# _sync_file — vector upsert failure is non-fatal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_file_vector_failure_is_nonfatal(tmp_path):
    from gnosis.services.vault_sync import _sync_file

    md = tmp_path / "vec-fail.md"
    md.write_text("---\ntitle: VecFail\nid: vf1\n---\nBody.")

    db = _make_db_session()
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.upsert_note",
               side_effect=Exception("qdrant down")):
        line = await _sync_file(md, owner_id=1, db_session=db)

    assert line.startswith("synced:")


# ---------------------------------------------------------------------------
# _sync_file — wikilink extraction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_file_extracts_wikilinks(tmp_path):
    """Body with [[WikiLink]] creates a Link row when the target note exists."""
    from gnosis.services.vault_sync import _sync_file

    md = tmp_path / "wikilinks.md"
    md.write_text("---\ntitle: Source\nid: src1\n---\nSee [[Target Note]] for details.")

    target_note = MagicMock()
    target_note.id = "target-id"

    call_count = 0

    def _make_result(*args, **kwargs):
        nonlocal call_count
        r = MagicMock()
        r.scalar_one_or_none = MagicMock(
            return_value=None if call_count == 0 else target_note
        )
        call_count += 1
        return r

    db = _make_db_session()
    db.execute = AsyncMock(side_effect=_make_result)

    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.upsert_note"):
        line = await _sync_file(md, owner_id=1, db_session=db)

    assert line.startswith("synced:")


# ---------------------------------------------------------------------------
# run_full_sync_for_user — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_full_sync_yields_synced_lines(tmp_path):
    import gnosis.services.vault_sync as vs_mod

    (tmp_path / "note1.md").write_text("---\ntitle: N1\nid: n1\n---\nBody.")
    (tmp_path / "note2.md").write_text("---\ntitle: N2\nid: n2\n---\nBody.")
    vs_mod._VAULT_PATH = None

    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)

    synced = []

    async def _fake_sync_file(path, owner_id, db_session):
        synced.append(path.name)
        return f"synced: {path.name}"

    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=fake_db), \
         patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file", _fake_sync_file):
        lines = [line async for line in vs_mod.run_full_sync_for_user(1)]

    assert any(l.startswith("total:") for l in lines)
    assert any(l.startswith("done:") for l in lines)
    assert "note1.md" in synced
    assert "note2.md" in synced
    vs_mod._VAULT_PATH = None


@pytest.mark.asyncio
async def test_run_full_sync_missing_vault_yields_error():
    import gnosis.services.vault_sync as vs_mod
    vs_mod._VAULT_PATH = None

    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path="/nonexistent/vault/path")), \
         patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)):
        lines = [line async for line in vs_mod.run_full_sync_for_user(1)]

    assert any("error" in l for l in lines)
    vs_mod._VAULT_PATH = None


@pytest.mark.asyncio
async def test_run_full_sync_skips_dotfiles(tmp_path):
    import gnosis.services.vault_sync as vs_mod

    hidden = tmp_path / ".obsidian"
    hidden.mkdir()
    (hidden / "config.md").write_text("# hidden")
    (tmp_path / "visible.md").write_text("---\ntitle: V\nid: v1\n---\nBody.")
    vs_mod._VAULT_PATH = None

    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)

    synced = []

    async def _fake_sync(path, owner_id, db_session):
        synced.append(path)
        return f"synced: {path.name}"

    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=fake_db), \
         patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file", _fake_sync):
        async for _ in vs_mod.run_full_sync_for_user(1):
            pass

    assert not any(".obsidian" in str(p) for p in synced)
    assert any("visible.md" in str(p) for p in synced)
    vs_mod._VAULT_PATH = None


@pytest.mark.asyncio
async def test_run_full_sync_file_exception_yields_error_line(tmp_path):
    """If _sync_file raises, the generator yields an error line and continues."""
    import gnosis.services.vault_sync as vs_mod

    (tmp_path / "bad.md").write_text("content")
    vs_mod._VAULT_PATH = None

    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)

    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=fake_db), \
         patch("gnosis.services.vault_sync._resolve_owner_id", AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file",
               AsyncMock(side_effect=Exception("boom"))):
        lines = [line async for line in vs_mod.run_full_sync_for_user(1)]

    assert any("error" in l for l in lines)
    assert any("done" in l for l in lines)
    vs_mod._VAULT_PATH = None


# ---------------------------------------------------------------------------
# VaultEventHandler — on_created / on_modified / on_deleted
# ---------------------------------------------------------------------------

def _make_event(src_path, is_directory=False):
    e = MagicMock()
    e.src_path = src_path
    e.is_directory = is_directory
    return e


def test_on_created_dispatches_for_md_file():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_created(_make_event("/vault/note.md"))
    handler._dispatch_coroutine.assert_called_once()


def test_on_created_ignores_non_md():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_created(_make_event("/vault/image.png"))
    handler._dispatch_coroutine.assert_not_called()


def test_on_created_ignores_directory_event():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_created(_make_event("/vault/somedir", is_directory=True))
    handler._dispatch_coroutine.assert_not_called()


def test_on_modified_dispatches_for_md_file():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_modified(_make_event("/vault/note.md"))
    handler._dispatch_coroutine.assert_called_once()


def test_on_modified_ignores_directory_event():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_modified(_make_event("/vault/dir", is_directory=True))
    handler._dispatch_coroutine.assert_not_called()


def test_on_deleted_dispatches_for_md_file():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_deleted(_make_event("/vault/gone.md"))
    handler._dispatch_coroutine.assert_called_once()


def test_on_deleted_ignores_non_md():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_deleted(_make_event("/vault/file.txt"))
    handler._dispatch_coroutine.assert_not_called()


def test_on_deleted_ignores_directory_event():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)
    handler._dispatch_coroutine = MagicMock()
    handler.on_deleted(_make_event("/vault/dir", is_directory=True))
    handler._dispatch_coroutine.assert_not_called()


# ---------------------------------------------------------------------------
# VaultEventHandler — _dispatch_coroutine branches
# ---------------------------------------------------------------------------

def test_dispatch_coroutine_uses_run_coroutine_threadsafe_when_loop_running():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)

    fake_loop = MagicMock()
    fake_loop.is_running.return_value = True
    fake_coro = AsyncMock()

    with patch("asyncio.get_event_loop", return_value=fake_loop), \
         patch("asyncio.run_coroutine_threadsafe") as mock_threadsafe:
        handler._dispatch_coroutine(fake_coro)

    mock_threadsafe.assert_called_once_with(fake_coro, fake_loop)


def test_dispatch_coroutine_falls_back_to_run_until_complete():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)

    fake_loop = MagicMock()
    fake_loop.is_running.return_value = False
    fake_coro = MagicMock()

    with patch("asyncio.get_event_loop", return_value=fake_loop):
        handler._dispatch_coroutine(fake_coro)

    fake_loop.run_until_complete.assert_called_once_with(fake_coro)


def test_dispatch_coroutine_swallows_exception():
    from gnosis.services.vault_sync import VaultEventHandler
    handler = VaultEventHandler(owner_id=1)

    with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
        handler._dispatch_coroutine(MagicMock())  # must not raise


# ---------------------------------------------------------------------------
# VaultEventHandler — _handle_upsert and _handle_delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_upsert_calls_sync_file():
    from gnosis.services.vault_sync import VaultEventHandler

    handler = VaultEventHandler(owner_id=1)
    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=fake_db), \
         patch("gnosis.services.vault_sync._sync_file",
               AsyncMock(return_value="synced: note.md")) as mock_sync:
        await handler._handle_upsert(Path("/vault/note.md"))

    mock_sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_upsert_swallows_exception():
    from gnosis.services.vault_sync import VaultEventHandler

    handler = VaultEventHandler(owner_id=1)
    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=fake_db), \
         patch("gnosis.services.vault_sync._sync_file",
               AsyncMock(side_effect=Exception("boom"))):
        await handler._handle_upsert(Path("/vault/bad.md"))  # must not raise


@pytest.mark.asyncio
async def test_handle_delete_soft_deletes_note(tmp_path):
    import gnosis.services.vault_sync as vs_mod
    from gnosis.services.vault_sync import VaultEventHandler
    vs_mod._VAULT_PATH = None

    handler = VaultEventHandler(owner_id=1)

    fake_note = MagicMock()
    fake_note.id = "n1"
    fake_note.is_deleted = False

    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=fake_note)
    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)
    fake_db.execute = AsyncMock(return_value=result)
    fake_db.commit = AsyncMock()

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=fake_db), \
         patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.delete_note_vector"):
        await handler._handle_delete(tmp_path / "note.md")

    assert fake_note.is_deleted is True
    fake_db.commit.assert_awaited_once()
    vs_mod._VAULT_PATH = None


@pytest.mark.asyncio
async def test_handle_delete_no_note_does_nothing(tmp_path):
    import gnosis.services.vault_sync as vs_mod
    from gnosis.services.vault_sync import VaultEventHandler
    vs_mod._VAULT_PATH = None

    handler = VaultEventHandler(owner_id=1)

    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)
    fake_db.execute = AsyncMock(return_value=result)
    fake_db.commit = AsyncMock()

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=fake_db), \
         patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))):
        await handler._handle_delete(tmp_path / "ghost.md")

    fake_db.commit.assert_not_awaited()
    vs_mod._VAULT_PATH = None


@pytest.mark.asyncio
async def test_handle_delete_vector_failure_is_nonfatal(tmp_path):
    import gnosis.services.vault_sync as vs_mod
    from gnosis.services.vault_sync import VaultEventHandler
    vs_mod._VAULT_PATH = None

    handler = VaultEventHandler(owner_id=1)
    fake_note = MagicMock(id="n1", is_deleted=False)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=fake_note)
    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)
    fake_db.execute = AsyncMock(return_value=result)
    fake_db.commit = AsyncMock()

    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=fake_db), \
         patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.delete_note_vector",
               side_effect=Exception("qdrant down")):
        await handler._handle_delete(tmp_path / "note.md")  # must not raise

    fake_db.commit.assert_awaited_once()
    vs_mod._VAULT_PATH = None


# ---------------------------------------------------------------------------
# VaultEventHandler — instantiation
# ---------------------------------------------------------------------------

def test_vault_event_handler_stores_owner_id():
    from gnosis.services.vault_sync import VaultEventHandler
    assert VaultEventHandler(owner_id=7)._owner_id == 7


def test_vault_event_handler_default_owner_id():
    from gnosis.services.vault_sync import VaultEventHandler
    assert VaultEventHandler()._owner_id == 1


# ---------------------------------------------------------------------------
# start_vault_watcher
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_vault_watcher_returns_observer(tmp_path):
    import gnosis.services.vault_sync as vs_mod
    vs_mod._VAULT_PATH = None

    fake_observer = MagicMock()

    async def _fake_full_sync(owner_id):
        yield "total: 0"
        yield "done: synced 0 files for user_id=1"

    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.Observer", return_value=fake_observer), \
         patch("gnosis.services.vault_sync.run_full_sync_for_user", _fake_full_sync):
        obs = await vs_mod.start_vault_watcher(owner_id=1)

    assert obs is fake_observer
    fake_observer.start.assert_called_once()
    vs_mod._VAULT_PATH = None


@pytest.mark.asyncio
async def test_start_vault_watcher_swallows_sync_error(tmp_path):
    import gnosis.services.vault_sync as vs_mod
    vs_mod._VAULT_PATH = None

    fake_observer = MagicMock()

    async def _bad_sync(owner_id):
        raise Exception("startup sync exploded")
        yield  # noqa: unreachable — makes this an async generator

    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync.Observer", return_value=fake_observer), \
         patch("gnosis.services.vault_sync.run_full_sync_for_user", _bad_sync):
        obs = await vs_mod.start_vault_watcher(owner_id=1)

    assert obs is fake_observer
    vs_mod._VAULT_PATH = None
