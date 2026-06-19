"""Health check router — liveness and readiness probes for DB and Qdrant."""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.config import settings
from gnosis.database import get_db

router = APIRouter(prefix="/health", tags=["observability"])
_start_time = time.time()


@router.get("/", summary="Readiness probe — checks DB + Qdrant liveness")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return 200 when the API, database, and vector store are all reachable."""
    checks: dict[str, str] = {}

    # Database ping
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"

    # Qdrant ping
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"{settings.qdrant_url}/healthz")
        checks["qdrant"] = "ok" if resp.status_code == 200 else f"http {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        checks["qdrant"] = f"error: {exc}"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {
        "status": overall,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "checks": checks,
        "version": "1.0.0",
    }


@router.get("/ping", summary="Liveness probe — always returns 200")
async def ping() -> dict[str, str]:
    """Minimal liveness check used by Docker/k8s."""
    return {"status": "pong"}
