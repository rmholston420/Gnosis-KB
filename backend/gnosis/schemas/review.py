"""Pydantic schemas for the SM-2 review system."""

from datetime import date

from pydantic import BaseModel, Field


class ReviewCardRead(BaseModel):
    """SM-2 state for a single note, returned by the API."""

    note_id: str
    easiness: float
    interval: int
    repetitions: int
    due_date: date
    last_quality: int | None = None

    model_config = {"from_attributes": True}


class ReviewCardWithNote(ReviewCardRead):
    """ReviewCard bundled with the note title and body for the review UI."""

    note_title: str
    note_body: str
    note_folder: str
    note_tags: list[str]


class ReviewSubmit(BaseModel):
    """Payload sent by the UI when the user rates a card."""

    quality: int = Field(
        ...,
        ge=0,
        le=5,
        description="SM-2 quality rating 0 (blackout) to 5 (perfect)",
    )


class ReviewEnroll(BaseModel):
    """Enroll a note into the review queue."""

    note_id: str
    due_today: bool = True


class ReviewStats(BaseModel):
    """Aggregate review queue statistics."""

    due_today: int
    due_this_week: int
    total_enrolled: int
    new_today: int          # cards reviewed for the first time today
    reviewed_today: int     # cards touched today (any quality)
