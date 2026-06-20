"""Coverage tests for gnosis/routers/vault.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.vault import router


def _make_app(db_mock: AsyncMock, user_id: int = 1) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    user = User(id=user_id, email="u@test.com", hashed_password="x")

    async def _db():
        yield db_mock

    async def _user():
        return user

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[require_user] = _user
    return app


# POST /vault/sync
def test_vault_sync_returns_200():
    db = AsyncMock()

    async def _fake_sync(*args, **kwargs):
        yield {"status": "ok", "added": 1, "updated": 0, "skipped": 0, "errors": 0}

    with patch("gnosis.routers.vault.run_full_sync_for_user", side_effect=_fake_sync):
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/vault/sync")
    assert resp.status_code == 200


def test_vault_sync_error_still_returns_200():
    db = AsyncMock()

    async def _fake_sync(*args, **kwargs):
        yield {"status": "error", "detail": "Vault not found"}

    with patch("gnosis.routers.vault.run_full_sync_for_user", side_effect=_fake_sync):
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/vault/sync")
    assert resp.status_code == 200


# POST /vault/sync/file
def test_vault_sync_file_returns_200():
    db = AsyncMock()

    with patch("gnosis.routers.vault.sync_single_file", new_callable=AsyncMock,
               return_value={"status": "created", "note_id": "abc"}):
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/vault/sync/file",
                           json={"path": "/vault/test.md"})
    assert resp.status_code == 200


def test_vault_sync_file_not_found():
    db = AsyncMock()

    with patch("gnosis.routers.vault.sync_single_file", new_callable=AsyncMock,
               return_value={"status": "error", "detail": "File not found"}):
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/vault/sync/file",
                           json={"path": "/vault/missing.md"})
    assert resp.status_code == 200


# GET /vault/status
def test_vault_status_returns_200():
    db = AsyncMock()
    r = MagicMock()
    r.scalar.return_value = 42
    db.execute.return_value = r
    db.scalar = AsyncMock(return_value=42)
    client = TestClient(_make_app(db))
    resp = client.get("/api/v1/vault/status")
    assert resp.status_code == 200
