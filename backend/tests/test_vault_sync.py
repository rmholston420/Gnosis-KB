"""Tests for gnosis.services.vault_sync.

All DB I/O (AsyncSessionFactory), vector store calls, watchdog Observer,
and lazy model imports inside _sync_file are patched out.
No live database, Qdrant, or watchdog required.
"""
from __future__ import annotations

import sys
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
    """Temporary vault directory with one well-formed markdown file."""
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
    vs._VAULT_PATH = None
    yield
    vs._VAULT_PATH = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_post(title="Hello", note_id="2024-01-01-hello", tags=None, body="Body."):
    """Return a mock python_frontmatter post object."""
    post = MagicMock()
    post.metadata = {
        "id": note_id,
        "title": title,
        "type": "permanent",
        "status": "active",
        "tags": tags or ["alpha", "beta"],
    }
    post.content = body
    return post


def _make_db(note_exists=False):
    """Return a fully-mocked async DB session whose execute always works."""
    session = AsyncMock()
    note_mock = None if not note_exists else MagicMock(
        id="2024-01-01-hello", title="Old", body="old",
        note_type="permanent", status="draft",
        vault_path="00-inbox/2024-01-01-hello.md",
        folder="00-inbox", source_url=None,
        word_count=1, owner_id=1, frontmatter={}, is_deleted=False,
    )
    # Every execute() returns a result whose scalar_one_or_none() is None
    # (tags & wikilink target lookups) unless this is the first call (note lookup)
    results = []
    first_result = MagicMock()
    first_result.scalar_one_or_none.return_value = note_mock
    subsequent = MagicMock()
    subsequent.scalar_one_or_none.return_value = None

    call_count = [0]
    async def _execute(*a, **kw):
        call_count[0] += 1
        return first_result if call_count[0] == 1 else subsequent

    session.execute = _execute
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


def _patch_lazy_imports(vault_root, post_obj):
    """Return a context-manager stack that patches every lazy import in _sync_file."""
    import contextlib

    # Fake python_frontmatter
    fake_fm_mod = MagicMock()
    fake_fm_mod.load.return_value = post_obj

    # Fake slugify module  (slugify.slugify(...))
    fake_slugify_mod = MagicMock()
    fake_slugify_mod.slugify.return_value = "hello"

    # Fake Note / Link / Tag / note_tags via their module paths
    fake_note_cls = MagicMock()
    fake_link_cls = MagicMock()
    fake_tag_cls = MagicMock()
    fake_note_tags = MagicMock()
    fake_note_tags.c.note_id = MagicMock()
    fake_note_tags.insert.return_value.values.return_value = MagicMock()

    @contextlib.contextmanager
    def _ctx():
        originals = {}
        injected = {
            "python_frontmatter": fake_fm_mod,
            "slugify": fake_slugify_mod,
        }
        for k, v in injected.items():
            originals[k] = sys.modules.get(k)
            sys.modules[k] = v
        with patch("gnosis.services.vault_sync.get_settings") as s, \
             patch("gnosis.services.vault_sync.upsert_note") as upsert, \
             patch("gnosis.models.note.Note", fake_note_cls), \
             patch("gnosis.models.link.Link", fake_link_cls), \
             patch("gnosis.models.tag.Tag", fake_tag_cls), \
             patch("gnosis.models.tag.note_tags", fake_note_tags):
            s.return_value.vault_path = str(vault_root)
            try:
                yield upsert
            finally:
                for k, orig in originals.items():
                    if orig is None:
                        sys.modules.pop(k, None)
                    else:
                        sys.modules[k] = orig

    return _ctx()


# ---------------------------------------------------------------------------
# _get_vault_path()
# ---------------------------------------------------------------------------

def test_get_vault_path_returns_cached(tmp_path):
    vs._VAULT_PATH = tmp_path
    with patch("gnosis.services.vault_sync.get_settings") as s:
        result = _get_vault_path()
    s.assert_not_called()
    assert result == tmp_path


