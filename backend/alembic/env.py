"""Alembic environment configuration for Gnosis migrations."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all models so metadata is populated
import gnosis.models  # noqa: F401
from alembic import context
from gnosis.config import get_settings

# Import Base so Alembic can detect all models
from gnosis.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_async_url() -> str:
    """Return the async (asyncpg) database URL for the async migration engine."""
    return get_settings().database_url


def get_sync_url() -> str:
    """Return the synchronous (psycopg2) database URL for offline migrations."""
    return get_settings().database_url_sync


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode without a DB connection."""
    url = get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations using an existing connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine.

    The URL passed here MUST use the asyncpg driver — async_engine_from_config
    will raise InvalidRequestError if a sync driver (psycopg2) is supplied.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_async_url()  # asyncpg URL
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
