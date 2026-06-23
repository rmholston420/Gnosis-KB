"""Tests for gnosis/services/query_parser.py — parse_query (sync) only."""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# ParsedQuery defaults
# ---------------------------------------------------------------------------

def test_parse_query_empty_returns_defaults():
    from gnosis.services.query_parser import ParsedQuery, parse_query
    pq = parse_query("")
    assert isinstance(pq, ParsedQuery)
    assert pq.sort_field == "modified_at"
    assert pq.sort_dir == "DESC"
    assert pq.limit == 50
    assert pq.from_folder is None
    assert pq.conditions == []


def test_parse_query_whitespace_returns_defaults():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("   ")
    assert pq.from_folder is None


# ---------------------------------------------------------------------------
# FROM clause
# ---------------------------------------------------------------------------

def test_parse_query_from_folder():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("FROM 10-zettelkasten")
    assert pq.from_folder == "10-zettelkasten"


def test_parse_query_from_lowercase():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("FROM 20-PROJECTS")
    assert pq.from_folder == "20-projects"


def test_parse_query_from_without_arg_raises():
    from gnosis.services.query_parser import GQLParseError, parse_query
    with pytest.raises(GQLParseError):
        parse_query("FROM")


# ---------------------------------------------------------------------------
# LIMIT clause
# ---------------------------------------------------------------------------

def test_parse_query_limit():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("LIMIT 10")
    assert pq.limit == 10


def test_parse_query_limit_zero_or_negative():
    from gnosis.services.query_parser import GQLParseError, parse_query
    with pytest.raises((GQLParseError, ValueError)):
        parse_query("LIMIT -5")


# ---------------------------------------------------------------------------
# SORT clause
# ---------------------------------------------------------------------------

def test_parse_query_sort_field_and_dir():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("SORT created_at ASC")
    assert pq.sort_field == "created_at"
    assert pq.sort_dir == "ASC"


def test_parse_query_sort_alias_modified():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("SORT modified DESC")
    assert pq.sort_field == "modified_at"


def test_parse_query_sort_unknown_field_raises():
    from gnosis.services.query_parser import GQLParseError, parse_query
    with pytest.raises(GQLParseError):
        parse_query("SORT unknown_field DESC")


# ---------------------------------------------------------------------------
# WHERE clause
# ---------------------------------------------------------------------------

def test_parse_query_where_status():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("WHERE status=draft")
    assert len(pq.conditions) == 1
    cond = pq.conditions[0]
    assert cond["field"] == "status"
    assert cond["op"] == "="
    assert cond["value"] == "draft"


def test_parse_query_where_tags_contains():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("WHERE tags CONTAINS eeg")
    assert len(pq.conditions) == 1
    assert pq.conditions[0]["type"] == "tag"
    assert pq.conditions[0]["tag"] == "eeg"


def test_parse_query_where_multiple_and():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("WHERE status=draft AND note_type=permanent")
    assert len(pq.conditions) == 2


def test_parse_query_where_unknown_field_raises():
    from gnosis.services.query_parser import GQLParseError, parse_query
    with pytest.raises(GQLParseError):
        parse_query("WHERE unknown_field=foo")


def test_parse_query_where_gt_operator():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("WHERE word_count>100")
    cond = pq.conditions[0]
    assert cond["field"] == "word_count"
    assert ">" in cond["op"]


# ---------------------------------------------------------------------------
# SELECT clause
# ---------------------------------------------------------------------------

def test_parse_query_select_cols():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("SELECT title,status")
    assert "title" in pq.select_cols
    assert "status" in pq.select_cols


# ---------------------------------------------------------------------------
# Combined queries
# ---------------------------------------------------------------------------

def test_parse_query_combined_from_where_sort_limit():
    from gnosis.services.query_parser import parse_query
    pq = parse_query("FROM 10-zettelkasten WHERE status=draft SORT modified DESC LIMIT 20")
    assert pq.from_folder == "10-zettelkasten"
    assert pq.limit == 20
    assert pq.sort_field == "modified_at"
    assert pq.sort_dir == "DESC"
    assert pq.conditions[0]["value"] == "draft"


def test_parse_query_too_long_raises():
    from gnosis.services.query_parser import GQLParseError, parse_query
    with pytest.raises(GQLParseError):
        parse_query("a" * 2001)


# ---------------------------------------------------------------------------
# GQLParseError is a ValueError subclass
# ---------------------------------------------------------------------------

def test_gql_parse_error_is_value_error():
    from gnosis.services.query_parser import GQLParseError
    assert issubclass(GQLParseError, ValueError)
