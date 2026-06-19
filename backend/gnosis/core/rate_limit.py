"""Rate limiting helpers using slowapi.

Usage in a router:
    from gnosis.core.rate_limit import limiter, auth_limit, write_limit
    @router.post("/token")
    @auth_limit
    async def login(request: Request, ...):
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

# Convenience decorators ---------------------------------------------------
# Auth endpoints: strict — 10 attempts/minute per IP to slow brute-force
auth_limit = limiter.limit("10/minute")

# Write endpoints: moderate — 60/minute per IP
write_limit = limiter.limit("60/minute")

# AI/ingest endpoints: expensive — 20/minute per IP
ai_limit = limiter.limit("20/minute")
