"""Coverage tests for gnosis/routers/vault.py.

Actual router:
  POST /vault/sync          -> 202 SyncStartResponse (background) or SSE (stream=true)
  GET  /vault/sync/status   -> SyncStatusResponse

Dependency used: get_current_user (NOT require_user, NOT get_db).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import get_current_user
from gnosis.models.user import User
from gnosis.routers.vault import router


def _make_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        email="u@test.com",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
    )


def _make_app(user: User | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    _user = user or _make_user()

    async def _current_user():
        return _user

    app.dependency_overrides[get_current_user] = _current_user
    return app


# ---------------------------------------------------------------------------
# POST /vault/sync  (background mode, default)
# ---------------------------------------------------------------------------

def test_vault_sync_background_returns_202():
    """POST /vault/sync without stream=true returns 202."""
    with patch("gnosis.routers.vault._run_sync_background", new_callable=AsyncMock):
        client = TestClient(_make_app())
        resp = client.post("/api/v1/vault/sync")
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["user_id"] == 1


def test_vault_sync_stream_returns_200():
    """POST /vault/sync?stream=true returns 200 with text/event-stream."""
    async def _fake_sse(user_id: int):
        yield "data: synced: 00-inbox/note.md\n\n"
        yield "data: [done]\n\n"

    with patch("gnosis.routers.vault._sync_sse_generator", side_effect=_fake_sse):
        client = TestClient(_make_app())
        resp = client.post("/api/v1/vault/sync?stream=true")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /vault/sync/status
# ---------------------------------------------------------------------------

def test_vault_sync_status_idle():
    """GET /vault/sync/status returns idle when no sync has run."""
    import gnosis.routers.vault as vault_router
    # Ensure no status entry for user 1
    vault_router._sync_status.pop(1, None)

    client = TestClient(_make_app())
    resp = client.get("/api/v1/vault/sync/status")
    assert resp.status_code == 200
    assert resp.json()["state"] == "idle"


def test_vault_sync_status_running():
    """GET /vault/sync/status returns running state."""
    import time
    import gnosis.routers.vault as vault_router
    vault_router._sync_status[1] = {
        "state": "running",
        "started": time.time(),
        "files_processed": 3,
        "files_total": 10,
        "last_error": None,
    }

    client = TestClient(_make_app())
    resp = client.get("/api/v1/vault/sync/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "running"
    assert data["files_processed"] == 3


def test_vault_sync_status_done():
    """GET /vault/sync/status returns done state."""
    import time
    import gnosis.routers.vault as vault_router
    vault_router._sync_status[1] = {
        "state": "done",
        "started": time.time() - 5,
        "files_processed": 7,
        "files_total": 7,
        "last_error": None,
    }

    client = TestClient(_make_app())
    resp = client.get("/api/v1/vault/sync/status")
    assert resp.status_code == 200
    assert resp.json()["state"] == "done"
