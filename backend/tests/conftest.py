"""Pytest fixtures for Gnosis test suite.

Provides:
  - async_client / client        : HTTPX async test clients, authenticated as FakeUser
  - unauthenticated_client       : HTTPX async test client that always returns HTTP 401
  - test_client                  : synchronous Starlette TestClient for sync test files
  - auth_headers                 : dummy Authorization header for endpoints that need it
  - test_db                      : isolated async session for direct DB operations
  - vault_dir                    : temporary directory acting as the vault

External service patching
-------------------------
Three lifespan calls are patched so that pytest runs cleanly on a dev
machine with no Postgres, Qdrant, Ollama, or LightRAG:

  1. ensure_collection()         — Qdrant collection setup  → no-op
  2. start_vault_watcher()       — watchdog + initial sync  → mock Observer
  3. graph_rag.initialize()      — LightRAG warm-up         → async no-op

Auth patching
-------------
BOTH require_user AND get_current_user are overridden.

_fake_require_user() — zero-argument, always returns _FakeUser(id=1).
  Used by async_client / client / test_client (the default authenticated
  fixtures). DO NOT add Request or any special type as a parameter —
  FastAPI reflects dependency-override signatures into the OpenAPI schema
  at app startup and will raise FastAPIError for injection-only types like
  starlette.requests.Request.

_fake_deny_user() — zero-argument, always raises HTTP 401.
  Used by unauthenticated_client. Auth-guard tests that assert 401/403
  should use the `unauthenticated_client` fixture instead of `client`.

Isolation
---------
test_engine is function-scoped: each test gets a brand-new in-memory SQLite
database with tables freshly created and dropped.

StaticPool — why it is required
--------------------------------
sqlite+aiosqlite:///:memory: creates a per-connection in-memory database.
SQLAlchemy's default pool opens multiple connections, so a second checkout
(e.g. the selectinload() subquery that fires after commit()) lands on a
fresh connection that has no schema and no data.  StaticPool forces the
entire async engine to reuse one connection for the lifetime of the test,
so every query — including selectinload subqueries — sees the same data.

_sync_app vault path cache
--------------------------
vault_sync._VAULT_PATH is a module-level cache set on first call to
_get_vault_path(). _sync_app resets it to None before and after each test
so that _get_vault_path() re-reads settings.vault_path (which is patched
to the tempdir) rather than returning a stale value from a previous test
or from the real on-disk vault.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import connect as sqlite3_connect
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from gnosis.database import Base, get_db
from gnosis.main import create_app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Async engine — function-scoped + StaticPool
#
# StaticPool is mandatory for sqlite:///:memory: tests.
# Without it the async connection pool can open a second physical connection
# for selectinload() sub-SELECTs after commit(), and that second connection
# sees a completely empty in-memory DB (each SQLite :memory: DB is private
# to its connection).  StaticPool forces every checkout to reuse the same
# single connection, so all queries within a test share the same data.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Vault directory
# ---------------------------------------------------------------------------


@pytest.fixture
def vault_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        for folder in [
            "00-inbox", "10-zettelkasten", "20-projects", "30-areas",
            "40-resources", "50-archive", "60-journals", "70-sources", "80-meta",
        ]:
            (vault / folder).mkdir()
        yield vault


# ---------------------------------------------------------------------------
# Service stubs
# ---------------------------------------------------------------------------


class _MockObserver:
    def stop(self) -> None: ...
    def join(self) -> None: ...


async def _mock_start_vault_watcher(owner_id: int = 1) -> _MockObserver:
    return _MockObserver()


# ---------------------------------------------------------------------------
# Fake users
# ---------------------------------------------------------------------------


@dataclass
class _FakeUser:
    id: int = 1
    email: str = "test@gnosis.local"
    full_name: str | None = "Test User"
    vault_slug: str | None = "test"
    vault_path: str | None = None
    is_active: bool = True
    is_superuser: bool = False


async def _fake_require_user() -> _FakeUser:
    """Always return a fake authenticated user.

    IMPORTANT: keep this zero-argument with no special types (e.g. no
    starlette.requests.Request).  FastAPI reflects dependency-override
    signatures into the OpenAPI schema at startup and raises FastAPIError
    for injection-only types that are not valid Pydantic field types.
    """
    return _FakeUser()


async def _fake_deny_user() -> _FakeUser:
    """Always raise HTTP 401.

    Used by the unauthenticated_client fixture so auth-guard tests receive
    the expected 401/403 without needing a real JWT stack.
    """
    raise HTTPException(status_code=401, detail="Not authenticated")


# ---------------------------------------------------------------------------
# Shared app factory
# ---------------------------------------------------------------------------


def _make_patches():
    return (
        patch("gnosis.services.vector_store.ensure_collection", return_value=None),
        patch("gnosis.services.vault_sync.start_vault_watcher", new=_mock_start_vault_watcher),
        patch("gnosis.services.graph_rag.graph_rag.initialize", new=AsyncMock(return_value=None)),
    )


# ---------------------------------------------------------------------------
# Async clients
# ---------------------------------------------------------------------------


async def _make_client(
    test_engine,
    vault_dir,
    *,
    auth_override=_fake_require_user,
) -> AsyncGenerator[AsyncClient, None]:
    p1, p2, p3 = _make_patches()
    with p1, p2, p3:
        from gnosis import config
        from gnosis.core.auth import get_current_user, require_user

        settings = config.get_settings()
        settings.vault_path = str(vault_dir)

        app = create_app()
        session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[require_user] = auth_override
        app.dependency_overrides[get_current_user] = auth_override

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(test_engine, vault_dir) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated HTTPX client — all requests resolve to FakeUser(id=1)."""
    async for c in _make_client(test_engine, vault_dir, auth_override=_fake_require_user):
        yield c


