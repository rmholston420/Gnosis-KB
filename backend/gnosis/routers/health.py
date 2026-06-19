"""Health check router — liveness and readiness probes.

Endpoints
---------
GET /health/ping      — Liveness: always 200 {"status": "pong"}
GET /health/          — Readiness: checks DB, Qdrant, disk space
                        Returns 200 when all checks pass, 503 when any fail.

Docker / k8s usage
------------------
  HEALTHCHECK --interval=30s --timeout=5s --retries=3 \\
    CMD wget -qO- http://localhost:8010/api/v1/health/ping || exit 1
"""
from __future__ import annotations

import shutil
import time
from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.config import settings
from gnosis.database import get_db

router = APIRouter(prefix="/health", tags=["observability"])
_start_time = time.time()

# Minimum free disk space before we report degraded (bytes)
_MIN_FREE_BYTES = 500 * 1024 * 1024  # 500 MiB


@router.get("/", summary="Readiness probe — checks DB, Qdrant, and disk space")
async def health(response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return 200 when everything is healthy, 503 when any check fails."""
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

    # Disk space probe (vault directory or cwd)
    try:
        vault_path = getattr(settings, "vault_path", "/vault")
        usage = shutil.disk_usage(vault_path)
        free_gb = round(usage.free / (1024 ** 3), 2)
        if usage.free < _MIN_FREE_BYTES:
            checks["disk"] = f"low: {free_gb} GiB free"
        else:
            checks["disk"] = f"ok ({free_gb} GiB free)"
    except Exception as exc:  # noqa: BLE001
        checks["disk"] = f"error: {exc}"

    overall = "healthy" if all(v.startswith("ok") for v in checks.values()) else "degraded"
    if overall == "degraded":
        response.status_code = 503

    return {
        "status": overall,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "checks": checks,
        "version": "1.0.0",
    }


@router.get("/ping", summary="Liveness probe — always returns 200")
async def ping() -> dict[str, str]:
    """Minimal liveness check used by Docker/k8s — never returns 503."""
    return {"status": "pong"}
