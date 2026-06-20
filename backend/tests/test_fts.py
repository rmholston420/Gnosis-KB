"""Unit tests for gnosis/services/fts.py.

Focus:
- happy-path fulltext_search output mapping
- SQL params include folder/note_type/tags filters
- DB failure returns empty results
- suggest_completions returns title list
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from gnosis.services.fts import fulltext_search, suggest_completions


@pytest.mark.asyncio
async def test_fulltext_search_happy_path_maps_rows():
    row = {
        "note_id": "n1",
        "title": "Graph Notes",
        "slug": "graph-notes",
        "folder": "10-zettelkasten",
        "note_type": "permanent",
        "status": "active",
        "score": 0.88,
        "highlight": "<mark>graph</mark> notes snippet",
        "tags": ["graph", "idea"],
    }
    result_obj = MagicMock()
    result_obj.mappings.return_value.all.return_value = [row]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_obj)

    result = await fulltext_search(db, "graph", limit=5)

    assert len(result["results"]) == 1
    item = result["results"][0]
    assert item["note_id"] == "n1"
    assert item["title"] == "Graph Notes"
    assert item["score"] == 0.88
    assert item["tags"] == ["graph", "idea"]


@pytest.mark.asyncio
async def test_fulltext_search_adds_folder_type_and_tag_params():
    result_obj = MagicMock()
    result_obj.mappings.return_value.all.return_value = []
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_obj)

    await fulltext_search(
        db,
        "graph",
        limit=7,
        folder="10-zettelkasten",
        note_type="permanent",
        tags=["idea", "ml"],
    )

    sql_arg, params_arg = db.execute.call_args.args
    sql_text = str(sql_arg)

    assert "n.folder = :folder" in sql_text
    assert "n.note_type = :note_type" in sql_text
    assert "JOIN note_tags nt0" in sql_text
    assert "JOIN note_tags nt1" in sql_text
    assert params_arg["folder"] == "10-zettelkasten"
    assert params_arg["note_type"] == "permanent"
    assert params_arg["tag_0"] == "idea"
    assert params_arg["tag_1"] == "ml"
    assert params_arg["limit"] == 7


@pytest.mark.asyncio
async def test_fulltext_search_db_failure_returns_empty():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))

    result = await fulltext_search(db, "graph")

    assert result == {"results": [], "elapsed_ms": 0.0}


@pytest.mark.asyncio
async def test_fulltext_search_nullish_fields_normalized():
    row = {
        "note_id": "n2",
        "title": "Untitled",
        "slug": None,
        "folder": None,
        "note_type": None,
        "status": None,
        "score": 0.42,
        "highlight": None,
        "tags": None,
    }
    result_obj = MagicMock()
    result_obj.mappings.return_value.all.return_value = [row]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_obj)

    result = await fulltext_search(db, "untitled")
    item = result["results"][0]
    assert item["slug"] == ""
    assert item["folder"] == ""
    assert item["note_type"] == ""
    assert item["status"] == ""
    assert item["highlight"] == ""
    assert item["tags"] == []


@pytest.mark.asyncio
async def test_suggest_completions_returns_titles():
    result_obj = MagicMock()
    result_obj.fetchall.return_value = [("Alpha",), ("Alphabet",), ("Alpine",)]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_obj)

    result = await suggest_completions(db, "Al", limit=3)

    assert result == ["Alpha", "Alphabet", "Alpine"]
