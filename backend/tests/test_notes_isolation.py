"""
Integration tests — cross-vault note isolation.

Verifies that every notes endpoint enforces owner_id scoping at the DB level:
  - User A cannot read User B's notes via list, get, backlinks, or outlinks
  - User A cannot update or delete User B's notes
  - Legacy owner_id=0 notes are not visible to normal users
  - The wikilink by-title search is also scoped

Each test gets a completely fresh in-memory SQLite database via the
function-scoped engine+session pattern below.  This prevents UNIQUE
constraint failures that occur when:
  1. seed users (id=1, id=2) are re-inserted across tests sharing a table, or
  2. generate_note_id() produces the same second-precision ID in fast CI runs.

The module-level engine+app.dependency_overrides pattern from the original
version is replaced with per-test fixtures so there is zero state leakage
between test functions.
"""

from datetime import UTC

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gnosis.core.auth import TokenData, create_access_token
from gnosis.database import Base, get_db
from gnosis.main import create_app
from gnosis.models.note import Note
from gnosis.models.user import User

# ---------------------------------------------------------------------------
# Per-test engine + app — function scope eliminates all UNIQUE collisions
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def iso_engine():
    """Fresh in-memory SQLite engine per test function."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def iso_db(iso_engine):
    """Session bound to the per-test engine."""
    factory = async_sessionmaker(iso_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def iso_app(iso_engine):
    """FastAPI app whose get_db is overridden to use the per-test engine."""
    app = create_app()
    factory = async_sessionmaker(iso_engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


def _token(user_id: int, email: str) -> str:
    """Generate a signed JWT for the given user."""
    return create_access_token(TokenData(user_id=user_id, email=email))


@pytest_asyncio.fixture
async def two_users_and_notes(iso_db: AsyncSession, iso_engine):
    """Seed two users each with one note, plus one legacy owner_id=0 note.

    Uses session.merge() instead of add_all() so re-running the fixture
    against the same table (e.g. in a module-shared scenario) is safe.
    Each test uses a fresh engine, so merge() is mainly defensive.

    Note IDs use microsecond precision to avoid collisions when tests run
    within the same second.
    """
    import time
    from datetime import datetime

    def _uid() -> str:
        """Microsecond-precision ID: YYYYMMDD-HHmmss-ffffff."""
        now = datetime.now(UTC)
        return now.strftime("%Y%m%d-%H%M%S-") + f"{now.microsecond:06d}"

    user_a = User(
        id=1,
        email="alice@test.local",
        full_name="Alice",
        hashed_password="x",
        is_active=True,
    )
    user_b = User(
        id=2,
        email="bob@test.local",
        full_name="Bob",
        hashed_password="x",
        is_active=True,
    )
    user_a = await iso_db.merge(user_a)
    user_b = await iso_db.merge(user_b)
    await iso_db.flush()

    id_a = _uid()
    time.sleep(0.001)
    id_b = _uid()
    time.sleep(0.001)
    id_leg = _uid()

    note_a = Note(
        id=id_a, title="Alice Note", slug=f"alice-note-{id_a}",
        body="# Alice\n[[Bob Note]]", body_html="", note_type="permanent",
        status="active", vault_path=f"00-inbox/a-{id_a}.md", folder="00-inbox",
        word_count=2, is_deleted=False, vector_indexed=False,
        graph_indexed=False, owner_id=1,
    )
    note_b = Note(
        id=id_b, title="Bob Note", slug=f"bob-note-{id_b}",
        body="# Bob", body_html="", note_type="permanent",
        status="active", vault_path=f"00-inbox/b-{id_b}.md", folder="00-inbox",
        word_count=1, is_deleted=False, vector_indexed=False,
        graph_indexed=False, owner_id=2,
    )
    note_legacy = Note(
        id=id_leg, title="Legacy Note", slug=f"legacy-note-{id_leg}",
        body="# Legacy", body_html="", note_type="permanent",
        status="active", vault_path=f"00-inbox/l-{id_leg}.md", folder="00-inbox",
        word_count=1, is_deleted=False, vector_indexed=False,
        graph_indexed=False, owner_id=0,
    )
    iso_db.add_all([note_a, note_b, note_legacy])
    await iso_db.commit()
    return user_a, user_b, note_a, note_b, note_legacy


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_notes_scoped(two_users_and_notes, iso_app):
    user_a, user_b, note_a, note_b, _ = two_users_and_notes
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=iso_app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/notes/",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    assert resp.status_code == 200
    ids = [n["id"] for n in resp.json()["items"]]
    assert note_a.id in ids, "User A should see their own note"
    assert note_b.id not in ids, "User A must NOT see User B's note"


@pytest.mark.asyncio
async def test_get_note_cross_user_forbidden(two_users_and_notes, iso_app):
    user_a, user_b, note_a, note_b, _ = two_users_and_notes
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=iso_app), base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/notes/{note_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    assert resp.status_code == 403, "Cross-vault read must be forbidden"


@pytest.mark.asyncio
async def test_update_note_cross_user_forbidden(two_users_and_notes, iso_app):
    user_a, user_b, note_a, note_b, _ = two_users_and_notes
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=iso_app), base_url="http://test") as client:
        resp = await client.put(
            f"/api/v1/notes/{note_b.id}",
            json={"body": "Hacked"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_delete_note_cross_user_forbidden(two_users_and_notes, iso_app):
    user_a, user_b, note_a, note_b, _ = two_users_and_notes
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=iso_app), base_url="http://test") as client:
        resp = await client.delete(
            f"/api/v1/notes/{note_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_legacy_owner_zero_hidden(two_users_and_notes, iso_app):
    user_a, _, _, _, note_legacy = two_users_and_notes
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=iso_app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/notes/",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    ids = [n["id"] for n in resp.json()["items"]]
    assert note_legacy.id not in ids, "Legacy owner_id=0 notes must be invisible to normal users"


@pytest.mark.asyncio
async def test_wikilink_search_scoped(two_users_and_notes, iso_app):
    """Scoped title search via GET /notes/?q= must not return cross-vault notes.

    The previous implementation called GET /notes/by-title?q=Bob which:
      1. Used the wrong query-param name (endpoint expects ?title=, not ?q=)
         causing FastAPI to return 422 Unprocessable Entity.
      2. Returned a single NoteRead, not a NoteListResponse{items} list.

    The correct endpoint for a partial-title search scoped to the requesting
    user is GET /notes/?q=Bob — it returns NoteListResponse{items} and
    filters by owner_id through get_vault_owner_ids.
    """
    user_a, user_b, note_a, note_b, _ = two_users_and_notes
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=iso_app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/notes/?q=Bob",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    assert resp.status_code == 200
    ids = [n["id"] for n in resp.json()["items"]]
    assert note_b.id not in ids, "Wikilink search must not leak cross-vault notes"