def test_get_vault_path_lazy_loads_from_settings(tmp_path):
    vs._VAULT_PATH = None
    with patch("gnosis.services.vault_sync.get_settings") as s:
        s.return_value.vault_path = str(tmp_path)
        result = _get_vault_path()
    assert result == tmp_path.resolve()
    assert vs._VAULT_PATH == tmp_path.resolve()


# ---------------------------------------------------------------------------
# _resolve_owner_id()
# ---------------------------------------------------------------------------

def _mock_session_cm(return_value):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_resolve_owner_id_user_found():
    mock_user = MagicMock(id=7)
    with patch("gnosis.services.vault_sync.AsyncSessionFactory",
               return_value=_mock_session_cm(mock_user)):
        assert await _resolve_owner_id(7) == 7


@pytest.mark.asyncio
async def test_resolve_owner_id_user_not_found_returns_arg():
    with patch("gnosis.services.vault_sync.AsyncSessionFactory",
               return_value=_mock_session_cm(None)):
        assert await _resolve_owner_id(99) == 99


# ---------------------------------------------------------------------------
# _sync_file()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_file_new_note_returns_synced(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    db = _make_db(note_exists=False)
    post = _fake_post()
    with _patch_lazy_imports(vault_dir, post) as upsert:
        result = await _sync_file(md, owner_id=1, db_session=db)
    assert result.startswith("synced:")
    upsert.assert_called_once()


@pytest.mark.asyncio
async def test_sync_file_existing_note_updates(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    db = _make_db(note_exists=True)
    post = _fake_post()
    with _patch_lazy_imports(vault_dir, post):
        result = await _sync_file(md, owner_id=1, db_session=db)
    assert result.startswith("synced:")


@pytest.mark.asyncio
async def test_sync_file_parse_error_returns_error_line(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    db = _make_db()
    fake_fm_mod = MagicMock()
    fake_fm_mod.load.side_effect = Exception("yaml error")
    fake_slugify_mod = MagicMock()
    fake_slugify_mod.slugify.return_value = "hello"
    originals = {}
    for k, v in {"python_frontmatter": fake_fm_mod, "slugify": fake_slugify_mod}.items():
        originals[k] = sys.modules.get(k)
        sys.modules[k] = v
    try:
        with patch("gnosis.services.vault_sync.get_settings") as s:
            s.return_value.vault_path = str(vault_dir)
            with patch("gnosis.services.vault_sync.upsert_note"):
                result = await _sync_file(md, owner_id=1, db_session=db)
    finally:
        for k, orig in originals.items():
            if orig is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = orig
    assert result.startswith("error:")
    assert "yaml error" in result


@pytest.mark.asyncio
async def test_sync_file_vector_upsert_failure_is_nonfatal(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    db = _make_db()
    post = _fake_post()
    fake_fm_mod = MagicMock()
    fake_fm_mod.load.return_value = post
    fake_slugify_mod = MagicMock()
    fake_slugify_mod.slugify.return_value = "hello"
    originals = {}
    for k, v in {"python_frontmatter": fake_fm_mod, "slugify": fake_slugify_mod}.items():
        originals[k] = sys.modules.get(k)
        sys.modules[k] = v
    try:
        with patch("gnosis.services.vault_sync.get_settings") as s:
            s.return_value.vault_path = str(vault_dir)
            with patch("gnosis.services.vault_sync.upsert_note",
                       side_effect=RuntimeError("qdrant down")):
                result = await _sync_file(md, owner_id=1, db_session=db)
    finally:
        for k, orig in originals.items():
            if orig is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = orig
    assert result.startswith("synced:")


@pytest.mark.asyncio
async def test_sync_file_tags_as_comma_string(tmp_path):
    """Tags as a comma string in frontmatter must be split into a list."""
    md = tmp_path / "note.md"
    md.write_text("---\nid: n1\ntitle: T\n---\nBody.", encoding="utf-8")
    db = _make_db()
    post = MagicMock()
    post.metadata = {"id": "n1", "title": "T", "tags": "foo, bar"}
    post.content = "Body."
    with _patch_lazy_imports(tmp_path, post) as upsert:
        await _sync_file(md, owner_id=1, db_session=db)
    # tags should have been split — verify upsert received a list
    tags_arg = upsert.call_args.args[6]
    assert isinstance(tags_arg, list)
    assert "foo" in tags_arg
    assert "bar" in tags_arg


@pytest.mark.asyncio
async def test_sync_file_path_outside_vault_uses_fallback(tmp_path):
    """A path that can't be made relative to vault_root falls back to str(path)."""
    md = tmp_path / "outside.md"
    md.write_text("---\nid: o1\ntitle: O\n---\nBody.", encoding="utf-8")
    different_root = tmp_path / "other"
    different_root.mkdir()
    db = _make_db()
    post = _fake_post(note_id="o1", title="O", tags=[])
    with _patch_lazy_imports(different_root, post):
        result = await _sync_file(md, owner_id=1, db_session=db)
    # Path fallback: result is either synced or error, but must not crash
    assert result.startswith("synced:") or result.startswith("error:")


# ---------------------------------------------------------------------------
# run_full_sync_for_user()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_sync_yields_total_and_done(vault_dir):
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(vault_dir))), \
         patch("gnosis.services.vault_sync._resolve_owner_id",
               new=AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file",
               new=AsyncMock(return_value="synced: 00-inbox/2024-01-01-hello.md")):
        lines = [line async for line in run_full_sync_for_user(1)]
    assert any(l.startswith("total:") for l in lines)
    assert any(l.startswith("done:") for l in lines)


@pytest.mark.asyncio
async def test_full_sync_nonexistent_vault_yields_error(tmp_path):
    ghost = tmp_path / "ghost"
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(ghost))), \
         patch("gnosis.services.vault_sync._resolve_owner_id",
               new=AsyncMock(return_value=1)):
        lines = [line async for line in run_full_sync_for_user(1)]
    assert lines[0].startswith("error: vault path does not exist")