@pytest_asyncio.fixture
async def client(test_engine, vault_dir) -> AsyncGenerator[AsyncClient, None]:
    """Alias for async_client (backward-compat)."""
    async for c in _make_client(test_engine, vault_dir, auth_override=_fake_require_user):
        yield c


@pytest_asyncio.fixture
async def unauthenticated_client(test_engine, vault_dir) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX client where every request raises HTTP 401.

    Use this fixture in auth-guard tests that assert the endpoint rejects
    unauthenticated callers::

        async def test_vault_sync_requires_auth(unauthenticated_client):
            r = await unauthenticated_client.post("/api/v1/vault/sync")
            assert r.status_code in (401, 403)
    """
    async for c in _make_client(test_engine, vault_dir, auth_override=_fake_deny_user):
        yield c


# ---------------------------------------------------------------------------
# Synchronous TestClient
#
# _sync_app owns its own DB engines and vault dir. It must NOT depend on
# test_engine (async fixture) and must NOT call asyncio.run() — both are
# incompatible with pytest-asyncio's event-loop ownership.
#
# StaticPool is used here for the same reason as test_engine: without it
# the async engine used by the ASGI app can open a second connection for
# sub-queries that sees an empty in-memory DB.
#
# _VAULT_PATH reset:
#   vault_sync._VAULT_PATH is a module-level cache. We reset it to None
#   before patching settings.vault_path so _get_vault_path() re-reads the
#   patched value. We reset again in the finally block so subsequent tests
#   (including async tests) start clean.
# ---------------------------------------------------------------------------


@pytest.fixture
def _sync_app():
    import gnosis.services.vault_sync as _vs

    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        for folder in [
            "00-inbox", "10-zettelkasten", "20-projects", "30-areas",
            "40-resources", "50-archive", "60-journals", "70-sources", "80-meta",
        ]:
            (vault / folder).mkdir()

        sync_engine = create_engine(
            "sqlite:///:memory:",
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(sync_engine)

        async_engine = create_async_engine(
            TEST_DB_URL,
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        _vs._VAULT_PATH = None

        try:
            p1, p2, p3 = _make_patches()
            with p1, p2, p3:
                from gnosis import config
                from gnosis.core.auth import get_current_user, require_user

                settings = config.get_settings()
                settings.vault_path = str(vault)

                app = create_app()
                session_factory = async_sessionmaker(
                    bind=async_engine, expire_on_commit=False
                )

                async def override_get_db():
                    async with session_factory() as session:
                        yield session

                app.dependency_overrides[get_db] = override_get_db
                app.dependency_overrides[require_user] = _fake_require_user
                app.dependency_overrides[get_current_user] = _fake_require_user

                yield app
                app.dependency_overrides.clear()
        finally:
            Base.metadata.drop_all(sync_engine)
            sync_engine.dispose()

            import asyncio
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(async_engine.dispose())
            finally:
                loop.close()

            _vs._VAULT_PATH = None


@pytest.fixture
def test_client(_sync_app) -> TestClient:
    with TestClient(_sync_app, raise_server_exceptions=False) as tc:
        yield tc


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_headers() -> dict:
    return {"Authorization": "Bearer test-token-gnosis"}
