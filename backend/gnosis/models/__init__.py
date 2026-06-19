"""SQLAlchemy ORM models for Gnosis.

Importing this module registers all models with Base.metadata,
enabling Alembic autogenerate and DB initialization.
"""

from gnosis.models.user import User  # noqa: F401
from gnosis.models.note import Note  # noqa: F401
from gnosis.models.tag import Tag, NoteTag  # noqa: F401
from gnosis.models.link import Link  # noqa: F401
from gnosis.models.attachment import Attachment  # noqa: F401
from gnosis.models.saved_query import SavedQuery  # noqa: F401
