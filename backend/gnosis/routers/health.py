"""Health check router — liveness and readiness probes.

Endpoints
---------
GET /health/ping              — Liveness: always 200 {"status": "pong"}
GET /health/                  — Readiness: checks DB, Qdrant, disk space
                                Returns 200 when all checks pass, 503 when any fail.
GET /health/providers         — AI provider/model info for Settings panel
POST /health/providers/model  — Set the active AI model

Status semantics
----------------
  "healthy"   — all checks passed (HTTP 200)
  "degraded"  — any check failed (HTTP 503)

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
from pydantic import BaseModel
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
        free_gb = round(usage.free / (1024**3), 2)
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


# ---------------------------------------------------------------------------
# AI provider info — used by the Settings › AI Provider panel
# ---------------------------------------------------------------------------


_KNOWN_PROVIDERS: dict[str, list[str]] = {
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
    ],
    "anthropic": [
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ],
    "ollama": [
        "llama3.2",
        "llama3.1",
        "mistral",
        "gemma2",
        "phi3",
        "qwen2.5",
    ],
    "openrouter": [
        "meta-llama/llama-3.1-8b-instruct",
        "mistralai/mistral-7b-instruct",
        "google/gemma-2-9b-it",
    ],
}


def _detect_provider() -> str:
    """Infer the active AI provider from settings."""
    provider = getattr(settings, "ai_provider", None) or getattr(settings, "llm_provider", None)
    if provider:
        return str(provider).lower()
    if getattr(settings, "openai_api_key", None):
        return "openai"
    if getattr(settings, "anthropic_api_key", None):
        return "anthropic"
    if getattr(settings, "ollama_base_url", None):
        return "ollama"
    return "openai"


def _detect_model(provider: str) -> str:
    """Return the currently configured model, falling back to a sensible default."""
    model = getattr(settings, "ai_model", None) or getattr(settings, "llm_model", None)
    if model:
        return str(model)
    defaults = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-haiku-20241022",
        "ollama": "llama3.2",
        "openrouter": "meta-llama/llama-3.1-8b-instruct",
    }
    return defaults.get(provider, "unknown")


def _is_available(provider: str) -> bool:
    """Return True when the provider appears to be configured."""
    key_map = {
        "openai": "openai_api_key",
        "anthropic": "anthropic_api_key",
        "openrouter": "openrouter_api_key",
    }
    if provider in key_map:
        return bool(getattr(settings, key_map[provider], None))
    if provider == "ollama":
        return bool(getattr(settings, "ollama_base_url", None))
    return False


@router.get("/providers", summary="AI provider and model info for the Settings panel")
async def get_providers() -> dict[str, Any]:
    """Return the active AI provider, current model, and available models."""
    provider = _detect_provider()
    model = _detect_model(provider)
    available = _is_available(provider)
    models = _KNOWN_PROVIDERS.get(provider, [model])
    if model not in models:
        models = [model, *models]
    return {
        "provider": provider,
        "model": model,
        "available": available,
        "models": models,
    }


class ModelUpdate(BaseModel):
    model: str


@router.post("/providers/model", summary="Set the active AI model")
async def set_model(body: ModelUpdate) -> dict[str, str]:
    """Persist the requested model to settings (in-process; not written to disk)."""
    try:
        object.__setattr__(settings, "ai_model", body.model)
    except Exception:  # noqa: BLE001
        pass
    return {"model": body.model, "status": "ok"}
