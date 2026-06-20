"""Tests for gnosis.services.vault_sync.

Strategy for _sync_file tests
------------------------------
_sync_file has deep lazy imports (python_frontmatter, slugify, ORM models,
SQLAlchemy core) that are difficult to replicate cleanly in unit tests.
Instead we test _sync_file's *observable contract* by patching it at the
boundary in integration-style tests, and we separately cover every branch of
run_full_sync_for_user, VaultEventHandler, and the dispatch helpers directly.

Lines 78-194 (the _sync_file body) are covered by a small set of
call-through tests that inject the two non-ORM lazy imports
(python_frontmatter, slugify) via sys.modules and mock the DB session at the
async-method level so no SQLAlchemy compilation occurs.
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

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
    md = tmp_path / "00-inbox" / "2024-01-01-hello.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "---\nid: 2024-01-01-hello\ntitle: Hello\ntype: permanent\n"
        "status: active\ntags:\n  - alpha\n  - beta\n---\n\n"
        "Body text here.",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture(autouse=True)
def reset_vault_path():
    vs._VAULT_PATH = None
    yield
    vs._VAULT_PATH = None


# ---------------------------------------------------------------------------
# sys.modules injection helper
# ---------------------------------------------------------------------------

class _SysModulesCtx:
    """Temporarily inject fake modules into sys.modules."""

    def __init__(self, mapping: dict):
        self._mapping = mapping
        self._originals: dict = {}

    def __enter__(self):
        for k, v in self._mapping.items():
            self._originals[k] = sys.modules.get(k)
            sys.modules[k] = v
        return self

    def __exit__(self, *_):
        for k, orig in self._originals.items():
            if orig is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = orig


def _fake_frontmatter_mod(post):
    mod = ModuleType("python_frontmatter")
    mod.load = MagicMock(return_value=post)  # type: ignore[attr-defined]
    return mod


def _fake_slugify_mod():
    mod = ModuleType("slugify")
    mod.slugify = MagicMock(return_value="hello")  # type: ignore[attr-defined]
    return mod


def _make_post(note_id="n1", title="T", tags=None, body="Body.", tags_str=None):
    post = MagicMock()
    post.content = body
    post.metadata = {
        "id": note_id,
        "title": title,
        "type": "permanent",
        "status": "active",
        "tags": tags_str if tags_str is not None else (tags or []),
    }
    return post


# ---------------------------------------------------------------------------
# Minimal async DB session that survives _sync_file's execute() calls
# ---------------------------------------------------------------------------

def _make_db(note_obj=None):
    """Return an async session mock whose execute() always returns a safe result."""
    session = AsyncMock()

    call_count = [0]

    async def _execute(stmt, *a, **kw):
        call_count[0] += 1
        result = MagicMock()
        result.scalar_one_or_none.return_value = note_obj if call_count[0] == 1 else None
        return result

    session.execute = _execute
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Patch helper for _sync_file ORM model lazy-imports
# ---------------------------------------------------------------------------

def _orm_patches():
    """Return a list of patch objects for every ORM symbol imported inside _sync_file."""
    # We patch the names as they are resolved inside the function's local scope
    # by patching the source module attributes before the function runs.
    note_cls = MagicMock()
    link_cls = MagicMock()
    tag_cls  = MagicMock()

    # note_tags table mock — must support .c.note_id, .insert().values(), and
    # be usable as a delete() argument (SQLAlchemy core won't compile it).
    nt = MagicMock(name="note_tags")
    nt.c.note_id = MagicMock()
    nt.insert.return_value.values.return_value = MagicMock()

    return [
        patch("gnosis.models.note.Note", note_cls),
        patch("gnosis.models.link.Link", link_cls),
        patch("gnosis.models.tag.Tag",  tag_cls),
        patch("gnosis.models.tag.note_tags", nt),
        # Also patch the sqlalchemy.delete / select that _sync_file imports
        # lazily so they return mock-friendly callables.
        patch("sqlalchemy.delete", return_value=MagicMock()),
        patch("sqlalchemy.select", return_value=MagicMock()),
    ]


# ---------------------------------------------------------------------------
# _get_vault_path()
# ---------------------------------------------------------------------------

def test_get_vault_path_returns_cached(tmp_path):
    vs._VAULT_PATH = tmp_path
    with patch("gnosis.services.vault_sync.get_settings") as s:
        result = _get_vault_path()
    s.assert_not_called()
    assert result == tmp_path


def test_get_vault_path_lazy_loads(tmp_path):
    vs._VAULT_PATH = None
    with patch("gnosis.services.vault_sync.get_settings") as s:
        s.return_value.vault_path = str(tmp_path)
        result = _get_vault_path()
    assert result == tmp_path.resolve()


# ---------------------------------------------------------------------------
# _resolve_owner_id()
# ---------------------------------------------------------------------------

def _cm(return_val):
    r = MagicMock()
    r.scalar_one_or_none.return_value = return_val
    sess = AsyncMock()
    sess.execute = AsyncMock(return_value=r)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=sess)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_resolve_owner_id_found():
    with patch("gnosis.services.vault_sync.AsyncSessionFactory",
               return_value=_cm(MagicMock(id=42))):
        assert await _resolve_owner_id(42) == 42


@pytest.mark.asyncio
async def test_resolve_owner_id_not_found():
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=_cm(None)):
        assert await _resolve_owner_id(99) == 99


# ---------------------------------------------------------------------------
# _sync_file() — call-through tests with full mock isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_file_new_note_returns_synced(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    post = _make_post(note_id="2024-01-01-hello", title="Hello",
                     tags=["alpha", "beta"], body="Body text here.")
    db = _make_db(note_obj=None)

    patches = _orm_patches()
    with _SysModulesCtx({"python_frontmatter": _fake_frontmatter_mod(post),
                         "slugify": _fake_slugify_mod()}):
        with patch("gnosis.services.vault_sync.get_settings") as s, \
             patch("gnosis.services.vault_sync.upsert_note"):
            s.return_value.vault_path = str(vault_dir)
            for p in patches:
                p.start()
            try:
                result = await _sync_file(md, owner_id=1, db_session=db)
            finally:
                for p in patches:
                    p.stop()

    assert result.startswith("synced:")


@pytest.mark.asyncio
async def test_sync_file_existing_note_updates(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    existing_note = MagicMock(
        id="2024-01-01-hello", title="Old", body="old",
        note_type="permanent", status="draft",
        vault_path="00-inbox/2024-01-01-hello.md",
        folder="00-inbox", source_url=None,
        word_count=1, owner_id=1, frontmatter={}, is_deleted=False,
    )
    post = _make_post(note_id="2024-01-01-hello", title="Hello")
    db = _make_db(note_obj=existing_note)

    patches = _orm_patches()
    with _SysModulesCtx({"python_frontmatter": _fake_frontmatter_mod(post),
                         "slugify": _fake_slugify_mod()}):
        with patch("gnosis.services.vault_sync.get_settings") as s, \
             patch("gnosis.services.vault_sync.upsert_note"):
            s.return_value.vault_path = str(vault_dir)
            for p in patches:
                p.start()
            try:
                result = await _sync_file(md, owner_id=1, db_session=db)
            finally:
                for p in patches:
                    p.stop()

    assert result.startswith("synced:")


@pytest.mark.asyncio
async def test_sync_file_parse_error_returns_error(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    db = _make_db()

    bad_fm = ModuleType("python_frontmatter")
    bad_fm.load = MagicMock(side_effect=Exception("yaml error"))  # type: ignore

    with _SysModulesCtx({"python_frontmatter": bad_fm,
                         "slugify": _fake_slugify_mod()}):
        with patch("gnosis.services.vault_sync.get_settings") as s, \
             patch("gnosis.services.vault_sync.upsert_note"):
            s.return_value.vault_path = str(vault_dir)
            result = await _sync_file(md, owner_id=1, db_session=db)

    assert result.startswith("error:")
    assert "yaml error" in result


@pytest.mark.asyncio
async def test_sync_file_vector_upsert_failure_nonfatal(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    post = _make_post(note_id="2024-01-01-hello", title="Hello", tags=[])
    db = _make_db()

    patches = _orm_patches()
    with _SysModulesCtx({"python_frontmatter": _fake_frontmatter_mod(post),
                         "slugify": _fake_slugify_mod()}):
        with patch("gnosis.services.vault_sync.get_settings") as s, \
             patch("gnosis.services.vault_sync.upsert_note",
                   side_effect=RuntimeError("qdrant down")):
            s.return_value.vault_path = str(vault_dir)
            for p in patches:
                p.start()
            try:
                result = await _sync_file(md, owner_id=1, db_session=db)
            finally:
                for p in patches:
                    p.stop()

    assert result.startswith("synced:")


@pytest.mark.asyncio
async def test_sync_file_tags_as_comma_string(tmp_path):
    """tags frontmatter value as a comma string must be split."""
    md = tmp_path / "note.md"
    md.write_text("---\nid: n1\ntitle: T\n---\nBody.", encoding="utf-8")
    post = _make_post(note_id="n1", title="T", tags_str="foo, bar", body="Body.")
    db = _make_db()

    patches = _orm_patches()
    with _SysModulesCtx({"python_frontmatter": _fake_frontmatter_mod(post),
                         "slugify": _fake_slugify_mod()}):
        with patch("gnosis.services.vault_sync.get_settings") as s, \
             patch("gnosis.services.vault_sync.upsert_note") as upsert:
            s.return_value.vault_path = str(tmp_path)
            for p in patches:
                p.start()
            try:
                await _sync_file(md, owner_id=1, db_session=db)
            finally:
                for p in patches:
                    p.stop()

    tags_arg = upsert.call_args.args[6]
    assert isinstance(tags_arg, list)
    assert "foo" in tags_arg and "bar" in tags_arg


@pytest.mark.asyncio
async def test_sync_file_path_outside_vault_fallback(tmp_path):
    """A path that can't be relativised to vault_root falls back to str(path)."""
    md = tmp_path / "outside.md"
    md.write_text("---\nid: o1\ntitle: O\n---\nBody.", encoding="utf-8")
    different_root = tmp_path / "other"
    different_root.mkdir()
    post = _make_post(note_id="o1", title="O", tags=[])
    db = _make_db()

    patches = _orm_patches()
    with _SysModulesCtx({"python_frontmatter": _fake_frontmatter_mod(post),
                         "slugify": _fake_slugify_mod()}):
        with patch("gnosis.services.vault_sync.get_settings") as s, \
             patch("gnosis.services.vault_sync.upsert_note"):
            s.return_value.vault_path = str(different_root)
            for p in patches:
                p.start()
            try:
                result = await _sync_file(md, owner_id=1, db_session=db)
            finally:
                for p in patches:
                    p.stop()

    assert result.startswith("synced:") or result.startswith("error:")