@pytest.mark.asyncio
async def test_full_sync_skips_dotfiles(tmp_path):
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
        lines = [line async for line in run_full_sync_for_user(1)]
    assert any("error:" in l for l in lines)
    assert any(l.startswith("done:") for l in lines)


@pytest.mark.asyncio
async def test_full_sync_count_matches_files(vault_dir):
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(vault_dir))), \
         patch("gnosis.services.vault_sync._resolve_owner_id",
               new=AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file",
               new=AsyncMock(return_value="synced: x")):
        lines = [line async for line in run_full_sync_for_user(1)]
    total_line = next(l for l in lines if l.startswith("total:"))
    # vault_dir fixture has exactly 1 .md file
    assert total_line == "total: 1"


# ---------------------------------------------------------------------------
# VaultEventHandler — event dispatch
# ---------------------------------------------------------------------------

def _evt(src_path, is_directory=False):
    ev = MagicMock()
    ev.src_path = src_path
    ev.is_directory = is_directory
    return ev


def test_on_created_ignores_directory():
    h = VaultEventHandler(owner_id=1)
    h._dispatch_coroutine = MagicMock()
    h.on_created(_evt("/v/dir", is_directory=True))
    h._dispatch_coroutine.assert_not_called()


def test_on_created_ignores_non_md():
    h = VaultEventHandler(owner_id=1)
    h._dispatch_coroutine = MagicMock()
    h.on_created(_evt("/v/note.txt"))
    h._dispatch_coroutine.assert_not_called()


def test_on_created_dispatches_md():
    h = VaultEventHandler(owner_id=1)
    h._dispatch_coroutine = MagicMock()
    h.on_created(_evt("/v/note.md"))
    h._dispatch_coroutine.assert_called_once()


def test_on_modified_dispatches_md():
    h = VaultEventHandler(owner_id=1)
    h._dispatch_coroutine = MagicMock()
    h.on_modified(_evt("/v/note.md"))
    h._dispatch_coroutine.assert_called_once()


def test_on_modified_ignores_directory():
    h = VaultEventHandler(owner_id=1)
    h._dispatch_coroutine = MagicMock()
    h.on_modified(_evt("/v/dir", is_directory=True))
    h._dispatch_coroutine.assert_not_called()


