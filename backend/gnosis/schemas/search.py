"""Search-related Pydantic schemas."""

from pydantic import BaseModel


class SearchResult(BaseModel):
    """Single search result item."""

    note_id: str
    title: str
    slug: str
    folder: str
    note_type: str
    status: str
    score: float
    highlight: str  # may contain <mark>...</mark> tags from ts_headline
    tags: list[str]


class SearchResponse(BaseModel):
    """Search results response."""

    query: str
    mode: str  # 'hybrid' | 'semantic' | 'fulltext'
    results: list[SearchResult]
    total: int
    elapsed_ms: float
