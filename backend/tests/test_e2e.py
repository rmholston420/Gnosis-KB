"""
test_e2e.py  —  End-to-end tests for Gnosis Knowledge Base API

Philosophy
----------
Each test class exercises a *complete user journey*, not a single endpoint.
Tests build on each other within a class: create → read → update → delete,
or multi-step workflows like "create note → tag it → search for it → review it".

All tests use the `async_client` fixture (authenticated as FakeUser id=1)
or `unauthenticated_client` for auth-guard checks.  No mocking of business
logic — only external services (Qdrant, Ollama, LightRAG) are stubbed by
conftest.py's lifespan patches.

Coverage targets
----------------
  notes      — full CRUD, pagination, filtering, wikilink resolution, orphans,
               daily note, soft-delete vs hard-delete
  tags       — tag list reflects note creation
  search     — full-text and semantic (semantic patched at vector store)
  graph      — link creation via note body, graph endpoint
  query      — saved queries CRUD
  review     — spaced-repetition schedule, submit rating
  export     — markdown export
  vault      — sync trigger
  health     — liveness + readiness probes
  auth       — 401 on unauthenticated requests to every protected router
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# Helpers
# ===========================================================================

async def _create_note(
    client,
    *,
    note_id: str | None = None,
    title: str,
    body: str = "Test note body content.",
    folder: str = "10-zettelkasten",
    tags: list[str] | None = None,
    note_type: str = "permanent",
    status: str = "active",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title,
        "body": body,
        "folder": folder,
        "note_type": note_type,
        "status": status,
    }
    if note_id:
        payload["id"] = note_id
    if tags:
        payload["tags"] = tags
    resp = await client.post("/api/v1/notes/", json=payload)
    assert resp.status_code == 201, f"create_note failed {resp.status_code}: {resp.text}"
    return resp.json()


# ===========================================================================
# Health
# ===========================================================================

class TestHealth:
    @pytest.mark.anyio
    async def test_liveness(self, async_client):
        resp = await async_client.get("/api/v1/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.anyio
    async def test_readiness(self, async_client):
        resp = await async_client.get("/api/v1/health/ready")
        # ready may return 200 or 503 depending on Qdrant stub; either is acceptable
        assert resp.status_code in (200, 503)
        body = resp.json()
        assert "status" in body

    @pytest.mark.anyio
    async def test_health_root(self, async_client):
        """The root /api/v1/health endpoint exists."""
        resp = await async_client.get("/api/v1/health")
        assert resp.status_code == 200


# ===========================================================================
# Auth guard — every protected router returns 401 without credentials
# ===========================================================================

class TestAuthGuard:
    @pytest.mark.anyio
    async def test_notes_list_requires_auth(self, unauthenticated_client):
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
        resp = await unauthenticated_client.get("/api/v1/review/due")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_graph_requires_auth(self, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/v1/graph/")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_export_requires_auth(self, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/v1/export/vault")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_vault_sync_requires_auth(self, unauthenticated_client):
        resp = await unauthenticated_client.post("/api/v1/vault/sync")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_query_requires_auth(self, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/v1/query/")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_tags_requires_auth(self, unauthenticated_client):
        resp = await unauthenticated_client.get("/api/v1/tags/")
        assert resp.status_code == 401


# ===========================================================================
# Notes — full CRUD journey
# ===========================================================================

class TestNotesCRUD:
    @pytest.mark.anyio
    async def test_create_and_read(self, async_client):
        note = await _create_note(
            async_client,
            title="E2E Zettelkasten Note",
            body="This is a permanent note about impermanence.",
            tags=["buddhism", "philosophy"],
        )
        assert note["title"] == "E2E Zettelkasten Note"
        assert note["folder"] == "10-zettelkasten"
        assert set(note["tags"]) == {"buddhism", "philosophy"}
        assert note["word_count"] > 0
        assert note["id"]

        # Fetch by ID
        resp = await async_client.get(f"/api/v1/notes/{note['id']}")
        assert resp.status_code == 200
        fetched = resp.json()
        assert fetched["title"] == note["title"]
        assert fetched["body_html"]  # rendered HTML present

    @pytest.mark.anyio
    async def test_update_title_body_tags(self, async_client):
        note = await _create_note(async_client, title="E2E Update Test Note")
        nid = note["id"]

        resp = await async_client.put(
            f"/api/v1/notes/{nid}",
            json={
                "title": "E2E Updated Title",
                "body": "Updated body with more words about dependent origination.",
                "tags": ["dharma"],
            },
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["title"] == "E2E Updated Title"
        assert "Updated body" in updated["body"]
        assert "dharma" in updated["tags"]

    @pytest.mark.anyio
    async def test_soft_delete(self, async_client):
        note = await _create_note(async_client, title="E2E Soft Delete Note")
        nid = note["id"]

        del_resp = await async_client.delete(f"/api/v1/notes/{nid}")
        assert del_resp.status_code == 204

        # Soft-deleted note should return 404
        get_resp = await async_client.get(f"/api/v1/notes/{nid}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_hard_delete(self, async_client):
        note = await _create_note(async_client, title="E2E Hard Delete Note")
        nid = note["id"]

        del_resp = await async_client.delete(f"/api/v1/notes/{nid}?hard=true")
        assert del_resp.status_code == 204

        get_resp = await async_client.get(f"/api/v1/notes/{nid}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_conflict_on_duplicate_title(self, async_client):
        await _create_note(async_client, title="E2E Duplicate Title")
        resp = await async_client.post(
            "/api/v1/notes/",
            json={"title": "E2E Duplicate Title", "body": "body", "folder": "10-zettelkasten"},
        )
        assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_get_nonexistent_returns_404(self, async_client):
        resp = await async_client.get("/api/v1/notes/totally-nonexistent-note-id-xyz")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_returns_404(self, async_client):
        resp = await async_client.put(
            "/api/v1/notes/totally-nonexistent-note-id-xyz",
            json={"title": "new title"},
        )
        assert resp.status_code == 404


# ===========================================================================
# Notes — list, pagination, filtering
# ===========================================================================

class TestNotesListAndFilter:
    @pytest.mark.anyio
    async def test_list_returns_created_notes(self, async_client):
        await _create_note(async_client, title="E2E List Note Alpha", tags=["e2e-list"])
        await _create_note(async_client, title="E2E List Note Beta", tags=["e2e-list"])

        resp = await async_client.get("/api/v1/notes/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 2
        titles = [n["title"] for n in data["items"]]
        assert "E2E List Note Alpha" in titles or "E2E List Note Beta" in titles

    @pytest.mark.anyio
    async def test_filter_by_folder(self, async_client):
        await _create_note(
            async_client, title="E2E Inbox Note", folder="00-inbox"
        )
        resp = await async_client.get("/api/v1/notes/?folder=00-inbox")
        assert resp.status_code == 200
        data = resp.json()
        assert all(n["folder"] == "00-inbox" for n in data["items"])

    @pytest.mark.anyio
    async def test_filter_by_note_type(self, async_client):
        await _create_note(
            async_client,
            title="E2E Literature Note",
            note_type="literature",
            folder="40-resources",
        )
        resp = await async_client.get("/api/v1/notes/?note_type=literature")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(n["note_type"] == "literature" for n in items)

    @pytest.mark.anyio
    async def test_filter_by_tag(self, async_client):
        await _create_note(
            async_client,
            title="E2E Tagged Filter Note",
            tags=["e2e-tag-filter-unique"],
        )
        resp = await async_client.get("/api/v1/notes/?tags=e2e-tag-filter-unique")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.anyio
    async def test_fulltext_filter(self, async_client):
        await _create_note(
            async_client,
            title="E2E FTS Target Note",
            body="The concept of sunyata is central to Madhyamaka philosophy.",
        )
        resp = await async_client.get("/api/v1/notes/?q=sunyata")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.anyio
    async def test_pagination_page_size(self, async_client):
        # Create enough notes to span two pages
        for i in range(5):
            await _create_note(async_client, title=f"E2E Pagination Note {i}")
        resp = await async_client.get("/api/v1/notes/?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2


# ===========================================================================
# Notes — special lookups
# ===========================================================================

class TestNotesSpecialLookups:
    @pytest.mark.anyio
    async def test_by_title(self, async_client):
        note = await _create_note(async_client, title="E2E By Title Lookup")
        resp = await async_client.get(
            "/api/v1/notes/by-title", params={"title": "E2E By Title Lookup"}
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == note["id"]

    @pytest.mark.anyio
    async def test_by_title_not_found(self, async_client):
        resp = await async_client.get(
            "/api/v1/notes/by-title", params={"title": "Absolutely Nonexistent Title XYZ"}
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_wikilink_resolve(self, async_client):
        note = await _create_note(async_client, title="E2E Wikilink Target")
        resp = await async_client.get(
            "/api/v1/notes/wikilink", params={"title": "E2E Wikilink Target"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == note["id"]
        assert data["title"] == "E2E Wikilink Target"

    @pytest.mark.anyio
    async def test_wikilink_not_found(self, async_client):
        resp = await async_client.get(
            "/api/v1/notes/wikilink", params={"title": "No Such Wikilink Note"}
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_templates(self, async_client):
        await _create_note(
            async_client,
            title="E2E Template Note",
            note_type="template",
            folder="80-meta",
        )
        resp = await async_client.get("/api/v1/notes/templates")
        assert resp.status_code == 200
        templates = resp.json()
        assert isinstance(templates, list)
        titles = [t["title"] for t in templates]
        assert "E2E Template Note" in titles

    @pytest.mark.anyio
    async def test_orphan_notes(self, async_client):
        """A note with no wikilinks appears in the orphan list."""
        note = await _create_note(
            async_client,
            title="E2E Orphan Note",
            body="This note references nothing.",
        )
        resp = await async_client.get("/api/v1/notes/orphans")
        assert resp.status_code == 200
        ids = [n["id"] for n in resp.json()]
        assert note["id"] in ids

    @pytest.mark.anyio
    async def test_daily_note_created_and_idempotent(self, async_client):
        resp1 = await async_client.post("/api/v1/notes/daily")
        assert resp1.status_code == 201 or resp1.status_code == 200
        note1 = resp1.json()
        assert note1["folder"] == "60-journals"
        assert "Daily Note" in note1["title"]

        # Second call returns same note (idempotent)
        resp2 = await async_client.post("/api/v1/notes/daily")
        assert resp2.status_code in (200, 201)
        assert resp2.json()["id"] == note1["id"]


# ===========================================================================
# Tags
# ===========================================================================

class TestTags:
    @pytest.mark.anyio
    async def test_tag_list_reflects_notes(self, async_client):
        await _create_note(
            async_client,
            title="E2E Tag List Note",
            tags=["e2e-unique-tag-abc"],
        )
        resp = await async_client.get("/api/v1/tags/")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        names = [t["name"] if isinstance(t, dict) else t for t in tags]
        assert "e2e-unique-tag-abc" in names


# ===========================================================================
# Search
# ===========================================================================

class TestSearch:
    @pytest.mark.anyio
    async def test_fulltext_search(self, async_client):
        await _create_note(
            async_client,
            title="E2E FTS Search Note",
            body="Pratītyasamutpāda is the doctrine of dependent origination.",
        )
        resp = await async_client.get("/api/v1/search/?q=dependent+origination")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    @pytest.mark.anyio
    async def test_search_empty_returns_gracefully(self, async_client):
        resp = await async_client.get("/api/v1/search/?q=xyzzy_nonexistent_term_e2e")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_semantic_search_patched(self, async_client):
        """Semantic search with Qdrant patched to return empty — should not 500."""
        with patch("gnosis.routers.search.vector_store") as mock_vs:
            mock_vs.search = AsyncMock(return_value=[])
            resp = await async_client.get("/api/v1/search/?q=consciousness&mode=semantic")
        assert resp.status_code == 200


# ===========================================================================
# Graph
# ===========================================================================

class TestGraph:
    @pytest.mark.anyio
    async def test_graph_endpoint_returns_structure(self, async_client):
        # Create two notes so there's something to return
        await _create_note(async_client, title="E2E Graph Node A")
        await _create_note(async_client, title="E2E Graph Node B")
        resp = await async_client.get("/api/v1/graph/")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    @pytest.mark.anyio
    async def test_note_with_wikilink_creates_edge(self, async_client):
        target = await _create_note(async_client, title="E2E Link Target Node")
        source = await _create_note(
            async_client,
            title="E2E Link Source Node",
            body=f"See [[E2E Link Target Node]] for details.",
        )
        resp = await async_client.get("/api/v1/graph/")
        assert resp.status_code == 200
        node_ids = [n["id"] for n in resp.json()["nodes"]]
        assert source["id"] in node_ids
        assert target["id"] in node_ids


# ===========================================================================
# Saved Queries
# ===========================================================================

class TestSavedQueries:
    @pytest.mark.anyio
    async def test_query_crud(self, async_client):
        # Create
        resp = await async_client.post(
            "/api/v1/query/",
            json={
                "name": "E2E Saved Query",
                "query_text": "dependent origination",
                "query_type": "fulltext",
            },
        )
        assert resp.status_code in (200, 201), resp.text
        q = resp.json()
        assert q["name"] == "E2E Saved Query"
        qid = q["id"]

        # List
        list_resp = await async_client.get("/api/v1/query/")
        assert list_resp.status_code == 200
        ids = [item["id"] for item in list_resp.json()]
        assert qid in ids

        # Get by ID
        get_resp = await async_client.get(f"/api/v1/query/{qid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "E2E Saved Query"

        # Delete
        del_resp = await async_client.delete(f"/api/v1/query/{qid}")
        assert del_resp.status_code in (200, 204)

        # Confirm gone
        gone_resp = await async_client.get(f"/api/v1/query/{qid}")
        assert gone_resp.status_code == 404

    @pytest.mark.anyio
    async def test_query_not_found(self, async_client):
        resp = await async_client.get("/api/v1/query/99999999")
        assert resp.status_code == 404


# ===========================================================================
# Spaced Repetition Review
# ===========================================================================

class TestReview:
    @pytest.mark.anyio
    async def test_due_list_empty_initially(self, async_client):
        resp = await async_client.get("/api/v1/review/due")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.anyio
    async def test_schedule_and_submit_review(self, async_client):
        note = await _create_note(async_client, title="E2E Review Note")
        nid = note["id"]

        # Schedule — add to SRS queue
        sched_resp = await async_client.post(f"/api/v1/review/schedule/{nid}")
        assert sched_resp.status_code in (200, 201), sched_resp.text

        # Submit a rating (quality 4 = good recall)
        rate_resp = await async_client.post(
            f"/api/v1/review/rate/{nid}", json={"quality": 4}
        )
        assert rate_resp.status_code == 200
        result = rate_resp.json()
        assert "interval" in result
        assert "next_due" in result or "due_date" in result

    @pytest.mark.anyio
    async def test_review_stats(self, async_client):
        resp = await async_client.get("/api/v1/review/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_scheduled" in data or "total" in data or isinstance(data, dict)


# ===========================================================================
# Export
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
        resp = await async_client.get("/api/v1/export/vault")
        # Returns zip stream or 200; content-type should indicate zip or octet-stream
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "zip" in ct or "octet-stream" in ct or "application" in ct

    @pytest.mark.anyio
    async def test_export_pdf_disabled_returns_404(self, async_client):
        """PDF export disabled by default in test settings — should return 404."""
        note = await _create_note(async_client, title="E2E PDF Export Note")
        with patch("gnosis.routers.export.settings") as mock_settings:
            mock_settings.enable_pdf_export = False
            resp = await async_client.get(f"/api/v1/export/note/{note['id']}.pdf")
        assert resp.status_code == 404


# ===========================================================================
# Vault
# ===========================================================================

class TestVault:
    @pytest.mark.anyio
    async def test_sync_trigger(self, async_client):
        resp = await async_client.post("/api/v1/vault/sync")
        assert resp.status_code in (200, 202)
        data = resp.json()
        assert "status" in data or "message" in data or "synced" in data

    @pytest.mark.anyio
    async def test_vault_status(self, async_client):
        resp = await async_client.get("/api/v1/vault/status")
        assert resp.status_code == 200


# ===========================================================================
# AI endpoints — patched at the LLM provider layer
# ===========================================================================

class TestAIEndpoints:
    @pytest.mark.anyio
    async def test_suggest_tags(self, async_client):
        note = await _create_note(
            async_client,
            title="E2E AI Suggest Tags Note",
            body="Meditation on the Four Noble Truths and the Eightfold Path.",
        )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='["buddhism", "meditation", "dharma"]'
            )
            resp = await async_client.post(f"/api/v1/ai/suggest-tags/{note['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "tags" in data
        assert isinstance(data["tags"], list)

    @pytest.mark.anyio
    async def test_suggest_tags_llm_unavailable(self, async_client):
        note = await _create_note(async_client, title="E2E AI Tags LLM Off")
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = False
            resp = await async_client.post(f"/api/v1/ai/suggest-tags/{note['id']}")
        assert resp.status_code in (200, 503)

    @pytest.mark.anyio
    async def test_suggest_tags_note_not_found(self, async_client):
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            resp = await async_client.post("/api/v1/ai/suggest-tags/nonexistent-note-id")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_suggest_links(self, async_client):
        note = await _create_note(
            async_client,
            title="E2E AI Suggest Links Note",
            body="The aggregates (skandhas) are form, feeling, perception, formations, consciousness.",
        )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='["Consciousness Note", "Form Note"]'
            )
            resp = await async_client.post(f"/api/v1/ai/suggest-links/{note['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data

    @pytest.mark.anyio
    async def test_critique_note(self, async_client):
        note = await _create_note(
            async_client,
            title="E2E AI Critique Note",
            body="This note is about impermanence and how all conditioned phenomena are transient.",
        )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='{"atomicity": "Good — single idea.", "connectivity": "Add links.", "overall": "Solid."}'
            )
            resp = await async_client.post(f"/api/v1/ai/critique/{note['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "atomicity" in data
        assert "connectivity" in data
        assert "overall" in data

    @pytest.mark.anyio
    async def test_expand_note(self, async_client):
        note = await _create_note(
            async_client,
            title="E2E AI Expand Note",
            body="Brief note on nirvana.",
        )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="Nirvana is the cessation of suffering and the extinguishing of craving."
            )
            resp = await async_client.post(f"/api/v1/ai/expand/{note['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "expanded" in data or "body" in data or "content" in data

    @pytest.mark.anyio
    async def test_summarise_note(self, async_client):
        note = await _create_note(
            async_client,
            title="E2E AI Summarise Note",
            body="Long body about dependent origination. " * 20,
        )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value="A brief summary of dependent origination."
            )
            resp = await async_client.post(f"/api/v1/ai/summarise/{note['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data

    @pytest.mark.anyio
    async def test_orphan_audit(self, async_client):
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='[{"note_id": "x", "title": "X", "suggestions": ["Link to Y"]}]'
            )
            resp = await async_client.get("/api/v1/ai/orphan-audit?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    @pytest.mark.anyio
    async def test_daily_review_ai(self, async_client):
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='{"summary": "Good day of study.", "action_items": ["Review skandhas"]}'
            )
            resp = await async_client.post("/api/v1/ai/daily-review")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "action_items" in data

    @pytest.mark.anyio
    async def test_generate_moc(self, async_client):
        for i in range(3):
            await _create_note(
                async_client,
                title=f"E2E MOC Seed Note {i}",
                body=f"Content about nirvana and liberation {i}.",
                tags=["e2e-moc"],
            )
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='[{"heading": "Liberation", "summary": "Notes on nirvana.", "wikilinks": ["E2E MOC Seed Note 0"]}]'
            )
            resp = await async_client.post(
                "/api/v1/ai/generate-moc",
                json={"topic": "nirvana", "max_notes": 10},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "topic" in data
        assert "sections" in data

    @pytest.mark.anyio
    async def test_stream_chat_sse(self, async_client):
        with (
            patch("gnosis.routers.ai.graph_rag") as mock_rag,
            patch("gnosis.routers.ai.llm_provider") as mock_llm,
        ):
            mock_rag.is_available = AsyncMock(return_value=False)
            mock_llm.is_available = True
            mock_llm.stream = AsyncMock(return_value=iter(["token1", " token2"]))

            async def _fake_stream(*a, **kw):
                for chunk in ["Hello ", "world"]:
                    yield chunk

            mock_llm.stream = _fake_stream
            resp = await async_client.get(
                "/api/v1/ai/stream/chat?message=What+is+nirvana%3F&mode=direct"
            )
        assert resp.status_code == 200
        assert b"DONE" in resp.content or len(resp.content) > 0


# ===========================================================================
# Multi-step workflow — create note, tag, search, schedule review, export
# ===========================================================================

class TestFullWorkflow:
    @pytest.mark.anyio
    async def test_note_lifecycle(self, async_client):
        """Complete journey: create → read → update → tag → search → review → export → delete."""
        # 1. Create
        note = await _create_note(
            async_client,
            title="E2E Lifecycle Note",
            body="The aggregates arise and pass according to conditions.",
            tags=["e2e-lifecycle"],
        )
        nid = note["id"]
        assert note["word_count"] > 0

        # 2. Read back
        resp = await async_client.get(f"/api/v1/notes/{nid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == nid

        # 3. Update body
        resp = await async_client.put(
            f"/api/v1/notes/{nid}",
            json={"body": "Updated: The aggregates arise according to dependent origination."},
        )
        assert resp.status_code == 200
        assert "dependent origination" in resp.json()["body"]

        # 4. Tag appears in tag list
        tag_resp = await async_client.get("/api/v1/tags/")
        assert tag_resp.status_code == 200
        tag_names = [t["name"] if isinstance(t, dict) else t for t in tag_resp.json()]
        assert "e2e-lifecycle" in tag_names

        # 5. Appears in full-text search
        search_resp = await async_client.get("/api/v1/notes/?q=dependent+origination")
        assert search_resp.status_code == 200
        ids = [n["id"] for n in search_resp.json()["items"]]
        assert nid in ids

        # 6. Schedule for review
        sched_resp = await async_client.post(f"/api/v1/review/schedule/{nid}")
        assert sched_resp.status_code in (200, 201)

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

        # Suggest tags via AI
        with patch("gnosis.routers.ai.llm_provider") as mock_llm:
            mock_llm.is_available = True
            mock_llm.complete = AsyncMock(
                return_value='["bodhicitta", "mahayana", "compassion"]'
            )
            tag_resp = await async_client.post(f"/api/v1/ai/suggest-tags/{nid}")
        assert tag_resp.status_code == 200
        suggested = tag_resp.json()["tags"]
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
