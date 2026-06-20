"""Unit tests for gnosis/services/query_parser.py.

Pure-Python parser tests — no DB required.
"""
from __future__ import annotations

import pytest

from gnosis.services.query_parser import GQLParseError, ParsedQuery, parse_query


# ---------------------------------------------------------------------------
# Empty / default query
# ---------------------------------------------------------------------------

def test_empty_query_returns_defaults():
    q = parse_query("")
    assert q.from_folder is None
    assert q.conditions == []
    assert q.sort_field == "modified_at"
    assert q.sort_dir == "DESC"
    assert q.limit == 50


def test_whitespace_only_query_returns_defaults():
    assert parse_query("   ").limit == 50


# ---------------------------------------------------------------------------
# FROM clause
# ---------------------------------------------------------------------------

def test_from_clause_sets_folder():
    q = parse_query("FROM 10-zettelkasten")
    assert q.from_folder == "10-zettelkasten"


def test_from_missing_arg_raises():
    with pytest.raises(GQLParseError, match="FROM"):
        parse_query("FROM")


# ---------------------------------------------------------------------------
# WHERE clause
# ---------------------------------------------------------------------------

def test_where_equality_condition():
    q = parse_query("WHERE status=draft")
    assert len(q.conditions) == 1
    c = q.conditions[0]
    assert c["type"] == "field"
    assert c["field"] == "status"
    assert c["op"] == "="
    assert c["value"] == "draft"


def test_where_gt_condition():
    q = parse_query("WHERE word_count > 100")
    c = q.conditions[0]
    assert c["op"] == ">"
    assert c["value"] == "100"


def test_where_tags_contains():
    q = parse_query("WHERE tags CONTAINS python")
    c = q.conditions[0]
    assert c["type"] == "tag"
    assert c["tag"] == "python"


def test_where_and_multiple_conditions():
    q = parse_query("WHERE status=draft AND note_type=permanent")
    assert len(q.conditions) == 2


def test_where_unknown_field_raises():
    with pytest.raises(GQLParseError, match="Unknown field"):
        parse_query("WHERE nonexistent=foo")


def test_where_tags_missing_contains_raises():
    with pytest.raises(GQLParseError):
        parse_query("WHERE tags python")


def test_where_tags_missing_tag_name_raises():
    with pytest.raises(GQLParseError):
        parse_query("WHERE tags CONTAINS")


# ---------------------------------------------------------------------------
# SORT clause
# ---------------------------------------------------------------------------

def test_sort_desc():
    q = parse_query("SORT modified_at DESC")
    assert q.sort_field == "modified_at"
    assert q.sort_dir == "DESC"


def test_sort_asc():
    q = parse_query("SORT created_at ASC")
    assert q.sort_dir == "ASC"


def test_sort_alias_modified():
    q = parse_query("SORT modified DESC")
    assert q.sort_field == "modified_at"


def test_sort_alias_created():
    q = parse_query("SORT created")
    assert q.sort_field == "created_at"


def test_sort_unknown_field_raises():
    with pytest.raises(GQLParseError, match="sort field"):
        parse_query("SORT banana DESC")


def test_sort_missing_field_raises():
    with pytest.raises(GQLParseError, match="SORT"):
        parse_query("SORT")


# ---------------------------------------------------------------------------
# LIMIT clause
# ---------------------------------------------------------------------------

def test_limit_sets_value():
    q = parse_query("LIMIT 10")
    assert q.limit == 10


def test_limit_boundary_low():
    q = parse_query("LIMIT 1")
    assert q.limit == 1


def test_limit_boundary_high():
    q = parse_query("LIMIT 500")
    assert q.limit == 500


def test_limit_out_of_range_raises():
    with pytest.raises(GQLParseError, match="between 1 and 500"):
        parse_query("LIMIT 501")


def test_limit_zero_raises():
    with pytest.raises(GQLParseError):
        parse_query("LIMIT 0")


def test_limit_non_integer_raises():
    with pytest.raises(GQLParseError, match="integer"):
        parse_query("LIMIT abc")


def test_limit_missing_arg_raises():
    with pytest.raises(GQLParseError, match="LIMIT"):
        parse_query("LIMIT")


# ---------------------------------------------------------------------------
# SELECT clause
# ---------------------------------------------------------------------------

def test_select_valid_columns():
    q = parse_query("SELECT title,status,folder")
    assert q.select_cols == ["title", "status", "folder"]


def test_select_unknown_column_raises():
    with pytest.raises(GQLParseError, match="Unknown SELECT"):
        parse_query("SELECT banana")


def test_select_missing_arg_raises():
    with pytest.raises(GQLParseError, match="SELECT"):
        parse_query("SELECT")


# ---------------------------------------------------------------------------
# Combined / edge cases
# ---------------------------------------------------------------------------

def test_full_query():
    q = parse_query("FROM 10-zettelkasten WHERE status=draft SORT modified_at DESC LIMIT 20 SELECT title,status")
    assert q.from_folder == "10-zettelkasten"
    assert q.conditions[0]["value"] == "draft"
    assert q.limit == 20
    assert q.select_cols == ["title", "status"]


def test_query_too_long_raises():
    with pytest.raises(GQLParseError, match="maximum length"):
        parse_query("FROM " + "x" * 2000)


def test_unknown_keyword_raises():
    with pytest.raises(GQLParseError, match="Unknown keyword"):
        parse_query("BOGUS foo")
