"""FastAPI application factory with MCP mount, rate limiting, CORS, and request tracing."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from gnosis.core.logging import configure_logging
from gnosis.core.middleware import RequestIDMiddleware, TimingMiddleware, install_request_id_filter
from gnosis.core.rate_limit import limiter
from gnosis.database import init_db
from gnosis.routers import auth, export, folders, graph, health, notes, review, search, tags

configure_logging()
install_request_id_filter()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle hook."""
    logger.info("Gnosis API starting up")
    await init_db()
    await _bootstrap_admin()
    yield
    logger.info("Gnosis API shutting down")


async def _bootstrap_admin() -> None:
    """Create the default admin user on first run if no users exist."""
    from sqlalchemy import select
    from gnosis.core.auth import get_password_hash
    from gnosis.config import settings
    from gnosis.database import AsyncSessionLocal
    from gnosis.models.user import User

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none() is None:
            user = User(
                email=settings.initial_admin_email,
                hashed_password=get_password_hash(settings.initial_admin_password),
                is_superuser=True,
            )
            db.add(user)
            await db.commit()
            logger.info("Bootstrap admin created: %s", settings.initial_admin_email)


app = FastAPI(
    title="Gnosis Knowledge Base API",
    version="1.0.0",
    description="Sovereign, AI-augmented personal knowledge base with MCP server.",
    lifespan=lifespan,
)

# ── Rate limiting ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)

# ── Request tracing & timing ───────────────────────────────────────────────────
app.add_middleware(RequestIDMiddleware)
app.add_middleware(TimingMiddleware)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
for r in (notes.router, search.router, review.router, tags.router, folders.router,
          graph.router, auth.router, export.router, health.router):
    app.include_router(r, prefix="/api/v1")

# ── MCP Server ─────────────────────────────────────────────────────────────────
try:
    from fastapi_mcp import FastApiMCP
    mcp = FastApiMCP(
        app,
        name="gnosis-kb",
        description="Gnosis Knowledge Base MCP — read/write/search/reason over your personal knowledge graph.",
        base_url="http://localhost:8010",
    )
    mcp.mount()
    logger.info("MCP server mounted at /mcp")
except ImportError:
    logger.warning("fastapi-mcp not installed — MCP server disabled")
