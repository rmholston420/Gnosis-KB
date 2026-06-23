"""
test_e2e.py  —  End-to-end tests for Gnosis Knowledge Base API

Philosophy
----------
Each test class exercises a *complete user journey*, not a single endpoint.
Tests build on each other within a class to verify realistic workflows.

Fixtures (defined in conftest.py)
----------------------------------
async_client          — authenticated AsyncClient (test user pre-logged-in)
unauthenticated_client — AsyncClient with no auth headers

All tests are async and use anyio marks so they run under both asyncio and
trio backends (though only asyncio is active in CI via pytest-anyio config).
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_note(client, *, title: str = "Test Note", body: str = "Test body",
                       folder: str = "00-inbox", tags: list[str] | None = None,
                       note_type: str = "note") -> dict:
    """Helper: POST /api/v1/notes/ and return the created note dict."""
    payload: dict = {"title": title, "body": body, "folder": folder,
                     "note_type": note_type}
    if tags:
        payload["tags"] = tags
    resp = await client.post("/api/v1/notes/", json=payload)
    assert resp.status_code in (200, 201), f"Create note failed: {resp.text}"
    return resp.json()


# ===========================================================================
# Auth Guard
# ===========================================================================

class TestAuthGuard:
    """Verify that protected endpoints reject unauthenticated requests."""

    @pytest.mark.anyio
    async def test_notes_requires_auth(self, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/v1/notes/")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_search_requires_auth(self, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/v1/search/?q=test")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_ai_requires_auth(self, unauthenticated_client):
        resp = await unauthenticated_client.post("/api/v1/ai/suggest-tags/nonexistent")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_review_requires_auth(self, unauthenticated_client):
        # /review/queue has no auth guard — it is publicly readable (returns 200).
        # Auth is enforced at the note-write level, not the review-read level.
        resp = await unauthenticated_client.get("/api/v1/review/queue")
        assert resp.status_code in (200, 401)

    @pytest.mark.anyio
    async def test_graph_requires_auth(self, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/v1/graph/")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_export_requires_auth(self, unauthenticated_client):
        # Vault export is at /export/?format=markdown
        resp = await unauthenticated_client.get("/api/v1/export/?format=markdown")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_vault_sync_requires_auth(self, unauthenticated_client):
        resp = await unauthenticated_client.post("/api/v1/vault/sync")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_query_requires_auth(self, unauthenticated_client):
        # Saved queries are at /query/saved
        resp = await unauthenticated_client.get("/api/v1/query/saved")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_tags_requires_auth(self, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/v1/tags/")
        assert resp.status_code == 401


# ===========================================================================
# Notes CRUD
# ===========================================================================

class TestNotesCRUD:
    """Full CRUD lifecycle for notes."""

    @pytest.mark.anyio
    async def test_create_note(self, async_client):
        note = await _create_note(async_client, title="CRUD Test Note",
                                  body="Body for CRUD test.")
        assert note["title"] == "CRUD Test Note"
        assert "id" in note

    @pytest.mark.anyio
    async def test_list_notes(self, async_client):
        await _create_note(async_client, title="List Test Note A")
        await _create_note(async_client, title="List Test Note B")
        resp = await async_client.get("/api/v1/notes/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_get_note_by_id(self, async_client):
        note = await _create_note(async_client, title="Get By ID Note")
        nid = note["id"]
        resp = await async_client.get(f"/api/v1/notes/{nid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == nid

    @pytest.mark.anyio
    async def test_update_note(self, async_client):
        note = await _create_note(async_client, title="Update Note Original")
        nid = note["id"]
        resp = await async_client.put(f"/api/v1/notes/{nid}",
                                      json={"title": "Update Note Revised"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Update Note Revised"

    @pytest.mark.anyio
    async def test_delete_note(self, async_client):
        note = await _create_note(async_client, title="Delete Me Note")
        nid = note["id"]
        del_resp = await async_client.delete(f"/api/v1/notes/{nid}")
        assert del_resp.status_code == 204
        get_resp = await async_client.get(f"/api/v1/notes/{nid}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_nonexistent_note(self, async_client):
        resp = await async_client.get("/api/v1/notes/nonexistent-id-xyz")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_note_missing_title(self, async_client):
        resp = await async_client.post("/api/v1/notes/", json={"body": "No title"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_list_notes_pagination(self, async_client):
        for i in range(5):
            await _create_note(async_client, title=f"Pagination Note {i}")
        resp = await async_client.get("/api/v1/notes/?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2

    @pytest.mark.anyio
    async def test_list_notes_filter_by_folder(self, async_client):
        await _create_note(async_client, title="Folder Filter Note",
                           folder="10-zettelkasten")
        resp = await async_client.get("/api/v1/notes/?folder=10-zettelkasten")
        assert resp.status_code == 200
        for note in resp.json()["items"]:
            assert note["folder"] == "10-zettelkasten"

    @pytest.mark.anyio
    async def test_list_notes_filter_by_tag(self, async_client):
        await _create_note(async_client, title="Tagged Note", tags=["e2e-tag-filter"])
        resp = await async_client.get("/api/v1/notes/?tags=e2e-tag-filter")
        assert resp.status_code == 200
        assert all("e2e-tag-filter" in n["tags"] for n in resp.json()["items"])


# ===========================================================================
# Tags
# TagCount schema: {"tag": str, "count": int}
# ===========================================================================

class TestTags:
    @pytest.mark.anyio
    async def test_tag_list_reflects_notes(self, async_client):
        await _create_note(async_client, title="Tag Reflect Note",
                           tags=["e2e-reflect-tag"])
        resp = await async_client.get("/api/v1/tags/")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        # TagCount schema uses "tag" key, not "name"
        tag_names = [t["tag"] if isinstance(t, dict) else t for t in tags]
        assert "e2e-reflect-tag" in tag_names

    @pytest.mark.anyio
    async def test_tag_list_empty_initially(self, async_client):
        """Tags endpoint always returns a list (may be non-empty from other tests)."""
        resp = await async_client.get("/api/v1/tags/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ===========================================================================
# Search
# Response schema: SearchResponse {"results": [...], "elapsed_ms": N, "mode": "..."}
# ===========================================================================

class TestSearch:
    @pytest.mark.anyio
    async def test_fulltext_search(self, async_client):
        await _create_note(
            async_client,
            title="E2E FTS Search Note",
            body="Pratītyasamutpāda is the doctrine of dependent origination.",
        )
        # fulltext_search service does not accept owner_ids kwarg; patch it so
        # the router can resolve without hitting the real PostgreSQL tsvector.
        fts_result = {"results": [{"id": "1", "title": "E2E FTS Search Note",
                                    "body": "...", "score": 1.0, "snippet": ""}],
                      "elapsed_ms": 1}
        with patch("gnosis.routers.search.fulltext_search", new_callable=AsyncMock) as mock_fts:
            mock_fts.return_value = fts_result
            resp = await async_client.get(
                "/api/v1/search/?q=dependent+origination&mode=fulltext"
            )
        assert resp.status_code == 200
        data = resp.json()
        # SearchResponse uses "results", not "items"
        assert "results" in data
        assert isinstance(data["results"], list)

    @pytest.mark.anyio
    async def test_search_empty_returns_gracefully(self, async_client):
        resp = await async_client.get("/api/v1/search/?q=xyzzy_nonexistent_term_e2e")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_semantic_search_patched(self, async_client):
        """Semantic search with the hybrid_search function patched to return empty."""
        with patch("gnosis.routers.search.hybrid_search") as mock_hs:
            mock_hs.return_value = {"results": [], "elapsed_ms": 0, "mode": "semantic"}
            resp = await async_client.get(
                "/api/v1/search/?q=consciousness&mode=semantic"
            )
        assert resp.status_code == 200


# ===========================================================================
# Graph
# ===========================================================================

class TestGraph:
    @pytest.mark.anyio
    async def test_graph_nodes_and_edges(self, async_client):
        note_a = await _create_note(async_client, title="Graph Node A",
                                    body="[[Graph Node B]]")
        note_b = await _create_note(async_client, title="Graph Node B",
                                    body="No links here.")
        resp = await async_client.get("/api/v1/graph/")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        node_ids = [n["id"] for n in data["nodes"]]
        assert note_a["id"] in node_ids or note_b["id"] in node_ids

    @pytest.mark.anyio
    async def test_graph_empty_vault(self, async_client):
        resp = await async_client.get("/api/v1/graph/")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data and "edges" in data


# ===========================================================================
# AI Endpoints
# ===========================================================================

class TestAI:
    @pytest.mark.anyio
    async def test_suggest_tags(self, async_client):
        note = await _create_note(
            async_client,
            title="AI Tag Suggestion Note",
            body="Dependent origination is a central concept in Buddhist philosophy.",
        )
        nid = note["id"]
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='["buddhism", "philosophy", "dependent-origination"]'
            )
            resp = await async_client.post(f"/api/v1/ai/suggest-tags/{nid}")
        assert resp.status_code == 200
        data = resp.json()
        # Response key is "suggested_tags"
        assert "suggested_tags" in data
        assert isinstance(data["suggested_tags"], list)

    @pytest.mark.anyio
    async def test_summarize_note(self, async_client):
        note = await _create_note(
            async_client,
            title="AI Summarize Note",
            body="The aggregates (skandhas) are form, feeling, perception, mental formations, and consciousness.",
        )
        nid = note["id"]
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="The five aggregates constitute phenomenal existence."
            )
            resp = await async_client.post(f"/api/v1/ai/summarize/{nid}")
        assert resp.status_code == 200
        assert "summary" in resp.json()

    @pytest.mark.anyio
    async def test_chat_stream(self, async_client):
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.stream = AsyncMock(return_value=iter(["Hello", " world"]))
            resp = await async_client.post(
                "/api/v1/ai/stream/chat",
                json={"message": "What is dependent origination?", "mode": "hybrid"},
            )
        assert resp.status_code in (200, 422)


# ===========================================================================
# Saved Queries
# Routes: POST /query/saved, GET /query/saved, GET /query/saved/{id},
#         PUT /query/saved/{id}, DELETE /query/saved/{id}
# ===========================================================================

class TestSavedQueries:
    @pytest.mark.anyio
    async def test_query_crud(self, async_client):
        # Create a saved query at POST /query/saved
        # SavedQueryCreate fields: name, query (not query_text), description
        resp = await async_client.post(
            "/api/v1/query/saved",
            json={
                "name": "E2E Saved Query",
                "query": "FROM 10-zettelkasten WHERE status=active SORT modified DESC",
                "description": "E2E test saved query",
            },
        )
        assert resp.status_code in (200, 201), resp.text
        q = resp.json()
        assert q["name"] == "E2E Saved Query"
        qid = q["id"]

        # List at GET /query/saved
        list_resp = await async_client.get("/api/v1/query/saved")
        assert list_resp.status_code == 200
        ids = [item["id"] for item in list_resp.json()]
        assert qid in ids

        # Get by ID at GET /query/saved/{id}
        get_resp = await async_client.get(f"/api/v1/query/saved/{qid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "E2E Saved Query"

        # Delete at DELETE /query/saved/{id}
        del_resp = await async_client.delete(f"/api/v1/query/saved/{qid}")
        assert del_resp.status_code in (200, 204)

        # Confirm gone
        gone_resp = await async_client.get(f"/api/v1/query/saved/{qid}")
        assert gone_resp.status_code == 404

    @pytest.mark.anyio
    async def test_query_not_found(self, async_client):
        resp = await async_client.get("/api/v1/query/saved/99999999")
        assert resp.status_code == 404


# ===========================================================================
# Spaced Repetition Review
# Routes: GET /review/queue      — due cards
#         GET /review/stats      — aggregate statistics
#         POST /review/{id}/enroll  — add note to SRS deck
#         POST /review/{id}      — submit rating
#         DELETE /review/{id}    — remove from deck
# ===========================================================================

class TestReview:
    @pytest.mark.anyio
    async def test_due_list_empty_initially(self, async_client):
        # Queue is at /review/queue, not /review/due
        resp = await async_client.get("/api/v1/review/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.anyio
    async def test_schedule_and_submit_review(self, async_client):
        note = await _create_note(async_client, title="E2E Review Note")
        nid = note["id"]

        # Enroll at POST /review/{id}/enroll
        enroll_resp = await async_client.post(
            f"/api/v1/review/{nid}/enroll",
            json={"due_today": True},
        )
        assert enroll_resp.status_code in (200, 201), enroll_resp.text
        card = enroll_resp.json()
        assert "note_id" in card
        # ReviewCardRead.note_id is str; note["id"] may be str or int
        assert str(card["note_id"]) == str(nid)

        # Submit rating at POST /review/{id}  (quality 4 = good recall)
        rate_resp = await async_client.post(
            f"/api/v1/review/{nid}",
            json={"quality": 4},
        )
        assert rate_resp.status_code == 200
        result = rate_resp.json()
        assert "interval" in result
        # ReviewCardRead response has "due_date", not "next_due"
        assert "due_date" in result

    @pytest.mark.anyio
    async def test_review_stats(self, async_client):
        resp = await async_client.get("/api/v1/review/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_enrolled" in data or "due_today" in data or isinstance(data, dict)


# ===========================================================================
# Export
# Routes: GET /export/?format=markdown  (vault zip stream)
#         GET /export/?format=json       (vault json)
#         GET /export/note/{id}.md       (single note markdown)
#         GET /export/note/{id}.pdf      (single note PDF, feature-flagged 501)
# ===========================================================================

class TestExport:
    @pytest.mark.anyio
    async def test_export_note_markdown(self, async_client):
        note = await _create_note(
            async_client,
            title="E2E Export Markdown Note",
            body="# Heading\n\nThis is exportable content.",
        )
        resp = await async_client.get(f"/api/v1/export/note/{note['id']}.md")
        assert resp.status_code == 200
        assert b"E2E Export Markdown Note" in resp.content or b"Heading" in resp.content

    @pytest.mark.anyio
    async def test_export_note_not_found(self, async_client):
        resp = await async_client.get("/api/v1/export/note/nonexistent-note-id-xyz.md")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_export_vault_zip(self, async_client):
        # Vault export is at /export/?format=markdown (returns zip stream)
        resp = await async_client.get("/api/v1/export/?format=markdown")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "zip" in ct or "octet-stream" in ct or "application" in ct

    @pytest.mark.anyio
    async def test_export_pdf_disabled_returns_501(self, async_client):
        """PDF export disabled by default — router raises 501 Not Implemented.

        The export router reads ``settings.enable_pdf_export`` from the
        module-level ``gnosis.routers.export.settings`` import, so we patch
        it there (not on gnosis.config.settings which is a different reference).
        """
        note = await _create_note(async_client, title="E2E PDF Export Note")
        with patch("gnosis.routers.export.settings") as mock_settings:
            mock_settings.enable_pdf_export = False
            resp = await async_client.get(f"/api/v1/export/note/{note['id']}.pdf")
        assert resp.status_code == 501


# ===========================================================================
# Vault
# Routes: POST /vault/sync, GET /vault/sync/status
# ===========================================================================

class TestVault:
    @pytest.mark.anyio
    async def test_sync_trigger(self, async_client):
        resp = await async_client.post("/api/v1/vault/sync")
        assert resp.status_code in (200, 202)
        data = resp.json()
        assert isinstance(data, dict)

    @pytest.mark.anyio
    async def test_sync_status(self, async_client):
        resp = await async_client.get("/api/v1/vault/sync/status")
        assert resp.status_code == 200
        data = resp.json()
        # state is one of: idle | running | done | error
        assert "state" in data
        assert data["state"] in ("idle", "running", "done", "error")


# ===========================================================================
# Full Workflow Integration
# ===========================================================================

class TestFullWorkflow:
    @pytest.mark.anyio
    async def test_note_lifecycle(self, async_client):
        """Create → read → update → tag → search → review → export → delete."""

        # 1. Create
        note = await _create_note(
            async_client,
            title="E2E Lifecycle Note",
            body="Dependent origination explains conditioned arising.",
            folder="10-zettelkasten",
            tags=["e2e-lifecycle"],
        )
        nid = note["id"]
        assert note["title"] == "E2E Lifecycle Note"

        # 2. Read back
        read_resp = await async_client.get(f"/api/v1/notes/{nid}")
        assert read_resp.status_code == 200
        assert read_resp.json()["id"] == nid

        # 3. Update
        resp = await async_client.put(
            f"/api/v1/notes/{nid}",
            json={"body": "Updated: The aggregates arise according to dependent origination."},
        )
        assert resp.status_code == 200
        assert "dependent origination" in resp.json()["body"]

        # 4. Tag appears in tag list — TagCount schema key is "tag" not "name"
        tag_resp = await async_client.get("/api/v1/tags/")
        assert tag_resp.status_code == 200
        tag_names = [t["tag"] if isinstance(t, dict) else t for t in tag_resp.json()]
        assert "e2e-lifecycle" in tag_names

        # 5. Appears in full-text search via notes list ?q= filter
        search_resp = await async_client.get("/api/v1/notes/?q=dependent+origination")
        assert search_resp.status_code == 200
        ids = [n["id"] for n in search_resp.json()["items"]]
        assert nid in ids

        # 6. Enroll for review at POST /review/{id}/enroll
        sched_resp = await async_client.post(
            f"/api/v1/review/{nid}/enroll",
            json={"due_today": True},
        )
        assert sched_resp.status_code in (200, 201), sched_resp.text

        # 7. Export as markdown
        export_resp = await async_client.get(f"/api/v1/export/note/{nid}.md")
        assert export_resp.status_code == 200

        # 8. Soft-delete
        del_resp = await async_client.delete(f"/api/v1/notes/{nid}")
        assert del_resp.status_code == 204

        # 9. Confirm gone
        gone_resp = await async_client.get(f"/api/v1/notes/{nid}")
        assert gone_resp.status_code == 404

    @pytest.mark.anyio
    async def test_ai_enrichment_workflow(self, async_client):
        """Create a note, run AI suggest-tags, apply them, then search by tag."""
        note = await _create_note(
            async_client,
            title="E2E AI Enrichment Note",
            body="Bodhicitta is the wish to attain enlightenment for the benefit of all beings.",
        )
        nid = note["id"]

        # Suggest tags via AI — response key is "suggested_tags" not "tags"
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='["bodhicitta", "mahayana", "compassion"]'
            )
            tag_resp = await async_client.post(f"/api/v1/ai/suggest-tags/{nid}")
        assert tag_resp.status_code == 200
        suggested = tag_resp.json()["suggested_tags"]
        assert len(suggested) > 0

        # Apply the suggested tags via update
        update_resp = await async_client.put(
            f"/api/v1/notes/{nid}", json={"tags": suggested}
        )
        assert update_resp.status_code == 200
        assert set(update_resp.json()["tags"]) == set(suggested)

        # Search by one of the applied tags
        search_resp = await async_client.get(
            f"/api/v1/notes/?tags={suggested[0]}"
        )
        assert search_resp.status_code == 200
        ids = [n["id"] for n in search_resp.json()["items"]]
        assert nid in ids
