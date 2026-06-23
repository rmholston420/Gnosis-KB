"""Coverage-focused tests for gnosis/routers/review.py edge branches."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from gnosis.models.note import Note
from gnosis.models.review import ReviewCard
from gnosis.schemas.review import ReviewEnroll, ReviewSubmit


@pytest.mark.asyncio
async def test_enroll_note_returns_existing_card_without_creating_new_one(test_db):
    from gnosis.routers.review import enroll_note

    note = Note(id="note-1", title="Existing", slug="existing", body="body", owner_id=1, is_deleted=False)
    existing = ReviewCard(
        note_id="note-1",
        easiness=2.5,
        interval=1,
        repetitions=0,
        due_date=date.today(),
        last_quality=None,
    )

    note_result = MagicMock()
    note_result.scalar_one_or_none.return_value = note
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing
    test_db.execute = AsyncMock(side_effect=[note_result, existing_result])
    test_db.add = MagicMock()
    test_db.commit = AsyncMock()
    test_db.refresh = AsyncMock()

    result = await enroll_note("note-1", ReviewEnroll(note_id="note-1", due_today=False), db=test_db)

    assert result.note_id == "note-1"
    test_db.add.assert_not_called()
    test_db.commit.assert_not_awaited()
    test_db.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_review_updates_card_even_when_note_missing(test_db):
    from gnosis.routers.review import submit_review

    card = ReviewCard(
        note_id="ghost-note",
        easiness=2.5,
        interval=1,
        repetitions=1,
        due_date=date.today(),
        last_quality=None,
    )
    card.note = MagicMock(title="Ghost", body="Body", folder="", tags=[])

    card_result = MagicMock()
    card_result.scalar_one_or_none.return_value = card
    note_result = MagicMock()
    note_result.scalar_one_or_none.return_value = None
    test_db.execute = AsyncMock(side_effect=[card_result, note_result])
    test_db.commit = AsyncMock()
    test_db.refresh = AsyncMock()

    result = await submit_review("ghost-note", ReviewSubmit(quality=4), db=test_db)

    assert result.note_id == "ghost-note"
    assert card.last_quality == 4
    assert card.repetitions >= 1
    test_db.commit.assert_awaited_once()
    test_db.refresh.assert_awaited_once_with(card)


@pytest.mark.asyncio
async def test_unenroll_note_deletes_card_and_commits(test_db):
    from gnosis.routers.review import unenroll_note

    card = ReviewCard(
        note_id="drop-me",
        easiness=2.5,
        interval=1,
        repetitions=0,
        due_date=date.today(),
        last_quality=None,
    )
    card.note = MagicMock(title="Drop", body="Body", folder="", tags=[])

    result_obj = MagicMock()
    result_obj.scalar_one_or_none.return_value = card
    test_db.execute = AsyncMock(return_value=result_obj)
    test_db.delete = AsyncMock()
    test_db.commit = AsyncMock()

    result = await unenroll_note("drop-me", db=test_db)

    assert result is None
    test_db.delete.assert_awaited_once_with(card)
    test_db.commit.assert_awaited_once()
