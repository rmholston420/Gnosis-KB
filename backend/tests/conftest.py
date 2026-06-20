"""Pytest fixtures for Gnosis test suite.

Provides:
  - async_client / client  : HTTPX async test clients (same instance, two names)
  - test_client            : synchronous Starlette TestClient for sync test files
  - auth_headers           : dummy Authorization header for endpoints that need it
  - test_db                : isolated async session for direct DB operations
  - vault_dir              : temporary directory acting as the vault

External service patching
-------------------------
Three lifespan calls are patched at *fixture* scope so that pytest runs
cleanly on a dev machine with no Postgres, Qdrant, Ollama, or LightRAG:

  1. ensure_collection()         — Qdrant collection setup  → no-op
  2. start_vault_watcher()       — watchdog + initial sync  → mock Observer
  3. graph_rag.initialize()      — LightRAG warm-up         → async no-op

Auth patching
-------------
BOTH require_user AND get_current_user are overridden so every request is
authenticated as FakeUser(id=1) without needing a real JWT or database User
row.

Isolation
---------
test_engine is function-scoped: each test gets a brand-new in-memory SQLite
database with tables freshly created and dropped.

_sync_app / test_client isolation
----------------------------------
_sync_app is a *synchronous* pytest fixture and MUST NOT depend on the async
test_engine fixture — pytest-asyncio cannot inject async fixtures into sync
fixtures.

Instead, _sync_app creates a plain synchronous SQLite engine (sqlalchemy
create_engine, no aiosqlite). asyncio.run() is NOT used here because
pytest-asyncio already owns the running event loop and asyncio.run()
raises RuntimeError when called inside a running loop.

The sync engine is used only for table DDL (create_all / drop_all).
The FastAPI app itself is async; Starlette's TestClient spawns it in a
background thread with anyio, where it gets its own event loop — so the
async session factory (aiosqlite) works fine inside the ASGI app.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine          # sync engine for DDL only
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from gnosis.database import Base, get_db
from gnosis.main import create_app

# ---------------------------------------------------------------------------
# Test database — async, function-scoped
# ---------------------------------------------------------------------------

TEST_DB_URL       = "sqlite+aiosqlite:///:memory:"
TEST_DB_URL_SYNC  = "sqlite:///:memory:"   # sync URL for DDL in sync fixtures


@pytest_asyncio.fixture
async def test_engine():
    """Function-scoped async engine backed by in-memory SQLite."""
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session per test."""
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Vault directory — temporary, pre-populated with PARA folders
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
# Service patches
# ---------------------------------------------------------------------------


class _MockObserver:
    def stop(self) -> None: ...
    def join(self) -> None: ...


async def _mock_start_vault_watcher(owner_id: int = 1) -> _MockObserver:
    return _MockObserver()


# ---------------------------------------------------------------------------
# Fake authenticated user
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
    return _FakeUser()


# ---------------------------------------------------------------------------
# Async client factory
# ---------------------------------------------------------------------------


async def _make_client(test_engine, vault_dir) -> AsyncGenerator[AsyncClient, None]:
    with (
        patch("gnosis.services.vector_store.ensure_collection", return_value=None),
        patch("gnosis.services.vault_sync.start_vault_watcher", new=_mock_start_vault_watcher),
        patch("gnosis.services.graph_rag.graph_rag.initialize", new=AsyncMock(return_value=None)),
    ):
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
        app.dependency_overrides[require_user] = _fake_require_user
        app.dependency_overrides[get_current_user] = _fake_require_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(test_engine, vault_dir) -> AsyncGenerator[AsyncClient, None]:
    async for c in _make_client(test_engine, vault_dir):
        yield c


@pytest_asyncio.fixture
async def client(test_engine, vault_dir) -> AsyncGenerator[AsyncClient, None]:
    async for c in _make_client(test_engine, vault_dir):
        yield c


# ---------------------------------------------------------------------------
# Synchronous TestClient
#
# _sync_app is a plain sync fixture.  It must NOT depend on test_engine
# (async fixture) and must NOT call asyncio.run() — both are incompatible
# with pytest-asyncio's event-loop ownership.
#
# Strategy:
#   1. Create a plain synchronous SQLite engine (no aiosqlite) for DDL only.
#      sqlalchemy's sync create_engine + Base.metadata.create_all / drop_all
#      require no event loop at all.
#   2. Create a SEPARATE async engine (aiosqlite) that the FastAPI app will
#      use for its async DB sessions inside the TestClient's anyio thread.
#   3. Wire the async engine into app.dependency_overrides[get_db].
#   4. Tear down: drop tables via the sync engine, dispose both engines.
#      The async engine is disposed via run_until_complete on a fresh loop
#      *only* during teardown (after pytest-asyncio has finished), which is
#      safe.
# ---------------------------------------------------------------------------


@pytest.fixture
def _sync_app():
    """Patched FastAPI app for sync TestClient — owns its own DB engines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        for folder in [
            "00-inbox", "10-zettelkasten", "20-projects", "30-areas",
            "40-resources", "50-archive", "60-journals", "70-sources", "80-meta",
        ]:
            (vault / folder).mkdir()

        # --- Sync engine: DDL only (no asyncio needed) ---
        sync_engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(sync_engine)

        # --- Async engine: used by the ASGI app inside TestClient's thread ---
        async_engine = create_async_engine(
            TEST_DB_URL,
            echo=False,
            connect_args={"check_same_thread": False},
        )

        with (
            patch("gnosis.services.vector_store.ensure_collection", return_value=None),
            patch("gnosis.services.vault_sync.start_vault_watcher", new=_mock_start_vault_watcher),
            patch("gnosis.services.graph_rag.graph_rag.initialize", new=AsyncMock(return_value=None)),
        ):
            from gnosis import config
            from gnosis.core.auth import get_current_user, require_user

            settings = config.get_settings()
            settings.vault_path = str(vault)

            app = create_app()
            session_factory = async_sessionmaker(bind=async_engine, expire_on_commit=False)

            async def override_get_db():
                async with session_factory() as session:
                    yield session

            app.dependency_overrides[get_db] = override_get_db
            app.dependency_overrides[require_user] = _fake_require_user
            app.dependency_overrides[get_current_user] = _fake_require_user

            yield app
            app.dependency_overrides.clear()

        # Teardown: drop tables synchronously, dispose async engine in a
        # fresh event loop that we create only for this purpose.
        Base.metadata.drop_all(sync_engine)
        sync_engine.dispose()

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(async_engine.dispose())
        finally:
            loop.close()


@pytest.fixture
def test_client(_sync_app) -> TestClient:
    """Synchronous Starlette TestClient for test_tag_autocomplete and
    test_vault_sync_endpoint.
    """
    with TestClient(_sync_app, raise_server_exceptions=False) as tc:
        yield tc


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_headers() -> dict:
    return {"Authorization": "Bearer test-token-gnosis"}
