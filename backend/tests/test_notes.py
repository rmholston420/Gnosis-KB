"""Tests for the Notes API router."""

import pytest


@pytest.mark.asyncio
async def test_health_check(async_client):
    """Health endpoint returns 200 and status ok."""
    response = await async_client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_list_notes_empty(async_client):
    """List notes returns empty list on fresh DB."""
    response = await async_client.get("/api/v1/notes/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_create_note(async_client, vault_dir):
    """Creating a note writes to DB and creates a vault file."""
    payload = {
        "title": "Test Atomic Note",
        "body": "This is a test note body with [[Another Note]] wikilink.",
        "note_type": "permanent",
        "status": "draft",
        "folder": "10-zettelkasten",
        "tags": ["test", "zettelkasten"],
    }
    response = await async_client.post("/api/v1/notes/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Atomic Note"
    assert data["note_type"] == "permanent"
    assert "test" in data["tags"]
    assert data["id"] is not None

    # Verify vault file was created
    vault_files = list(vault_dir.rglob("*.md"))
    assert len(vault_files) >= 1


@pytest.mark.asyncio
async def test_get_note(async_client):
    """Fetching a note by ID returns the correct note."""
    # First create one
    payload = {"title": "Fetch Me", "body": "Body text.", "folder": "10-zettelkasten"}
    create_resp = await async_client.post("/api/v1/notes/", json=payload)
    assert create_resp.status_code == 201
    note_id = create_resp.json()["id"]

    # Now fetch
    get_resp = await async_client.get(f"/api/v1/notes/{note_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == note_id


@pytest.mark.asyncio
async def test_update_note(async_client):
    """Updating a note changes the title and body."""
    create_resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": "Original Title", "body": "Original body.", "folder": "10-zettelkasten"},
    )
    assert create_resp.status_code == 201
    note_id = create_resp.json()["id"]

    update_resp = await async_client.put(
        f"/api/v1/notes/{note_id}",
        json={"title": "Updated Title", "body": "Updated body."},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_delete_note(async_client):
    """Deleting a note marks it as deleted (soft delete)."""
    create_resp = await async_client.post(
        "/api/v1/notes/",
        json={"title": "Delete Me", "body": "Body.", "folder": "00-inbox"},
    )
    assert create_resp.status_code == 201
    note_id = create_resp.json()["id"]

    del_resp = await async_client.delete(f"/api/v1/notes/{note_id}")
    assert del_resp.status_code == 204

    get_resp = await async_client.get(f"/api/v1/notes/{note_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_404_on_missing_note(async_client):
    """Requesting a non-existent note returns 404."""
    response = await async_client.get("/api/v1/notes/nonexistent-id")
    assert response.status_code == 404