def test_on_deleted_dispatches_md():
    h = VaultEventHandler(owner_id=1)
    h._dispatch_coroutine = MagicMock()
    h.on_deleted(_evt("/v/note.md"))
    h._dispatch_coroutine.assert_called_once()


def test_on_deleted_ignores_directory():
    h = VaultEventHandler(owner_id=1)
    h._dispatch_coroutine = MagicMock()
    h.on_deleted(_evt("/v/dir", is_directory=True))
    h._dispatch_coroutine.assert_not_called()


def test_on_deleted_ignores_non_md():
    h = VaultEventHandler(owner_id=1)
    h._dispatch_coroutine = MagicMock()
    h.on_deleted(_evt("/v/note.txt"))
    h._dispatch_coroutine.assert_not_called()


# ---------------------------------------------------------------------------
# _dispatch_coroutine
# ---------------------------------------------------------------------------

def test_dispatch_loop_running():
    h = VaultEventHandler(owner_id=1)
    coro = AsyncMock()
    loop = MagicMock()
    loop.is_running.return_value = True
    with patch("asyncio.get_event_loop", return_value=loop):
        with patch("asyncio.run_coroutine_threadsafe") as rcts:
            h._dispatch_coroutine(coro)
    rcts.assert_called_once_with(coro, loop)


def test_dispatch_loop_not_running():
    h = VaultEventHandler(owner_id=1)
    coro = AsyncMock()
    loop = MagicMock()
    loop.is_running.return_value = False
    with patch("asyncio.get_event_loop", return_value=loop):
        h._dispatch_coroutine(coro)
    loop.run_until_complete.assert_called_once_with(coro)


def test_dispatch_swallows_runtime_error():
    h = VaultEventHandler(owner_id=1)
    with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
        h._dispatch_coroutine(AsyncMock())  # must not raise


# ---------------------------------------------------------------------------
# _handle_upsert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_upsert_calls_sync_file():
    h = VaultEventHandler(owner_id=1)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        with patch("gnosis.services.vault_sync._sync_file",
                   new=AsyncMock(return_value="synced: x")) as mock_sync:
            await h._handle_upsert(Path("/v/note.md"))
    mock_sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_upsert_swallows_exception():
    h = VaultEventHandler(owner_id=1)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        with patch("gnosis.services.vault_sync._sync_file",
                   new=AsyncMock(side_effect=Exception("boom"))):
            await h._handle_upsert(Path("/v/note.md"))  # must not raise


# ---------------------------------------------------------------------------
# _handle_delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_delete_soft_deletes_note(tmp_path):
    h = VaultEventHandler(owner_id=1)
    md = tmp_path / "note.md"
    mock_note = MagicMock(id="n1", is_deleted=False)
    first_result = MagicMock()
    first_result.scalar_one_or_none.return_value = mock_note
    session = AsyncMock()
    session.execute = AsyncMock(return_value=first_result)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    vs._VAULT_PATH = tmp_path.resolve()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        with patch("gnosis.services.vault_sync.delete_note_vector"):
            await h._handle_delete(md)
    assert mock_note.is_deleted is True
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_handle_delete_noop_when_note_missing(tmp_path):
    h = VaultEventHandler(owner_id=1)
    md = tmp_path / "ghost.md"
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    vs._VAULT_PATH = tmp_path.resolve()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        with patch("gnosis.services.vault_sync.delete_note_vector") as dvec:
            await h._handle_delete(md)
    dvec.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_delete_vector_failure_nonfatal(tmp_path):
    h = VaultEventHandler(owner_id=1)
    md = tmp_path / "note.md"
    mock_note = MagicMock(id="n1", is_deleted=False)
    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_note
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    vs._VAULT_PATH = tmp_path.resolve()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
        with patch("gnosis.services.vault_sync.delete_note_vector",
                   side_effect=RuntimeError("qdrant down")):
            await h._handle_delete(md)  # must not raise
    assert mock_note.is_deleted is True
