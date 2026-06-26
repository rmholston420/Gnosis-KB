"""FastAPI application factory for Gnosis KB."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[misc]
    """Manage application startup and shutdown."""
    from gnosis.core.events import on_startup

    await on_startup()

    observer: Any = None
    try:
        from gnosis.services.vault_sync import start_vault_watcher

        observer = await start_vault_watcher()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vault watcher could not start: %s", exc)

    yield

    if observer is not None:
        try:
            observer.stop()  # type: ignore[union-attr]
            observer.join()  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error stopping vault watcher: %s", exc)

    from gnosis.core.events import on_shutdown

    await on_shutdown()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from gnosis.config import get_settings

    settings = get_settings()

    application = FastAPI(
        title="Gnosis KB",
        description="Personal knowledge base API",
        version=getattr(settings, "app_version", "0.1.0"),
        lifespan=lifespan,
    )

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address

        limiter = Limiter(key_func=get_remote_address)
        application.state.limiter = limiter
        application.add_exception_handler(  # type: ignore[arg-type]
            RateLimitExceeded, _rate_limit_exceeded_handler
        )
    except ImportError:
        logger.info("slowapi not installed; rate limiting disabled")

    from gnosis.routers import (
        admin,
        ai,
        auth,
        export,
        graph,
        health,
        ingest,
        neurolink,
        notes,
        query,
        review,
        search,
        tags,
        users,
        vault,
        ws,
    )

    _api_v1 = "/api/v1"
    application.include_router(health.router, prefix=_api_v1)
    application.include_router(auth.router, prefix=_api_v1)
    application.include_router(notes.router, prefix=_api_v1)
    application.include_router(tags.router, prefix=_api_v1)
    application.include_router(search.router, prefix=_api_v1)
    application.include_router(query.router, prefix=_api_v1)
    application.include_router(review.router, prefix=_api_v1)
    application.include_router(export.router, prefix=_api_v1)
    application.include_router(ai.router, prefix=_api_v1)
    application.include_router(graph.router, prefix=_api_v1)
    application.include_router(ingest.router, prefix=_api_v1)
    application.include_router(vault.router, prefix=_api_v1)
    application.include_router(admin.router, prefix=_api_v1)
    application.include_router(users.router, prefix=_api_v1)
    application.include_router(neurolink.router, prefix=_api_v1)
    # WebSocket router — must be last so the WS upgrade doesn't interfere
    # with HTTP middleware ordering.
    application.include_router(ws.router, prefix=_api_v1)

    @application.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return application


app = create_app()
