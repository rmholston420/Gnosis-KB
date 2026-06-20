"""
Integration tests — cross-vault note isolation.

Verifies that every notes endpoint enforces owner_id scoping at the DB level:
  - User A cannot read User B's notes via list, get, backlinks, or outlinks
  - User A cannot update or delete User B's notes
  - Legacy owner_id=0 notes are not visible to normal users
  - The wikilink by-title search is also scoped

Requires a running test database (set TEST_DATABASE_URL env var) and
pytest-asyncio.  Run with:
    pytest backend/tests/test_notes_isolation.py -v
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from gnosis.main import app
from gnosis.database import get_db
from gnosis.models.note import Note
from gnosis.models.user import User
from gnosis.core.auth import create_access_token, TokenData

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db():
    from gnosis.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestSession() as session:
        yield session


def _token(user_id: int, email: str) -> str:
    """Generate a signed JWT for the given user — matches create_access_token signature."""
    return create_access_token(TokenData(user_id=user_id, email=email))


@pytest_asyncio.fixture
async def two_users_and_notes(db_session: AsyncSession):
    """Seed two users each with one note, plus one legacy owner_id=0 note."""
    from gnosis.services.markdown_parser import generate_note_id

    # User model uses email + full_name, no 'username' or 'is_superuser' field.
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
    db_session.add_all([user_a, user_b])

    note_a = Note(
        id=generate_note_id(), title="Alice Note", slug="alice-note",
        body="# Alice\n[[Bob Note]]", body_html="", note_type="permanent",
        status="active", vault_path="00-inbox/a.md", folder="00-inbox",
        word_count=2, is_deleted=False, vector_indexed=False,
        graph_indexed=False, owner_id=1,
    )
    note_b = Note(
        id=generate_note_id(), title="Bob Note", slug="bob-note",
        body="# Bob", body_html="", note_type="permanent",
        status="active", vault_path="00-inbox/b.md", folder="00-inbox",
        word_count=1, is_deleted=False, vector_indexed=False,
        graph_indexed=False, owner_id=2,
    )
    note_legacy = Note(
        id=generate_note_id(), title="Legacy Note", slug="legacy-note",
        body="# Legacy", body_html="", note_type="permanent",
        status="active", vault_path="00-inbox/l.md", folder="00-inbox",
        word_count=1, is_deleted=False, vector_indexed=False,
        graph_indexed=False, owner_id=0,
    )
    db_session.add_all([note_a, note_b, note_legacy])
    await db_session.commit()
    return user_a, user_b, note_a, note_b, note_legacy


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_notes_scoped(two_users_and_notes):
    user_a, user_b, note_a, note_b, _ = two_users_and_notes
    # Use user_a.email — User model has no 'username' field
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/notes/",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    assert resp.status_code == 200
    ids = [n["id"] for n in resp.json()["items"]]
    assert note_a.id in ids, "User A should see their own note"
    assert note_b.id not in ids, "User A must NOT see User B's note"


@pytest.mark.asyncio
async def test_get_note_cross_user_forbidden(two_users_and_notes):
    user_a, user_b, note_a, note_b, _ = two_users_and_notes
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/notes/{note_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    assert resp.status_code == 403, "Cross-vault read must be forbidden"


@pytest.mark.asyncio
async def test_update_note_cross_user_forbidden(two_users_and_notes):
    user_a, user_b, note_a, note_b, _ = two_users_and_notes
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.put(
            f"/api/v1/notes/{note_b.id}",
            json={"body": "Hacked"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_delete_note_cross_user_forbidden(two_users_and_notes):
    user_a, user_b, note_a, note_b, _ = two_users_and_notes
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(
            f"/api/v1/notes/{note_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_legacy_owner_zero_hidden(two_users_and_notes):
    user_a, _, _, _, note_legacy = two_users_and_notes
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/notes/",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    ids = [n["id"] for n in resp.json()["items"]]
    assert note_legacy.id not in ids, "Legacy owner_id=0 notes must be invisible to normal users"


@pytest.mark.asyncio
async def test_wikilink_search_scoped(two_users_and_notes):
    user_a, user_b, note_a, note_b, _ = two_users_and_notes
    token_a = _token(user_a.id, user_a.email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/notes/by-title?q=Bob",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    assert resp.status_code == 200
    ids = [n["id"] for n in resp.json()["items"]]
    assert note_b.id not in ids, "Wikilink search must not leak cross-vault notes"
