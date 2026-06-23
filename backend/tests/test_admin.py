"""Tests for POST /api/v1/admin/reindex.

Covers three scenarios:
  1. No legacy notes — endpoint returns fixed=0 immediately.
  2. One legacy note (owner_id=0) — note is reassigned to new_owner_id.
  3. Non-admin caller (FakeUser id=2) — endpoint returns 403.

The conftest.py fixtures handle:
  - SQLite in-memory DB (test_engine / test_db)
  - require_user override → FakeUser(id=1) by default
  - LightRAG / Qdrant / vault-watcher patches

For scenario 3 we temporarily override require_user a second time inside
the test to return a FakeUser with id=2.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.models.note import Note
from gnosis.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_user(db: AsyncSession, user_id: int = 1) -> User:
    """Insert a minimal User row so _get_primary_user() can resolve owner."""
    user = User(
        id=user_id,
        email=f"user{user_id}@gnosis.local",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _seed_legacy_note(db: AsyncSession) -> Note:
    """Insert a Note with owner_id=0 (the legacy sentinel)."""
    note = Note(
        id="legacy-note-001",
        title="Legacy Note",
        slug="legacy-note-001",
        body="This note has no owner.",
        owner_id=0,
        vault_path="10-zettelkasten/legacy-note-001.md",
        note_type="permanent",
        is_deleted=False,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


# ---------------------------------------------------------------------------
# Scenario 1 — no legacy notes
# ---------------------------------------------------------------------------


async def test_reindex_no_legacy_notes(client: AsyncClient, test_db: AsyncSession) -> None:
    """When no notes have owner_id=0 the endpoint returns fixed=0."""
    # Seed a real user so _get_primary_user() doesn't 500
    await _seed_user(test_db)

    resp = await client.post(
        "/api/v1/admin/reindex",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["fixed"] == 0
    assert body["notes"] == []


# ---------------------------------------------------------------------------
# Scenario 2 — one legacy note gets reassigned
# ---------------------------------------------------------------------------


async def test_reindex_reassigns_legacy_note(client: AsyncClient, test_db: AsyncSession) -> None:
    """A note with owner_id=0 is updated to owner_id=1 and ingest is attempted."""
    await _seed_user(test_db, user_id=1)
    note = await _seed_legacy_note(test_db)

    resp = await client.post(
        "/api/v1/admin/reindex",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["fixed"] == 1
    assert body["new_owner_id"] == 1

    note_result = body["notes"][0]
    assert note_result["id"] == note.id
    assert note_result["old_owner_id"] == 0
    assert note_result["new_owner_id"] == 1
    # LightRAG is patched to a no-op in tests; ingest will be a lightrag_error
    # or "ingested" depending on mock depth — either is acceptable.
    assert note_result["status"] == "ok"


# ---------------------------------------------------------------------------
# Scenario 3 — non-admin user gets 403
# ---------------------------------------------------------------------------


async def test_reindex_forbidden_for_non_admin(
    async_client: AsyncClient, test_db: AsyncSession
) -> None:
    """A user with id != 1 receives HTTP 403 Forbidden."""
    import tempfile
    from dataclasses import dataclass
    from pathlib import Path
    from unittest.mock import AsyncMock, patch

    from httpx import ASGITransport

    from gnosis.core.auth import require_user
    from gnosis.main import create_app

    @dataclass
    class _NonAdminUser:
        id: int = 2
        email: str = "other@gnosis.local"
        full_name: str | None = "Other User"
        vault_slug: str | None = "other"
        vault_path: str | None = None
        is_active: bool = True
        is_superuser: bool = False

    async def _non_admin() -> _NonAdminUser:
        return _NonAdminUser()

    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        for folder in ["00-inbox", "10-zettelkasten"]:
            (vault / folder).mkdir()

        with (
            patch("gnosis.services.vector_store.ensure_collection", return_value=None),
            patch(
                "gnosis.services.vault_sync.start_vault_watcher",
                new=AsyncMock(
                    return_value=type("O", (), {"stop": lambda s: None, "join": lambda s: None})()
                ),
            ),
            patch(
                "gnosis.services.graph_rag.graph_rag.initialize", new=AsyncMock(return_value=None)
            ),
        ):
            from gnosis import config

            settings = config.get_settings()
            settings.vault_path = str(vault)

            app2 = create_app()
            app2.dependency_overrides[require_user] = _non_admin

            async with AsyncClient(
                transport=ASGITransport(app=app2),
                base_url="http://test",
            ) as c:
                resp = await c.post(
                    "/api/v1/admin/reindex",
                    headers={"Authorization": "Bearer test-token"},
                )

            app2.dependency_overrides.clear()

    assert resp.status_code == 403
    assert "Admin-only" in resp.json()["detail"]
