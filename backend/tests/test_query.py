"""Tests for the GQL query engine — parser + executor."""
from __future__ import annotations

import pytest
from sqlalchemy import insert

from gnosis.models.note import Note
from gnosis.models.tag import NoteTag, Tag
from gnosis.services.query_parser import GQLParseError, ParsedQuery, execute_query, parse_query

# ---------------------------------------------------------------------------
# Parser — happy-path tests
# ---------------------------------------------------------------------------

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
    assert q.sort_field == "modified_at"
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
    q = parse_query("")
    assert q.from_folder is None
    assert q.sort_field == "modified_at"
    assert q.limit == 50


# ---------------------------------------------------------------------------
# Parser — edge-case / error paths
# ---------------------------------------------------------------------------

def test_parse_query_too_long_raises():
    with pytest.raises(GQLParseError, match="exceeds maximum length"):
        parse_query("FROM " + "x" * 2100)


def test_parse_from_missing_arg_raises():
    with pytest.raises(GQLParseError, match="FROM requires"):
        parse_query("FROM")


def test_parse_sort_missing_field_raises():
    with pytest.raises(GQLParseError, match="SORT requires"):
        parse_query("SORT")


def test_parse_sort_unknown_field_raises():
    with pytest.raises(GQLParseError, match="Unknown sort field"):
        parse_query("SORT nonexistent")


def test_parse_limit_missing_arg_raises():
    with pytest.raises(GQLParseError, match="LIMIT requires"):
        parse_query("LIMIT")


def test_parse_select_missing_arg_raises():
    with pytest.raises(GQLParseError, match="SELECT requires"):
        parse_query("SELECT")


def test_parse_tags_missing_contains_raises():
    with pytest.raises(GQLParseError, match="Expected TAGS CONTAINS"):
        parse_query("WHERE tags MISSING eeg")


def test_parse_tags_contains_missing_tag_raises():
    with pytest.raises(GQLParseError, match="TAGS CONTAINS requires"):
        parse_query("WHERE tags CONTAINS")


def test_parse_where_unparseable_condition_raises():
    with pytest.raises(GQLParseError, match="Cannot parse WHERE condition"):
        parse_query("WHERE justword")


def test_parse_spaced_operator_three_tokens():
    """WHERE field OP value as three separate tokens (not inline)."""
    q = parse_query("WHERE word_count >= 100")
    assert q.conditions == [{"type": "field", "field": "word_count", "op": ">=", "value": "100"}]


def test_parse_not_equal_operator():
    q = parse_query("WHERE status!=published")
    assert q.conditions[0]["op"] == "!="


def test_parse_lte_operator():
    q = parse_query("WHERE word_count <= 500")
    assert q.conditions[0]["op"] == "<="


def test_parse_sort_no_direction_defaults_desc():
    q = parse_query("SORT title")
    assert q.sort_field == "title"
    assert q.sort_dir == "DESC"


def test_parse_sort_asc_explicit():
    q = parse_query("SORT word_count ASC")
    assert q.sort_dir == "ASC"


def test_parse_limit_min_boundary():
    q = parse_query("LIMIT 1")
    assert q.limit == 1


def test_parse_limit_max_boundary():
    q = parse_query("LIMIT 500")
    assert q.limit == 500


def test_parse_limit_zero_raises():
    with pytest.raises(GQLParseError, match="LIMIT must be between"):
        parse_query("LIMIT 0")


# ---------------------------------------------------------------------------
# Executor — execute_query() DB paths
#
# Note.id   — String(20), no server default: must supply explicitly.
# Tag.name  — String(100), primary key: pass as keyword arg.
# NoteTag   — Core Table object (not a mapped class): use insert().
# ---------------------------------------------------------------------------


async def _seed_notes(db):
    """Insert two live notes, one deleted note, one tag, and one association."""
    n1 = Note(
        id="20260101-000001",
        title="Alpha Note",
        slug="alpha-note",
        folder="10-zettelkasten",
        status="published",
        note_type="zettel",
        word_count=200,
        is_deleted=False,
        owner_id=1,
    )
    n2 = Note(
        id="20260101-000002",
        title="Beta Note",
        slug="beta-note",
        folder="20-projects",
        status="draft",
        note_type="project",
        word_count=50,
        is_deleted=False,
        owner_id=1,
    )
    deleted = Note(
        id="20260101-000003",
        title="Gone Note",
        slug="gone-note",
        folder="10-zettelkasten",
        status="published",
        note_type="zettel",
        word_count=10,
        is_deleted=True,
        owner_id=1,
    )
    db.add_all([n1, n2, deleted])
    await db.flush()

    # Tag PK is name (string) — no separate id column
    tag = Tag(name="zettelkasten")
    db.add(tag)
    await db.flush()

    # NoteTag is a Core Table, not a mapped class — use insert()
    await db.execute(
        insert(NoteTag).values(note_id=n1.id, tag_id="zettelkasten")
    )
    await db.commit()
    return n1, n2, tag


