"""SM-2 Spaced-Repetition review router.

Endpoints
---------
GET  /api/v1/review/queue          -- notes due today (paginated)
GET  /api/v1/review/stats          -- queue statistics
POST /api/v1/review/{note_id}/enroll -- enroll a note into the queue
POST /api/v1/review/{note_id}      -- submit a rating and advance the card
DELETE /api/v1/review/{note_id}    -- remove a note from the queue
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gnosis.core.sm2 import SM2State, advance, initial_state
from gnosis.database import get_db
from gnosis.models.note import Note
from gnosis.models.review import ReviewCard
from gnosis.schemas.review import (
    ReviewCardRead,
    ReviewCardWithNote,
    ReviewEnroll,
    ReviewStats,
    ReviewSubmit,
)

# prefix is /review only — main.py prepends /api/v1 when including this router
router = APIRouter(prefix="/review", tags=["review"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _card_to_with_note(card: ReviewCard) -> ReviewCardWithNote:
    return ReviewCardWithNote(
        note_id=card.note_id,
        easiness=card.easiness,
        interval=card.interval,
        repetitions=card.repetitions,
        due_date=card.due_date,
        last_quality=card.last_quality,
        note_title=card.note.title,
        note_body=card.note.body,
        note_folder=card.note.folder or "",
        note_tags=[t.name for t in card.note.tags],
    )


async def _get_card_or_404(note_id: str, db: AsyncSession) -> ReviewCard:
    result = await db.execute(
        select(ReviewCard)
        .options(selectinload(ReviewCard.note).selectinload(Note.tags))
        .where(ReviewCard.note_id == note_id)
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note {note_id!r} is not enrolled in the review queue.",
        )
    return card


# ---------------------------------------------------------------------------
# GET /queue  -- cards due today
# ---------------------------------------------------------------------------


@router.get("/queue", response_model=list[ReviewCardWithNote])
async def get_due_queue(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ReviewCardWithNote]:
    """Return notes due for review today (oldest due-date first)."""
    today = date.today()
    result = await db.execute(
        select(ReviewCard)
        .options(selectinload(ReviewCard.note).selectinload(Note.tags))
        .where(ReviewCard.due_date <= today)
        .order_by(ReviewCard.due_date.asc(), ReviewCard.easiness.asc())
        .limit(limit)
        .offset(offset)
    )
    cards = result.scalars().all()
    return [_card_to_with_note(c) for c in cards]


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=ReviewStats)
async def get_stats(db: AsyncSession = Depends(get_db)) -> ReviewStats:
    """Return aggregate queue statistics."""
    today = date.today()
    week_end = today + timedelta(days=7)

    due_today_count = await db.scalar(select(func.count()).where(ReviewCard.due_date <= today))
    due_week_count = await db.scalar(select(func.count()).where(ReviewCard.due_date <= week_end))
    total_count = await db.scalar(select(func.count(ReviewCard.note_id)))
    reviewed_today_count = await db.scalar(select(func.count()).where(ReviewCard.due_date == today))

    return ReviewStats(
        due_today=due_today_count or 0,
        due_this_week=due_week_count or 0,
        total_enrolled=total_count or 0,
        new_today=0,
        reviewed_today=reviewed_today_count or 0,
    )


# ---------------------------------------------------------------------------
# POST /{note_id}/enroll  -- MUST be registered before POST /{note_id}
# so FastAPI does not swallow "/x/enroll" as submit with note_id="x/enroll"
# ---------------------------------------------------------------------------


@router.post(
    "/{note_id}/enroll", response_model=ReviewCardRead, status_code=status.HTTP_201_CREATED
)
async def enroll_note(
    note_id: str,
    payload: ReviewEnroll,
    db: AsyncSession = Depends(get_db),
) -> ReviewCardRead:
    """Enroll a note into the SM-2 review queue."""
    note_result = await db.execute(
        select(Note).where(Note.id == note_id, Note.is_deleted.is_(False))
    )
    if note_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Note {note_id!r} not found.")

    existing = await db.execute(select(ReviewCard).where(ReviewCard.note_id == note_id))
    if card := existing.scalar_one_or_none():
        return ReviewCardRead.model_validate(card)

    state, due = initial_state(due_today=payload.due_today)
    card = ReviewCard(
        note_id=note_id,
        easiness=state.easiness,
        interval=state.interval,
        repetitions=state.repetitions,
        due_date=due,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return ReviewCardRead.model_validate(card)


# ---------------------------------------------------------------------------
# POST /{note_id}  -- submit a rating
# ---------------------------------------------------------------------------


@router.post("/{note_id}", response_model=ReviewCardRead)
async def submit_review(
    note_id: str,
    payload: ReviewSubmit,
    db: AsyncSession = Depends(get_db),
) -> ReviewCardRead:
    """Submit an SM-2 quality rating for a note and advance its schedule."""
    card = await _get_card_or_404(note_id, db)

    current = SM2State(
        easiness=card.easiness,
        interval=card.interval,
        repetitions=card.repetitions,
    )
    new_state, next_due = advance(current, payload.quality)

    card.easiness = new_state.easiness
    card.interval = new_state.interval
    card.repetitions = new_state.repetitions
    card.due_date = next_due
    card.last_quality = payload.quality

    note_result = await db.execute(select(Note).where(Note.id == note_id))
    if note := note_result.scalar_one_or_none():
        from datetime import date as _date

        note.last_reviewed = _date.today()

    await db.commit()
    await db.refresh(card)
    return ReviewCardRead.model_validate(card)


# ---------------------------------------------------------------------------
# DELETE /{note_id}  -- unenroll
# ---------------------------------------------------------------------------


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unenroll_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a note from the review queue (card deleted, note preserved)."""
    card = await _get_card_or_404(note_id, db)
    await db.delete(card)
    await db.commit()
