"""Tests for routers/admin.py — admin reindex endpoint."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from gnosis.models.note import Note
from gnosis.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_user(db, user_id: int = 1, email: str = "admin@gnosis.local") -> User:
    user = User(
        id=user_id,
        email=email,
        hashed_password="hashed",
        full_name="Admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_note(
    db,
    note_id: str = "legacy-1",
    owner_id: int = 0,
    title: str = "Legacy Note",
) -> Note:
    note = Note(
        id=note_id,
        title=title,
        slug=note_id,
        body="legacy body",
        body_html="<p>legacy body</p>",
        folder="00-inbox",
        owner_id=owner_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


# ---------------------------------------------------------------------------
# POST /api/v1/admin/reindex
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reindex_no_legacy_notes(client, test_db):
    await _make_user(test_db)
    r = await client.post("/api/v1/admin/reindex")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["fixed"] == 0


@pytest.mark.asyncio
async def test_reindex_fixes_legacy_notes(client, test_db):
    """Legacy notes with owner_id=0 are re-attributed to the primary user."""
    await _make_user(test_db)
    await _make_note(test_db, note_id="legacy-1", owner_id=0)
    await _make_note(test_db, note_id="legacy-2", owner_id=0)

    # graph_rag is imported lazily inside _reindex_note — patch at source module
    with patch("gnosis.services.graph_rag.graph_rag") as mock_rag:
        mock_rag.ingest_note = AsyncMock(return_value=None)
        r = await client.post("/api/v1/admin/reindex")

    assert r.status_code == 200
    data = r.json()
    assert data["fixed"] == 2
    assert data["new_owner_id"] == 1


@pytest.mark.asyncio
async def test_reindex_requires_admin_user(test_engine, vault_dir):
    """Non-admin user (id != 1) receives 403."""
    from dataclasses import dataclass
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from gnosis.database import get_db
    from gnosis.main import create_app
    from gnosis.core.auth import require_user, get_current_user
    from unittest.mock import patch, AsyncMock

    @dataclass
    class _NonAdminUser:
        id: int = 99
        email: str = "other@gnosis.local"
        full_name: str = "Other"
        vault_slug: str = "other"
        vault_path: str | None = None
        is_active: bool = True
        is_superuser: bool = False

    async def _fake_non_admin():
        return _NonAdminUser()

    p1 = patch("gnosis.services.vector_store.ensure_collection", return_value=None)
    p2 = patch("gnosis.services.vault_sync.start_vault_watcher")
    p3 = patch("gnosis.services.graph_rag.graph_rag.initialize", new=AsyncMock(return_value=None))

    with p1, p2, p3:
        from gnosis import config
        settings = config.get_settings()
        settings.vault_path = str(vault_dir)

        app = create_app()
        session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[require_user] = _fake_non_admin
        app.dependency_overrides[get_current_user] = _fake_non_admin

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/admin/reindex")

        app.dependency_overrides.clear()

    assert r.status_code == 403


@pytest.mark.asyncio
async def test_reindex_unauthenticated(unauthenticated_client):
    r = await unauthenticated_client.post("/api/v1/admin/reindex")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_reindex_lightrag_error_is_non_fatal(client, test_db):
    """Even if LightRAG ingest raises, the note is still fixed."""
    await _make_user(test_db)
    await _make_note(test_db, note_id="legacy-err", owner_id=0)

    # graph_rag imported lazily inside _reindex_note — patch at source
    with patch("gnosis.services.graph_rag.graph_rag") as mock_rag:
        mock_rag.ingest_note = AsyncMock(side_effect=RuntimeError("lightrag down"))
        r = await client.post("/api/v1/admin/reindex")

    assert r.status_code == 200
    data = r.json()
    assert data["fixed"] >= 1
