"""SQLAlchemy model registry.

Import all models here so Alembic's autogenerate can detect them.
"""

from gnosis.models.attachment import Attachment
from gnosis.models.link import Link
from gnosis.models.note import Note
from gnosis.models.review import ReviewCard
from gnosis.models.saved_query import SavedQuery
from gnosis.models.shared_vault import SharedVault
from gnosis.models.tag import Tag
from gnosis.models.user import User

__all__ = [
    "Attachment",
    "Link",
    "Note",
    "ReviewCard",
    "SavedQuery",
    "SharedVault",
    "Tag",
    "User",
]
