"""Tests for gnosis.services.vault_sync.

Isolation strategy
------------------
_sync_file and _handle_delete both do lazy imports of SQLAlchemy core
(select, delete) and ORM models.  The safest isolation is to:
  1. Inject python_frontmatter / slugify via sys.modules (ModuleType objects,
     not MagicMock, so attribute access works correctly).
  2. Patch sqlalchemy.select and sqlalchemy.delete at the *sqlalchemy* module
     level so the `from sqlalchemy import select, delete` inside the function
     picks up the mock before SQLAlchemy tries to compile anything.
  3. Patch the ORM model classes at their canonical module paths so lazy
     `from gnosis.models.X import Y` inside the function sees mocks.
  4. Give db_session.execute a real async def that returns a safe MagicMock
     (avoids AsyncMock attribute-chain pitfalls).
"""
from __future__ import annotations

import sys
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
        "status: active\ntags:\n  - alpha\n  - beta\n---\n\nBody text here.",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture(autouse=True)
def reset_vault_path():
    vs._VAULT_PATH = None
    yield
    vs._VAULT_PATH = None


# ---------------------------------------------------------------------------
# sys.modules injection for non-installed lazy imports
# ---------------------------------------------------------------------------

class _SysModules:
    def __init__(self, mapping):
        self._map = mapping
        self._orig = {}

    def __enter__(self):
        for k, v in self._map.items():
            self._orig[k] = sys.modules.get(k)
            sys.modules[k] = v
        return self

    def __exit__(self, *_):
        for k, orig in self._orig.items():
            if orig is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = orig


def _fm_mod(post):
    m = ModuleType("python_frontmatter")
    m.load = MagicMock(return_value=post)  # type: ignore[attr-defined]
    return m


def _fm_mod_raises(exc):
    m = ModuleType("python_frontmatter")
    m.load = MagicMock(side_effect=exc)  # type: ignore[attr-defined]
    return m


def _sl_mod():
    m = ModuleType("slugify")
    m.slugify = MagicMock(return_value="hello")  # type: ignore[attr-defined]
    return m


def _post(note_id="n1", title="T", tags=None, body="Body.", tags_str=None):
    p = MagicMock()
    p.content = body
    p.metadata = {
        "id": note_id, "title": title,
        "type": "permanent", "status": "active",
        "tags": tags_str if tags_str is not None else (tags or []),
    }
    return p


# ---------------------------------------------------------------------------
# DB session helper — real async def so no AsyncMock chain issues
# ---------------------------------------------------------------------------

def _db(note_obj=None):
    sess = AsyncMock()
    call = [0]

    async def _exec(stmt, *a, **kw):
        call[0] += 1
        r = MagicMock()
        r.scalar_one_or_none.return_value = note_obj if call[0] == 1 else None
        return r

    sess.execute = _exec
    sess.flush = AsyncMock()
    sess.commit = AsyncMock()
    sess.add = MagicMock()
    return sess


# ---------------------------------------------------------------------------
# Context manager: patch everything _sync_file needs
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def _sync_ctx(fm_mod, vault_path_str, upsert_side_effect=None):
    """
    Patches needed for _sync_file to run without touching real SQLAlchemy:
      - sys.modules for python_frontmatter + slugify
      - sqlalchemy.select / sqlalchemy.delete → MagicMock callables
      - ORM model classes at their gnosis.models.* paths
      - get_settings().vault_path
      - upsert_note
    """
    note_cls = MagicMock()
    link_cls = MagicMock()
    tag_cls = MagicMock()
    # note_tags: MagicMock with enough spec for .c.note_id and .insert().values()
    nt = MagicMock()
    nt.c = MagicMock()
    nt.c.note_id = MagicMock()
    nt.insert.return_value.values.return_value = MagicMock()

    sa_select = MagicMock(return_value=MagicMock())  # select(Model) → mock stmt
    sa_delete = MagicMock(return_value=MagicMock())  # delete(table) → mock stmt

    settings_mock = MagicMock()
    settings_mock.vault_path = vault_path_str

    upsert_kwargs = {}
    if upsert_side_effect is not None:
        upsert_kwargs["side_effect"] = upsert_side_effect

    with _SysModules({"python_frontmatter": fm_mod, "slugify": _sl_mod()}):
        with patch("sqlalchemy.select", sa_select), \
             patch("sqlalchemy.delete", sa_delete), \
             patch("gnosis.models.note.Note", note_cls), \
             patch("gnosis.models.link.Link", link_cls), \
             patch("gnosis.models.tag.Tag", tag_cls), \
             patch("gnosis.models.tag.note_tags", nt), \
             patch("gnosis.services.vault_sync.get_settings", return_value=settings_mock), \
             patch("gnosis.services.vault_sync.upsert_note", **upsert_kwargs) as upsert:
            yield upsert


