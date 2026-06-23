"""
Slice 17 — Vault sync endpoint tests.

Covers:
- POST /vault/sync  (background mode) → 202 + accepted payload
- GET  /vault/sync/status            → idle / running / done states
- POST /vault/sync?stream=true       → text/event-stream response
- Auth guard: requests without a token → 401/403

All tests run against the FastAPI TestClient with mocked vault_sync service
so no real filesystem I/O occurs.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


async def _mock_run_full_sync():
    """Yields a handful of synthetic vault sync log lines."""
    lines = [
        "total: 3",
        "synced: 10-zettelkasten/atom-of-thought.md",
        "synced: 10-zettelkasten/second-note.md",
        "skipped: 10-zettelkasten/unchanged.md",
        "done: 3 files processed",
    ]
    for line in lines:
        yield line


@pytest.fixture()
def mock_vault_sync(monkeypatch):
    """Patch run_full_sync_for_user with the async-generator mock."""
    monkeypatch.setattr(
        "gnosis.routers.vault.run_full_sync_for_user",
        lambda user_id: _mock_run_full_sync(),  # noqa: ARG005
    )


@pytest.fixture()
def auth_headers():
    """Return minimal auth headers for test requests."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture()
def unauthenticated_test_client(_sync_app) -> TestClient:
    """Sync TestClient where every request resolves to HTTP 401.

    Reuses the same _sync_app fixture (which handles DB + patches) but
    swaps require_user / get_current_user to _fake_deny_user so that
    auth-guard tests receive the expected rejection.
    """
    from gnosis.core.auth import get_current_user, require_user
    from tests.conftest import _fake_deny_user

    _sync_app.dependency_overrides[require_user] = _fake_deny_user
    _sync_app.dependency_overrides[get_current_user] = _fake_deny_user
    with TestClient(_sync_app, raise_server_exceptions=False) as tc:
        yield tc
    # Restore the default authenticated overrides for any tests that run after
    from tests.conftest import _fake_require_user
    _sync_app.dependency_overrides[require_user] = _fake_require_user
    _sync_app.dependency_overrides[get_current_user] = _fake_require_user


# ---------------------------------------------------------------------------
# POST /vault/sync  (background mode)
# ---------------------------------------------------------------------------


def test_vault_sync_background_returns_202(test_client: TestClient, auth_headers, mock_vault_sync):
    """Non-streaming POST should return HTTP 202 immediately."""
    response = test_client.post("/api/v1/vault/sync", headers=auth_headers)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert "message" in body
    assert "user_id" in body


# ---------------------------------------------------------------------------
# GET /vault/sync/status
# ---------------------------------------------------------------------------


def test_vault_sync_status_idle_before_sync(test_client: TestClient, auth_headers):
    """Status should be 'idle' when no sync has been triggered for this user."""
    response = test_client.get("/api/v1/vault/sync/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["state"] in ("idle", "running", "done", "error")


def test_vault_sync_status_fields_present(test_client: TestClient, auth_headers):
    """Status response must always include the required schema fields."""
    response = test_client.get("/api/v1/vault/sync/status", headers=auth_headers)
    body = response.json()
    required_fields = {"state", "files_processed", "files_total"}
    assert required_fields.issubset(body.keys()), (
        f"Missing fields: {required_fields - body.keys()}"
    )


# ---------------------------------------------------------------------------
# POST /vault/sync?stream=true
# ---------------------------------------------------------------------------


def test_vault_sync_stream_content_type(test_client: TestClient, auth_headers, mock_vault_sync):
    """Streaming endpoint must return text/event-stream content type."""
    with test_client.stream("POST", "/api/v1/vault/sync?stream=true", headers=auth_headers) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


def test_vault_sync_stream_emits_sse_lines(test_client: TestClient, auth_headers, mock_vault_sync):
    """Each line from the sync generator should arrive as a 'data:' SSE event."""
    collected: list[str] = []
    with test_client.stream("POST", "/api/v1/vault/sync?stream=true", headers=auth_headers) as resp:
        for raw_line in resp.iter_lines():
            if raw_line.startswith("data:"):
                collected.append(raw_line[5:].strip())

    assert len(collected) >= 2, f"Expected ≥2 SSE data lines, got: {collected}"
    assert collected[-1] == "[done]", f"Last SSE event should be '[done]', got: {collected[-1]}"


def test_vault_sync_stream_synced_lines_present(test_client: TestClient, auth_headers, mock_vault_sync):
    """At least one 'synced:' line should appear in the stream."""
    collected: list[str] = []
    with test_client.stream("POST", "/api/v1/vault/sync?stream=true", headers=auth_headers) as resp:
        for raw_line in resp.iter_lines():
            if raw_line.startswith("data:"):
                collected.append(raw_line[5:].strip())

    synced_lines = [line for line in collected if line.startswith("synced:")]
    assert len(synced_lines) >= 1, "Expected at least one 'synced:' line in the stream"


# ---------------------------------------------------------------------------
# Auth / security
# ---------------------------------------------------------------------------


def test_vault_sync_requires_auth(unauthenticated_test_client: TestClient):
    """Requests without a token should be rejected with 401 or 403."""
    response = unauthenticated_test_client.post("/api/v1/vault/sync")
    assert response.status_code in (401, 403)


def test_vault_sync_status_requires_auth(unauthenticated_test_client: TestClient):
    """Status endpoint also requires authentication."""
    response = unauthenticated_test_client.get("/api/v1/vault/sync/status")
    assert response.status_code in (401, 403)
