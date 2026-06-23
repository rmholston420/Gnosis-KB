"""
Vault router.

Endpoints
---------
- POST /vault/sync           — trigger full vault sync for authenticated user
- GET  /vault/sync/status    — poll current sync state

The POST endpoint returns HTTP 202 immediately and runs vault sync in a
FastAPI BackgroundTask so the caller is never blocked on filesystem I/O.

When the query-param ``stream=true`` is added, the endpoint instead returns
an ``EventSource``-compatible ``text/event-stream`` response and yields one
SSE ``data:`` line per file processed.  This is what the SettingsPage uses
so the user can watch progress in real time.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from gnosis.core.auth import get_current_user
from gnosis.models.user import User
from gnosis.services.vault_sync import run_full_sync_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vault", tags=["vault"])

# ---------------------------------------------------------------------------
# In-memory sync status  (per user_id — adequate for single-host deployment)
# ---------------------------------------------------------------------------

_sync_status: dict[int, dict[str, object]] = {}
# e.g. { 1: { "state": "running", "started": 1719800000.0, "files": 7, "done": 3 } }


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SyncStartResponse(BaseModel):
    """Returned by POST /vault/sync when background=true (default)."""

    status: str  # "accepted"
    message: str
    user_id: int


class SyncStatusResponse(BaseModel):
    """Returned by GET /vault/sync/status."""

    state: str  # idle | running | done | error
    started: float | None = None
    elapsed: float | None = None
    files_processed: int = 0
    files_total: int = 0
    last_error: str | None = None


# ---------------------------------------------------------------------------
# Background task helper
# ---------------------------------------------------------------------------


async def _run_sync_background(user_id: int) -> None:
    """Run vault sync in a background task, updating _sync_status."""
    _sync_status[user_id] = {
        "state": "running",
        "started": time.time(),
        "files_processed": 0,
        "files_total": 0,
        "last_error": None,
    }
    try:
        async for line in run_full_sync_for_user(user_id):
            status = _sync_status.get(user_id, {})
            # Count processed files from the log lines
            if (
                line.startswith("synced:")
                or line.startswith("skipped:")
                or line.startswith("deleted:")
            ):
                status["files_processed"] = int(status.get("files_processed", 0)) + 1  # type: ignore[assignment]
            elif line.startswith("total:"):
                try:
                    status["files_total"] = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            logger.debug("[vault-sync uid=%d] %s", user_id, line)
        _sync_status[user_id]["state"] = "done"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Vault sync failed for user_id=%d", user_id)
        _sync_status.setdefault(user_id, {})["state"] = "error"  # type: ignore[assignment]
        _sync_status[user_id]["last_error"] = str(exc)


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------


async def _sync_sse_generator(user_id: int) -> AsyncIterator[str]:
    """Async generator that yields SSE-formatted lines from run_full_sync_for_user."""
    _sync_status[user_id] = {
        "state": "running",
        "started": time.time(),
        "files_processed": 0,
        "files_total": 0,
        "last_error": None,
    }
    try:
        async for line in run_full_sync_for_user(user_id):
            status = _sync_status.get(user_id, {})
            if line.startswith(("synced:", "skipped:", "deleted:")):
                status["files_processed"] = int(status.get("files_processed", 0)) + 1  # type: ignore[assignment]
            elif line.startswith("total:"):
                try:
                    status["files_total"] = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            yield f"data: {line}\n\n"
            await asyncio.sleep(0)  # yield to event loop

        _sync_status[user_id]["state"] = "done"
        yield "data: [done]\n\n"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Vault sync stream failed for user_id=%d", user_id)
        _sync_status[user_id]["state"] = "error"
        _sync_status[user_id]["last_error"] = str(exc)
        yield f"data: [error] {exc}\n\n"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/sync",
    status_code=202,
    summary="Trigger full vault sync for the authenticated user",
    response_model=SyncStartResponse,
)
async def trigger_vault_sync(
    background_tasks: BackgroundTasks,
    stream: bool = Query(
        default=False,
        description="When true, return an SSE text/event-stream instead of 202 JSON.",
    ),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse | SyncStartResponse:
    """Trigger a full vault resync for the current user.

    - **stream=false** (default): returns HTTP 202 immediately; sync runs in
      the background.  Poll ``GET /vault/sync/status`` for progress.
    - **stream=true**: returns ``text/event-stream``; the client receives one
      ``data: <line>`` event per file processed, ending with ``data: [done]``.
    """
    if stream:
        return StreamingResponse(
            _sync_sse_generator(current_user.id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming: fire and forget
    background_tasks.add_task(_run_sync_background, current_user.id)
    return SyncStartResponse(
        status="accepted",
        message="Vault sync started in background. Poll GET /vault/sync/status for progress.",
        user_id=current_user.id,
    )


@router.get(
    "/sync/status",
    summary="Poll the current vault sync state for the authenticated user",
    response_model=SyncStatusResponse,
)
async def get_sync_status(
    current_user: User = Depends(get_current_user),
) -> SyncStatusResponse:
    """Return the most recent sync state for the current user.

    States: ``idle`` | ``running`` | ``done`` | ``error``.
    """
    status = _sync_status.get(current_user.id)
    if status is None:
        return SyncStatusResponse(state="idle")

    started = status.get("started")
    elapsed = round(time.time() - float(started), 1) if started else None

    return SyncStatusResponse(
        state=str(status.get("state", "idle")),
        started=float(started) if started else None,
        elapsed=elapsed,
        files_processed=int(status.get("files_processed", 0)),  # type: ignore[arg-type]
        files_total=int(status.get("files_total", 0)),  # type: ignore[arg-type]
        last_error=status.get("last_error") if status.get("last_error") else None,  # type: ignore[arg-type]
    )
