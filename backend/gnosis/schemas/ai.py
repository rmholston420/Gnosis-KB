"""Pydantic schemas for AI router requests and responses."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for /ai/chat."""

    message: str = Field(..., min_length=1, max_length=8000, description="User message")
    mode: str = Field(
        default="hybrid",
        description="LightRAG query mode: local | global | hybrid",
    )
    session_id: Optional[str] = Field(
        default=None, description="Optional chat session ID for history"
    )


class ChatResponse(BaseModel):
    """Response from /ai/chat."""

    answer: str
    mode: str
    session_id: Optional[str] = None


class SummarizeResponse(BaseModel):
    """Response from /ai/summarize/{note_id}."""

    note_id: str
    summary: str


class LinkSuggestionsResponse(BaseModel):
    """Response from /ai/suggest-links/{note_id}."""

    note_id: str
    suggestions: list[str] = Field(
        description="List of suggested note titles to link to"
    )
    rationale: list[str] = Field(
        description="Matching rationale for each suggestion"
    )


class TagSuggestionsResponse(BaseModel):
    """Response from /ai/suggest-tags/{note_id}."""

    note_id: str
    suggested_tags: list[str]


class CritiqueResponse(BaseModel):
    """Response from /ai/critique/{note_id}."""

    note_id: str
    atomicity: str = Field(description="Is there exactly one idea?")
    connectivity: str = Field(description="Does it have sufficient outgoing links?")
    self_containedness: str = Field(
        description="Can it be understood without external context?"
    )
    insight_density: str = Field(description="Does it capture why this matters?")
    overall: str = Field(description="Overall Zettelkasten quality assessment")


class OrphanAuditItem(BaseModel):
    """A single orphan note with AI-suggested connections."""

    note_id: str
    title: str
    suggestions: list[str]


class OrphanAuditResponse(BaseModel):
    """Response from GET /ai/orphan-audit."""

    orphan_count: int
    items: list[OrphanAuditItem]


class DailyReviewResponse(BaseModel):
    """Response from POST /ai/daily-review."""

    date: str
    summary: str
    inbox_note_count: int
    action_items: list[str]


# ---------------------------------------------------------------------------
# MOC Generator
# ---------------------------------------------------------------------------

class MocSection(BaseModel):
    """A single H2 section within a generated MOC."""

    heading: str = Field(description="Section heading (used as H2 in the MOC note)")
    wikilinks: list[str] = Field(
        description="Titles of notes to link under this heading"
    )
    summary: str = Field(
        description="1-2 sentence description of what this section covers"
    )


class MocRequest(BaseModel):
    """Request body for POST /ai/generate-moc."""

    topic: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Topic or tag name to generate the MOC around",
    )
    tag: Optional[str] = Field(
        default=None,
        description="If provided, only notes tagged with this value are considered",
    )
    folder: Optional[str] = Field(
        default=None,
        description="If provided, only notes in this folder prefix are considered",
    )
    max_notes: int = Field(
        default=60,
        ge=5,
        le=200,
        description="Maximum number of vault notes to pass to the LLM for grouping",
    )


class MocResponse(BaseModel):
    """Response from POST /ai/generate-moc."""

    topic: str
    moc_title: str = Field(description="Suggested title for the MOC note")
    vault_path: str = Field(description="Suggested file path: 80-meta/<slug>.md")
    sections: list[MocSection]
    markdown: str = Field(
        description="Complete ready-to-save Markdown body for the MOC note"
    )
    note_count: int = Field(description="Number of vault notes scanned")
