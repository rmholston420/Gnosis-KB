"""
Gnosis FastAPI application entry point.

Routers registered:
  /api/v1/health   — liveness + readiness probes
  /api/v1/auth     — JWT login
  /api/v1/notes    — CRUD
  /api/v1/search   — FTS + semantic
  /api/v1/ai       — LLM features
  /api/v1/graph    — wikilink graph
  /api/v1/query    — saved queries
  /api/v1/review   — spaced repetition
  /api/v1/export   — vault export
  /api/v1/tags     — tag list
  /api/v1/vault    — vault sync trigger (Slice 15)
  /api/v1/ingest   — vault watcher ingest
  /api/v1/users    — user profiles + vault sharing (multi-user)
  /api/v1/admin    — admin utilities (reindex, etc.)
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from gnosis.config import get_settings
from gnosis.core.rate_limit import limiter
from gnosis.database import Base, get_engine
from gnosis.routers import admin as admin_router
from gnosis.routers import (
    ai,
    auth,
    export,
    graph,
    health,
    ingest,
    notes,
    query,
    review,
    search,
    tags,
    users,
)
from gnosis.routers import vault as vault_router
from gnosis.services.graph_rag import graph_rag
from gnosis.services.llm_provider import llm_provider
from gnosis.services.vault_sync import start_vault_watcher
from gnosis.services.vector_store import ensure_collection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: create tables, init LLM provider, ensure Qdrant collection,
    start vault watcher, then warm-up LightRAG for the primary user."""
    # 1. Ensure all SQLAlchemy tables exist (dev convenience; prod uses Alembic)
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Gnosis API ready — database tables ensured")

    # 2. Initialize LLM provider (probe Ollama / Groq / OpenAI)
    await llm_provider.initialize()

    # 3. Ensure Qdrant collection exists (idempotent)
    ensure_collection()

    # 4. Start vault filesystem watcher + initial full sync
    observer = await start_vault_watcher()

    # 5. Warm-up LightRAG for user_id=1 (primary/admin user) so the graph-based
    #    path is immediately available for thematic queries without the first-request
    #    init penalty.  Additional users are lazily warmed on their first query.
    try:
        await graph_rag.initialize(user_id=1)
        logger.info("LightRAG warm-up complete for user_id=1")
    except Exception as exc:  # noqa: BLE001
        # Non-fatal — Qdrant RAG is the fallback
        logger.warning("LightRAG warm-up skipped: %s", exc)

    yield

    # 6. Graceful shutdown
    observer.stop()
    observer.join()
    logger.info("Gnosis API shutting down")


def create_app() -> FastAPI:
    """Application factory — returns a fully-configured FastAPI instance.

    Used by:
    - Production / Docker: module-level ``app`` below calls this once.
    - Tests: ``conftest.py`` calls this per-session so dependency overrides
      (e.g. test DB, mock vault) can be applied before the first request.
    """
    _settings = get_settings()

    application = FastAPI(
        title="Gnosis Knowledge Base API",
        version="0.6.0",
        description=(
            "REST + SSE backend for the Gnosis personal knowledge management system. "
            "Features: vault sync, Zettelkasten notes, LightRAG graph-RAG, "
            "spaced-repetition review, AI critique, multi-user vault sharing."
        ),
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Rate limiting
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _api_v1 = "/api/v1"  # noqa: N806 — lowercase per ruff N806
    application.include_router(health.router,        prefix=_api_v1)
    application.include_router(auth.router,          prefix=_api_v1)
    application.include_router(notes.router,         prefix=_api_v1)
    application.include_router(search.router,        prefix=_api_v1)
    application.include_router(ai.router,            prefix=_api_v1)
    application.include_router(graph.router,         prefix=_api_v1)
    application.include_router(query.router,         prefix=_api_v1)
    application.include_router(review.router,        prefix=_api_v1)
    application.include_router(export.router,        prefix=_api_v1)
    application.include_router(tags.router,          prefix=_api_v1)
    application.include_router(vault_router.router,  prefix=_api_v1)  # Slice 15
    application.include_router(ingest.router,        prefix=_api_v1)
    application.include_router(users.router,         prefix=_api_v1)
    application.include_router(admin_router.router,  prefix=_api_v1)  # Slice 18

    return application


# Module-level app instance — used by uvicorn / gunicorn in production.
# Tests should call create_app() directly so they get an isolated instance.
app = create_app()
