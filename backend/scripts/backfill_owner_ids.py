"""One-shot backfill: stamp owner_id on legacy notes where owner_id IS NULL.

Usage (from the backend/ directory):

    python -m scripts.backfill_owner_ids

The script resolves the owner for each un-stamped note by matching its
``vault_path`` against each user's resolved vault root (same algorithm used
by vault_sync._resolve_owner_id).  Notes that cannot be matched are left
with owner_id=None (they remain visible to all users via the
``include_null_owner`` flag in scoped_note_stmt).

After stamping the DB rows the script calls ``vector_upsert_note`` for each
affected note so Qdrant payloads are updated with the correct owner_id
filter field.  This is idempotent — safe to run multiple times.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ensure the parent package is importable when run as __main__
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update

from gnosis.core.namespace import VAULT_ROOT, resolve_vault_path
from gnosis.database import AsyncSessionLocal
from gnosis.models.note import Note
from gnosis.models.user import User
from gnosis.services.vector_store import upsert_note as vector_upsert_note

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger("backfill_owner_ids")


async def _resolve_owner_for_vault_path(vault_path: str, users: list[User]) -> int | None:
    """Return user.id whose vault root is a prefix of *vault_path*, or None."""
    p = Path(vault_path)
    # vault_path is stored relative to VAULT_ROOT in the DB
    abs_path = VAULT_ROOT / p if not p.is_absolute() else p
    for user in users:
        user_root = resolve_vault_path(user)
        try:
            abs_path.relative_to(user_root)
            return user.id
        except ValueError:
            continue
    return None


async def run_backfill() -> None:
    async with AsyncSessionLocal() as db:
        # 1. Load all users
        result = await db.execute(select(User))
        users: list[User] = result.scalars().all()
        if not users:
            logger.warning("No users found — nothing to backfill.")
            return

        # 2. Load all notes missing an owner_id
        result = await db.execute(
            select(Note).where(
                Note.owner_id.is_(None),
                Note.is_deleted.is_(False),
            )
        )
        orphan_notes: list[Note] = result.scalars().all()
        logger.info("%d notes with owner_id=NULL found", len(orphan_notes))

        if not orphan_notes:
            logger.info("Nothing to backfill — all notes already have an owner_id.")
            return

        # 3. Stamp each note
        stamped = 0
        unresolved = 0
        for note in orphan_notes:
            owner_id = await _resolve_owner_for_vault_path(note.vault_path or "", users)
            if owner_id is not None:
                await db.execute(
                    update(Note)
                    .where(Note.id == note.id)
                    .values(owner_id=owner_id, vector_indexed=False)
                )
                stamped += 1
                logger.debug("Stamped note %s → owner_id=%s", note.id, owner_id)
            else:
                unresolved += 1
                logger.debug(
                    "Could not resolve owner for note %s (vault_path=%s) — skipping",
                    note.id,
                    note.vault_path,
                )

        await db.commit()
        logger.info(
            "Backfill DB phase complete: %d stamped, %d unresolved",
            stamped,
            unresolved,
        )

        # 4. Re-upsert affected notes into Qdrant with corrected owner_id
        if stamped:
            result = await db.execute(
                select(Note).where(
                    Note.owner_id.is_not(None),
                    Note.vector_indexed.is_(False),
                    Note.is_deleted.is_(False),
                )
            )
            to_reindex: list[Note] = result.scalars().all()
            logger.info("Re-indexing %d notes in Qdrant…", len(to_reindex))
            for note in to_reindex:
                try:
                    tags_result = await db.execute(
                        select(User)  # placeholder — tags loaded lazily below
                    )
                    # Fetch tags for this note via the association table
                    from gnosis.models.tag import NoteTag, Tag

                    tag_rows = await db.execute(
                        select(Tag.name)
                        .join(NoteTag, NoteTag.c.tag_id == Tag.name)
                        .where(NoteTag.c.note_id == note.id)
                    )
                    tag_names = [r[0] for r in tag_rows.all()]

                    vector_upsert_note(
                        note_id=note.id,
                        title=note.title,
                        body=note.body or "",
                        folder=note.folder or "",
                        note_type=note.note_type or "note",
                        status=note.status or "draft",
                        tags=tag_names,
                        owner_id=note.owner_id,
                    )
                    await db.execute(
                        update(Note).where(Note.id == note.id).values(vector_indexed=True)
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Qdrant re-index failed for note %s: %s", note.id, exc)
            await db.commit()
            logger.info("Qdrant re-index phase complete.")

    logger.info("Backfill finished.")


if __name__ == "__main__":
    asyncio.run(run_backfill())
