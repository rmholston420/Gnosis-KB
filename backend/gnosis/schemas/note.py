"""Note-related Pydantic schemas."""

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class LinkSchema(BaseModel):
    """Represents a directional link between two notes."""

    source_id: str
    target_id: str
    link_text: str
    link_type: str = "wikilink"
    context: Optional[str] = None


class NoteBase(BaseModel):
    """Base fields shared by create/update schemas."""

    title: str = Field(..., min_length=1, max_length=500)
    body: str = Field(default="")
    note_type: str = Field(default="permanent")
    status: str = Field(default="draft")
    folder: str = Field(default="10-zettelkasten")
    tags: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    last_reviewed: Optional[date] = None


class NoteCreate(NoteBase):
    """Schema for creating a new note."""

    id: Optional[str] = None  # If None, auto-generated timestamp ID


class NoteUpdate(BaseModel):
    """Schema for partially updating a note (all fields optional)."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    body: Optional[str] = None
    note_type: Optional[str] = None
    status: Optional[str] = None
    folder: Optional[str] = None
    tags: Optional[list[str]] = None
    source_url: Optional[str] = None
    frontmatter: Optional[dict[str, Any]] = None
    last_reviewed: Optional[date] = None


class NoteRead(BaseModel):
    """Full note representation returned by the API."""

    id: str
    title: str
    slug: str
    body: str
    body_html: str
    note_type: str
    status: str
    vault_path: Optional[str] = None
    folder: str
    source_url: Optional[str] = None
    word_count: int
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    last_reviewed: Optional[date] = None
    is_deleted: bool
    vector_indexed: bool
    graph_indexed: bool
    frontmatter: dict[str, Any]
    tags: list[str]
    outgoing_links: list[LinkSchema]
    incoming_links: list[LinkSchema]

    model_config = {"from_attributes": True}


class NoteListItem(BaseModel):
    """Lightweight note representation for list views."""

    id: str
    title: str
    slug: str
    note_type: str
    status: str
    folder: str
    word_count: int
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    tags: list[str]

    model_config = {"from_attributes": True}


class NoteListResponse(BaseModel):
    """Paginated list of notes."""

    items: list[NoteListItem]
    total: int
    page: int
    page_size: int
    pages: int
