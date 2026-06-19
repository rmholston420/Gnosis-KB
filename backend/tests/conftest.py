"""Pytest fixtures for Gnosis test suite.

Provides:
  - async_client: HTTPX async test client with in-memory SQLite DB
  - test_db: isolated async session for direct DB operations
  - test_vault: temporary directory acting as the vault
"""

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gnosis.database import Base, get_db
from gnosis.main import create_app

# Use SQLite for tests (no PostgreSQL needed in CI)
TEST_DB_URL = "sqlite+aiosqlite:///./test_gnosis.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test async engine with SQLite."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test."""
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def vault_dir():
    """Provide a temporary vault directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        for folder in [
            "00-inbox", "10-zettelkasten", "20-projects", "30-areas",
            "40-resources", "50-archive", "60-journals", "70-sources", "80-meta",
        ]:
            (vault / folder).mkdir()
        yield vault


@pytest_asyncio.fixture
async def async_client(test_engine, vault_dir) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX async client wired to the FastAPI app with test DB and vault."""
    from gnosis import config
    settings = config.get_settings()
    settings.vault_path = vault_dir

    app = create_app()

    # Override DB dependency
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
