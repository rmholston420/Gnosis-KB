"""Vault filesystem watcher and sync service.

Watches ``GNOSIS_VAULT_ROOT/`` for .md file changes using watchdog.
On create/modify: parse frontmatter + body, upsert to DB, queue for vector
indexing.  On delete: mark as ``is_deleted=True`` in DB (never hard-delete).
Maintains bidirectional link table from parsed [[wikilinks]].

Namespace contract
------------------
Every note that enters the DB through this service is stamped with an
``owner_id`` resolved from the vault directory path.  The resolution
algorithm (``_resolve_owner_id``) matches the file path against each
``User``'s effective vault root in priority order:

1. Explicit ``user.vault_path`` override (absolute)
2. ``GNOSIS_VAULT_ROOT / user.vault_slug``
3. ``GNOSIS_VAULT_ROOT / str(user.id)``

If no user is matched the note is upserted with ``owner_id=None``,
preserving backwards-compatible visibility (null-owner rows are returned
for all users by ``scoped_note_stmt`` with ``include_null_owner=True``).

This service runs as a background thread started in FastAPI's lifespan.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from watchdog.events import FileCreatedEvent, FileDeletedEvent, FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from gnosis.config import get_settings
from gnosis.core.namespace import VAULT_ROOT, resolve_vault_path
from gnosis.database import AsyncSessionLocal
from gnosis.models.link import Link
from gnosis.models.note import Note
from gnosis.models.tag import Tag
from gnosis.models.user import User
from gnosis.services.markdown_parser import parse_note_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Owner resolution
# ---------------------------------------------------------------------------


async def _resolve_owner_id(file_path: Path, db: Any) -> Optional[int]:
    """Return the ``User.id`` that owns *file_path*, or ``None``.

    Resolution walks every User row and checks whether *file_path* is
    nested under that user's effective vault root (respecting the same
    priority order as ``resolve_vault_path``).

    The query is a full table scan but the User table is expected to be
    small (hundreds of rows at most), so this is acceptable.

    Args:
        file_path: Absolute filesystem path of the .md file.
        db: Active async SQLAlchemy session.

    Returns:
        Matched ``User.id``, or ``None`` if no vault root contains the file.
    """
    result = await db.execute(select(User))
    users = result.scalars().all()
    for user in users:
        vault_root = resolve_vault_path(user)
        try:
            file_path.relative_to(vault_root)
            return user.id
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------


class VaultEventHandler(FileSystemEventHandler):
    """Watchdog event handler for the Gnosis vault root directory.

    Processes file system events and syncs changes to PostgreSQL.
    Uses asyncio.run_coroutine_threadsafe to bridge the sync watchdog
    callbacks into the async FastAPI event loop.

    The handler watches ``GNOSIS_VAULT_ROOT`` (all user vaults) rather
    than a single user's vault, so new vaults are detected automatically
    without a service restart.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        """Initialize the handler with the running event loop.

        Args:
            loop: The asyncio event loop from the FastAPI process.
        """
        super().__init__()
        self.loop = loop
        self.settings = get_settings()

    def _is_md_file(self, path: str) -> bool:
        """Return True if path is a Markdown file."""
        return path.endswith(".md")

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        """Handle file creation events."""
        if not event.is_directory and self._is_md_file(str(event.src_path)):
            asyncio.run_coroutine_threadsafe(
                self._sync_note(Path(str(event.src_path))), self.loop
            )

    def on_modified(self, event: FileModifiedEvent) -> None:  # type: ignore[override]
        """Handle file modification events."""
        if not event.is_directory and self._is_md_file(str(event.src_path)):
            asyncio.run_coroutine_threadsafe(
                self._sync_note(Path(str(event.src_path))), self.loop
            )

    def on_deleted(self, event: FileDeletedEvent) -> None:  # type: ignore[override]
        """Handle file deletion events (soft delete in DB)."""
        if not event.is_directory and self._is_md_file(str(event.src_path)):
            asyncio.run_coroutine_threadsafe(
                self._soft_delete_note(str(event.src_path)), self.loop
            )

    async def _sync_note(self, path: Path) -> None:
        """Parse a .md file and upsert the note into PostgreSQL.

        The ``owner_id`` is resolved from the file path.  The upsert
        uses a coalesce pattern for ``owner_id`` so that a note already
        stamped with an owner (via the API) is never overwritten by a
        subsequent filesystem event with ``None``.

        Args:
            path: Absolute path to the Markdown file.
        """
        try:
            data = parse_note_file(path)
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
            return

        # Compute vault-relative path (relative to VAULT_ROOT for display)
        try:
            vault_path = str(path.relative_to(VAULT_ROOT))
        except ValueError:
            # Fallback: path is outside VAULT_ROOT (e.g. legacy single-vault)
            try:
                vault_path = str(path.relative_to(self.settings.vault_path))
            except ValueError:
                vault_path = str(path)

        async with AsyncSessionLocal() as db:
            try:
                # Resolve owner from directory structure
                owner_id = await _resolve_owner_id(path, db)

                # Build INSERT with owner_id stamped
                insert_values = {
                    "id": data["id"],
                    "title": data["title"],
                    "slug": data["slug"],
                    "body": data["body"],
                    "body_html": data["body_html"],
                    "note_type": data["note_type"],
                    "status": data["status"],
                    "vault_path": vault_path,
                    "folder": data["folder"],
                    "source_url": data["source_url"],
                    "word_count": data["word_count"],
                    "frontmatter": data["frontmatter"],
                    "is_deleted": False,
                    "vector_indexed": False,
                    "graph_indexed": False,
                    "owner_id": owner_id,
                }

                stmt = insert(Note).values(**insert_values).on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "title": data["title"],
                        "slug": data["slug"],
                        "body": data["body"],
                        "body_html": data["body_html"],
                        "note_type": data["note_type"],
                        "status": data["status"],
                        "word_count": data["word_count"],
                        "frontmatter": data["frontmatter"],
                        "source_url": data["source_url"],
                        "is_deleted": False,
                        "vector_indexed": False,
                        # Coalesce: only stamp owner_id if the existing row
                        # has owner_id IS NULL (never overwrite a set value).
                        "owner_id": text(
                            "COALESCE(notes.owner_id, EXCLUDED.owner_id)"
                        ),
                    },
                )
                await db.execute(stmt)

                # Sync tags
                await _sync_tags(db, data["id"], data["tags"])

                await db.commit()

                # Rebuild links (after commit so note exists)
                await _rebuild_links(db, data["id"], data["wikilinks"])
                await db.commit()

                logger.debug(
                    "Synced note %s (owner=%s, path=%s)",
                    data["id"],
                    owner_id,
                    vault_path,
                )
            except Exception as e:
                await db.rollback()
                logger.error("Error syncing note %s: %s", vault_path, e)

    async def _soft_delete_note(self, vault_path_str: str) -> None:
        """Mark a note as deleted in the DB (never hard-delete).

        Matches the note by its stored ``vault_path`` value, which is
        relative to ``VAULT_ROOT``.

        Args:
            vault_path_str: Absolute filesystem path of deleted file.
        """
        # Try VAULT_ROOT-relative first, then legacy settings.vault_path
        for root in (VAULT_ROOT, self.settings.vault_path):
            try:
                rel_path = str(Path(vault_path_str).relative_to(root))
                break
            except ValueError:
                continue
        else:
            rel_path = vault_path_str

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Note).where(Note.vault_path == rel_path)
            )
            note = result.scalar_one_or_none()
            if note:
                note.is_deleted = True
                await db.commit()
                logger.info("Soft-deleted note at %s", rel_path)


