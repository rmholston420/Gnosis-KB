"""Gnosis Knowledge Base — FastAPI application factory.

Mounts:
  - All API routers at /api/v1/*
  - FastAPI-MCP server at /mcp (port 8011 via separate mount)
  - CORS middleware
  - OpenAPI docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP  # type: ignore[import-untyped]

from gnosis.config import get_settings
from gnosis.core.events import lifespan
from gnosis.core.exceptions import gnosis_exception_handler
from gnosis.routers import (
    notes,
    search,
    graph,
    ai,
    ingest,
    tags,
    health,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
Gnosis is a sovereign, Linux-native, AI-augmented personal knowledge base.

All notes are stored as plain Markdown files. This API provides:
- Full CRUD for notes with automatic vault filesystem sync
- Hybrid BM25 + vector search (Qdrant)
- Knowledge graph traversal (NetworkX)
- AI-powered features: LightRAG chat, summarization, critique, link suggestions
- Document ingestion: PDF, DOCX, PPTX, XLSX, images
- MCP server for AI agent integration (FastAPI-MCP)
""",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(Exception, gnosis_exception_handler)  # type: ignore[arg-type]

    # Routers
    app.include_router(health.router)
    app.include_router(notes.router)
    app.include_router(search.router)
    app.include_router(graph.router)
    app.include_router(ai.router)
    app.include_router(ingest.router)
    app.include_router(tags.router)

    # MCP server: auto-expose all FastAPI routes as MCP tools
    # AI agents connect at http://localhost:8011/mcp
    mcp = FastApiMCP(
        app,
        name="gnosis-kb",
        description=(
            "Gnosis Knowledge Base MCP server. "
            "Tools for reading, writing, searching, and reasoning over a personal knowledge graph."
        ),
        base_url="http://localhost:8010",
    )
    mcp.mount()  # Mounts at /mcp on the same process

    logger.info("Gnosis API initialized. Docs at /docs, MCP at /mcp")
    return app


app = create_app()
