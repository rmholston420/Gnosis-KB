"""
Admin router.

Endpoints
---------
- POST /admin/reindex   — fix legacy notes with owner_id=0 and re-ingest into LightRAG

This endpoint is intentionally restricted to superusers only.  In development
where there is no dedicated superuser concept yet, it checks that the
authenticated user has user_id == 1 (the bootstrap admin).

Why this exists
---------------
Early vault syncs wrote notes with owner_id = 0 (a sentinel meaning “unresolved”).
Those rows are invisible to normal queries that filter by the authenticated
user’s real ID.  This endpoint:
  1. Selects all Note rows with owner_id = 0.
  2. Resolves the canonical owner using the same logic as vault_sync.
  3. Updates the row in-place (owner_id, updated_at).
  4. Re-ingests the note content into LightRAG so it appears in the graph.
  5. Returns a per-note status list so the caller can verify the operation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import get_current_user
from gnosis.database import get_db
from gnosis.models.note import Note
from gnosis.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_primary_user(db: AsyncSession) -> User | None:
    """Return the oldest user record (bootstrap admin, user_id=1 by convention)."""
    result = await db.execute(select(User).order_by(User.id.asc()).limit(1))
    return result.scalars().first()


async def _reindex_note(
    note: Note,
    new_owner_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    """Update owner_id on *note* and re-ingest into LightRAG."""
    try:
        await db.execute(
            update(Note)
            .where(Note.id == note.id)
            .values(owner_id=new_owner_id, updated_at=datetime.now(timezone.utc))
        )
        await db.flush()
    except Exception as exc:  # noqa: BLE001
        logger.error("DB update failed for note %s: %s", note.id, exc)
        return {"id": note.id, "title": note.title, "status": "error", "detail": str(exc)}

    # Re-ingest into LightRAG (non-fatal if LightRAG is unavailable)
    ingest_status = "skipped"
    try:
        from gnosis.services.graph_rag import graph_rag  # lazy

        content = note.content or ""
        if content.strip():
            await graph_rag.ingest_note(
                note_id=note.id,
                content=content,
                user_id=new_owner_id,
            )
            ingest_status = "ingested"
        else:
            ingest_status = "empty"
    except Exception as exc:  # noqa: BLE001
        logger.warning("LightRAG ingest skipped for note %s: %s", note.id, exc)
        ingest_status = f"lightrag_error: {exc}"

    return {
        "id": note.id,
        "title": note.title,
        "old_owner_id": 0,
        "new_owner_id": new_owner_id,
        "ingest": ingest_status,
        "status": "ok",
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/reindex",
    summary="Re-index legacy notes with owner_id=0",
    response_description="Per-note status list with ingest result",
)
async def reindex_legacy_notes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Fix notes written with the legacy ``owner_id=0`` sentinel.

    Only callable by the primary admin user (user_id == 1).
    Returns a summary with one entry per affected note.
    """
    # Restrict to admin user only
    if current_user.id != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin-only endpoint.",
        )

    # Resolve the target owner — use the primary user (first registered)
    target_user = await _get_primary_user(db)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No users found in the database.",
        )

    new_owner_id = target_user.id

    # Find all legacy notes
    result = await db.execute(
        select(Note)
        .where(Note.owner_id == 0, Note.is_deleted.is_(False))
        .order_by(Note.created_at.asc())
    )
    legacy_notes = result.scalars().all()

    if not legacy_notes:
        return {
            "status": "ok",
            "message": "No legacy notes found with owner_id=0.",
            "fixed": 0,
            "notes": [],
        }

    logger.info(
        "Reindexing %d legacy note(s) → owner_id=%d",
        len(legacy_notes),
        new_owner_id,
    )

    note_results: list[dict[str, Any]] = []
    for note in legacy_notes:
        row = await _reindex_note(note, new_owner_id, db)
        note_results.append(row)

    await db.commit()

    fixed = sum(1 for r in note_results if r["status"] == "ok")
    errors = sum(1 for r in note_results if r["status"] == "error")

    return {
        "status": "ok" if errors == 0 else "partial",
        "message": f"{fixed} note(s) re-indexed, {errors} error(s).",
        "fixed": fixed,
        "errors": errors,
        "new_owner_id": new_owner_id,
        "notes": note_results,
    }
