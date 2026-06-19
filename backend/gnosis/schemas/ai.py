"""AI / RAG-related Pydantic schemas."""

from typing import Optional

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """A single chat message."""

    role: str  # user | assistant | system
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    """Chat request payload."""

    message: str
    history: list[ChatMessage] = []
    mode: str = "hybrid"  # hybrid | local | global
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response payload."""

    answer: str
    sources: list[str] = []
    mode: str = "hybrid"
    session_id: Optional[str] = None


class SummarizeResponse(BaseModel):
    """Note summarization result."""

    note_id: str
    title: str
    summary: str
    key_concepts: list[str]
    suggested_tags: list[str]


class CritiqueResponse(BaseModel):
    """Zettelkasten critique result."""

    note_id: str
    atomicity_score: int
    atomicity_feedback: str
    connectivity_score: int
    connectivity_feedback: str
    self_containedness_score: int
    self_containedness_feedback: str
    insight_density_score: int
    insight_density_feedback: str
    overall_feedback: str
    action_items: list[str]


class LinkSuggestion(BaseModel):
    """A single wikilink suggestion."""

    target_note_id: str
    target_title: str
    reason: str
    confidence: float


class LinkSuggestionsResponse(BaseModel):
    """Wikilink suggestions for a note."""

    note_id: str
    suggestions: list[LinkSuggestion]
