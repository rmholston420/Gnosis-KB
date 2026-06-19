"""Tag management endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.database import get_db
from gnosis.models.tag import NoteTag, Tag

router = APIRouter(prefix="/api/v1/tags", tags=["tags"])


@router.get("/", summary="List all tags with note counts")
async def list_tags(db: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    """Return all tags with their associated note counts.

    Returns:
        List of dicts: {name, description, note_count}.
    """
    result = await db.execute(
        select(Tag.name, Tag.description, func.count(NoteTag.c.note_id).label("note_count"))
        .outerjoin(NoteTag, Tag.name == NoteTag.c.tag_id)
        .group_by(Tag.name, Tag.description)
        .order_by(func.count(NoteTag.c.note_id).desc())
    )
    rows = result.all()
    return [
        {"name": row.name, "description": row.description, "note_count": row.note_count}
        for row in rows
    ]