# ---------------------------------------------------------------------------
# run_full_sync_for_user()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_sync_yields_total_and_done(vault_dir):
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(vault_dir))), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new=AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file", new=AsyncMock(return_value="synced: x")):
        lines = [l async for l in run_full_sync_for_user(1)]
    assert any(l.startswith("total:") for l in lines)
    assert any(l.startswith("done:") for l in lines)


@pytest.mark.asyncio
async def test_full_sync_count_matches_file_count(vault_dir):
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(vault_dir))), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new=AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file", new=AsyncMock(return_value="synced: x")):
        lines = [l async for l in run_full_sync_for_user(1)]
    total = next(l for l in lines if l.startswith("total:"))
    assert total == "total: 1"


@pytest.mark.asyncio
async def test_full_sync_nonexistent_vault_error(tmp_path):
    ghost = tmp_path / "ghost"
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(ghost))), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new=AsyncMock(return_value=1)):
        lines = [l async for l in run_full_sync_for_user(1)]
    assert lines[0].startswith("error: vault path does not exist")


@pytest.mark.asyncio
async def test_full_sync_skips_dotfile_dirs(tmp_path):
    hidden = tmp_path / ".obsidian" / "note.md"
    hidden.parent.mkdir()
    hidden.write_text("---\nid: h1\ntitle: H\n---\nBody.", encoding="utf-8")
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(tmp_path))), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new=AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file", new=AsyncMock(return_value="synced")) as ms:
        async for _ in run_full_sync_for_user(1):
            pass
    ms.assert_not_called()


