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

    # Ensure DB tables exist (idempotent — safe to run on every startup).
    try:
        from gnosis.database import init_db

        await init_db()
        logger.info("Database schema initialised")
    except Exception as exc:  # noqa: BLE001
        logger.error("Database init failed — app may be non-functional: %s", exc)

    # Ensure the Qdrant collection exists (idempotent — no-op if it already exists).
    # Fix (2025-06-26): ensure_collection() was never called at startup, so on a
    # fresh deploy with an empty Qdrant instance every upsert_note() call raised
    # UnexpectedResponse (collection not found), silently dropping all vectors.
    try:
        from gnosis.services.vector_store import ensure_collection

        ensure_collection()
        logger.info("Qdrant collection ensured")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Qdrant collection init skipped (Qdrant may be unavailable): %s", exc)

    # Pre-warm the LightRAG graph store if available.
    try:
        from gnosis.services.graph_rag import graph_rag as graph_rag_service

        await graph_rag_service.initialize()
        logger.info("LightRAG graph store initialised")
    except Exception as exc:  # noqa: BLE001
        logger.warning("LightRAG init skipped: %s", exc)


async def on_shutdown() -> None:
    """Run once when the FastAPI application shuts down."""
    logger.info("Gnosis KB shutting down")
