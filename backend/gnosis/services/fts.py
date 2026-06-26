"""Full-text search service — PostgreSQL tsvector-based search.

Public API
----------
fulltext_search(db, query, *, owner_ids, limit, folder, note_type, tags)
    Search notes using PostgreSQL FTS (tsvector/tsquery).

suggest_completions(db, prefix, *, owner_ids, limit)
    Return note titles that start with *prefix* for autocomplete.

rebuild_fts_index(db)
    Rebuild the fts_vector column for all notes. Called after bulk imports.

Fix (2025-06-26)
----------------
rebuild_fts_index() previously swallowed exceptions at WARNING with no
recovery path. A corrupt or stale FTS index silently degraded search quality
indefinitely with no observable failure signal. Now logs at ERROR and re-raises
so callers can distinguish transient from permanent failures and alert operators.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_FTS_CONFIG = "english"  # PostgreSQL FTS dictionary


async def fulltext_search(
    db: AsyncSession,
    query: str,
    *,
    owner_ids: set[int],
    limit: int = 10,
    folder: str | None = None,
    note_type: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Search notes using PostgreSQL FTS.

    Args:
        db: Async SQLAlchemy session.
        query: Raw search query string (will be converted to tsquery).
        owner_ids: Set of owner IDs to scope the search to.
        limit: Maximum number of results to return.
        folder: Optional vault folder filter.
        note_type: Optional note type filter.
        tags: Optional list of tag names to filter by.

    Returns:
        Dict with keys ``results`` (list of result dicts) and ``elapsed_ms`` (float).
    """
    from gnosis.models.note import Note
    from gnosis.models.tag import NoteTag, Tag

    t0 = time.monotonic()

    # Convert free-text query to a safe plainto_tsquery expression
    ts_query = func.plainto_tsquery(_FTS_CONFIG, query)

    stmt = (
        select(
            Note.id,
            Note.title,
            Note.slug,
            Note.folder,
            Note.note_type,
            Note.status,
            Note.body,
            func.ts_rank_cd(Note.fts_vector, ts_query).label("rank"),
            func.ts_headline(
                _FTS_CONFIG,
                Note.body,
                ts_query,
                "MaxWords=35, MinWords=15, ShortWord=3, HighlightAll=FALSE, "
                "MaxFragments=2, FragmentDelimiter=' … '",
            ).label("highlight"),
        )
        .where(
            Note.fts_vector.op("@@")(ts_query),
            Note.is_deleted.is_(False),
            Note.owner_id.in_(owner_ids),
        )
        .order_by(text("rank DESC"))
        .limit(limit)
    )

    if folder:
        stmt = stmt.where(Note.folder == folder)
    if note_type:
        stmt = stmt.where(Note.note_type == note_type)

    result = await db.execute(stmt)
    rows = result.fetchall()

    # Build tag map for returned note IDs
    note_ids = [r.id for r in rows]
    tag_map: dict[str, list[str]] = {nid: [] for nid in note_ids}
    if note_ids:
        tag_stmt = (
            select(NoteTag.c.note_id, Tag.name)
            .join(Tag, Tag.id == NoteTag.c.tag_id)
            .where(NoteTag.c.note_id.in_(note_ids))
        )
        tag_rows = await db.execute(tag_stmt)
        for note_id, tag_name in tag_rows:
            tag_map[note_id].append(tag_name)

    # Apply tag filter client-side (avoids complex SQL for small result sets)
    results = []
    for row in rows:
        note_tags = tag_map.get(row.id, [])
        if tags and not any(t in note_tags for t in tags):
            continue
        results.append(
            {
                "note_id": row.id,
                "title": row.title,
                "slug": row.slug or "",
                "folder": row.folder or "",
                "note_type": row.note_type or "",
                "status": row.status or "",
                "score": float(row.rank),
                "highlight": row.highlight or "",
                "tags": note_tags,
            }
        )

    elapsed = (time.monotonic() - t0) * 1000
    return {"results": results, "elapsed_ms": round(elapsed, 2)}


async def suggest_completions(
    db: AsyncSession,
    prefix: str,
    *,
    owner_ids: set[int],
    limit: int = 8,
) -> list[str]:
    """Return note titles that start with *prefix* (case-insensitive).

    Used for search-bar autocomplete. Results are ordered alphabetically.

    Args:
        db: Async SQLAlchemy session.
        prefix: The prefix to match against note titles.
        owner_ids: Set of owner IDs to scope suggestions to.
        limit: Maximum number of suggestions to return.

    Returns:
        List of matching note titles.
    """
    from gnosis.models.note import Note

    stmt = (
        select(Note.title)
        .where(
            Note.title.ilike(f"{prefix}%"),
            Note.is_deleted.is_(False),
            Note.owner_id.in_(owner_ids),
        )
        .order_by(Note.title)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [row.title for row in result]


async def rebuild_fts_index(db: AsyncSession) -> None:
    """Rebuild the fts_vector column for all non-deleted notes.

    This is an expensive operation and should only be called after bulk
    imports or schema migrations. In normal operation the fts_vector column
    is kept up-to-date by a PostgreSQL trigger.

    Fix (2025-06-26): previously swallowed exceptions at WARNING with no
    recovery path, silently leaving a corrupt index in place. Now logs at
    ERROR and re-raises so callers can surface the failure to operators.

    Raises:
        Exception: Re-raises any SQLAlchemy or database error so callers
            can distinguish transient from permanent failures.
    """
    try:
        await db.execute(
            text(
                """
                UPDATE notes
                SET fts_vector = to_tsvector('english',
                    coalesce(title, '') || ' ' || coalesce(body, ''))
                WHERE is_deleted = false
                """
            )
        )
        await db.commit()
        logger.info("FTS index rebuild complete")
    except Exception as exc:
        # Fix: was logged at WARNING and swallowed. Now logged at ERROR and
        # re-raised so the caller can decide whether to alert or retry.
        logger.error("FTS index rebuild failed: %s", exc, exc_info=True)
        await db.rollback()
        raise
