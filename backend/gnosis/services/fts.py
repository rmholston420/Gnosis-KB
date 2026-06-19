"""PostgreSQL tsvector full-text search service.

Provides a single public coroutine::

    results = await fulltext_search(
        db, query, limit=10, folder=None, note_type=None, tags=None
    )

The function is intentionally self-contained and async-safe.  It is called
by the search router when ``mode=fulltext`` is requested, or as a fallback
when the Qdrant hybrid search raises an exception.

Ranking
-------
Uses ``ts_rank_cd`` (cover-density ranking) which rewards query terms that
appear close together.  The ``fts`` column is already weighted::

    A = title   (highest weight)
    B = body
    C = folder  (lowest weight)

Highlighting
------------
``ts_headline`` returns a snippet of body text with matching terms wrapped
in <mark> tags.  The StartSel/StopSel options are kept as plain strings so
the frontend can style them with CSS without parsing HTML.
"""

import logging
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ts_headline options — short snippet, <mark> wrapping
_HEADLINE_OPTS = "MaxWords=35, MinWords=15, ShortWord=3, StartSel='<mark>', StopSel='</mark>', HighlightAll=false"


async def fulltext_search(
    db: AsyncSession,
    query: str,
    *,
    limit: int = 10,
    folder: str | None = None,
    note_type: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Run a tsvector full-text search against the notes table.

    Parameters
    ----------
    db:
        An open async SQLAlchemy session.
    query:
        Raw user query string.  Converted to a tsquery with
        ``plainto_tsquery`` (no special syntax required from users).
    limit:
        Maximum number of results (1-100).
    folder, note_type, tags:
        Optional filters applied as AND conditions.

    Returns
    -------
    dict with keys:
        ``results`` -- list of result dicts
        ``elapsed_ms`` -- wall-clock time in milliseconds
    """
    start = time.monotonic()

    # Build WHERE clause additions
    conditions = [
        "n.is_deleted = false",
        "n.fts @@ plainto_tsquery('english', :query)",
    ]
    params: dict[str, Any] = {"query": query, "limit": limit}

    if folder:
        conditions.append("n.folder = :folder")
        params["folder"] = folder

    if note_type:
        conditions.append("n.note_type = :note_type")
        params["note_type"] = note_type

    where_clause = " AND ".join(conditions)

    # Tag filter: all requested tags must be present (AND semantics)
    tag_join = ""
    if tags:
        for i, tag in enumerate(tags):
            alias = f"nt{i}"
            tag_param = f"tag_{i}"
            tag_join += (
                f" JOIN note_tags {alias} ON {alias}.note_id = n.id"
                f" JOIN tags t{i} ON t{i}.id = {alias}.tag_id AND t{i}.name = :{tag_param}"
            )
            params[tag_param] = tag

    sql = text(f"""
        SELECT
            n.id                                                   AS note_id,
            n.title,
            n.slug,
            n.folder,
            n.note_type,
            n.status,
            n.word_count,
            ts_rank_cd(n.fts, plainto_tsquery('english', :query))  AS score,
            ts_headline(
                'english',
                n.body,
                plainto_tsquery('english', :query),
                '{_HEADLINE_OPTS}'
            )                                                      AS highlight,
            COALESCE(
                (
                    SELECT array_agg(t.name ORDER BY t.name)
                    FROM note_tags nt
                    JOIN tags t ON t.id = nt.tag_id
                    WHERE nt.note_id = n.id
                ),
                ARRAY[]::text[]
            )                                                      AS tags
        FROM notes n
        {tag_join}
        WHERE {where_clause}
        ORDER BY score DESC
        LIMIT :limit
    """)

    try:
        result = await db.execute(sql, params)
        rows = result.mappings().all()
    except Exception as exc:
        logger.error("FTS query failed: %s", exc)
        return {"results": [], "elapsed_ms": 0.0}

    elapsed_ms = (time.monotonic() - start) * 1000

    output = [
        {
            "note_id":   row["note_id"],
            "title":     row["title"],
            "slug":      row["slug"] or "",
            "folder":    row["folder"] or "",
            "note_type": row["note_type"] or "",
            "status":    row["status"] or "",
            "score":     float(row["score"]),
            "highlight": row["highlight"] or "",
            "tags":      list(row["tags"]) if row["tags"] else [],
        }
        for row in rows
    ]

    logger.info(
        "FTS '%s' → %d results in %.1fms",
        query[:60],
        len(output),
        elapsed_ms,
    )
    return {"results": output, "elapsed_ms": elapsed_ms}


async def suggest_completions(
    db: AsyncSession,
    prefix: str,
    limit: int = 8,
) -> list[str]:
    """Return note titles that start with ``prefix`` (case-insensitive).

    Used for the search-bar autocomplete dropdown.  Returns raw title strings;
    the frontend can highlight the matching prefix.
    """
    result = await db.execute(
        text(
            """
            SELECT title FROM notes
            WHERE is_deleted = false
              AND lower(title) LIKE lower(:prefix) || '%'
            ORDER BY title
            LIMIT :limit
            """
        ),
        {"prefix": prefix, "limit": limit},
    )
    return [row[0] for row in result.fetchall()]
