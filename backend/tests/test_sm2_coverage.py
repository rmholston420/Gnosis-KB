"""Full coverage for gnosis/core/sm2.py.

The SM-2 algorithm is pure logic with no I/O, so every branch can be
tested with simple unit tests — no mocking required.

Branches covered
----------------
- advance(): quality 0-2 (reset), quality 3-5 (advance)
  - repetitions == 0  → interval = 1
  - repetitions == 1  → interval = 6
  - repetitions >= 2  → interval = round(interval * easiness)
  - easiness clamped to EASINESS_FLOOR
  - quality out-of-range raises ValueError
- initial_state(): due_today=True and due_today=False
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from gnosis.core.sm2 import (
    EASINESS_FLOOR,
    EASINESS_START,
    SM2State,
    advance,
    initial_state,
)

# ---------------------------------------------------------------------------
# initial_state
# ---------------------------------------------------------------------------


def test_initial_state_due_today():
    state, due = initial_state(due_today=True)
    assert state.easiness == EASINESS_START
    assert state.interval == 1
    assert state.repetitions == 0
    assert due == date.today()


def test_initial_state_not_due_today():
    _, due = initial_state(due_today=False)
    assert due == date.today() + timedelta(days=1)


# ---------------------------------------------------------------------------
# advance() — invalid quality
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [-1, 6, 100])
def test_advance_invalid_quality_raises(bad):
    state = SM2State(easiness=EASINESS_START, interval=1, repetitions=0)
    with pytest.raises(ValueError, match="quality must be 0-5"):
        advance(state, bad)


# ---------------------------------------------------------------------------
# advance() — reset branch (quality 0, 1, 2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("quality", [0, 1, 2])
def test_advance_reset_branch(quality):
    state = SM2State(easiness=2.0, interval=10, repetitions=5)
    new_state, due = advance(state, quality)

    assert new_state.interval == 1
    assert new_state.repetitions == 0
    assert new_state.easiness == 2.0
    assert due == date.today() + timedelta(days=1)


# ---------------------------------------------------------------------------
# advance() — correct branch (quality 3, 4, 5)
# ---------------------------------------------------------------------------


def test_advance_quality3_rep0_gives_interval1():
    state = SM2State(easiness=EASINESS_START, interval=1, repetitions=0)
    new_state, due = advance(state, 3)
    assert new_state.interval == 1
    assert new_state.repetitions == 1
    assert due == date.today() + timedelta(days=1)


def test_advance_quality4_rep1_gives_interval6():
    state = SM2State(easiness=EASINESS_START, interval=1, repetitions=1)
    new_state, due = advance(state, 4)
    assert new_state.interval == 6
    assert new_state.repetitions == 2
    assert due == date.today() + timedelta(days=6)


def test_advance_quality5_rep2_multiplies_interval():
    state = SM2State(easiness=2.5, interval=6, repetitions=2)
    new_state, due = advance(state, 5)
    expected_interval = round(6 * 2.5)  # 15
    assert new_state.interval == expected_interval
    assert new_state.repetitions == 3
    assert due == date.today() + timedelta(days=expected_interval)


def test_advance_quality5_perfect_increases_easiness():
    state = SM2State(easiness=2.5, interval=1, repetitions=0)
    new_state, _ = advance(state, 5)
    assert new_state.easiness > state.easiness


def test_advance_quality3_decreases_easiness():
    state = SM2State(easiness=2.5, interval=1, repetitions=0)
    new_state, _ = advance(state, 3)
    assert new_state.easiness < state.easiness


def test_advance_easiness_clamped_to_floor():
    state = SM2State(easiness=EASINESS_FLOOR + 0.01, interval=1, repetitions=2)
    new_state, _ = advance(state, 3)
    assert new_state.easiness >= EASINESS_FLOOR


def test_advance_easiness_already_at_floor_stays_at_floor():
    state = SM2State(easiness=EASINESS_FLOOR, interval=6, repetitions=2)
    new_state, _ = advance(state, 3)
    assert new_state.easiness == EASINESS_FLOOR


# ---------------------------------------------------------------------------
# Round-trip: enrol → review several times
# ---------------------------------------------------------------------------


def test_full_sm2_cycle():
    """Simulate a realistic review schedule over 4 sessions."""
    state, _ = initial_state(due_today=True)

    # Session 1: perfect recall (rep=0 → interval stays 1)
    state, _ = advance(state, 5)
    assert state.repetitions == 1
    assert state.interval == 1

    # Session 2: correct with hesitation (rep=1 → interval jumps to 6)
    state, _ = advance(state, 4)
    assert state.repetitions == 2
    assert state.interval == 6

    # Session 3: correct with difficulty (rep>=2 → interval = round(6 * easiness))
    state, _ = advance(state, 3)
    assert state.repetitions == 3
    assert state.interval >= 6  # must not shrink below the previous interval

    # Session 4: complete blackout → resets streak
    state, _ = advance(state, 0)
    assert state.repetitions == 0
    assert state.interval == 1
