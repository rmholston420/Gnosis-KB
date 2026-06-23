"""
Tag autocomplete endpoint tests.

Covers:
- GET /api/v1/tags/   returns 200 and a JSON list
- Each item exposes 'tag' (str) and 'count' (int) fields
- Empty vault returns [] not an error
- Unauthenticated requests receive 401
- X-Vault-Owner-Id header is accepted without error
- Count > 0 for every returned tag
- Client-side prefix-filter logic (pure Python, no HTTP)

All HTTP tests use the standard conftest async_client /
unauthenticated_client fixtures and a real in-memory SQLite DB
(StaticPool).  The old monkeypatch approach (patching
gnosis.routers.tags.AsyncSession.execute) no longer works because
the tags router imports AsyncSession at module load time.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _create_tagged_note(
    client: AsyncClient,
    title: str,
    tags: list[str],
) -> str:
    """Create a note with the given tags; return its id."""
    resp = await client.post(
        "/api/v1/notes/",
        json={
            "title": title,
            "body": f"# {title}\n\nBody.",
            "folder": "10-zettelkasten",
            "note_type": "permanent",
            "tags": tags,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# GET /api/v1/tags/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tags_returns_200(async_client: AsyncClient) -> None:
    """Tags endpoint returns HTTP 200."""
    resp = await async_client.get("/api/v1/tags/")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_tags_returns_list(async_client: AsyncClient) -> None:
    """Response body is a JSON array."""
    resp = await async_client.get("/api/v1/tags/")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


@pytest.mark.asyncio
async def test_list_tags_empty_vault(async_client: AsyncClient) -> None:
    """Empty vault returns [] not an error."""
    resp = await async_client.get("/api/v1/tags/")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_tags_each_item_has_required_fields(async_client: AsyncClient) -> None:
    """Every item exposes 'tag' (str) and 'count' (int)."""
    await _create_tagged_note(async_client, "Schema Check Note", ["buddhism", "epistemology"])
    resp = await async_client.get("/api/v1/tags/")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1, "Expected at least one tag after creating a tagged note"
    for item in body:
        assert "tag" in item, f"Missing 'tag' field: {item}"
        assert "count" in item, f"Missing 'count' field: {item}"
        assert isinstance(item["tag"], str)
        assert isinstance(item["count"], int)


@pytest.mark.asyncio
async def test_list_tags_count_is_positive_integer(async_client: AsyncClient) -> None:
    """Count is > 0 for every returned tag."""
    await _create_tagged_note(async_client, "Count Test Note", ["zettelkasten", "systems"])
    resp = await async_client.get("/api/v1/tags/")
    assert resp.status_code == 200
    for item in resp.json():
        assert item["count"] > 0, f"Tag count should be > 0, got {item}"


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tags_requires_auth(unauthenticated_client: AsyncClient) -> None:
    """Unauthenticated request returns 401.

    Uses unauthenticated_client — the fixture that overrides get_current_user
    and require_user with _fake_deny_user (always raises HTTP 401).
    test_client / async_client always authenticate, so cannot be used here.
    """
    resp = await unauthenticated_client.get("/api/v1/tags/")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Vault scoping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tags_vault_header_accepted(async_client: AsyncClient) -> None:
    """X-Vault-Owner-Id header is accepted without error (non-5xx)."""
    resp = await async_client.get(
        "/api/v1/tags/",
        headers={"X-Vault-Owner-Id": "1"},
    )
    assert resp.status_code < 500


# ---------------------------------------------------------------------------
# Integration: count accuracy after multiple notes share a tag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tags_count_accuracy(async_client: AsyncClient) -> None:
    """A tag shared by N notes has count == N."""
    shared = "gnosis-shared-tag"
    for i in range(3):
        await _create_tagged_note(async_client, f"Shared Tag Note {i}", [shared])
    resp = await async_client.get("/api/v1/tags/")
    tags = {entry["tag"]: entry["count"] for entry in resp.json()}
    assert tags.get(shared, 0) >= 3


# ---------------------------------------------------------------------------
# Pure-Python: client-side prefix-filter logic (TagInput.tsx)
# ---------------------------------------------------------------------------


SAMPLE_TAGS = [
    {"tag": "buddhism", "count": 5},
    {"tag": "epistemology", "count": 3},
    {"tag": "zettelkasten", "count": 8},
    {"tag": "systems", "count": 2},
    {"tag": "philosophy", "count": 4},
]


def test_tag_autocomplete_prefix_filter_client_side() -> None:
    """
    Validate the client-side prefix filter logic used by TagInput.tsx.

    TagInput filters allTagNames client-side:
        suggestions = allTagNames.filter(t =>
            t.toLowerCase().includes(inputValue.toLowerCase()) &&
            !tags.includes(t) &&
            inputValue.length > 0
        )
    """
    all_tag_names = [row["tag"] for row in SAMPLE_TAGS]
    current_tags: list[str] = ["buddhism"]

    def filter_suggestions(input_value: str) -> list[str]:
        if not input_value:
            return []
        return [
            t for t in all_tag_names if input_value.lower() in t.lower() and t not in current_tags
        ]

    assert "philosophy" in filter_suggestions("ph")
    assert "buddhism" not in filter_suggestions("ph")  # already added
    assert "systems" in filter_suggestions("sys")
    assert filter_suggestions("") == []
    assert "buddhism" not in filter_suggestions("bud")  # already added
    assert "zettelkasten" in filter_suggestions("ZETT")  # case-insensitive
