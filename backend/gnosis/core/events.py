"""Application startup / shutdown event handlers."""

from __future__ import annotations

import logging

from gnosis.config import get_settings

logger = logging.getLogger(__name__)


async def on_startup() -> None:
    """Run once when the FastAPI application starts."""
    settings = get_settings()

    # Log startup banner
    try:
        from gnosis.models.user import User  # noqa: F401

        logger.info("Gnosis KB starting up")
        logger.info(
            "Database URL: %s", settings.database_url[:40] if settings.database_url else "unset"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Startup banner error: %s", exc)

    # Log optional app version if available
    try:
        version = getattr(settings, "app_version", None)
        if version:
            logger.info("App version: %s", version)
    except Exception:  # noqa: BLE001
        pass

    # Initialise LightRAG if available
    try:
        from gnosis.services import graph_rag

        init_fn = getattr(graph_rag, "init_lightrag", None)
        if init_fn is not None:
            await init_fn()
            logger.info("LightRAG graph store initialised")
    except Exception as exc:  # noqa: BLE001
        logger.warning("LightRAG init skipped: %s", exc)


async def on_shutdown() -> None:
    """Run once when the FastAPI application shuts down."""
    logger.info("Gnosis KB shutting down")
