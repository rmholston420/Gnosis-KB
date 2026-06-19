"""Pydantic schemas for search operations."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    """Hybrid search request."""

    q: str = Field(..., min_length=1, description="Search query string")
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    folder: Optional[str] = None
    note_type: Optional[str] = None
    tags: Optional[list[str]] = None
    mode: str = Field(
        default="hybrid",
        pattern="^(hybrid|semantic|fulltext)$",
        description="Search mode: hybrid (BM25+vector), semantic (vector only), fulltext (BM25 only)",
    )


class SearchResult(BaseModel):
    """A single search result with score and highlights."""

    note_id: str
    title: str
    slug: str
    folder: str
    note_type: str
    status: str
    score: float
    highlight: str = ""  # Relevant snippet with matched terms highlighted
    tags: list[str] = []


class SearchResponse(BaseModel):
    """Search results response."""

    query: str
    mode: str
    results: list[SearchResult]
    total: int
    elapsed_ms: float
