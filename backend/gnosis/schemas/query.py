"""Pydantic schemas for the Dataview query engine and AI query endpoint."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Dataview / GQL engine schemas  (used by routers/query.py)
# ---------------------------------------------------------------------------

class QueryRun(BaseModel):
    """Execute a one-off query without saving it."""

    query: str = Field(
        ...,
        min_length=1,
        json_schema_extra={
            "example": "FROM 10-zettelkasten WHERE status=draft SORT modified DESC LIMIT 20"
        },
        description=(
            "Gnosis query language string. Supported clauses: "
            "FROM <folder_prefix>, WHERE <field>=<value> AND …, "
            "SORT <field> ASC|DESC, LIMIT <n>, SELECT <col1,col2,…>"
        ),
    )


class QueryResult(BaseModel):
    """Result rows returned by a query execution."""

    rows: list[dict[str, Any]]
    total: int
    query_time_ms: float


class SavedQueryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    query: str = Field(..., min_length=1)
    description: str = ""


class SavedQueryUpdate(BaseModel):
    name: str | None = None
    query: str | None = None
    description: str | None = None


class SavedQueryRead(BaseModel):
    id: int
    name: str
    query: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# AI / semantic search schemas  (used by routers/ai.py or similar)
# ---------------------------------------------------------------------------

class AIQueryRequest(BaseModel):
    query: str = Field(
        ...,
        json_schema_extra={"example": "What are the key ideas in my Zettelkasten?"},
    )
    top_k: int = Field(default=5, ge=1, le=50)
    include_graph: bool = Field(default=False)
    rerank: bool = Field(default=True)


class AIQueryResultItem(BaseModel):
    note_id: str
    title: str
    score: float
    snippet: str
    tags: list[str] = []


class AIQueryResponse(BaseModel):
    answer: str
    results: list[AIQueryResultItem] = []
    query: str
    model: str = ""
    sources: list[dict[str, Any]] = []
