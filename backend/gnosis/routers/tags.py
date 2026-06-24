"""Tag endpoints -- user-scoped tag aggregation.

GET /tags/
  Returns all tags that have at least one note belonging to the requesting
  user, together with the per-tag note count.  Results are sorted by count
  descending then alphabetically so the most-used tags appear first.

  Response shape expected by TagsPage.tsx:
    [ { "tag": "buddhism", "count": 12 }, ... ]
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import get_current_user
from gnosis.database import get_db
from gnosis.models.note import Note
from gnosis.models.tag import NoteTag, Tag
from gnosis.models.user import User

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("/", summary="List all tags with per-user note counts")
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, object]]:
    """Return tags visible to *current_user* with their note counts.

    Only counts notes owned by the requesting user so cross-user leakage
    is impossible even on a shared database.
    """
    # Join Tag -> NoteTag (by integer PK) -> Note, filter by owner, group by tag name
    stmt = (
        select(
            Tag.name.label("tag"),
            func.count(NoteTag.c.note_id).label("count"),
        )
        .join(NoteTag, Tag.id == NoteTag.c.tag_id)
        .join(Note, Note.id == NoteTag.c.note_id)
        .where(
            Note.owner_id == current_user.id,
            Note.is_deleted == False,  # noqa: E712
        )
        .group_by(Tag.name)
        .order_by(
            func.count(NoteTag.c.note_id).desc(),
            Tag.name.asc(),
        )
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [{"tag": row.tag, "count": row.count} for row in rows]