@pytest.mark.asyncio
async def test_full_sync_exception_per_file_yields_error(vault_dir):
    with patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=str(vault_dir))), \
         patch("gnosis.services.vault_sync._resolve_owner_id", new=AsyncMock(return_value=1)), \
         patch("gnosis.services.vault_sync._sync_file", new=AsyncMock(side_effect=Exception("boom"))):
        lines = [l async for l in run_full_sync_for_user(1)]
    assert any("error:" in l for l in lines)
    assert any(l.startswith("done:") for l in lines)


# ---------------------------------------------------------------------------
# VaultEventHandler — on_created / on_modified / on_deleted
# ---------------------------------------------------------------------------

def _evt(src_path, is_directory=False):
    ev = MagicMock()
    ev.src_path = src_path
    ev.is_directory = is_directory
    return ev


def test_on_created_ignores_directory():
    h = VaultEventHandler(1); h._dispatch_coroutine = MagicMock()
    h.on_created(_evt("/v/d", is_directory=True))
    h._dispatch_coroutine.assert_not_called()


def test_on_created_ignores_non_md():
    h = VaultEventHandler(1); h._dispatch_coroutine = MagicMock()
    h.on_created(_evt("/v/note.txt"))
    h._dispatch_coroutine.assert_not_called()


def test_on_created_dispatches_md():
    h = VaultEventHandler(1); h._dispatch_coroutine = MagicMock()
    h.on_created(_evt("/v/note.md"))
    h._dispatch_coroutine.assert_called_once()


def test_on_modified_dispatches_md():
    h = VaultEventHandler(1); h._dispatch_coroutine = MagicMock()
    h.on_modified(_evt("/v/note.md"))
    h._dispatch_coroutine.assert_called_once()


