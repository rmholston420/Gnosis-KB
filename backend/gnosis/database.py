"""Async SQLAlchemy engine and session factory.

Provides:
    - async_engine: the SQLAlchemy async engine
    - AsyncSessionLocal: async session factory
    - Base: declarative base for all ORM models
    - get_db: FastAPI dependency that yields an async session
    - init_db: called at startup to ensure tables/dirs exist
"""

import logging
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from gnosis.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""

    pass


def _build_engine() -> object:
    """Build and return the async SQLAlchemy engine."""
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        echo=settings.debug,
        future=True,
    )
    return engine


async_engine = _build_engine()  # type: ignore[assignment]

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,  # type: ignore[arg-type]
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    Usage:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database: create vault directories, log connection status.

    Called from the FastAPI lifespan context manager on startup.
    Table creation is handled by Alembic migrations, not this function.
    """
    settings = get_settings()

    # Ensure vault PARA directories exist
    for dir_name in settings.vault_dirs:
        vault_dir = settings.vault_path / dir_name
        vault_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Database initialized. Vault path: %s", settings.vault_path)
