"""Pydantic schemas for AI/RAG operations."""

from typing import Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: str = Field(pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    """Request body for the AI chat endpoint."""

    message: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    mode: str = Field(
        default="hybrid",
        pattern="^(local|global|hybrid)$",
        description="LightRAG query mode",
    )
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from the AI chat endpoint."""

    answer: str
    sources: list[str] = []  # Note titles cited
    mode: str
    session_id: Optional[str] = None


class SummarizeResponse(BaseModel):
    """AI-generated summary of a note."""

    note_id: str
    title: str
    summary: str
    key_concepts: list[str]
    suggested_tags: list[str]


class LinkSuggestion(BaseModel):
    """A suggested wikilink with reasoning."""

    target_note_id: str
    target_title: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class LinkSuggestionsResponse(BaseModel):
    """Suggested wikilinks for a note."""

    note_id: str
    suggestions: list[LinkSuggestion]


class CritiqueResponse(BaseModel):
    """Zettelkasten critique of a note."""

    note_id: str
    atomicity_score: int = Field(ge=1, le=5)
    atomicity_feedback: str
    connectivity_score: int = Field(ge=1, le=5)
    connectivity_feedback: str
    self_containedness_score: int = Field(ge=1, le=5)
    self_containedness_feedback: str
    insight_density_score: int = Field(ge=1, le=5)
    insight_density_feedback: str
    overall_feedback: str
    action_items: list[str]


class ExtractEntitiesRequest(BaseModel):
    """Request to extract named entities from text."""

    text: str
    note_id: Optional[str] = None


class EntityResult(BaseModel):
    """A single extracted entity."""

    name: str
    entity_type: str  # concept | person | project | tool | technique | insight | question
    description: str
