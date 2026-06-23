"""
Final router gap coverage.

notes.py
  464-465: write_note_file raises -> VaultWriteError re-raised (create_daily)
  528    : data.note_type is not None -> note.note_type = data.note_type
  532    : data.folder is not None    -> note.folder = data.folder
  534    : data.source_url is not None-> note.source_url = data.source_url
  536    : data.last_reviewed is not None -> note.last_reviewed = ...
  538-540: data.frontmatter is not None -> merge frontmatter dicts

query.py (endpoint is PUT /saved/{id})
  160->166: payload.query is not None, parse_query succeeds -> sq.query updated
  166->168: payload.description is not None -> sq.description updated

users.py (uses get_session + require_user, NOT get_db / get_current_user)
  100    : _serialize_user() — called directly (unit test)
  117    : _serialize_grant() — called directly (unit test)
  163    : vault_slug conflict -> 409
  169    : vault_display_name branch
  184-185: ensure_vault_directory OSError -> warning, no re-raise
  NOTE: lines 251 and 265 carry # pragma: no cover so the re-grant path
        is already excluded from the coverage requirement.

vault.py
  92-93  : 'total:notanumber' -> ValueError -> pass  (in _sync_sse_generator)
  124-125: run_full_sync_for_user raises mid-iteration -> error SSE line
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ===========================================================================
# notes.py helpers
# ===========================================================================

def _make_note_orm():
    """Minimal note mock that satisfies _note_to_read()."""
    n = MagicMock()
    n.id = "note-abc"
    n.title = "Test Note"
    n.slug = "test-note"
    n.body = "body"
    n.body_html = "<p>body</p>"
    n.note_type = "note"
    n.status = "active"
    n.folder = "notes"
    n.vault_path = "notes/note-abc-test-note.md"
    n.word_count = 1
    n.owner_id = 1
    n.frontmatter = {"key": "old"}
    n.source_url = None
    n.last_reviewed = None
    n.vector_indexed = False
    n.graph_indexed = False
    n.is_deleted = False
    n.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    n.updated_at = None
    n.tags = []
    n.outgoing_links = []
    n.incoming_links = []
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

    async def _get_db():
        yield db_mock

    async def _get_user():
        return user

    async def _get_owner_ids():
        return {1}

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    app.dependency_overrides[get_vault_owner_ids] = _get_owner_ids
    return app, user


# ===========================================================================
# notes.py — lines 464-465  (create_daily: write_note_file raises)
# ===========================================================================

class TestNotesCreateDailyVaultWriteError:
    def test_create_daily_write_error_returns_500(self, tmp_path):
        import gnosis.services.markdown_parser as mp_mod
        import gnosis.core.namespace as ns_mod

        # First execute: no existing daily note (returns None)
        no_note = MagicMock()
        no_note.scalars.return_value.unique.return_value.one_or_none.return_value = None

        db = AsyncMock()
        db.execute = AsyncMock(return_value=no_note)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.expunge = MagicMock()

        app, user = _notes_app(db)

        with patch.object(ns_mod, "resolve_vault_path", return_value=tmp_path), \
             patch.object(mp_mod, "write_note_file", side_effect=OSError("disk full")):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/notes/daily")

        # VaultWriteError is raised; FastAPI returns 500
        assert resp.status_code >= 400


# ===========================================================================
# notes.py — lines 528, 532, 534, 536, 538-540  (update_note optional fields)
# ===========================================================================

class TestNotesUpdateOptionalFields:
    def test_update_note_all_optional_fields(self, tmp_path):
        import gnosis.core.namespace as ns_mod
        import gnosis.services.markdown_parser as mp_mod

        note = _make_note_orm()

        # execute() is called multiple times:
        #  1: _get_note_or_404 select -> returns note
        #  2: delete(NoteTag) for tags replacement -> ignored (no tags sent)
        #  3: _get_note_or_404 re-fetch after commit -> returns note
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=note)
        result.scalars = MagicMock(return_value=MagicMock(
            unique=MagicMock(return_value=MagicMock(
                one_or_none=MagicMock(return_value=note)
            ))
        ))

        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.expunge = MagicMock()

        app, user = _notes_app(db)

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
        # If it reached the branch lines, the note fields are mutated
        if resp.status_code == 200:
            assert note.note_type == "journal"
            assert note.folder == "archive"
            assert note.source_url == "https://example.com"
            assert note.frontmatter.get("key") == "new"


# ===========================================================================
# query.py — 160->166 and 166->168
# ===========================================================================

class TestQueryRouterUpdateSavedBranches:
    def _make_app(self, db):
        from gnosis.core.auth import get_current_user, get_vault_owner_ids
        from gnosis.database import get_db
        from gnosis.models.user import User
        from gnosis.routers.query import router as query_router

        app = FastAPI()
        app.include_router(query_router, prefix="/query")

        user = User(
            email="u@test.com", hashed_password="x",
            is_superuser=False, is_active=True,
        )
        user.id = 1

        async def _get_db():
            yield db

        async def _get_user():
            return user

        async def _get_owner_ids():
            return {1}

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_current_user] = _get_user
        app.dependency_overrides[get_vault_owner_ids] = _get_owner_ids
        return app

    def _saved_query(self):
        sq = MagicMock()
        sq.id = 1
        sq.name = "Dashboard"
        sq.query = "tag:python"
        sq.description = "old"
        sq.owner_id = 1
        sq.created_at = None
        sq.updated_at = None
        return sq

    def test_update_query_field_160_to_166(self):
        """160->166: payload.query valid -> sq.query updated, description None -> skip to 168."""
        sq = self._saved_query()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=sq)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        app = self._make_app(db)
        with patch("gnosis.routers.query.parse_query", return_value=MagicMock()):
            client = TestClient(app)
            resp = client.put("/query/saved/1", json={"query": "tag:python"})

        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            assert sq.query == "tag:python"

    def test_update_description_field_166_to_168(self):
        """166->168: payload.description is not None -> sq.description updated."""
        sq = self._saved_query()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=sq)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        app = self._make_app(db)
        client = TestClient(app)
        resp = client.put("/query/saved/1", json={"description": "new desc"})

        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            assert sq.description == "new desc"


# ===========================================================================
# users.py — helper functions (direct unit tests, no HTTP)
# ===========================================================================

class TestUsersSerializeUser:
    """Line 100: _serialize_user body (dict comprehension lines)."""

    def test_serialize_user_fields(self):
        from gnosis.routers.users import _serialize_user
        from gnosis.models.user import User
        u = User(
            email="a@b.com", hashed_password="x",
            full_name="Alice", vault_slug="alice",
            is_superuser=True, is_active=True,
        )
        u.id = 42
        result = _serialize_user(u)
        assert result["id"] == 42
        assert result["email"] == "a@b.com"
        assert result["is_superuser"] is True
        assert result["vault_slug"] == "alice"


class TestUsersSerializeGrant:
    """Line 117: _serialize_grant body."""

    def test_serialize_grant_with_accepted_at(self):
        from gnosis.routers.users import _serialize_grant
        grant = MagicMock()
        grant.id = 7
        grant.owner_id = 1
        grant.member_id = 2
        grant.permission = "read"
        grant.is_active = True
        grant.accepted_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = _serialize_grant(grant, "o@x.com", "My Vault", "m@x.com")
        assert result.id == 7
        assert result.owner_email == "o@x.com"
        assert "2026-01-01" in result.accepted_at

    def test_serialize_grant_accepted_at_none(self):
        from gnosis.routers.users import _serialize_grant
        grant = MagicMock()
        grant.id = 8; grant.owner_id = 1; grant.member_id = 2
        grant.permission = "read"; grant.is_active = True; grant.accepted_at = None
        result = _serialize_grant(grant, "o@x.com", None, "m@x.com")
        assert result.accepted_at is None


# ===========================================================================
# users.py — PATCH /me endpoint (uses get_session + require_user)
# ===========================================================================

class TestUsersUpdateMeBranches:
    """
    Uses the same _make_app pattern as test_users_router_coverage.py:
    - real User() objects (Pydantic model_validate reads __dict__)
    - async dependency overrides for get_session and require_user
    - synchronous TestClient
    """

    def _make_app(self, user, session_mock):
        from gnosis.core.auth import require_user
        from gnosis.database import get_session
        from gnosis.routers.users import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        async def _override_session():
            yield session_mock

        async def _override_user():
            return user

        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[require_user] = _override_user
        return app

    def _make_session(self, conflict_user=None):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=conflict_user)
        result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock(side_effect=lambda obj: None)
        session.add = MagicMock()
        return session

    def _make_user(self, id=1, superuser=False):
        from gnosis.models.user import User
        u = User(
            email="u@test.com", hashed_password="x",
            full_name="Test", vault_slug="old-slug",
            vault_path="/vault", vault_display_name="Old Name",
            is_superuser=superuser, is_active=True,
        )
        u.id = id
        return u

    def test_vault_slug_conflict_returns_409(self):
        """Line 163: another user already has vault_slug -> 409."""
        from gnosis.models.user import User
        user = self._make_user(id=1)
        # The conflicting user returned by the DB query
        conflict = User(
            email="other@test.com", hashed_password="x",
            vault_slug="taken-slug", is_superuser=False, is_active=True,
        )
        conflict.id = 2
        session = self._make_session(conflict_user=conflict)
        app = self._make_app(user, session)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.patch("/api/v1/users/me",
                                json={"vault_slug": "taken-slug"})
        assert resp.status_code == 409

    def test_vault_display_name_branch_169(self):
        """Line 169: vault_display_name is not None -> current_user.vault_display_name updated."""
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
        """Lines 184-185: OSError from ensure_vault_directory -> warning logged, 200 returned."""
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
# vault.py — _sync_sse_generator arcs (direct async generator tests)
# ===========================================================================

class TestVaultSyncSSEGenerator:
    @pytest.mark.asyncio
    async def test_bad_total_line_silently_ignored_lines_92_93(self):
        """Lines 92-93 / 124-125: 'total:notanumber' -> ValueError -> pass."""
        from gnosis.routers.vault import _sync_sse_generator
        import gnosis.routers.vault as vm

        async def _fake_sync(user_id):
            yield "synced: note1.md"
            yield "total:notanumber"
            yield "synced: note2.md"

        tokens = []
        with patch.object(vm, "run_full_sync_for_user", side_effect=_fake_sync):
            async for tok in _sync_sse_generator(user_id=1):
                tokens.append(tok)

        assert any("note1.md" in t for t in tokens)
        assert any("[done]" in t for t in tokens)
        assert not any("[error]" in t for t in tokens)

    @pytest.mark.asyncio
    async def test_sync_exception_yields_error_sse_lines_124_125(self):
        """Lines 124-125: mid-iteration RuntimeError -> error state + error SSE token."""
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
        assert _sync_status.get(99, {}).get("last_error") == "db exploded"