# ---------------------------------------------------------------------------
# Tag + link helpers
# ---------------------------------------------------------------------------


async def _sync_tags(db: Any, note_id: str, tag_names: list[str]) -> None:
    """Ensure tags exist and are associated with the note."""
    from gnosis.models.tag import NoteTag

    # Remove old note-tag associations
    await db.execute(
        NoteTag.delete().where(NoteTag.c.note_id == note_id)  # type: ignore[attr-defined]
    )

    for name in tag_names:
        # Upsert tag
        tag_stmt = insert(Tag).values(name=name, description="").on_conflict_do_nothing()
        await db.execute(tag_stmt)
        # Insert note-tag association
        assoc_stmt = insert(NoteTag).values(note_id=note_id, tag_id=name).on_conflict_do_nothing()
        await db.execute(assoc_stmt)


async def _rebuild_links(
    db: Any, source_id: str, wikilink_titles: list[str]
) -> None:
    """Delete and rebuild all outgoing links for a note.

    Args:
        db: Active database session.
        source_id: The note ID that owns these links.
        wikilink_titles: List of [[Title]] targets found in the note body.
    """
    # Delete existing outgoing links
    await db.execute(
        Link.__table__.delete().where(Link.source_id == source_id)
    )

    for title in wikilink_titles:
        # Find target note by title (case-insensitive)
        result = await db.execute(
            select(Note).where(
                Note.title.ilike(title),
                Note.is_deleted.is_(False),
            )
        )
        target = result.scalar_one_or_none()
        if target and target.id != source_id:
            link = Link(
                source_id=source_id,
                target_id=target.id,
                link_text=title,
                link_type="wikilink",
            )
            db.add(link)


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------


async def start_vault_watcher() -> Observer:
    """Start the watchdog observer for the vault root directory.

    Watches ``GNOSIS_VAULT_ROOT`` recursively so every user's vault
    sub-directory is covered without needing a restart when a new vault
    is created.

    Returns:
        Running Observer instance (call .stop() + .join() on shutdown).
    """
    loop = asyncio.get_event_loop()
    handler = VaultEventHandler(loop)
    observer = Observer()
    # Watch the shared vault root, not a single user's vault
    observer.schedule(handler, str(VAULT_ROOT), recursive=True)
    observer.start()
    logger.info("Vault watcher started on %s", VAULT_ROOT)

    # Perform initial full sync
    await full_vault_sync()

    return observer


async def full_vault_sync() -> int:
    """Scan all vaults under GNOSIS_VAULT_ROOT and sync every .md file.

    Returns:
        Number of notes synced.
    """
    md_files = list(VAULT_ROOT.rglob("*.md"))
    handler = VaultEventHandler(asyncio.get_event_loop())
    count = 0
    for md_file in md_files:
        await handler._sync_note(md_file)
        count += 1
    logger.info("Full vault sync complete: %d notes processed", count)
    return count