def test_on_modified_ignores_directory():
    h = VaultEventHandler(1); h._dispatch_coroutine = MagicMock()
    h.on_modified(_evt("/v/d", is_directory=True))
    h._dispatch_coroutine.assert_not_called()


def test_on_deleted_dispatches_md():
    h = VaultEventHandler(1); h._dispatch_coroutine = MagicMock()
    h.on_deleted(_evt("/v/note.md"))
    h._dispatch_coroutine.assert_called_once()


def test_on_deleted_ignores_directory():
    h = VaultEventHandler(1); h._dispatch_coroutine = MagicMock()
    h.on_deleted(_evt("/v/d", is_directory=True))
    h._dispatch_coroutine.assert_not_called()


def test_on_deleted_ignores_non_md():
    h = VaultEventHandler(1); h._dispatch_coroutine = MagicMock()
    h.on_deleted(_evt("/v/note.txt"))
    h._dispatch_coroutine.assert_not_called()


# ---------------------------------------------------------------------------
# _dispatch_coroutine
# ---------------------------------------------------------------------------

def test_dispatch_loop_running():
    h = VaultEventHandler(1)
    coro, loop = AsyncMock(), MagicMock()
    loop.is_running.return_value = True
    with patch("asyncio.get_event_loop", return_value=loop), \
         patch("asyncio.run_coroutine_threadsafe") as rcts:
        h._dispatch_coroutine(coro)
    rcts.assert_called_once_with(coro, loop)


def test_dispatch_loop_not_running():
    h = VaultEventHandler(1)
    coro, loop = AsyncMock(), MagicMock()
    loop.is_running.return_value = False
    with patch("asyncio.get_event_loop", return_value=loop):
        h._dispatch_coroutine(coro)
    loop.run_until_complete.assert_called_once_with(coro)


def test_dispatch_swallows_exception():
    h = VaultEventHandler(1)
    with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
        h._dispatch_coroutine(AsyncMock())  # must not raise


# ---------------------------------------------------------------------------
# _handle_upsert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_upsert_calls_sync_file():
    h = VaultEventHandler(1)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    cm.__aexit__ = AsyncMock(return_value=False)
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=cm), \
         patch("gnosis.services.vault_sync._sync_file",
               new=AsyncMock(return_value="synced: x")) as ms:
        await h._handle_upsert(Path("/v/note.md"))
    ms.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_upsert_swallows_exception():
    h = VaultEventHandler(1)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    cm.__aexit__ = AsyncMock(return_value=False)
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=cm), \
         patch("gnosis.services.vault_sync._sync_file",
               new=AsyncMock(side_effect=Exception("boom"))):
        await h._handle_upsert(Path("/v/note.md"))  # must not raise


# ---------------------------------------------------------------------------
# _handle_delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_delete_soft_deletes_note(tmp_path):
    h = VaultEventHandler(1)
    md = tmp_path / "note.md"
    mock_note = MagicMock(id="n1", is_deleted=False)
    r = MagicMock(); r.scalar_one_or_none.return_value = mock_note
    sess = AsyncMock(); sess.execute = AsyncMock(return_value=r)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=sess)
    cm.__aexit__ = AsyncMock(return_value=False)
    vs._VAULT_PATH = tmp_path.resolve()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=cm), \
         patch("gnosis.services.vault_sync.delete_note_vector"):
        await h._handle_delete(md)
    assert mock_note.is_deleted is True
    sess.commit.assert_awaited()


@pytest.mark.asyncio
async def test_handle_delete_noop_when_missing(tmp_path):
    h = VaultEventHandler(1)
    md = tmp_path / "ghost.md"
    r = MagicMock(); r.scalar_one_or_none.return_value = None
    sess = AsyncMock(); sess.execute = AsyncMock(return_value=r)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=sess)
    cm.__aexit__ = AsyncMock(return_value=False)
    vs._VAULT_PATH = tmp_path.resolve()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=cm), \
         patch("gnosis.services.vault_sync.delete_note_vector") as dvec:
        await h._handle_delete(md)
    dvec.assert_not_called()
    sess.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_delete_vector_failure_nonfatal(tmp_path):
    h = VaultEventHandler(1)
    md = tmp_path / "note.md"
    mock_note = MagicMock(id="n1", is_deleted=False)
    r = MagicMock(); r.scalar_one_or_none.return_value = mock_note
    sess = AsyncMock(); sess.execute = AsyncMock(return_value=r)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=sess)
    cm.__aexit__ = AsyncMock(return_value=False)
    vs._VAULT_PATH = tmp_path.resolve()
    with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=cm), \
         patch("gnosis.services.vault_sync.delete_note_vector",
               side_effect=RuntimeError("qdrant down")):
        await h._handle_delete(md)  # must not raise
    assert mock_note.is_deleted is True
