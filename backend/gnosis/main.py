"""Gnosis Knowledge Base — FastAPI application factory."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gnosis.config import get_settings
from gnosis.core.events import lifespan
from gnosis.core.exceptions import gnosis_exception_handler
from gnosis.routers import notes, search, graph, ai, ingest, tags, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Gnosis sovereign AI-augmented personal knowledge base.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(Exception, gnosis_exception_handler)  # type: ignore[arg-type]

    app.include_router(health.router)
    app.include_router(notes.router)
    app.include_router(search.router)
    app.include_router(graph.router)
    app.include_router(ai.router)
    app.include_router(ingest.router)
    app.include_router(tags.router)

    # Mount MCP server — lazy so import failure doesn’t crash the whole app
    try:
        from fastapi_mcp import FastApiMCP  # type: ignore[import-untyped]
        mcp = FastApiMCP(
            app,
            name="gnosis-kb",
            description="Gnosis Knowledge Base MCP server.",
            base_url="http://localhost:8010",
        )
        mcp.mount()
        logger.info("MCP server mounted at /mcp")
    except Exception as exc:
        logger.warning("fastapi-mcp not available — MCP endpoint disabled: %s", exc)

    logger.info("Gnosis API ready. Docs: /docs")
    return app


app = create_app()
