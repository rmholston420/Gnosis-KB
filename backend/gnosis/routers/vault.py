"""Vault router -- sync (background + SSE), sync status, stats, and path.

Endpoints
---------
POST /vault/sync               -- Trigger a full vault sync.
                                  ?stream=false (default) -> 202 SyncStartResponse (BackgroundTask)
                                  ?stream=true            -> 200 text/event-stream SSE
GET  /vault/sync/status        -- Poll background sync progress (SyncStatusResponse)
GET  /vault/stats              -- Aggregate note counts and disk usage
GET  /vault/path               -- Resolved filesystem path for the current user

Module-level state
------------------
_sync_status : dict[int, dict]  -- per-user background sync state
    Keys: state (idle|running|done|error), started (float), files_processed (int),
          files_total (int), last_error (str|None)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import get_current_user, get_vault_owner_ids
from gnosis.database import get_db
from gnosis.models.note import Note
from gnosis.models.user import User
from gnosis.services.vault_sync import run_full_sync_for_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vault", tags=["vault"])

# Per-user background sync state: user_id -> status dict
_sync_status: dict[int, dict] = {}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SyncStartResponse(BaseModel):
    status: str
    user_id: int
    message: str = "Sync started in background"


class SyncStatusResponse(BaseModel):
    state: str  # idle | running | done | error
    files_processed: int = 0
    files_total: int = 0
    elapsed: float | None = None
    last_error: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _run_sync_background(user_id: int) -> None:
    """Run a full vault sync as a background task, updating _sync_status."""
    _sync_status[user_id] = {
        "state": "running",
        "started": time.time(),
        "files_processed": 0,
        "files_total": 0,
        "last_error": None,
    }
    try:
        async for line in run_full_sync_for_user(user_id):
            line = line.strip()
            if line.startswith("total:"):
                try:
                    _sync_status[user_id]["files_total"] = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith(("synced:", "updated:", "deleted:", "skipped:")):
                _sync_status[user_id]["files_processed"] += 1
        _sync_status[user_id]["state"] = "done"
    except Exception as exc:  # noqa: BLE001
        _sync_status[user_id]["state"] = "error"
        _sync_status[user_id]["last_error"] = str(exc)
        logger.error("Background vault sync failed for user %s: %s", user_id, exc)


async def _sync_sse_generator(user_id: int):
    """Async generator that yields SSE-formatted lines for a vault sync."""
    _sync_status[user_id] = {
        "state": "running",
        "started": time.time(),
        "files_processed": 0,
        "files_total": 0,
        "last_error": None,
    }
    try:
        async for line in run_full_sync_for_user(user_id):
            line = line.strip()
            if line.startswith("total:"):
                try:
                    _sync_status[user_id]["files_total"] = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith(("synced:", "updated:", "deleted:", "skipped:")):
                _sync_status[user_id]["files_processed"] += 1
            yield f"data: {line}\n\n"
        _sync_status[user_id]["state"] = "done"
        yield "data: [done]\n\n"
    except Exception as exc:  # noqa: BLE001
        _sync_status[user_id]["state"] = "error"
        _sync_status[user_id]["last_error"] = str(exc)
        yield f"data: [error] {exc}\n\n"
        logger.error("SSE vault sync failed for user %s: %s", user_id, exc)


# ---------------------------------------------------------------------------
# POST /vault/sync
# ---------------------------------------------------------------------------


@router.post(
    "/sync",
    summary="Trigger a full vault sync for the current user",
    status_code=202,
)
async def trigger_vault_sync(
    background_tasks: BackgroundTasks,
    stream: bool = Query(False, description="Stream progress as Server-Sent Events"),
    current_user: User = Depends(get_current_user),
):
    """Trigger a vault sync.

    - ``stream=false`` (default): enqueue as a background task, return 202.
    - ``stream=true``:  stream progress as text/event-stream SSE.
    """
    if stream:
        return StreamingResponse(
            _sync_sse_generator(current_user.id),
            media_type="text/event-stream",
            status_code=200,
        )

    background_tasks.add_task(_run_sync_background, current_user.id)
    return SyncStartResponse(status="accepted", user_id=current_user.id)


# ---------------------------------------------------------------------------
# GET /vault/sync/status
# ---------------------------------------------------------------------------


@router.get("/sync/status", response_model=SyncStatusResponse, summary="Poll background sync state")
async def get_sync_status(
    current_user: User = Depends(get_current_user),
) -> SyncStatusResponse:
    """Return the current background sync state for the authenticated user."""
    entry = _sync_status.get(current_user.id)
    if entry is None:
        return SyncStatusResponse(state="idle")

    elapsed: float | None = None
    if entry.get("started"):
        elapsed = round(time.time() - entry["started"], 2)

    return SyncStatusResponse(
        state=entry["state"],
        files_processed=entry.get("files_processed", 0),
        files_total=entry.get("files_total", 0),
        elapsed=elapsed,
        last_error=entry.get("last_error"),
    )


# ---------------------------------------------------------------------------
# GET /vault/stats
# ---------------------------------------------------------------------------


@router.get("/stats", summary="Aggregate note statistics for the current user")
async def get_vault_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict:
    """Return counts by note_type and total word count."""
    from gnosis.core.namespace import scoped_note_stmt

    base = scoped_note_stmt(
        select(Note).where(Note.is_deleted.is_(False)),
        owner_ids,
    )
    total_count = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    total_words = (
        await db.execute(
            select(func.coalesce(func.sum(Note.word_count), 0)).select_from(
                scoped_note_stmt(
                    select(Note).where(Note.is_deleted.is_(False)),
                    owner_ids,
                ).subquery()
            )
        )
    ).scalar_one()
    type_counts_rows = await db.execute(
        select(Note.note_type, func.count())
        .select_from(
            scoped_note_stmt(
                select(Note).where(Note.is_deleted.is_(False)),
                owner_ids,
            ).subquery()
        )
        .group_by(Note.note_type)
    )
    type_counts = {row[0] or "unknown": row[1] for row in type_counts_rows.all()}
    return {
        "total_notes": total_count,
        "total_words": total_words,
        "by_type": type_counts,
    }


# ---------------------------------------------------------------------------
# GET /vault/path
# ---------------------------------------------------------------------------


@router.get("/path", summary="Resolved filesystem path for the current user's vault")
async def get_vault_path(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the resolved filesystem path for the current user's vault."""
    from gnosis.core.namespace import resolve_vault_path

    path = resolve_vault_path(current_user)
    return {"vault_path": str(path), "exists": path.exists()}
