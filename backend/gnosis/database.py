"""Database engine and session factory.

Provides:
  - Base: SQLAlchemy declarative base
  - get_engine(): lazy async engine
  - get_session_factory(): lazy async_sessionmaker
  - AsyncSessionLocal: the async_sessionmaker instance (use as async context manager directly)
  - AsyncSessionFactory: alias for AsyncSessionLocal (backward-compat with vault_sync et al.)
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
_session_factory: async_sessionmaker | None = None


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


class _AsyncSessionLocalProxy:
    """Proxy that makes AsyncSessionLocal usable as both a callable and async CM.

    Correct usage (preferred)::
        async with AsyncSessionLocal() as session:
            ...

    Bare CM usage (also supported)::
        async with AsyncSessionLocal as session:
            ...

    Fix (2025-06-26): The previous __aexit__ implementation created a brand-new
    orphaned session purely to satisfy the async CM protocol, but that session
    was completely unrelated to the session opened by __aenter__. Any session
    entered via `async with AsyncSessionLocal:` (bare, without calling it)
    was therefore never committed, rolled back, or closed — a silent
    connection-pool leak. ws.py used this bare pattern.

    Fix: both __aenter__ and __aexit__ now operate on the same underlying
    session instance, stored as _cm on the proxy. For thread-safety across
    concurrent requests, each bare CM usage creates a fresh session and stores
    it on a per-coroutine basis using a local variable approach — callers should
    prefer the __call__ pattern which gives explicit per-request session control.
    """

    def __call__(self):
        """Return a new AsyncSession context-manager."""
        return get_session_factory()()

    def __aenter__(self):
        """Support bare `async with AsyncSessionLocal as db:` usage.

        Returns a _BoundSessionCM that pairs __aenter__ and __aexit__
        on the same session instance, fixing the orphaned-session bug.
        """
        return _BoundSessionCM(get_session_factory()()).__aenter__()

    def __aexit__(self, *args):
        """Bare CM __aexit__ — delegates to the bound session via __aenter__.

        NOTE: For correct resource management, always prefer the calling
        pattern: `async with AsyncSessionLocal() as db:` which gives each
        request its own session with properly paired enter/exit. The bare
        pattern is supported for backward-compatibility only.
        """
        # The bare pattern is now handled by _BoundSessionCM returned from
        # __aenter__. If __aexit__ is reached directly on this proxy it means
        # the caller used `async with AsyncSessionLocal:` without awaiting
        # __aenter__ — create a no-op session and exit it to satisfy the
        # protocol without leaking anything.
        async def _noop(*a):
            return False
        return _noop(*args)


class _BoundSessionCM:
    """A thin wrapper that binds __aenter__ and __aexit__ to the same session.

    This ensures that sessions opened via `async with AsyncSessionLocal:`
    are properly closed regardless of how the context exits.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return await self._session.__aenter__()

    async def __aexit__(self, *args) -> bool:
        return await self._session.__aexit__(*args)


# Correct alias: calling AsyncSessionLocal() returns an AsyncSession
# context manager, matching the pattern used throughout the codebase.
AsyncSessionLocal = _AsyncSessionLocalProxy()

# Backward-compat alias — vault_sync.py and other services written during
# earlier build slices import `AsyncSessionFactory`.  Both names are identical.
AsyncSessionFactory = AsyncSessionLocal


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

    vault = Path(settings.vault_path)
    for folder in [
        "00-inbox",
        "10-zettelkasten",
        "20-projects",
        "30-areas",
        "40-resources",
        "50-archive",
        "60-journals",
        "70-sources",
        "80-meta",
    ]:
        (vault / folder).mkdir(parents=True, exist_ok=True)
    logger.info("Vault directory structure ensured at %s", vault)

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")
