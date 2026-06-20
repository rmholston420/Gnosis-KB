"""Pydantic schemas for the /query endpoint."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        json_schema_extra={"example": "What are the key ideas in my Zettelkasten?"},
    )
    top_k: int = Field(default=5, ge=1, le=50)
    include_graph: bool = Field(default=False)
    rerank: bool = Field(default=True)


class QueryResult(BaseModel):
    note_id: str
    title: str
    score: float
    snippet: str
    tags: list[str] = []


class QueryResponse(BaseModel):
    answer: str
    results: list[QueryResult] = []
    query: str
    model: str = ""
    sources: list[dict[str, Any]] = []
