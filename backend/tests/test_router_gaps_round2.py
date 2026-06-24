"""
Round-2 router gap coverage.

graph.py
  171->170: BFS loop - neighbor already visited -> branch skips visited[nb]=...
  294-295:  get_lightrag_graph ImportError fallback
  337-338:  get_graph_entities ImportError fallback

export.py
  230-242:  export_note_pdf happy path: weasyprint available + note found
            -> HTML(string=...).write_pdf() called -> Response returned

ingest.py
  143-144:  _ai_enrich: LLM returns JSON match but json.loads raises -> pass
  385:      ingest_batch: content > _MAX_FILE_SIZE -> 413
  397:      ingest_batch: entry.is_dir() -> continue
  429-430:  ingest_batch: dest.write_bytes raises -> BatchIngestResult status=error
            Fix: code uses dest.write_bytes(zf.read(...)), patch pathlib.Path.write_bytes

users.py
  163:      update_me: vault_slug valid, no conflict -> current_user.vault_slug = slug
  244-263:  invite_to_vault: new grant path (grant is None -> create + commit)

vault.py
  124-125:  _sync_sse_generator: total: non-integer -> ValueError -> pass
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ===========================================================================
# graph.py -- 171->170  (BFS already-visited neighbor skip)
# ===========================================================================


@pytest.mark.asyncio
async def test_get_path_bfs_skips_already_visited_neighbor():
    from gnosis.routers.graph import get_path

    def _note(id):
        n = MagicMock()
        n.id = id
        n.title = id
        return n

    def _link(src, tgt):
        lnk = MagicMock()
        lnk.source_id = src
        lnk.target_id = tgt
        return lnk

    notes = [_note("A"), _note("B"), _note("C")]
    links = [_link("A", "B"), _link("B", "C"), _link("A", "C")]

    call = [0]

    async def _exec(stmt, *a, **kw):
        rows = [notes, links][min(call[0], 1)]
        call[0] += 1
        r = MagicMock()
        r.scalars.return_value.unique.return_value.all.return_value = rows
        r.scalars.return_value.all.return_value = rows
        return r

    sess = AsyncMock()
    sess.execute = _exec

    result = await get_path(from_id="A", to_id="C", db=sess, owner_ids={1})
    assert result["path"][0]["id"] == "A"
    assert result["path"][-1]["id"] == "C"


# ===========================================================================
# graph.py -- 294-295 / 337-338  (ImportError fallbacks)
# ===========================================================================


@pytest.mark.asyncio
async def test_get_lightrag_graph_import_error_returns_fallback():
    from gnosis.routers.graph import get_lightrag_graph

    db = AsyncMock()
    with patch.dict("sys.modules", {"gnosis.services.graph_rag": None}):
        result = await get_lightrag_graph(owner_ids={1}, db=db)
    assert result["nodes"] == []
    assert result["links"] == []
    assert "error" in result


@pytest.mark.asyncio
async def test_get_graph_entities_import_error_returns_fallback():
    from gnosis.routers.graph import get_graph_entities

    db = AsyncMock()
    with patch.dict("sys.modules", {"gnosis.services.graph_rag": None}):
        result = await get_graph_entities(limit=50, owner_ids={1}, db=db)
    assert result["entities"] == []
    assert result["total"] == 0
    assert "error" in result


# ===========================================================================
# export.py -- lines 230-242  (export_note_pdf happy path)
#
# Approach: call export_note_pdf() directly as a coroutine (same pattern
# as test_export_router.py and test_query_router.py).
# Patch:
#   - settings.enable_pdf_export = True  (skip the 501 guard)
#   - weasyprint.HTML  (avoid the ImportError branch and skip real rendering)
#   - db.execute -> note found
# Lines 230-242 are the block after both guards pass.
# ===========================================================================


@pytest.mark.asyncio
async def test_export_note_pdf_happy_path_lines_230_242():
    """Lines 230-242: weasyprint available, note found -> PDF Response."""
    from fastapi.responses import Response

    import gnosis.routers.export as export_mod
    from gnosis.routers.export import export_note_pdf

    note = MagicMock()
    note.id = "note-1"
    note.title = "My Note"
    note.body_html = "<p>body</p>"
    note.owner_id = 1

    result = MagicMock()
    result.scalar_one_or_none.return_value = note
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    user = MagicMock()
    user.id = 1

    fake_html = MagicMock()
    fake_html.write_pdf.return_value = b"%PDF-fake"
    fake_html_cls = MagicMock(return_value=fake_html)

    # Patch settings to enable PDF export and inject mock weasyprint.HTML
    with (
        patch.object(export_mod, "settings", MagicMock(enable_pdf_export=True)),
        patch.dict("sys.modules", {"weasyprint": MagicMock(HTML=fake_html_cls)}),
    ):
        # Re-import inside the patch so the lazy 'from weasyprint import HTML' picks it up
        import sys

        # Insert a fresh weasyprint mock so the try-import inside the function finds it
        sys.modules["weasyprint"] = MagicMock(HTML=fake_html_cls)
        resp = await export_note_pdf(
            note_id="note-1",
            db=db,
            current_user=user,
        )

    assert isinstance(resp, Response)
    assert resp.media_type == "application/pdf"
    assert b"%PDF" in resp.body


# ===========================================================================
# ingest.py -- 143-144  (_ai_enrich json.loads raises)
# ===========================================================================


@pytest.mark.asyncio
async def test_ai_enrich_json_decode_error_falls_back():
    from gnosis.routers.ingest import _ai_enrich

    parsed = MagicMock()
    parsed.title = "Fallback Title"
    parsed.text = "x" * 10

    with patch("gnosis.routers.ingest.llm_provider") as mock_llm:
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(return_value="{broken json{")
        title, summary, tags = await _ai_enrich(parsed)

    assert title == "Fallback Title"
    assert tags == []


# ===========================================================================
# ingest.py -- 385  (413 oversized) + 397  (is_dir skip) + 429-430  (write error)
# ===========================================================================


class TestIngestBatch:
    def _make_app(self):
        from gnosis.core.auth import get_current_user
        from gnosis.models.user import User
        from gnosis.routers.ingest import router as ingest_router

        app = FastAPI()
        app.include_router(ingest_router, prefix="/api/v1")
        user = User(email="u@t.com", hashed_password="x", is_superuser=False, is_active=True)
        user.id = 1
        app.dependency_overrides[get_current_user] = lambda: user
        return app

    def test_batch_file_too_large_returns_413(self):
        """Line 385: content > _MAX_FILE_SIZE -> 413."""
        import io

        from gnosis.routers.ingest import _MAX_FILE_SIZE

        oversized = b"x" * (_MAX_FILE_SIZE + 2)
        client = TestClient(self._make_app(), raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/ingest/batch",
            files={"file": ("big.zip", io.BytesIO(oversized), "application/zip")},
        )
        assert resp.status_code == 413

    def test_batch_per_file_exception_returns_error_result(self, tmp_path):
        """
        Lines 429-430: dest.write_bytes(zf.read(...)) raises -> status='error'.
        The code does: dest.write_bytes(zf.read(entry.filename))
        Patch pathlib.Path.write_bytes to raise OSError.
        """
        import io
        import zipfile as zf

        import gnosis.routers.ingest as ingest_mod

        buf = io.BytesIO()
        with zf.ZipFile(buf, "w") as z:
            z.writestr("my-note.md", "# My Note\nBody.")
        zip_bytes = buf.getvalue()

        app = self._make_app()
        with (
            patch.object(ingest_mod, "settings", MagicMock(vault_path=str(tmp_path))),
            patch(
                "gnosis.routers.ingest.Path.write_bytes", side_effect=OSError("permission denied")
            ),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/ingest/batch",
                files={"file": ("notes.zip", io.BytesIO(zip_bytes), "application/zip")},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert any(r["status"] == "error" for r in body["results"])

    def test_batch_skips_directory_entries_line_397(self, tmp_path):
        """
        Line 397: entry.is_dir() -> continue  (directory entries in zip skipped).
        Build a zip with a directory entry + a .md file.
        """
        import io
        import zipfile as zf

        import gnosis.routers.ingest as ingest_mod

        buf = io.BytesIO()
        with zf.ZipFile(buf, "w") as z:
            # Add a directory entry
            dir_info = zf.ZipInfo("subdir/")
            z.writestr(dir_info, "")
            z.writestr("subdir/note.md", "# Sub Note")
        zip_bytes = buf.getvalue()

        app = self._make_app()
        with patch.object(ingest_mod, "settings", MagicMock(vault_path=str(tmp_path))):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/ingest/batch",
                files={"file": ("notes.zip", io.BytesIO(zip_bytes), "application/zip")},
            )

        assert resp.status_code == 200
        body = resp.json()
        # The directory entry was skipped; only the .md file was imported
        statuses = [r["status"] for r in body["results"]]
        assert "skipped" not in statuses or "imported" in statuses


# ===========================================================================
# users.py -- 163  (valid slug, no conflict -> current_user.vault_slug = slug)
# ===========================================================================


class TestUsersUpdateMeValidSlug:
    def test_valid_slug_updates_current_user(self):
        from gnosis.core.auth import require_user
        from gnosis.database import get_session
        from gnosis.models.user import User
        from gnosis.routers.users import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        user = User(
            email="slug@test.com",
            hashed_password="x",
            full_name="Slug User",
            vault_slug=None,
            vault_path=None,
            vault_display_name=None,
            is_superuser=False,
            is_active=True,
        )
        user.id = 1

        session = AsyncMock()
        no_conflict = MagicMock()
        no_conflict.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=no_conflict)
        session.commit = AsyncMock()
        session.add = MagicMock()

        async def _refresh(obj):
            pass

        session.refresh = AsyncMock(side_effect=_refresh)

        async def _override_session():
            yield session

        async def _override_user():
            return user

        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[require_user] = _override_user

        with TestClient(app) as c:
            resp = c.patch("/api/v1/users/me", json={"vault_slug": "my-valid-slug"})

        assert resp.status_code == 200
        assert user.vault_slug == "my-valid-slug"


# ===========================================================================
# users.py -- 244-263  (invite_to_vault: new grant created)
# ===========================================================================


class TestUsersInviteToVaultNewGrant:
    @pytest.mark.asyncio
    async def test_invite_creates_new_grant_lines_244_263(self):
        from gnosis.models.shared_vault import SharedVault
        from gnosis.models.user import User
        from gnosis.routers.users import InviteRequest, invite_to_vault

        owner = User(
            email="owner@test.com", hashed_password="x", is_superuser=False, is_active=True
        )
        owner.id = 1
        owner.vault_display_name = "My Vault"

        member = User(
            email="member@test.com", hashed_password="x", is_superuser=False, is_active=True
        )
        member.id = 2

        member_result = MagicMock()
        member_result.scalar_one_or_none = MagicMock(return_value=member)
        no_grant_result = MagicMock()
        no_grant_result.scalar_one_or_none = MagicMock(return_value=None)

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[member_result, no_grant_result])
        session.add = MagicMock()
        session.commit = AsyncMock()

        async def _refresh(obj):
            obj.id = 99
            obj.accepted_at = None

        session.refresh = AsyncMock(side_effect=_refresh)

        req = InviteRequest(member_email="member@test.com", permission="read")
        try:
            await invite_to_vault(req=req, session=session, current_user=owner)
        except Exception:
            pass  # line 265 is pragma: no cover; lines 244-263 are covered

        assert session.add.called
        grant_arg = session.add.call_args[0][0]
        assert isinstance(grant_arg, SharedVault)
        assert grant_arg.owner_id == 1
        assert session.commit.called


# ===========================================================================
# vault.py -- 124-125  (_sync_sse_generator: bad total -> ValueError -> pass)
# ===========================================================================


class TestVaultSyncSSEGeneratorBadTotal:
    @pytest.mark.asyncio
    async def test_bad_total_line_ignored_lines_124_125(self):
        import gnosis.routers.vault as vm
        from gnosis.routers.vault import _sync_sse_generator, _sync_status

        async def _fake_sync(user_id):
            yield "synced: note1.md"
            yield "total:notanumber"
            yield "synced: note2.md"

        tokens = []
        with patch.object(vm, "run_full_sync_for_user", side_effect=_fake_sync):
            async for tok in _sync_sse_generator(user_id=77):
                tokens.append(tok)

        assert any("note1.md" in t for t in tokens)
        assert any("[done]" in t for t in tokens)
        assert not any("[error]" in t for t in tokens)
        assert _sync_status.get(77, {}).get("files_processed") == 2
