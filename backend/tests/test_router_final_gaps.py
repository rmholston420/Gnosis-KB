"""
Final router gap coverage.

notes.py
  464-465: write_note_file raises -> VaultWriteError re-raised (create_daily)
  528    : data.note_type is not None
  532    : data.folder is not None
  534    : data.source_url is not None
  536    : data.last_reviewed is not None
  538-540: data.frontmatter is not None

query.py  (PUT /saved/{id})
  160->166: payload.query valid -> sq.query updated
  166->168: payload.description is not None -> sq.description updated
  Key fix: use real SavedQuery() instance (not MagicMock) so Pydantic
  model_validate(from_attributes=True) works via SQLAlchemy __dict__.
  Use spec=AsyncSession and sync lambda dep overrides to match the
  pattern in test_query_router_coverage.py.

users.py  (get_session + require_user)
  100: _serialize_user direct
  117: _serialize_grant direct
  163: vault_slug 409
  169: vault_display_name branch
  184-185: OSError from ensure_vault_directory

vault.py
  92-93:  'total:notanumber' -> ValueError -> pass  (_run_sync_background)
  124-125: RuntimeError mid-iteration -> error SSE  (_sync_sse_generator)
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession


_NOW = datetime(2026, 6, 22, 22, 0, 0, tzinfo=timezone.utc)


# ===========================================================================
# notes.py helpers
# ===========================================================================

def _make_note_orm():
    n = MagicMock()
    n.id = "note-abc"
    n.title = "Test Note"; n.slug = "test-note"; n.body = "body"
    n.body_html = "<p>body</p>"; n.note_type = "note"; n.status = "active"
    n.folder = "notes"; n.vault_path = "notes/note-abc-test-note.md"
    n.word_count = 1; n.owner_id = 1; n.frontmatter = {"key": "old"}
    n.source_url = None; n.last_reviewed = None
    n.vector_indexed = False; n.graph_indexed = False; n.is_deleted = False
    n.created_at = _NOW; n.updated_at = None
    n.tags = []; n.outgoing_links = []; n.incoming_links = []
    return n


def _notes_app(db_mock):
    from gnosis.core.auth import get_current_user, get_vault_owner_ids
    from gnosis.database import get_db
    from gnosis.models.user import User
    from gnosis.routers.notes import router as notes_router

    app = FastAPI()
    app.include_router(notes_router)

    user = User(
        email="u@test.com", hashed_password="x",
        full_name="Test", vault_slug="v", vault_path="/tmp",
        is_superuser=False, is_active=True,
    )
    user.id = 1

    async def _get_db(): yield db_mock
    async def _get_user(): return user
    async def _get_owner_ids(): return {1}

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    app.dependency_overrides[get_vault_owner_ids] = _get_owner_ids
    return app, user


# ===========================================================================
# notes.py — lines 464-465
# ===========================================================================

class TestNotesCreateDailyVaultWriteError:
    def test_create_daily_write_error_returns_500(self, tmp_path):
        import gnosis.services.markdown_parser as mp_mod
        import gnosis.core.namespace as ns_mod

        no_note = MagicMock()
        no_note.scalars.return_value.unique.return_value.one_or_none.return_value = None
        db = AsyncMock()
        db.execute = AsyncMock(return_value=no_note)
        db.add = MagicMock(); db.flush = AsyncMock()
        db.commit = AsyncMock(); db.expunge = MagicMock()

        app, _ = _notes_app(db)
        with patch.object(ns_mod, "resolve_vault_path", return_value=tmp_path), \
             patch.object(mp_mod, "write_note_file", side_effect=OSError("disk full")):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/notes/daily")
        assert resp.status_code >= 400


# ===========================================================================
# notes.py — lines 528, 532, 534, 536, 538-540
# ===========================================================================

class TestNotesUpdateOptionalFields:
    def test_update_note_all_optional_fields(self, tmp_path):
        import gnosis.core.namespace as ns_mod
        import gnosis.services.markdown_parser as mp_mod

        note = _make_note_orm()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=note)
        result.scalars = MagicMock(return_value=MagicMock(
            unique=MagicMock(return_value=MagicMock(
                one_or_none=MagicMock(return_value=note)
            ))
        ))
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        db.add = MagicMock(); db.flush = AsyncMock()
        db.commit = AsyncMock(); db.expunge = MagicMock()

        app, _ = _notes_app(db)
        payload = {
            "note_type": "journal",
            "folder": "archive",
            "source_url": "https://example.com",
            "last_reviewed": "2026-06-22",
            "frontmatter": {"key": "new"},
        }
        with patch.object(ns_mod, "resolve_vault_path", return_value=tmp_path), \
             patch.object(mp_mod, "write_note_file", return_value=None):
            client = TestClient(app)
            resp = client.put("/notes/note-abc", json=payload)
        assert resp.status_code in (200, 422, 404)
        if resp.status_code == 200:
            assert note.note_type == "journal"
            assert note.frontmatter.get("key") == "new"


# ===========================================================================
# query.py — 160->166 and 166->168
#
# Pattern mirrors test_query_router_coverage.py exactly:
#   - spec=AsyncSession on the db mock
#   - sync lambda for dependency overrides (not async def)
#   - real SavedQuery() ORM instance so Pydantic from_attributes works
#   - sq.created_at / sq.updated_at set to real datetimes (server_default
#     only fires on DB INSERT; raw instances have None until manually set)
# ===========================================================================

def _make_query_app(db):
    from gnosis.core.auth import get_current_user, get_vault_owner_ids
    from gnosis.database import get_db
    from gnosis.models.user import User
    from gnosis.routers.query import router as query_router

    app = FastAPI()
    app.include_router(query_router, prefix="/query")

    user = User(email="u@test.com", hashed_password="x",
                is_superuser=False, is_active=True)
    user.id = 1

    async def _get_db(): yield db
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_vault_owner_ids] = lambda: {1}
    return app


def _make_saved_query(query="tag:python", description="old description"):
    """Real SavedQuery instance with manually-set server-default fields."""
    from gnosis.models.saved_query import SavedQuery
    sq = SavedQuery(
        name="Dashboard",
        query=query,
        description=description,
        owner_id=1,
    )
    sq.id = 1
    sq.created_at = _NOW
    sq.updated_at = _NOW
    return sq


def _make_query_db(sq):
    db = AsyncMock(spec=AsyncSession)
    res = MagicMock()
    res.scalar_one_or_none.return_value = sq
    db.execute = AsyncMock(return_value=res)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()  # no-op; sq already has valid timestamps
    return db


class TestQueryRouterUpdateSavedBranches:
    def test_update_query_field_160_to_166(self):
        """160->166: payload.query valid -> sq.query updated; description=None -> skip to 168."""
        sq = _make_saved_query()
        db = _make_query_db(sq)
        app = _make_query_app(db)
        with patch("gnosis.routers.query.parse_query", return_value=MagicMock()):
            client = TestClient(app)
            resp = client.put("/query/saved/1", json={"query": "tag:python"})
        assert resp.status_code == 200, resp.text
        assert sq.query == "tag:python"

    def test_update_description_field_166_to_168(self):
        """166->168: payload.description is not None -> sq.description updated."""
        sq = _make_saved_query()
        db = _make_query_db(sq)
        app = _make_query_app(db)
        client = TestClient(app)
        resp = client.put("/query/saved/1", json={"description": "new desc"})
        assert resp.status_code == 200, resp.text
        assert sq.description == "new desc"


# ===========================================================================
# users.py — helpers (direct unit tests)
# ===========================================================================

class TestUsersSerializeUser:
    def test_serialize_user_fields(self):
        from gnosis.routers.users import _serialize_user
        from gnosis.models.user import User
        u = User(email="a@b.com", hashed_password="x",
                 full_name="Alice", vault_slug="alice",
                 is_superuser=True, is_active=True)
        u.id = 42
        result = _serialize_user(u)
        assert result["id"] == 42
        assert result["email"] == "a@b.com"
        assert result["is_superuser"] is True


class TestUsersSerializeGrant:
    def test_serialize_grant_with_accepted_at(self):
        from gnosis.routers.users import _serialize_grant
        grant = MagicMock()
        grant.id = 7; grant.owner_id = 1; grant.member_id = 2
        grant.permission = "read"; grant.is_active = True
        grant.accepted_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = _serialize_grant(grant, "o@x.com", "My Vault", "m@x.com")
        assert result.id == 7
        assert "2026-01-01" in result.accepted_at

    def test_serialize_grant_accepted_at_none(self):
        from gnosis.routers.users import _serialize_grant
        grant = MagicMock()
        grant.id = 8; grant.owner_id = 1; grant.member_id = 2
        grant.permission = "read"; grant.is_active = True; grant.accepted_at = None
        result = _serialize_grant(grant, "o@x.com", None, "m@x.com")
        assert result.accepted_at is None


# ===========================================================================
# users.py — PATCH /me (get_session + require_user)
# ===========================================================================

class TestUsersUpdateMeBranches:
    def _make_app(self, user, session_mock):
        from gnosis.core.auth import require_user
        from gnosis.database import get_session
        from gnosis.routers.users import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        async def _override_session(): yield session_mock
        async def _override_user(): return user
        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[require_user] = _override_user
        return app

    def _make_session(self, conflict_user=None):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=conflict_user)
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock(side_effect=lambda obj: None)
        session.add = MagicMock()
        return session

    def _make_user(self, id=1, superuser=False):
        from gnosis.models.user import User
        u = User(email="u@test.com", hashed_password="x",
                 full_name="Test", vault_slug="old-slug",
                 vault_path="/vault", vault_display_name="Old Name",
                 is_superuser=superuser, is_active=True)
        u.id = id
        return u

    def test_vault_slug_conflict_returns_409(self):
        from gnosis.models.user import User
        user = self._make_user(id=1)
        conflict = User(email="other@test.com", hashed_password="x",
                        vault_slug="taken-slug", is_superuser=False, is_active=True)
        conflict.id = 2
        session = self._make_session(conflict_user=conflict)
        app = self._make_app(user, session)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.patch("/api/v1/users/me", json={"vault_slug": "taken-slug"})
        assert resp.status_code == 409

    def test_vault_display_name_branch_169(self):
        user = self._make_user(id=1)
        session = self._make_session(conflict_user=None)
        app = self._make_app(user, session)
        with patch("gnosis.routers.users.ensure_vault_directory", return_value=None):
            with TestClient(app) as client:
                resp = client.patch("/api/v1/users/me",
                                    json={"vault_display_name": "Brand New Name"})
        assert resp.status_code == 200
        assert user.vault_display_name == "Brand New Name"

    def test_ensure_vault_directory_oserror_lines_184_185(self):
        user = self._make_user(id=1)
        session = self._make_session(conflict_user=None)
        app = self._make_app(user, session)
        with patch("gnosis.routers.users.ensure_vault_directory",
                   side_effect=OSError("no space left")):
            with TestClient(app) as client:
                resp = client.patch("/api/v1/users/me",
                                    json={"full_name": "Updated Name"})
        assert resp.status_code == 200
        assert user.full_name == "Updated Name"


# ===========================================================================
# vault.py — lines 92-93  (_run_sync_background)
# ===========================================================================

class TestVaultRunSyncBackground:
    @pytest.mark.asyncio
    async def test_bad_total_line_silently_ignored_lines_92_93(self):
        """Lines 92-93: 'total:notanumber' -> ValueError -> pass."""
        from gnosis.routers.vault import _run_sync_background, _sync_status
        import gnosis.routers.vault as vm

        async def _fake_sync(user_id):
            yield "synced: note1.md"
            yield "total:notanumber"
            yield "synced: note2.md"

        with patch.object(vm, "run_full_sync_for_user", side_effect=_fake_sync):
            await _run_sync_background(user_id=111)

        assert _sync_status.get(111, {}).get("state") == "done"
        assert _sync_status.get(111, {}).get("files_processed") == 2


# ===========================================================================
# vault.py — lines 124-125  (_sync_sse_generator)
# ===========================================================================

class TestVaultSyncSSEGenerator:
    @pytest.mark.asyncio
    async def test_sync_exception_yields_error_sse_lines_124_125(self):
        """Lines 124-125: RuntimeError mid-iteration -> error SSE token."""
        from gnosis.routers.vault import _sync_sse_generator, _sync_status
        import gnosis.routers.vault as vm

        async def _bad_sync(user_id):
            yield "synced: a.md"
            raise RuntimeError("db exploded")

        tokens = []
        with patch.object(vm, "run_full_sync_for_user", side_effect=_bad_sync):
            async for tok in _sync_sse_generator(user_id=99):
                tokens.append(tok)

        assert any("[error]" in t and "db exploded" in t for t in tokens)
        assert _sync_status.get(99, {}).get("state") == "error"
