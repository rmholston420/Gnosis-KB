"""Regression tests for the Note.tags uselist=False collapse bug.

Root cause (fixed): SQLAlchemy's selectinload strategy for a uselist=False
relationship on a child model (e.g. Tag.notes back_populates) would collapse
the tags collection to a scalar when a second eager-load pass ran over an
instance that was already partially populated. The guard in _note_to_read
checks isinstance(note.tags, list) and returns [] for scalars/None.

These tests confirm:
  1. _note_to_read handles None, scalar Tag, and proper list correctly.
  2. Tag model has uselist=True on its back-ref to Note.
  3. Note model has uselist=True on its tags relationship.
"""

from __future__ import annotations

from datetime import UTC
from unittest.mock import MagicMock

from gnosis.models.note import Note
from gnosis.models.tag import Tag
from gnosis.routers.notes import _note_to_read

# ---------------------------------------------------------------------------
# Guard in _note_to_read
# ---------------------------------------------------------------------------


def _make_note(tags_value):
    from datetime import datetime

    n = MagicMock()
    n.id = "n1"
    n.title = "T"
    n.slug = "t"
    n.body = "."
    n.body_html = ""
    n.note_type = "permanent"
    n.status = "active"
    n.vault_path = "i/n.md"
    n.folder = "00-inbox"
    n.source_url = None
    n.word_count = 1
    n.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    n.modified_at = datetime(2024, 1, 1, tzinfo=UTC)
    n.last_reviewed = None
    n.is_deleted = False
    n.vector_indexed = False
    n.graph_indexed = False
    n.frontmatter = {}
    n.outgoing_links = []
    n.incoming_links = []
    n.tags = tags_value
    return n


def test_tags_none_returns_empty_list():
    """tags=None (uselist=False returned NULL) → serializes as []."""
    read = _note_to_read(_make_note(None))
    assert read.tags == []


def test_tags_scalar_tag_returns_empty_list():
    """tags=single Tag object (uselist=False returned 1 row) → serializes as []."""
    tag = MagicMock(spec=Tag)
    tag.name = "only"
    read = _note_to_read(_make_note(tag))
    assert read.tags == []


def test_tags_proper_list_serializes_correctly():
    """tags=[Tag, Tag] (correct uselist=True) → returns name list."""
    t1 = MagicMock(spec=Tag)
    t1.name = "alpha"
    t2 = MagicMock(spec=Tag)
    t2.name = "beta"
    read = _note_to_read(_make_note([t1, t2]))
    assert read.tags == ["alpha", "beta"]


def test_tags_empty_list_returns_empty():
    read = _note_to_read(_make_note([]))
    assert read.tags == []


# ---------------------------------------------------------------------------
# ORM relationship declarations — uselist must be True on both sides
# ---------------------------------------------------------------------------


def test_note_tags_relationship_uselist_true():
    """Note.tags must be uselist=True (collection, not scalar)."""
    rel = Note.__mapper__.relationships["tags"]
    assert rel.uselist is True, (
        f"Note.tags has uselist={rel.uselist!r} — must be True. "
        "A uselist=False relationship here collapses the tag collection to a scalar."
    )


def test_tag_notes_relationship_uselist_true():
    """Tag.notes back-ref must also be uselist=True."""
    rel = Tag.__mapper__.relationships["notes"]
    assert rel.uselist is True, (
        f"Tag.notes has uselist={rel.uselist!r} — must be True. "
        "uselist=False on the back-ref is what triggers the SAWarning and collapses Note.tags."
    )


def test_note_tags_lazy_is_select():
    """Note.tags lazy strategy must be 'select', not 'selectin'.

    Using lazy='selectin' on the model AND selectinload() in queries fires
    the loader twice. The second pass sees a partially-populated collection
    and can trigger the uselist=False warning.
    """
    rel = Note.__mapper__.relationships["tags"]
    assert rel.lazy == "select", (
        f"Note.tags lazy={rel.lazy!r}. Should be 'select' so selectinload() "
        "in query sites is the only load path."
    )


def test_tag_notes_lazy_is_select():
    """Tag.notes must also be lazy='select' for the same reason."""
    rel = Tag.__mapper__.relationships["notes"]
    assert rel.lazy == "select", f"Tag.notes lazy={rel.lazy!r}. Should be 'select'."
