"""HTTP-level tests for the /api/v1/query router.

Covers:
  POST /query/run                 — execute one-off GQL
  GET  /query/saved               — list saved dashboards
  POST /query/saved               — create saved dashboard
  GET  /query/saved/{id}          — get by id
  PUT  /query/saved/{id}          — update
  DELETE /query/saved/{id}        — delete
  POST /query/saved/{id}/run      — execute saved dashboard

Auth note
---------
auth_headers is a dummy dict only — actual auth is controlled by the
dependency override in conftest.  Use `unauthenticated_client` (which
overrides to _fake_deny_user) to test 401 responses.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# /run — one-off GQL execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_query_valid_returns_200(async_client, auth_headers):
    """A simple valid GQL returns 200 with expected shape."""
    resp = await async_client.post(
        "/api/v1/query/run",
        json={"query": "SORT title ASC LIMIT 10"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "rows" in body
    assert "total" in body
    assert "query_time_ms" in body


@pytest.mark.asyncio
async def test_run_query_from_filter(async_client, auth_headers):
    resp = await async_client.post(
        "/api/v1/query/run",
        json={"query": "FROM 10-zettelkasten LIMIT 5"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json()["rows"], list)


@pytest.mark.asyncio
async def test_run_query_where_condition(async_client, auth_headers):
    resp = await async_client.post(
        "/api/v1/query/run",
        json={"query": "WHERE status=draft LIMIT 5"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_run_query_invalid_gql_returns_422(async_client, auth_headers):
    resp = await async_client.post(
        "/api/v1/query/run",
        json={"query": "JOIN notes ON id"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_run_query_requires_auth(unauthenticated_client):
    """Unauthenticated requests must be rejected with 401."""
    resp = await unauthenticated_client.post(
        "/api/v1/query/run",
        json={"query": "SORT title ASC LIMIT 1"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /saved — list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_saved_empty(async_client, auth_headers):
    resp = await async_client.get("/api/v1/query/saved", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_saved_requires_auth(unauthenticated_client):
    resp = await unauthenticated_client.get("/api/v1/query/saved")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /saved — create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_saved_returns_201(async_client, auth_headers):
    resp = await async_client.post(
        "/api/v1/query/saved",
        json={"name": "My Dashboard", "query": "SORT title ASC LIMIT 5"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Dashboard"
    assert body["query"] == "SORT title ASC LIMIT 5"
    assert "id" in body


@pytest.mark.asyncio
async def test_create_saved_with_description(async_client, auth_headers):
    resp = await async_client.post(
        "/api/v1/query/saved",
        json={"name": "Described", "query": "LIMIT 2", "description": "My desc"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["description"] == "My desc"


@pytest.mark.asyncio
async def test_create_saved_invalid_gql_returns_422(async_client, auth_headers):
    resp = await async_client.post(
        "/api/v1/query/saved",
        json={"name": "Bad", "query": "JOIN notes ON id"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_saved_duplicate_name_returns_409(async_client, auth_headers):
    payload = {"name": "Duplicate", "query": "LIMIT 1"}
    r1 = await async_client.post("/api/v1/query/saved", json=payload, headers=auth_headers)
    assert r1.status_code == 201
    r2 = await async_client.post("/api/v1/query/saved", json=payload, headers=auth_headers)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_create_saved_appears_in_list(async_client, auth_headers):
    await async_client.post(
        "/api/v1/query/saved",
        json={"name": "Listed", "query": "LIMIT 2"},
        headers=auth_headers,
    )
    resp = await async_client.get("/api/v1/query/saved", headers=auth_headers)
    names = [d["name"] for d in resp.json()]
    assert "Listed" in names


# ---------------------------------------------------------------------------
# /saved/{id} — get
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_saved_returns_dashboard(async_client, auth_headers):
    create = await async_client.post(
        "/api/v1/query/saved",
        json={"name": "Getter", "query": "LIMIT 3"},
        headers=auth_headers,
    )
    sq_id = create.json()["id"]
    resp = await async_client.get(f"/api/v1/query/saved/{sq_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Getter"


@pytest.mark.asyncio
async def test_get_saved_not_found_returns_404(async_client, auth_headers):
    resp = await async_client.get("/api/v1/query/saved/999999", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /saved/{id} — update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_saved_name(async_client, auth_headers):
    create = await async_client.post(
        "/api/v1/query/saved",
        json={"name": "OldName", "query": "LIMIT 1"},
        headers=auth_headers,
    )
    sq_id = create.json()["id"]
    resp = await async_client.put(
        f"/api/v1/query/saved/{sq_id}",
        json={"name": "NewName"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "NewName"


@pytest.mark.asyncio
async def test_update_saved_query_text(async_client, auth_headers):
    create = await async_client.post(
        "/api/v1/query/saved",
        json={"name": "UpdateQ", "query": "LIMIT 1"},
        headers=auth_headers,
    )
    sq_id = create.json()["id"]
    resp = await async_client.put(
        f"/api/v1/query/saved/{sq_id}",
        json={"query": "LIMIT 5"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["query"] == "LIMIT 5"


@pytest.mark.asyncio
async def test_update_saved_description(async_client, auth_headers):
    create = await async_client.post(
        "/api/v1/query/saved",
        json={"name": "UpdateDesc", "query": "LIMIT 1"},
        headers=auth_headers,
    )
    sq_id = create.json()["id"]
    resp = await async_client.put(
        f"/api/v1/query/saved/{sq_id}",
        json={"description": "updated desc"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "updated desc"


@pytest.mark.asyncio
async def test_update_saved_invalid_gql_returns_422(async_client, auth_headers):
    create = await async_client.post(
        "/api/v1/query/saved",
        json={"name": "UpdateBad", "query": "LIMIT 1"},
        headers=auth_headers,
    )
    sq_id = create.json()["id"]
    resp = await async_client.put(
        f"/api/v1/query/saved/{sq_id}",
        json={"query": "JOIN notes ON id"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_saved_not_found_returns_404(async_client, auth_headers):
    resp = await async_client.put(
        "/api/v1/query/saved/999999",
        json={"name": "Ghost"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /saved/{id} — delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_saved_returns_204(async_client, auth_headers):
    create = await async_client.post(
        "/api/v1/query/saved",
        json={"name": "ToDelete", "query": "LIMIT 1"},
        headers=auth_headers,
    )
    sq_id = create.json()["id"]
    resp = await async_client.delete(f"/api/v1/query/saved/{sq_id}", headers=auth_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_saved_then_get_returns_404(async_client, auth_headers):
    create = await async_client.post(
        "/api/v1/query/saved",
        json={"name": "ToDelete2", "query": "LIMIT 1"},
        headers=auth_headers,
    )
    sq_id = create.json()["id"]
    await async_client.delete(f"/api/v1/query/saved/{sq_id}", headers=auth_headers)
    resp = await async_client.get(f"/api/v1/query/saved/{sq_id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_saved_not_found_returns_404(async_client, auth_headers):
    resp = await async_client.delete("/api/v1/query/saved/999999", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /saved/{id}/run — execute saved dashboard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_saved_returns_query_result(async_client, auth_headers):
    create = await async_client.post(
        "/api/v1/query/saved",
        json={"name": "RunMe", "query": "SORT title ASC LIMIT 5"},
        headers=auth_headers,
    )
    sq_id = create.json()["id"]
    resp = await async_client.post(f"/api/v1/query/saved/{sq_id}/run", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "rows" in body
    assert "total" in body
    assert "query_time_ms" in body


@pytest.mark.asyncio
async def test_run_saved_not_found_returns_404(async_client, auth_headers):
    resp = await async_client.post("/api/v1/query/saved/999999/run", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_saved_requires_auth(unauthenticated_client):
    resp = await unauthenticated_client.post("/api/v1/query/saved/1/run")
    assert resp.status_code == 401
