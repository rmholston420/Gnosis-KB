"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", summary="Health check")
async def health_check() -> dict[str, str]:
    """Return API health status.

    Returns:
        dict with status 'ok' and version string.
    """
    from gnosis.config import get_settings
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version}
