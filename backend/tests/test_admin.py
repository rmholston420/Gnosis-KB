"""Tests for POST /api/v1/admin/reindex.

Covers three scenarios:
  1. No legacy notes — endpoint returns fixed=0 immediately.
  2. One legacy note (owner_id=0) — note is reassigned to new_owner_id.
  3. Non-admin caller (FakeUser id=2) — endpoint returns 403.

Isolation strategy
------------------
The ``client`` fixture wires ``get_db`` to its own session factory so that
the HTTP layer and any direct DB seeds use the same in-memory SQLite
connection (StaticPool).

For tests 1 & 2 we need seeds written by ``test_db`` to be visible to the
router.  We achieve this by building a *shared* session factory from
``test_engine`` and injecting it into both the client's ``get_db`` override
and the seed helper — rather than using the separate ``test_db`` fixture
which opens a different session object.
"""

from __future__ import annotations

import tempfile
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gnosis.models.note import Note
from gnosis.models.user import User


# ---------------------------------------------------------------------------
# Shared-session client fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_client(test_engine, vault_dir) -> AsyncGenerator[tuple[AsyncClient, AsyncSession], None]:
    """Yield (client, session) that share the same SQLite connection.

    Both the HTTP layer's get_db override and the seed session use the same
    async_sessionmaker so that rows inserted before the request are visible
    to the router.
    """
    from unittest.mock import AsyncMock, patch

    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)

    p1 = patch("gnosis.services.vector_store.ensure_collection", return_value=None)
    p2 = patch(
        "gnosis.services.vault_sync.start_vault_watcher",
        new=AsyncMock(
            return_value=type("O", (), {"stop": lambda s: None, "join": lambda s: None})()
        ),
    )
    p3 = patch("gnosis.services.graph_rag.graph_rag.initialize", new=AsyncMock(return_value=None))

    with p1, p2, p3:
        from gnosis import config
        from gnosis.core.auth import get_current_user, get_vault_owner_ids, require_user
        from gnosis.main import create_app

        settings = config.get_settings()
        settings.vault_path = str(vault_dir)

        app = create_app()

        async def _override_get_db():
            async with session_factory() as session:
                yield session

        async def _fake_user():
            @dataclass
            class _FU:
                id: int = 1
                email: str = "test@gnosis.local"
                full_name: str | None = "Test User"
                vault_slug: str | None = "test"
                vault_path: str | None = None
                is_active: bool = True
                is_superuser: bool = False
            return _FU()

        async def _fake_owner_ids() -> set[int]:
            return {1}

        from gnosis.database import get_db
        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[require_user] = _fake_user
        app.dependency_overrides[get_current_user] = _fake_user
        app.dependency_overrides[get_vault_owner_ids] = _fake_owner_ids

        async with session_factory() as seed_session:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                yield c, seed_session

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession, user_id: int = 1) -> User:
    user = User(
        id=user_id,
        email=f"user{user_id}@gnosis.local",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _seed_legacy_note(session: AsyncSession) -> Note:
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
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


# ---------------------------------------------------------------------------
# Scenario 1 — no legacy notes
# ---------------------------------------------------------------------------


async def test_reindex_no_legacy_notes(admin_client) -> None:
    """When no notes have owner_id=0 the endpoint returns fixed=0."""
    client, session = admin_client
    await _seed_user(session)

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


async def test_reindex_reassigns_legacy_note(admin_client) -> None:
    """A note with owner_id=0 is updated to owner_id=1 and ingest is attempted."""
    client, session = admin_client
    await _seed_user(session, user_id=1)
    note = await _seed_legacy_note(session)

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
    assert note_result["status"] == "ok"


# ---------------------------------------------------------------------------
# Scenario 3 — non-admin user gets 403
# ---------------------------------------------------------------------------


async def test_reindex_forbidden_for_non_admin(
    async_client: AsyncClient,
) -> None:
    """A user with id != 1 receives HTTP 403 Forbidden."""
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

        p1 = patch("gnosis.services.vector_store.ensure_collection", return_value=None)
        p2 = patch(
            "gnosis.services.vault_sync.start_vault_watcher",
            new=AsyncMock(
                return_value=type("O", (), {"stop": lambda s: None, "join": lambda s: None})()
            ),
        )
        p3 = patch(
            "gnosis.services.graph_rag.graph_rag.initialize", new=AsyncMock(return_value=None)
        )

        with p1, p2, p3:
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
