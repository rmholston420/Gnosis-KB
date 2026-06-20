"""Pytest fixtures for Gnosis test suite.

Provides:
  - async_client / client  : HTTPX async test clients (same instance, two names)
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
require_user is overridden so every request is authenticated as
FakeUser(id=1) without needing a real JWT or database User row.
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gnosis.database import Base, get_db
from gnosis.main import create_app

# ---------------------------------------------------------------------------
# Test database — SQLite (no Postgres needed in CI or local runs)
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///./test_gnosis.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop shared across the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Session-scoped async engine backed by SQLite."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean, rolled-back database session per test."""
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Vault directory — temporary, pre-populated with PARA folders
# ---------------------------------------------------------------------------


@pytest.fixture
def vault_dir():
    """Provide a temporary vault directory with standard PARA sub-folders."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        for folder in [
            "00-inbox", "10-zettelkasten", "20-projects", "30-areas",
            "40-resources", "50-archive", "60-journals", "70-sources", "80-meta",
        ]:
            (vault / folder).mkdir()
        yield vault


# ---------------------------------------------------------------------------
# Service patches — applied per-fixture so lifespan doesn't hit real services
# ---------------------------------------------------------------------------


class _MockObserver:
    """Minimal stand-in for watchdog.observers.Observer."""
    def stop(self) -> None: ...
    def join(self) -> None: ...


async def _mock_start_vault_watcher(owner_id: int = 1) -> _MockObserver:  # noqa: ARG001
    return _MockObserver()


# ---------------------------------------------------------------------------
# Fake authenticated user — returned by the require_user dependency override
# ---------------------------------------------------------------------------


@dataclass
class _FakeUser:
    """Lightweight stand-in for gnosis.models.user.User in tests.

    Uses a plain dataclass so SQLAlchemy's _sa_instance_state guard is never
    triggered.  All fields that routers access are present.
    """
    id: int = 1
    email: str = "test@gnosis.local"
    full_name: str | None = "Test User"
    vault_slug: str | None = "test"
    vault_path: str | None = None
    is_active: bool = True
    is_superuser: bool = False


async def _fake_require_user() -> _FakeUser:
    """Dependency override: always returns the canonical test user."""
    return _FakeUser()


# ---------------------------------------------------------------------------
# Test client factory — shared implementation
# ---------------------------------------------------------------------------


async def _make_client(test_engine, vault_dir) -> AsyncGenerator[AsyncClient, None]:
    """Build a patched HTTPX async client.

    Extracted so both 'async_client' and 'client' fixtures can share the
    same implementation without code duplication.
    """
    with (
        patch(
            "gnosis.services.vector_store.ensure_collection",
            return_value=None,
        ),
        patch(
            "gnosis.services.vault_sync.start_vault_watcher",
            new=_mock_start_vault_watcher,
        ),
        patch(
            "gnosis.services.graph_rag.graph_rag.initialize",
            new=AsyncMock(return_value=None),
        ),
    ):
        from gnosis import config
        from gnosis.core.auth import require_user

        settings = config.get_settings()
        settings.vault_path = str(vault_dir)

        app = create_app()

        session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[require_user] = _fake_require_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c

        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(test_engine, vault_dir) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX async client — primary name used by test_notes, test_export, etc."""
    async for c in _make_client(test_engine, vault_dir):
        yield c


@pytest_asyncio.fixture
async def client(test_engine, vault_dir) -> AsyncGenerator[AsyncClient, None]:
    """Alias for async_client — used by test_ai, test_auth, test_health,
    test_ingest, test_graph, test_moc, test_query, test_tag_autocomplete,
    test_vault_sync_endpoint.
    """
    async for c in _make_client(test_engine, vault_dir):
        yield c


# ---------------------------------------------------------------------------
# Auth headers — dummy Bearer token accepted by patched require_user
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_headers() -> dict:
    """Return Authorization headers for tests that pass headers explicitly.

    The require_user dependency is already overridden to return FakeUser(id=1)
    regardless of the token value, so any non-empty Bearer string works.
    """
    return {"Authorization": "Bearer test-token-gnosis"}
