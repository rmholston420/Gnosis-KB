"""FastAPI lifespan event handlers.

Handles startup and shutdown logic:
- Startup: init DB, ensure vault dirs, start vault watcher, init LightRAG
- Shutdown: stop vault watcher, close connections
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import select, text

from gnosis.config import get_settings
from gnosis.core.auth import get_password_hash
from gnosis.database import AsyncSessionLocal, init_db
from gnosis.models.user import User

logger = logging.getLogger(__name__)


async def _ensure_default_user() -> None:
    """Create the default admin user if it does not exist.

    In single-user mode, this is the only user. The password defaults to
    'gnosis' and should be changed immediately in production.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()
        if user is None:
            admin = User(
                username="admin",
                email="admin@gnosis.local",
                hashed_password=get_password_hash("gnosis"),
                is_active=True,
                is_superuser=True,
            )
            db.add(admin)
            await db.commit()
            logger.info("Default admin user created (username=admin, password=gnosis)")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan context manager.

    Runs startup tasks before yield and shutdown tasks after yield.
    """
    settings = get_settings()
    logger.info("Starting Gnosis Knowledge Base v%s", settings.app_version)

    # 1. Initialize database and vault directories
    await init_db()

    # 2. Ensure default admin user exists
    try:
        await _ensure_default_user()
    except Exception as e:
        logger.warning("Could not create default user (DB may not be migrated yet): %s", e)

    # 3. Start vault filesystem watcher
    try:
        from gnosis.services.vault_sync import start_vault_watcher
        watcher = await start_vault_watcher()
        app.state.vault_watcher = watcher
        logger.info("Vault watcher started for path: %s", settings.vault_path)
    except Exception as e:
        logger.warning("Vault watcher could not start: %s", e)
        app.state.vault_watcher = None

    # 4. Initialize LightRAG (non-blocking — degrades gracefully if Ollama unavailable)
    try:
        from gnosis.services.graph_rag import init_lightrag
        await init_lightrag()
        logger.info("LightRAG initialized")
    except Exception as e:
        logger.warning("LightRAG initialization failed (AI features degraded): %s", e)

    logger.info("Gnosis startup complete. API on :8010, MCP on :8011")

    yield  # Application runs here

    # --- Shutdown ---
    logger.info("Shutting down Gnosis...")

    if getattr(app.state, "vault_watcher", None):
        try:
            app.state.vault_watcher.stop()
            app.state.vault_watcher.join()
        except Exception as e:
            logger.warning("Error stopping vault watcher: %s", e)

    logger.info("Gnosis shutdown complete")
