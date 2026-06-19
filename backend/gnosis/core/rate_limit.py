"""Rate limiting helpers using slowapi (Starlette middleware wrapper for limits).

Usage in a router:
    from gnosis.core.rate_limit import limiter
    @router.get("/search")
    @limiter.limit("30/minute")
    async def search(request: Request, ...):
        ...

The Limiter instance is attached to app.state.limiter in main.py.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    headers_enabled=True,  # Adds X-RateLimit-* headers to every response
)
