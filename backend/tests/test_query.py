"""Tests for the GQL query engine."""
from __future__ import annotations

import pytest

from gnosis.services.query_parser import GQLParseError, parse_query


def test_parse_from_only():
    q = parse_query("FROM 10-zettelkasten")
    assert q.from_folder == "10-zettelkasten"
    assert q.conditions == []
    assert q.limit == 50


def test_parse_from_where_sort_limit():
    q = parse_query("FROM 10-zettelkasten WHERE status=draft SORT modified DESC LIMIT 20")
    assert q.from_folder == "10-zettelkasten"
    assert len(q.conditions) == 1
    assert q.conditions[0] == {"type": "field", "field": "status", "op": "=", "value": "draft"}
    assert q.sort_field == "modified_at"  # alias resolved
    assert q.sort_dir == "DESC"
    assert q.limit == 20


def test_parse_tags_contains():
    q = parse_query("WHERE tags CONTAINS eeg")
    assert q.conditions == [{"type": "tag", "tag": "eeg"}]


def test_parse_multiple_where():
    q = parse_query("FROM 20-projects WHERE note_type=project AND word_count > 100 LIMIT 50")
    assert q.from_folder == "20-projects"
    assert len(q.conditions) == 2
    assert q.conditions[1]["op"] == ">"
    assert q.conditions[1]["value"] == "100"


def test_parse_select_cols():
    q = parse_query("FROM 00-inbox SORT modified_at DESC LIMIT 10 SELECT title,status,modified_at")
    assert q.select_cols == ["title", "status", "modified_at"]


def test_parse_sort_alias_created():
    q = parse_query("FROM 10-zettelkasten SORT created ASC")
    assert q.sort_field == "created_at"
    assert q.sort_dir == "ASC"


def test_parse_unknown_field_raises():
    with pytest.raises(GQLParseError, match="Unknown field"):
        parse_query("WHERE body=foo")


def test_parse_bad_limit_raises():
    with pytest.raises(GQLParseError, match="LIMIT must be an integer"):
        parse_query("LIMIT abc")


def test_parse_limit_out_of_range():
    with pytest.raises(GQLParseError, match="LIMIT must be between"):
        parse_query("LIMIT 999")


def test_parse_unknown_keyword_raises():
    with pytest.raises(GQLParseError, match="Unknown keyword"):
        parse_query("JOIN notes ON id")


def test_parse_select_bad_col_raises():
    with pytest.raises(GQLParseError, match="Unknown SELECT column"):
        parse_query("SELECT body,password")


def test_parse_empty_query_runs_defaults():
    """An empty query string should default to all notes, sort modified DESC, limit 50."""
    q = parse_query("")
    assert q.from_folder is None
    assert q.sort_field == "modified_at"
    assert q.limit == 50
