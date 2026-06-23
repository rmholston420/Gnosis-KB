"""Gap-closure tests for markdown_parser.py.

Line 31→33: generate_note_id(dt=<explicit datetime>) — the non-None branch.
"""

from __future__ import annotations

from datetime import UTC, datetime

from gnosis.services.markdown_parser import generate_note_id


def test_generate_note_id_with_explicit_datetime():
    """Passing an explicit datetime hits the non-None branch (line 33)."""
    dt = datetime(2024, 6, 15, 10, 30, 45, tzinfo=UTC)
    result = generate_note_id(dt)
    assert result == "20240615-103045"


def test_generate_note_id_without_argument_returns_string():
    """Calling with no argument (None path) returns a valid timestamp string."""
    result = generate_note_id()
    assert len(result) == 15  # YYYYMMDD-HHmmss
    assert result[8] == "-"
    assert result.replace("-", "").isdigit()


def test_generate_note_id_format_is_sortable():
    """IDs generated from consecutive datetimes sort lexicographically."""
    early = generate_note_id(datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC))
    late = generate_note_id(datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC))
    assert early < late
