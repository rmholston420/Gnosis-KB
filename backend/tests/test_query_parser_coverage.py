"""Coverage tests for gnosis/services/query_parser.py.

Actual API:
  parse_query(raw: str) -> ParsedQuery   SYNC, not async
  execute_query(parsed, db, owner_ids)   async
  GQLParseError                          raised on bad syntax

There is NO build_search_context function. The old tests assumed an LLM-based
async parse_query — the real implementation is a pure regex/token parser.
"""

from __future__ import annotations

import pytest

from gnosis.services.query_parser import GQLParseError, ParsedQuery, parse_query

# ---------------------------------------------------------------------------
# parse_query (sync) tests
# ---------------------------------------------------------------------------


def test_parse_query_empty_returns_defaults():
    """Empty string → ParsedQuery with defaults."""
    result = parse_query("")
    assert isinstance(result, ParsedQuery)
    assert result.sort_field == "modified_at"
    assert result.limit == 50


def test_parse_query_from_folder():
    result = parse_query("FROM 10-zettelkasten")
    assert result.from_folder == "10-zettelkasten"


def test_parse_query_sort_asc():
    result = parse_query("SORT title ASC")
    assert result.sort_field == "title"
    assert result.sort_dir == "ASC"


def test_parse_query_limit():
    result = parse_query("LIMIT 10")
    assert result.limit == 10


def test_parse_query_where_status():
    result = parse_query("WHERE status=draft")
    assert len(result.conditions) == 1
    assert result.conditions[0]["field"] == "status"
    assert result.conditions[0]["value"] == "draft"


def test_parse_query_where_tags_contains():
    result = parse_query("WHERE TAGS CONTAINS python")
    assert result.conditions[0]["type"] == "tag"
    assert result.conditions[0]["tag"] == "python"


def test_parse_query_select_cols():
    result = parse_query("SELECT title,status,modified_at")
    assert "title" in result.select_cols
    assert "status" in result.select_cols


def test_parse_query_full_expression():
    result = parse_query("FROM 20-projects WHERE status=active SORT modified_at DESC LIMIT 20")
    assert result.from_folder == "20-projects"
    assert result.limit == 20
    assert result.sort_dir == "DESC"


def test_parse_query_invalid_keyword_raises():
    with pytest.raises(GQLParseError):
        parse_query("INVALID syntax here")


def test_parse_query_unknown_field_raises():
    with pytest.raises(GQLParseError):
        parse_query("WHERE badfield=value")


def test_parse_query_limit_too_large_raises():
    with pytest.raises(GQLParseError):
        parse_query("LIMIT 9999")


def test_parse_query_sort_alias_modified():
    """'modified' is aliased to 'modified_at'."""
    result = parse_query("SORT modified DESC")
    assert result.sort_field == "modified_at"


def test_parse_query_sort_alias_created():
    result = parse_query("SORT created ASC")
    assert result.sort_field == "created_at"
