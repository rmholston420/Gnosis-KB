"""Unit tests for the SM-2 algorithm.

Run with:  pytest backend/gnosis/core/sm2_test.py -v
"""
import pytest
from datetime import date, timedelta
from gnosis.core.sm2 import SM2State, advance, initial_state, EASINESS_FLOOR, EASINESS_START


def test_initial_state_due_today():
    state, due = initial_state(due_today=True)
    assert state.easiness == EASINESS_START
    assert state.interval == 1
    assert state.repetitions == 0
    assert due == date.today()


def test_initial_state_not_due_today():
    _, due = initial_state(due_today=False)
    assert due == date.today() + timedelta(days=1)


def test_first_perfect_review():
    state, due = initial_state()
    new_state, new_due = advance(state, quality=5)
    assert new_state.repetitions == 1
    assert new_state.interval == 1
    assert new_due == date.today() + timedelta(days=1)


def test_second_perfect_review():
    state = SM2State(easiness=2.5, interval=1, repetitions=1)
    new_state, new_due = advance(state, quality=5)
    assert new_state.interval == 6
    assert new_state.repetitions == 2
    assert new_due == date.today() + timedelta(days=6)


def test_third_review_uses_easiness():
    state = SM2State(easiness=2.5, interval=6, repetitions=2)
    new_state, _ = advance(state, quality=5)
    assert new_state.interval == round(6 * 2.5)
    assert new_state.repetitions == 3


def test_incorrect_resets_repetitions():
    state = SM2State(easiness=2.5, interval=10, repetitions=5)
    new_state, new_due = advance(state, quality=2)
    assert new_state.repetitions == 0
    assert new_state.interval == 1
    assert new_due == date.today() + timedelta(days=1)
    # Easiness unchanged on wrong answer
    assert new_state.easiness == state.easiness


def test_easiness_increases_on_perfect():
    state = SM2State(easiness=2.5, interval=6, repetitions=2)
    new_state, _ = advance(state, quality=5)
    assert new_state.easiness > state.easiness


def test_easiness_decreases_on_hard():
    state = SM2State(easiness=2.5, interval=6, repetitions=2)
    new_state, _ = advance(state, quality=3)
    assert new_state.easiness < state.easiness


def test_easiness_floor():
    state = SM2State(easiness=EASINESS_FLOOR + 0.01, interval=6, repetitions=2)
    new_state, _ = advance(state, quality=3)
    assert new_state.easiness >= EASINESS_FLOOR


def test_invalid_quality_raises():
    state = SM2State(easiness=2.5, interval=1, repetitions=0)
    with pytest.raises(ValueError):
        advance(state, quality=6)
    with pytest.raises(ValueError):
        advance(state, quality=-1)
