"""Vault filesystem watcher and sync service.

Watches ~/gnosis-vault/ for .md file changes using watchdog.
On create/modify: parse frontmatter + body, upsert to DB, queue for vector indexing.
On delete: mark as is_deleted=True in DB (never hard-delete).
Maintains bidirectional link table from parsed [[wikilinks]].

This service runs as a background thread started in FastAPI's lifespan.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from watchdog.events import FileCreatedEvent, FileDeletedEvent, FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from gnosis.config import get_settings
from gnosis.database import AsyncSessionLocal
from gnosis.models.link import Link
from gnosis.models.note import Note
from gnosis.models.tag import Tag
from gnosis.services.markdown_parser import parse_note_file

logger = logging.getLogger(__name__)


class VaultEventHandler(FileSystemEventHandler):
    """Watchdog event handler for the Gnosis vault directory.

    Processes file system events and syncs changes to PostgreSQL.
    Uses asyncio.run_coroutine_threadsafe to bridge the sync watchdog
    callbacks into the async FastAPI event loop.
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

        Args:
            path: Absolute path to the Markdown file.
        """
        try:
            data = parse_note_file(path)
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)
            return

        # Compute vault-relative path
        try:
            vault_path = str(path.relative_to(self.settings.vault_path))
        except ValueError:
            vault_path = str(path)

        async with AsyncSessionLocal() as db:
            try:
                # Upsert note
                stmt = insert(Note).values(
                    id=data["id"],
                    title=data["title"],
                    slug=data["slug"],
                    body=data["body"],
                    body_html=data["body_html"],
                    note_type=data["note_type"],
                    status=data["status"],
                    vault_path=vault_path,
                    folder=data["folder"],
                    source_url=data["source_url"],
                    word_count=data["word_count"],
                    frontmatter=data["frontmatter"],
                    is_deleted=False,
                    vector_indexed=False,
                    graph_indexed=False,
                ).on_conflict_do_update(
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
                    },
                )
                await db.execute(stmt)

                # Sync tags
                await _sync_tags(db, data["id"], data["tags"])

                await db.commit()

                # Rebuild links (after commit so note exists)
                await _rebuild_links(db, data["id"], data["wikilinks"])
                await db.commit()

                logger.debug("Synced note %s (%s)", data["id"], vault_path)
            except Exception as e:
                await db.rollback()
                logger.error("Error syncing note %s: %s", vault_path, e)

    async def _soft_delete_note(self, vault_path_str: str) -> None:
        """Mark a note as deleted in the DB (never hard-delete).

        Args:
            vault_path_str: Absolute filesystem path of deleted file.
        """
        try:
            rel_path = str(
                Path(vault_path_str).relative_to(self.settings.vault_path)
            )
        except ValueError:
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


async def start_vault_watcher() -> Observer:
    """Start the watchdog observer for the vault directory.

    Returns:
        Running Observer instance (call .stop() + .join() on shutdown).
    """
    settings = get_settings()
    loop = asyncio.get_event_loop()
    handler = VaultEventHandler(loop)
    observer = Observer()
    observer.schedule(handler, str(settings.vault_path), recursive=True)
    observer.start()

    # Perform initial full sync
    await full_vault_sync()

    return observer


async def full_vault_sync() -> int:
    """Scan the entire vault and sync all .md files to the DB.

    Returns:
        Number of notes synced.
    """
    settings = get_settings()
    md_files = list(settings.vault_path.rglob("*.md"))
    handler = VaultEventHandler(asyncio.get_event_loop())
    count = 0
    for md_file in md_files:
        await handler._sync_note(md_file)
        count += 1
    logger.info("Full vault sync complete: %d notes processed", count)
    return count
