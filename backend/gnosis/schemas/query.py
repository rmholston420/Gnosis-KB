"""Pydantic schemas for the Dataview query engine."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QueryRun(BaseModel):
    """Execute a one-off query without saving it."""

    query: str = Field(
        ...,
        min_length=1,
        example="FROM 10-zettelkasten WHERE status=draft SORT modified DESC LIMIT 20",
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
