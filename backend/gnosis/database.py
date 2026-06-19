"""Database engine and session factory.

Provides:
  - Base: SQLAlchemy declarative base
  - get_engine(): lazy async engine
  - get_session_factory(): lazy async_sessionmaker
  - AsyncSessionLocal: alias for get_session_factory (callable → session)
  - get_db: FastAPI dependency for database sessions
  - get_session: alias for get_db (backward-compat)
  - init_db: create schema and vault directories
"""

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from gnosis.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all Gnosis models."""


# Engine and session factory (initialized lazily on first access)
_engine = None
_session_factory = None


def get_engine():
    """Return the async database engine, creating it if needed."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker:
    """Return the async session factory, creating it if needed."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


# Convenience alias — vault_sync.py and others import this and call it as:
#   async with AsyncSessionLocal() as session: ...
AsyncSessionLocal = get_session_factory


async def get_db():
    """FastAPI dependency: yields an async database session.

    Usage::
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with get_session_factory()() as session:
        yield session


# Backward-compat alias — older routers imported `get_session`
get_session = get_db


async def init_db() -> None:
    """Initialize database tables and vault directory structure.

    Creates all tables defined in Base.metadata.
    Also ensures the vault folder structure exists.
    """
    settings = get_settings()

    # Create vault folders
    for folder in [
        "00-inbox", "10-zettelkasten", "20-projects",
        "30-areas", "40-resources", "50-archive",
        "60-journals", "70-sources", "80-meta",
    ]:
        (settings.vault_path / folder).mkdir(parents=True, exist_ok=True)
    logger.info("Vault directory structure ensured at %s", settings.vault_path)

    # Tables are created via Alembic migrations in production.
    # For dev/test, create directly.
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")
