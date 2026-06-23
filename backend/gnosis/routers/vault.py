"""Vault router — sync, stats, and watcher control."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import get_current_user, get_vault_owner_ids
from gnosis.database import get_db
from gnosis.models.note import Note
from gnosis.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vault", tags=["vault"])


@router.post("/sync", summary="Trigger a full vault sync for the current user")
async def sync_vault(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream sync progress as Server-Sent Events."""
    from gnosis.services.vault_sync import run_full_sync_for_user

    async def _generate():
        async for line in run_full_sync_for_user(current_user.id):
            yield f"data: {line}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")


@router.get("/stats", summary="Vault statistics for the current user")
async def vault_stats(
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> dict[str, Any]:
    """Return aggregate counts and storage metrics for the user's vault."""
    from gnosis.core.namespace import scoped_note_stmt

    base = scoped_note_stmt(
        select(Note).where(Note.is_deleted.is_(False)),
        owner_ids,
    )

    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total_notes: int = int(total_result.scalar_one() or 0)  # type: ignore[arg-type]

    word_result = await db.execute(select(func.sum(Note.word_count)).select_from(base.subquery()))
    total_words: int = int(word_result.scalar_one() or 0)  # type: ignore[arg-type]

    folder_result = await db.execute(
        select(Note.folder, func.count(Note.id))
        .select_from(base.subquery().alias("scoped"))
        .join(Note, Note.id == base.subquery().c.id)
        .group_by(Note.folder)
        .order_by(func.count(Note.id).desc())
        .limit(10)
    )

    folders = [{"folder": row[0] or "(none)", "count": int(row[1])} for row in folder_result.all()]

    settings_obj = None
    vault_path_str: str | None = None
    disk_used_mb: float | None = None
    file_count: int | None = None

    try:
        from gnosis.config import get_settings

        settings_obj = get_settings()
        vault_path_str = str(getattr(settings_obj, "vault_path", None) or "")
        if vault_path_str:
            vault_path = Path(vault_path_str)
            if vault_path.exists():
                total_size = sum(f.stat().st_size for f in vault_path.rglob("*") if f.is_file())
                disk_used_mb = round(total_size / (1024 * 1024), 2)
                file_count = sum(1 for _ in vault_path.rglob("*.md"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read vault disk stats: %s", exc)

    return {
        "total_notes": total_notes,
        "total_words": total_words,
        "top_folders": folders,
        "vault_path": vault_path_str,
        "disk_used_mb": disk_used_mb,
        "file_count": file_count,
    }


@router.get("/path", summary="Resolve vault filesystem path for the current user")
async def get_vault_path(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    from gnosis.core.namespace import resolve_vault_path

    path = resolve_vault_path(current_user)
    return {"vault_path": str(path), "exists": str(path.exists())}
