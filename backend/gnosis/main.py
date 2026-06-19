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

from gnosis.config import settings
from gnosis.database import engine, Base
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create tables on startup (dev convenience; production uses Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Gnosis API ready — database tables ensured")
    yield
    logger.info("Gnosis API shutting down")


app = FastAPI(
    title="Gnosis Knowledge Base API",
    version="0.4.0",
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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
app.include_router(users.router, prefix=API_V1)   # ← new
