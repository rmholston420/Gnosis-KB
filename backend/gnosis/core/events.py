"""FastAPI lifespan: startup / shutdown."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from gnosis.config import get_settings
from gnosis.core.auth import get_password_hash
from gnosis.database import AsyncSessionLocal, init_db
from gnosis.models.user import User

logger = logging.getLogger(__name__)


async def _ensure_default_user() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none() is None:
            db.add(User(
                username="admin",
                email="admin@gnosis.local",
                hashed_password=get_password_hash("gnosis"),
                is_active=True,
                is_superuser=True,
            ))
            await db.commit()
            logger.info("Default admin user created (username=admin password=gnosis)")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info("Starting Gnosis KB v%s", settings.app_version)

    # 1. DB
    try:
        await init_db()
    except Exception as exc:
        logger.error("DB init failed: %s", exc)
        raise

    # 2. Default user
    try:
        await _ensure_default_user()
    except Exception as exc:
        logger.warning("Could not create default user: %s", exc)

    # 3. Vault watcher
    try:
        from gnosis.services.vault_sync import start_vault_watcher
        app.state.vault_watcher = await start_vault_watcher()
        logger.info("Vault watcher started")
    except Exception as exc:
        logger.warning("Vault watcher unavailable: %s", exc)
        app.state.vault_watcher = None

    # 4. LightRAG — entirely optional, degrades gracefully
    try:
        from gnosis.services.graph_rag import init_lightrag
        await init_lightrag()
        logger.info("LightRAG initialized")
    except Exception as exc:
        logger.warning("LightRAG unavailable (AI graph features disabled): %s", exc)

    logger.info("Gnosis startup complete")
    yield

    # Shutdown
    watcher = getattr(app.state, "vault_watcher", None)
    if watcher:
        try:
            watcher.stop()
            watcher.join()
        except Exception as exc:
            logger.warning("Vault watcher stop error: %s", exc)
    logger.info("Gnosis shutdown complete")
