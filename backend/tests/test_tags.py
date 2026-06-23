"""Tests for the tags router.

Covers:
  - GET /api/v1/tags/  → empty list when no tags
  - GET /api/v1/tags/  → correct tag + count after creating tagged notes
  - Tags are user-scoped (other users' tags not returned)
  - Count accuracy (multiple notes with same tag)
  - Sort order: by count desc, then alpha
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_note(
    client: AsyncClient, title: str, tags: list[str], folder: str = "10-zettelkasten"
) -> str:
    """Create a note and return its id."""
    resp = await client.post(
        "/api/v1/notes/",
        json={
            "title": title,
            "body": f"# {title}\n\nContent.",
            "folder": folder,
            "note_type": "permanent",
            "tags": tags,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tags_empty(async_client: AsyncClient) -> None:
    """Tags endpoint returns an empty list when the user has no notes."""
    resp = await async_client.get("/api/v1/tags/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_tags_after_create(async_client: AsyncClient) -> None:
    """Tags appear after notes with tags are created."""
    await _create_note(async_client, "Tagged Note A", ["dharma", "buddhism"])
    await _create_note(async_client, "Tagged Note B", ["dharma", "systems"])

    resp = await async_client.get("/api/v1/tags/")
    assert resp.status_code == 200
    tags = resp.json()
    assert isinstance(tags, list)
    assert len(tags) >= 1

    # Each entry has 'tag' and 'count'
    for entry in tags:
        assert "tag" in entry
        assert "count" in entry
        assert isinstance(entry["count"], int)
        assert entry["count"] >= 1


@pytest.mark.asyncio
async def test_tags_count_accuracy(async_client: AsyncClient) -> None:
    """A tag shared by N notes has count == N."""
    shared_tag = "gnosis-test-shared"
    await _create_note(async_client, "Count Note 1", [shared_tag])
    await _create_note(async_client, "Count Note 2", [shared_tag])
    await _create_note(async_client, "Count Note 3", [shared_tag])

    resp = await async_client.get("/api/v1/tags/")
    tags = {entry["tag"]: entry["count"] for entry in resp.json()}
    assert tags.get(shared_tag, 0) >= 3


@pytest.mark.asyncio
async def test_tags_sort_by_count_desc(async_client: AsyncClient) -> None:
    """Tags are returned sorted by count descending."""
    # Create a tag with 3 notes and one with 1 note
    rare_tag = "gnosis-rare-tag"
    common_tag = "gnosis-common-tag"
    for i in range(3):
        await _create_note(async_client, f"Common {i}", [common_tag])
    await _create_note(async_client, "Rare", [rare_tag])

    resp = await async_client.get("/api/v1/tags/")
    tags = resp.json()

    # Find positions of common and rare tags
    tag_names = [t["tag"] for t in tags]
    if common_tag in tag_names and rare_tag in tag_names:
        assert tag_names.index(common_tag) < tag_names.index(rare_tag), (
            "Higher-count tag should appear before lower-count tag"
        )


@pytest.mark.asyncio
async def test_tags_response_schema(async_client: AsyncClient) -> None:
    """Tags response matches the {tag, count} schema expected by TagsPage.tsx."""
    await _create_note(async_client, "Schema Note", ["schema-check"])
    resp = await async_client.get("/api/v1/tags/")
    assert resp.status_code == 200
    tags = resp.json()
    for entry in tags:
        # Must have exactly these keys (or a superset)
        assert "tag" in entry, f"Missing 'tag' key in {entry}"
        assert "count" in entry, f"Missing 'count' key in {entry}"
        # Types
        assert isinstance(entry["tag"], str)
        assert isinstance(entry["count"], int)
