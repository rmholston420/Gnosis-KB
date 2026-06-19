"""Pure SM-2 spaced-repetition algorithm.

Reference: SuperMemo 2 by Piotr Wozniak.
https://www.supermemo.com/en/archives1990-2015/english/ol/sm2

Quality ratings
---------------
0 -- complete blackout
1 -- incorrect; correct answer barely remembered
2 -- incorrect; correct answer felt easy to recall
3 -- correct with serious difficulty
4 -- correct with hesitation
5 -- perfect response

Ratings 0-2 reset the card (interval back to 1, repetitions = 0).
Ratings 3-5 advance the card.
"""

from dataclasses import dataclass
from datetime import date, timedelta

EASINESS_FLOOR = 1.3
EASINESS_START = 2.5


@dataclass
class SM2State:
    easiness: float
    interval: int
    repetitions: int


def advance(state: SM2State, quality: int) -> tuple[SM2State, date]:
    """Apply one SM-2 review and return (new_state, next_due_date).

    Parameters
    ----------
    state:
        Current SM-2 state of the card.
    quality:
        User rating 0-5.

    Returns
    -------
    (new_state, due_date)
        new_state -- updated SM-2 fields to persist.
        due_date  -- calendar date the card should next be shown.
    """
    if not 0 <= quality <= 5:
        raise ValueError(f"quality must be 0-5, got {quality}")

    if quality < 3:
        # Incorrect response: reset streak, keep easiness, restart intervals
        new_state = SM2State(
            easiness=state.easiness,
            interval=1,
            repetitions=0,
        )
    else:
        # Correct response: update easiness and advance interval
        new_easiness = max(
            EASINESS_FLOOR,
            state.easiness + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02),
        )
        if state.repetitions == 0:
            new_interval = 1
        elif state.repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(state.interval * state.easiness)

        new_state = SM2State(
            easiness=new_easiness,
            interval=new_interval,
            repetitions=state.repetitions + 1,
        )

    due_date = date.today() + timedelta(days=new_state.interval)
    return new_state, due_date


def initial_state(due_today: bool = True) -> tuple[SM2State, date]:
    """Return a brand-new SM-2 state for a card being enrolled.

    Parameters
    ----------
    due_today:
        If True (default), the card is due immediately (due_date = today).
        If False, due_date = today + 1.
    """
    state = SM2State(
        easiness=EASINESS_START,
        interval=1,
        repetitions=0,
    )
    offset = 0 if due_today else 1
    return state, date.today() + timedelta(days=offset)
