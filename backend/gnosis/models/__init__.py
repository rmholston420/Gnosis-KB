"""Gnosis ORM models package.

Import all model classes here so that SQLAlchemy's metadata is fully
populated before ``Base.metadata.create_all()`` / Alembic ``env.py`` runs.

Explicit ``__all__`` prevents accidental star-import exposure of internal
helpers and makes the public surface of the models package unambiguous.

Fix (2025-06-26):
- Removed ``from gnosis.models.flashcard import Flashcard`` — flashcard.py
  was never created; the import caused ModuleNotFoundError at startup that
  cascaded through conftest.py and blocked the entire pytest suite.
- Removed ``from gnosis.models.review_log import ReviewLog`` — review_log.py
  does not exist; the correct module is ``gnosis.models.review`` and the
  class is ``ReviewCard``.
- Added correct import: ``from gnosis.models.review import ReviewCard``.
- Added remaining existing models: Attachment, SavedQuery, SharedVault.
"""

from gnosis.models.attachment import Attachment
from gnosis.models.link import Link
from gnosis.models.note import Note
from gnosis.models.review import ReviewCard
from gnosis.models.saved_query import SavedQuery
from gnosis.models.shared_vault import SharedVault
from gnosis.models.tag import NoteTag, Tag
from gnosis.models.user import User

__all__ = [
    "Attachment",
    "Link",
    "Note",
    "NoteTag",
    "ReviewCard",
    "SavedQuery",
    "SharedVault",
    "Tag",
    "User",
]
