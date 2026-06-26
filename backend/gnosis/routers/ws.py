"""WebSocket router — real-time vault event push.

Endpoint
--------
GET /ws/vault?token=<jwt>   WebSocket upgrade

Auth
----
WebSocket handshake requests cannot carry an ``Authorization: Bearer`` header
(browsers don't support it for WS).  Token is read from the ``token`` query
parameter instead.

When ``AUTH_REQUIRED=false`` (default for local single-user mode) the token
query param is optional: the backend resolves the first active DB user
automatically.  This is the correct behaviour for the dev setup.

Connection manager
------------------
A module-level ``_manager`` instance holds the set of active connections.
``broadcast_vault_event(payload)`` can be imported by other modules
(e.g. ``ingest_queue.py``) to push events to all connected clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from gnosis.config import settings
from gnosis.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------


class _ConnectionManager:
    """Thread-safe set of active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        logger.debug("WS client connected. total=%d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        logger.debug("WS client disconnected. total=%d", len(self._connections))

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Send *payload* as JSON to every connected client.

        Dead connections are removed silently.
        """
        dead: set[WebSocket] = set()
        data = json.dumps(payload)
        for ws in list(self._connections):
            try:
                await ws.send_text(data)
            except Exception:  # noqa: BLE001
                dead.add(ws)
        self._connections -= dead


_manager = _ConnectionManager()


async def broadcast_vault_event(payload: dict[str, Any]) -> None:
    """Module-level helper imported by ingest_queue and vault_sync."""
    await _manager.broadcast(payload)


# ---------------------------------------------------------------------------
# Auth helper for WebSocket (query-param token)
# ---------------------------------------------------------------------------


async def _resolve_ws_user(token: str | None) -> Any:
    """Resolve the user from a WS query-param token.

    * AUTH_REQUIRED=false → auto-resolve first active DB user (no token needed).
    * AUTH_REQUIRED=true  → decode JWT; return None on failure.

    Fix (2025-06-26): was using bare `async with AsyncSessionLocal:` which hit
    the broken __aexit__ path in _AsyncSessionLocalProxy, leaking DB sessions.
    Changed to `async with AsyncSessionLocal():` (calling the proxy) which
    returns a properly-bound session context manager.
    """
    from gnosis.core.auth import ALGORITHM, synthetic_guest
    from gnosis.models.user import User

    # Fix: call AsyncSessionLocal() to get a properly-bound session CM.
    async with AsyncSessionLocal() as db:
        if not settings.auth_required:
            result = await db.execute(
                select(User).where(User.is_active == True).limit(1)  # noqa: E712
            )
            user = result.scalar_one_or_none()
            return user if user is not None else synthetic_guest()

        if not token:
            return None

        try:
            from jose import JWTError, jwt  # noqa: F401

            payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
            user_id: int = int(payload["sub"])
        except (Exception,):  # noqa: BLE001
            return None

        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)  # noqa: E712
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

_PING_INTERVAL = 30  # seconds between server-side pings


@router.websocket("/vault")
async def vault_ws(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """Real-time vault event stream.

    Clients receive JSON messages with the following shapes:

    .. code-block:: json

        {"type": "note_created", "note_id": "abc", "title": "My Note"}
        {"type": "note_updated", "note_id": "abc"}
        {"type": "note_deleted", "note_id": "abc"}
        {"type": "sync_complete", "synced": 12}
        {"type": "ping"}
    """
    user = await _resolve_ws_user(token)
    if user is None:
        # auth_required=true and token missing/invalid → reject
        await websocket.close(code=4001)
        return

    await _manager.connect(websocket)
    try:
        # Keep-alive: send ping every _PING_INTERVAL seconds.
        # Also drain any client messages (browsers may send pong frames).
        while True:
            try:
                # Wait for a client message with timeout — this keeps the
                # receive loop alive while not blocking the ping task.
                await asyncio.wait_for(websocket.receive_text(), timeout=_PING_INTERVAL)
            except asyncio.TimeoutError:
                # No message from client → send a ping to verify the connection.
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:  # noqa: BLE001
                    break
            except WebSocketDisconnect:
                break
            except asyncio.CancelledError:
                # Server shutdown or task cancellation — break cleanly so the
                # finally block removes the connection from the registry before
                # CancelledError propagates up the call stack.
                break
    finally:
        _manager.disconnect(websocket)
