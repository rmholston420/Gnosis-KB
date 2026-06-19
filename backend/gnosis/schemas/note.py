"""Pydantic schemas for Note CRUD operations."""

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator
from python_slugify import slugify  # type: ignore[import-untyped]


class NoteBase(BaseModel):
    """Shared fields for note create and update."""

    title: str = Field(..., min_length=1, max_length=500)
    body: str = Field(default="")
    note_type: str = Field(
        default="permanent",
        pattern="^(fleeting|literature|permanent|project|area|resource|journal|moc)$",
    )
    status: str = Field(
        default="draft",
        pattern="^(draft|in-progress|evergreen)$",
    )
    folder: str = Field(
        default="10-zettelkasten",
        description="PARA folder: 00-inbox, 10-zettelkasten, etc.",
    )
    tags: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    last_reviewed: Optional[date] = None


class NoteCreate(NoteBase):
    """Schema for creating a new note."""

    id: Optional[str] = Field(
        default=None,
        description="Timestamp ID (auto-generated if not provided)",
    )
    frontmatter: dict[str, Any] = Field(default_factory=dict)


class NoteUpdate(BaseModel):
    """Schema for updating an existing note (all fields optional)."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    body: Optional[str] = None
    note_type: Optional[str] = Field(
        default=None,
        pattern="^(fleeting|literature|permanent|project|area|resource|journal|moc)$",
    )
    status: Optional[str] = Field(
        default=None,
        pattern="^(draft|in-progress|evergreen)$",
    )
    folder: Optional[str] = None
    tags: Optional[list[str]] = None
    source_url: Optional[str] = None
    last_reviewed: Optional[date] = None
    frontmatter: Optional[dict[str, Any]] = None


class LinkSchema(BaseModel):
    """Represents a link between two notes."""

    source_id: str
    target_id: str
    link_text: str
    link_type: str
    context: Optional[str] = None

    model_config = {"from_attributes": True}


class NoteRead(BaseModel):
    """Full note response schema, including computed fields."""

    id: str
    title: str
    slug: str
    body: str
    body_html: str
    note_type: str
    status: str
    vault_path: str
    folder: str
    source_url: Optional[str] = None
    word_count: int
    created_at: datetime
    modified_at: Optional[datetime] = None
    last_reviewed: Optional[date] = None
    is_deleted: bool
    vector_indexed: bool
    graph_indexed: bool
    frontmatter: dict[str, Any]
    tags: list[str] = []
    outgoing_links: list[LinkSchema] = []
    incoming_links: list[LinkSchema] = []

    model_config = {"from_attributes": True}


class NoteListItem(BaseModel):
    """Compact note schema for list views."""

    id: str
    title: str
    slug: str
    note_type: str
    status: str
    folder: str
    word_count: int
    created_at: datetime
    modified_at: Optional[datetime] = None
    tags: list[str] = []

    model_config = {"from_attributes": True}


class NoteListResponse(BaseModel):
    """Paginated note list response."""

    items: list[NoteListItem]
    total: int
    page: int
    page_size: int
    pages: int
