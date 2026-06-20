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
  /api/v1/ingest   — vault watcher ingest
  /api/v1/users    — user profiles + vault sharing (multi-user)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from gnosis.config import get_settings
from gnosis.core.rate_limit import limiter
from gnosis.database import get_engine, Base
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


_settings = get_settings()

app = FastAPI(
    title="Gnosis Knowledge Base API",
    version="0.4.1",
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
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_V1 = "/api/v1"
app.include_router(health.router, prefix=API_V1)
app.include_router(auth.router, prefix=API_V1)
app.include_router(notes.router, prefix=API_V1)
app.include_router(search.router, prefix=API_V1)
app.include_router(ai.router, prefix=API_V1)
app.include_router(graph.router, prefix=API_V1)
app.include_router(query.router, prefix=API_V1)
app.include_router(review.router, prefix=API_V1)
app.include_router(export.router, prefix=API_V1)
app.include_router(tags.router, prefix=API_V1)
app.include_router(ingest.router, prefix=API_V1)
app.include_router(users.router, prefix=API_V1)
