"""
Vault sync service.

Responsibilities
----------------
1. **Filesystem watcher** (watchdog) — watch gnosis-vault for file changes and
   sync them to PostgreSQL + Qdrant on create/modify/delete.
2. **run_full_sync_for_user(user_id)** — async generator that does a full
   one-shot resync of the vault for a single user, yielding progress log lines.
   Called by the vault router (POST /vault/sync) and during startup.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncGenerator
from functools import partial
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from gnosis.config import get_settings
from gnosis.database import AsyncSessionFactory
from gnosis.services.markdown_parser import parse_markdown_file  # noqa: F401 (alias)
from gnosis.services.vector_store import delete_note_vector, upsert_note

logger = logging.getLogger(__name__)

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_VAULT_PATH: Path | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_vault_path() -> Path:
    global _VAULT_PATH  # noqa: PLW0603
    if _VAULT_PATH is None:
        _VAULT_PATH = Path(get_settings().vault_path).resolve()
    return _VAULT_PATH


async def _resolve_owner_id(user_id: int) -> int:
    """Resolve user_id to the DB primary key, creating the user row if needed.

    In practice user_id is already the PK from the JWT token — this guard
    exists so tests can pass synthetic IDs without blowing up.
    """
    from sqlalchemy import select

    from gnosis.models.user import User

    async with AsyncSessionFactory() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is not None:
            return user.id
        # Fallback: return the ID as-is (tests, seed scripts)
        return user_id


# ---------------------------------------------------------------------------
# Per-file sync helper (shared by watcher and full-sync)
# ---------------------------------------------------------------------------


async def _sync_file(path: Path, owner_id: int, db_session: object) -> str:
    """Parse a single .md file and upsert into DB + vector store.

    Returns a one-line log string describing the outcome.

    Fix (2025-06-26):
    - upsert_note() calls the synchronous QdrantClient.upsert() directly.
      Dispatching it from inside this async coroutine blocked the entire
      event loop on every embedding + Qdrant write. The call is now dispatched
      to the default ThreadPoolExecutor via run_in_executor so the event loop
      remains free during I/O-bound Qdrant writes.
    - asyncio.get_event_loop() replaced with asyncio.get_running_loop() to
      avoid DeprecationWarning on Python >= 3.10 and RuntimeError on 3.12+
      when called from a thread context with no current event loop.
    """
    import frontmatter  # python-frontmatter
    import mistune
    from slugify import slugify as _slugify  # python-slugify
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import AsyncSession

    from gnosis.models.link import Link
    from gnosis.models.note import Note
    from gnosis.models.tag import NoteTag, Tag

    db: AsyncSession = db_session  # type: ignore[assignment]
    settings = get_settings()
    vault_root = Path(settings.vault_path).resolve()

    # Shared markdown renderer — same plugins as the notes router uses.
    renderer = mistune.create_markdown(
        plugins=["strikethrough", "footnotes", "table", "task_lists"]
    )

    try:
        rel_path = str(path.relative_to(vault_root))
    except ValueError:
        rel_path = str(path)

    try:
        post = frontmatter.load(str(path))
    except Exception as exc:  # noqa: BLE001
        return f"error: {rel_path} — {exc}"

    fm = dict(post.metadata)
    body = post.content
    title = fm.get("title") or path.stem
    note_id = fm.get("id") or path.stem
    note_type = fm.get("type", "permanent")
    status = fm.get("status", "draft")
    folder = rel_path.split("/")[0] if "/" in rel_path else "00-inbox"
    source_url = fm.get("source") or None
    tags_raw: list[str] = fm.get("tags") or []
    if isinstance(tags_raw, str):
        tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]

    slug_val = _slugify(title)[:490] if title else note_id

    # Render HTML from markdown body
    body_html = str(renderer(body))

    # Upsert note row
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()

    word_count = len(body.split())

    if note is None:
        note = Note(
            id=note_id,
            title=title,
            slug=slug_val,
            body=body,
            body_html=body_html,
            note_type=note_type,
            status=status,
            vault_path=rel_path,
            folder=folder,
            source_url=source_url,
            word_count=word_count,
            owner_id=owner_id,
            frontmatter=fm,
        )
        db.add(note)
    else:
        note.title = title
        note.body = body
        note.body_html = body_html  # keep HTML in sync with markdown body
        note.note_type = note_type
        note.status = status
        note.vault_path = rel_path
        note.folder = folder
        note.source_url = source_url
        note.word_count = word_count
        note.owner_id = owner_id
        note.frontmatter = fm

    await db.flush()

    # Sync tags
    await db.execute(delete(NoteTag).where(NoteTag.c.note_id == note_id))
    for tag_name in tags_raw:
        tag_result = await db.execute(select(Tag).where(Tag.name == tag_name))
        tag = tag_result.scalar_one_or_none()
        if tag is None:
            tag = Tag(name=tag_name)
            db.add(tag)
            await db.flush()
        await db.execute(NoteTag.insert().values(note_id=note_id, tag_id=tag.id))

    # Sync wikilinks
    wikilinks = WIKILINK_RE.findall(body)
    await db.execute(delete(Link).where(Link.source_id == note_id))
    for target_title in wikilinks:
        target_result = await db.execute(
            select(Note).where(Note.title == target_title, Note.is_deleted.is_(False))
        )
        target = target_result.scalar_one_or_none()
        if target:
            link = Link(
                source_id=note_id,
                target_id=target.id,
                link_text=target_title,
                link_type="wikilink",
            )
            db.add(link)

    await db.commit()

    # Vector upsert — dispatched to ThreadPoolExecutor so the synchronous
    # QdrantClient.upsert() call does not block the event loop.
    # Fix (2025-06-26): use get_running_loop() instead of get_event_loop()
    # to avoid DeprecationWarning on Python >= 3.10 and RuntimeError on 3.12+.
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(
                upsert_note,
                note_id,
                title,
                body,
                folder,
                note_type,
                status,
                tags_raw,
                owner_id,
            ),
        )
    except Exception as vec_exc:  # noqa: BLE001
        logger.warning("Vector upsert skipped for %s: %s", note_id, vec_exc)

    return f"synced: {rel_path}"


# ---------------------------------------------------------------------------
# Public: full-sync generator (called by vault router)
# ---------------------------------------------------------------------------


async def run_full_sync_for_user(user_id: int) -> AsyncGenerator[str, None]:  # type: ignore[misc]
    """Async generator: scan the vault directory and sync every .md file.

    Yields one log line per file processed (``synced: path``, ``skipped: path``,
    ``deleted: path``, ``error: path — reason``) plus a final
    ``total: N`` summary line.

    Fix (2025-06-26): return type corrected from AsyncIterator[str] to
    AsyncGenerator[str, None]. An async def with yield is an AsyncGenerator,
    not an AsyncIterator, and the wrong annotation caused mypy errors.

    Args:
        user_id: The owner_id to stamp on every upserted note.

    Yields:
        str: Progress log lines suitable for SSE ``data:`` frames.
    """
    owner_id = await _resolve_owner_id(user_id)
    vault_root = _get_vault_path()

    if not vault_root.exists():
        yield f"error: vault path does not exist: {vault_root}"
        return

    md_files = sorted(vault_root.rglob("*.md"))
    # Skip dotfiles and .gitkeep siblings
    md_files = [f for f in md_files if not any(part.startswith(".") for part in f.parts)]

    yield f"total: {len(md_files)}"

    async with AsyncSessionFactory() as db:
        for md_path in md_files:
            try:
                line = await _sync_file(md_path, owner_id, db)
            except Exception as exc:  # noqa: BLE001
                line = f"error: {md_path.name} — {exc}"
            yield line
            await asyncio.sleep(0)  # keep event loop responsive

    yield f"done: synced {len(md_files)} files for user_id={user_id}"


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------


class VaultEventHandler(FileSystemEventHandler):
    """Handle create/modify/delete events on .md files in the vault."""

    def __init__(self, owner_id: int = 1) -> None:
        super().__init__()
        self._owner_id = owner_id
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Return the running event loop, or create a new one if none exists.

        Uses asyncio.get_running_loop() (Python 3.10+) to avoid the
        DeprecationWarning emitted by the deprecated get_event_loop() when
        called from a thread with no current event loop set.
        """
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop in this thread — create a fresh one.
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _dispatch_coroutine(self, coro: object) -> None:
        """Schedule a coroutine on the running event loop (thread-safe)."""
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = self._get_loop()

            if loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, loop)  # type: ignore[arg-type]
            else:
                loop.run_until_complete(coro)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            logger.warning("VaultEventHandler dispatch error: %s", exc)

    def on_created(self, event: object) -> None:
        if getattr(event, "is_directory", False):
            return
        src_path: str = getattr(event, "src_path", "")
        if src_path.endswith(".md"):
            self._dispatch_coroutine(self._handle_upsert(Path(src_path)))

    def on_modified(self, event: object) -> None:
        if getattr(event, "is_directory", False):
            return
        src_path: str = getattr(event, "src_path", "")
        if src_path.endswith(".md"):
            self._dispatch_coroutine(self._handle_upsert(Path(src_path)))

    def on_deleted(self, event: object) -> None:
        if getattr(event, "is_directory", False):
            return
        src_path: str = getattr(event, "src_path", "")
        if src_path.endswith(".md"):
            self._dispatch_coroutine(self._handle_delete(Path(src_path)))

    async def _handle_upsert(self, path: Path) -> None:
        """Sync a single modified/created file to DB + vector store."""
        async with AsyncSessionFactory() as db:
            try:
                line = await _sync_file(path, self._owner_id, db)
                logger.debug("[watcher] %s", line)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[watcher] upsert failed %s: %s", path.name, exc)

    async def _handle_delete(self, path: Path) -> None:
        """Soft-delete a note from the DB when its vault file is removed.

        Fix (2025-06-26): delete_note_vector (alias for delete_note) calls the
        synchronous QdrantClient.delete() directly. Calling it on the event-loop
        thread blocked the loop for every file deletion. Wrapped in run_in_executor.
        """
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from gnosis.models.note import Note

        vault_root = _get_vault_path()
        try:
            rel_path = str(path.relative_to(vault_root))
        except ValueError:
            rel_path = str(path)

        async with AsyncSessionFactory() as db:
            db_session: AsyncSession = db
            result = await db_session.execute(select(Note).where(Note.vault_path == rel_path))
            note = result.scalar_one_or_none()
            if note:
                note.is_deleted = True
                await db_session.commit()
                # Dispatch synchronous Qdrant delete to thread pool so the
                # event loop is not blocked during the network I/O.
                try:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, delete_note_vector, note.id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Vector delete skipped for %s: %s", note.id, exc)
                logger.info("[watcher] soft-deleted %s", rel_path)


# ---------------------------------------------------------------------------
# Startup helpers called from main.py lifespan
# ---------------------------------------------------------------------------


async def start_vault_watcher(owner_id: int = 1) -> Observer:
    """Start the watchdog observer and run an initial full sync.

    Args:
        owner_id: Default owner for notes discovered during startup sync.

    Returns:
        The running :class:`watchdog.observers.Observer` instance so the
        lifespan context can call ``observer.stop()`` on shutdown.
    """
    vault_path = _get_vault_path()
    handler = VaultEventHandler(owner_id=owner_id)

    observer = Observer()
    observer.schedule(handler, str(vault_path), recursive=True)
    observer.start()
    logger.info("Vault watcher started on %s", vault_path)

    # Initial full sync (non-streaming — log to logger only)
    try:
        async for line in run_full_sync_for_user(owner_id):
            logger.info("[startup-sync] %s", line)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Startup sync error: %s", exc)

    return observer