@pytest.mark.asyncio
async def test_execute_query_no_filter_returns_non_deleted(test_db):
    await _seed_notes(test_db)
    rows, ms = await execute_query(ParsedQuery(), test_db)
    titles = {r["title"] for r in rows}
    assert "Alpha Note" in titles
    assert "Beta Note" in titles
    assert "Gone Note" not in titles
    assert ms >= 0


@pytest.mark.asyncio
async def test_execute_query_from_folder_filter(test_db):
    await _seed_notes(test_db)
    q = parse_query("FROM 10-zettelkasten")
    rows, _ = await execute_query(q, test_db)
    assert all(r["folder"].startswith("10-zettelkasten") for r in rows)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_execute_query_where_field_condition(test_db):
    await _seed_notes(test_db)
    q = parse_query("WHERE status=draft")
    rows, _ = await execute_query(q, test_db)
    assert len(rows) == 1
    assert rows[0]["title"] == "Beta Note"


@pytest.mark.asyncio
async def test_execute_query_where_word_count_gt(test_db):
    await _seed_notes(test_db)
    q = parse_query("WHERE word_count > 100")
    rows, _ = await execute_query(q, test_db)
    assert len(rows) == 1
    assert rows[0]["word_count"] == 200


@pytest.mark.asyncio
async def test_execute_query_where_tag_contains(test_db):
    await _seed_notes(test_db)
    q = parse_query("WHERE tags CONTAINS zettelkasten")
    rows, _ = await execute_query(q, test_db)
    assert len(rows) == 1
    assert rows[0]["title"] == "Alpha Note"


@pytest.mark.asyncio
async def test_execute_query_where_tag_no_match(test_db):
    await _seed_notes(test_db)
    q = parse_query("WHERE tags CONTAINS nonexistent")
    rows, _ = await execute_query(q, test_db)
    assert rows == []


@pytest.mark.asyncio
async def test_execute_query_sort_asc(test_db):
    await _seed_notes(test_db)
    q = parse_query("SORT word_count ASC")
    rows, _ = await execute_query(q, test_db)
    counts = [r["word_count"] for r in rows]
    assert counts == sorted(counts)


@pytest.mark.asyncio
async def test_execute_query_sort_desc(test_db):
    await _seed_notes(test_db)
    q = parse_query("SORT word_count DESC")
    rows, _ = await execute_query(q, test_db)
    counts = [r["word_count"] for r in rows]
    assert counts == sorted(counts, reverse=True)


@pytest.mark.asyncio
async def test_execute_query_limit(test_db):
    await _seed_notes(test_db)
    q = parse_query("LIMIT 1")
    rows, _ = await execute_query(q, test_db)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_execute_query_select_cols(test_db):
    await _seed_notes(test_db)
    q = parse_query("SELECT title,status")
    rows, _ = await execute_query(q, test_db)
    for row in rows:
        assert set(row.keys()) == {"title", "status"}


@pytest.mark.asyncio
async def test_execute_query_owner_ids_scoped(test_db):
    """owner_ids branch: scoped results should be subset of unscoped."""
    await _seed_notes(test_db)
    q = ParsedQuery()
    rows_scoped, _ = await execute_query(q, test_db, owner_ids={1})
    rows_all, _ = await execute_query(q, test_db, owner_ids=None)
    assert len(rows_scoped) <= len(rows_all)


@pytest.mark.asyncio
async def test_execute_query_date_fields_serialised_as_isoformat(test_db):
    await _seed_notes(test_db)
    q = parse_query("SELECT title,created_at LIMIT 1")
    rows, _ = await execute_query(q, test_db)
    if rows and rows[0].get("created_at") is not None:
        assert isinstance(rows[0]["created_at"], str)


@pytest.mark.asyncio
async def test_execute_query_multiple_conditions(test_db):
    await _seed_notes(test_db)
    q = parse_query("FROM 20-projects WHERE status=draft AND word_count <= 100")
    rows, _ = await execute_query(q, test_db)
    assert len(rows) == 1
    assert rows[0]["title"] == "Beta Note"