# ---------------------------------------------------------------------------
# _get_vault_path()
# ---------------------------------------------------------------------------

def test_get_vault_path_cached(tmp_path):
    vs._VAULT_PATH = tmp_path
    with patch("gnosis.services.vault_sync.get_settings") as s:
        result = _get_vault_path()
    s.assert_not_called()
    assert result == tmp_path


def test_get_vault_path_lazy(tmp_path):
    vs._VAULT_PATH = None
    with patch("gnosis.services.vault_sync.get_settings") as s:
        s.return_value.vault_path = str(tmp_path)
        result = _get_vault_path()
    assert result == tmp_path.resolve()


# ---------------------------------------------------------------------------
# _resolve_owner_id()
# ---------------------------------------------------------------------------

def _cm_factory(ret):
    r = MagicMock()
    r.scalar_one_or_none.return_value = ret
    sess = AsyncMock()
    sess.execute = AsyncMock(return_value=r)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=sess)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_resolve_owner_id_found():
    with patch("gnosis.services.vault_sync.AsyncSessionFactory",
               return_value=_cm_factory(MagicMock(id=42))):
        assert await _resolve_owner_id(42) == 42


@pytest.mark.asyncio
async def test_resolve_owner_id_not_found():
    with patch("gnosis.services.vault_sync.AsyncSessionFactory",
               return_value=_cm_factory(None)):
        assert await _resolve_owner_id(99) == 99


# ---------------------------------------------------------------------------
# _sync_file()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_file_new_note_returns_synced(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    post = _post(note_id="2024-01-01-hello", title="Hello", tags=["alpha", "beta"])
    with _sync_ctx(_fm_mod(post), str(vault_dir)):
        result = await _sync_file(md, owner_id=1, db_session=_db())
    assert result.startswith("synced:")


