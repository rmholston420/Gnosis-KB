"""SQLAlchemy model registry.

Import all models here so Alembic's autogenerate can detect them.
"""

from gnosis.models.attachment import Attachment  # noqa: F401
from gnosis.models.link import Link  # noqa: F401
from gnosis.models.note import Note  # noqa: F401
from gnosis.models.review import ReviewCard  # noqa: F401
from gnosis.models.saved_query import SavedQuery  # noqa: F401
from gnosis.models.shared_vault import SharedVault  # noqa: F401
from gnosis.models.tag import Tag  # noqa: F401
from gnosis.models.user import User  # noqa: F401