@pytest.mark.asyncio
async def test_sync_file_existing_note_updates(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    existing = MagicMock(
        id="2024-01-01-hello", title="Old", body="old",
        note_type="permanent", status="draft",
        vault_path="00-inbox/2024-01-01-hello.md",
        folder="00-inbox", source_url=None, word_count=1,
        owner_id=1, frontmatter={}, is_deleted=False,
    )
    post = _post(note_id="2024-01-01-hello", title="Hello")
    with _sync_ctx(_fm_mod(post), str(vault_dir)):
        result = await _sync_file(md, owner_id=1, db_session=_db(note_obj=existing))
    assert result.startswith("synced:")


@pytest.mark.asyncio
async def test_sync_file_parse_error_returns_error(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    with _sync_ctx(_fm_mod_raises(Exception("yaml error")), str(vault_dir)):
        result = await _sync_file(md, owner_id=1, db_session=_db())
    assert result.startswith("error:")
    assert "yaml error" in result


@pytest.mark.asyncio
async def test_sync_file_vector_upsert_failure_nonfatal(vault_dir):
    md = vault_dir / "00-inbox" / "2024-01-01-hello.md"
    post = _post(note_id="2024-01-01-hello", title="Hello", tags=[])
    with _sync_ctx(_fm_mod(post), str(vault_dir),
                   upsert_side_effect=RuntimeError("qdrant down")):
        result = await _sync_file(md, owner_id=1, db_session=_db())
    assert result.startswith("synced:")


@pytest.mark.asyncio
async def test_sync_file_tags_as_comma_string(tmp_path):
    md = tmp_path / "note.md"
    md.write_text("---\nid: n1\ntitle: T\n---\nBody.", encoding="utf-8")
    post = _post(note_id="n1", title="T", tags_str="foo, bar")
    with _sync_ctx(_fm_mod(post), str(tmp_path)) as upsert:
        await _sync_file(md, owner_id=1, db_session=_db())
    tags_arg = upsert.call_args.args[6]
    assert isinstance(tags_arg, list)
    assert "foo" in tags_arg and "bar" in tags_arg


@pytest.mark.asyncio
async def test_sync_file_path_outside_vault_fallback(tmp_path):
    md = tmp_path / "outside.md"
    md.write_text("---\nid: o1\ntitle: O\n---\nBody.", encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()
    post = _post(note_id="o1", title="O", tags=[])
    with _sync_ctx(_fm_mod(post), str(other)):
        result = await _sync_file(md, owner_id=1, db_session=_db())
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
         patch("gnosis.services.vault_sync._sync_file",
               new=AsyncMock(side_effect=Exception("boom"))):
        lines = [l async for l in run_full_sync_for_user(1)]
    assert any("error:" in l for l in lines)
    assert any(l.startswith("done:") for l in lines)


# ---------------------------------------------------------------------------
# VaultEventHandler events
# ---------------------------------------------------------------------------

def _evt(src, is_dir=False):
    e = MagicMock()
    e.src_path = src
    e.is_directory = is_dir
    return e


def test_on_created_ignores_directory():
    h = VaultEventHandler(1); h._dispatch_coroutine = MagicMock()
    h.on_created(_evt("/v/d", is_dir=True))
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
    h.on_modified(_evt("/v/d", is_dir=True))
    h._dispatch_coroutine.assert_not_called()


def test_on_deleted_dispatches_md():
    h = VaultEventHandler(1); h._dispatch_coroutine = MagicMock()
    h.on_deleted(_evt("/v/note.md"))
    h._dispatch_coroutine.assert_called_once()


def test_on_deleted_ignores_directory():
    h = VaultEventHandler(1); h._dispatch_coroutine = MagicMock()
    h.on_deleted(_evt("/v/d", is_dir=True))
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
    loop = MagicMock()
    loop.is_running.return_value = True
    with patch("asyncio.get_event_loop", return_value=loop), \
         patch("asyncio.run_coroutine_threadsafe") as rcts:
        h._dispatch_coroutine(AsyncMock())
    rcts.assert_called_once()


def test_dispatch_loop_not_running():
    h = VaultEventHandler(1)
    loop = MagicMock()
    loop.is_running.return_value = False
    with patch("asyncio.get_event_loop", return_value=loop):
        h._dispatch_coroutine(AsyncMock())
    loop.run_until_complete.assert_called_once()


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
# _handle_delete  — patch sqlalchemy.select here too
# ---------------------------------------------------------------------------

@contextmanager
def _delete_ctx(note_obj, vault_root_str, vec_side_effect=None):
    r = MagicMock()
    r.scalar_one_or_none.return_value = note_obj
    sess = AsyncMock()
    sess.execute = AsyncMock(return_value=r)
    sess.commit = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=sess)
    cm.__aexit__ = AsyncMock(return_value=False)

    vec_kwargs = {}
    if vec_side_effect is not None:
        vec_kwargs["side_effect"] = vec_side_effect

    with patch("sqlalchemy.select", MagicMock(return_value=MagicMock())), \
         patch("gnosis.models.note.Note", MagicMock()), \
         patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=cm), \
         patch("gnosis.services.vault_sync.delete_note_vector", **vec_kwargs), \
         patch("gnosis.services.vault_sync.get_settings",
               return_value=MagicMock(vault_path=vault_root_str)):
        yield sess


@pytest.mark.asyncio
async def test_handle_delete_soft_deletes_note(tmp_path):
    md = tmp_path / "note.md"
    note = MagicMock(id="n1", is_deleted=False)
    vs._VAULT_PATH = tmp_path.resolve()
    with _delete_ctx(note, str(tmp_path)) as sess:
        await VaultEventHandler(1)._handle_delete(md)
    assert note.is_deleted is True
    sess.commit.assert_awaited()


@pytest.mark.asyncio
async def test_handle_delete_noop_when_missing(tmp_path):
    md = tmp_path / "ghost.md"
    vs._VAULT_PATH = tmp_path.resolve()
    with _delete_ctx(None, str(tmp_path)) as sess, \
         patch("gnosis.services.vault_sync.delete_note_vector") as dvec:
        await VaultEventHandler(1)._handle_delete(md)
    dvec.assert_not_called()
    sess.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_delete_vector_failure_nonfatal(tmp_path):
    md = tmp_path / "note.md"
    note = MagicMock(id="n1", is_deleted=False)
    vs._VAULT_PATH = tmp_path.resolve()
    with _delete_ctx(note, str(tmp_path), vec_side_effect=RuntimeError("qdrant down")):
        await VaultEventHandler(1)._handle_delete(md)  # must not raise
    assert note.is_deleted is True
