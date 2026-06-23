"""Gap-filling tests for gnosis/services/markdown_parser.py.

Targets the uncovered lines reported in coverage:
  31-33, 38-59, 86, 91-95, 107-108

All file I/O is done through tmp_path (pytest fixture) — no mocking needed.
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from pathlib import Path

from gnosis.services.markdown_parser import (
    build_default_frontmatter,
    extract_wikilinks,
    generate_note_id,
    parse_markdown_file,
    parse_note_file,
    write_note_file,
)

# ---------------------------------------------------------------------------
# generate_note_id
# ---------------------------------------------------------------------------


def test_generate_note_id_uses_provided_dt():
    dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=UTC)
    assert generate_note_id(dt) == "20240315-103000"


def test_generate_note_id_without_arg_returns_14_char_string():
    nid = generate_note_id()
    assert len(nid) == 15  # YYYYMMDD-HHmmss
    assert nid[8] == "-"


# ---------------------------------------------------------------------------
# parse_note_file — covers lines 38-59
# ---------------------------------------------------------------------------

MINIMAL_MD = textwrap.dedent("""\
    ---
    id: "test-001"
    title: My Note
    type: permanent
    status: active
    tags:
      - python
      - testing
    source: https://example.com
    created: "2024-01-01"
    modified: "2024-01-02"
    last_reviewed: "2024-01-03"
    ---
    Body text here. [[LinkedNote]] and [[Another|Alias]].
""")


def test_parse_note_file_full_frontmatter(tmp_path: Path):
    p = tmp_path / "notes" / "my-note.md"
    p.parent.mkdir()
    p.write_text(MINIMAL_MD, encoding="utf-8")

    result = parse_note_file(p)

    assert result["id"] == "test-001"
    assert result["title"] == "My Note"
    assert result["note_type"] == "permanent"
    assert result["status"] == "active"
    assert result["tags"] == ["python", "testing"]
    assert result["source_url"] == "https://example.com"
    assert result["last_reviewed"] == "2024-01-03"
    assert result["folder"] == "notes"
    assert "Body text here" in result["body"]
    assert "<p>" in result["body_html"]
    assert result["wikilinks"] == ["LinkedNote", "Another"]
    assert result["word_count"] >= 3


def test_parse_note_file_minimal_no_frontmatter(tmp_path: Path):
    """File with no YAML frontmatter — defaults kick in."""
    p = tmp_path / "00-inbox" / "bare.md"
    p.parent.mkdir()
    p.write_text("Just some words.\n", encoding="utf-8")

    result = parse_note_file(p)

    assert result["title"] == "bare"  # falls back to stem
    assert result["note_type"] == "permanent"  # default
    assert result["status"] == "draft"  # default
    assert result["tags"] == []
    assert result["source_url"] is None
    assert result["folder"] == "00-inbox"


def test_parse_note_file_uses_source_url_key(tmp_path: Path):
    """Frontmatter key 'source_url' is also accepted."""
    md = textwrap.dedent("""\
        ---
        source_url: https://other.com
        ---
        Text.
    """)
    p = tmp_path / "note.md"
    p.write_text(md, encoding="utf-8")
    result = parse_note_file(p)
    assert result["source_url"] == "https://other.com"


def test_parse_markdown_file_alias(tmp_path: Path):
    """parse_markdown_file is an alias for parse_note_file."""
    p = tmp_path / "alias.md"
    p.write_text("Hello\n", encoding="utf-8")
    assert parse_markdown_file(p) == parse_note_file(p)


# ---------------------------------------------------------------------------
# extract_wikilinks — line 86
# ---------------------------------------------------------------------------


def test_extract_wikilinks_deduplicates():
    body = "[[A]] and [[A]] and [[B]]"
    assert extract_wikilinks(body) == ["A", "B"]


def test_extract_wikilinks_with_alias():
    assert extract_wikilinks("[[Target|Display Text]]") == ["Target"]


def test_extract_wikilinks_empty():
    assert extract_wikilinks("") == []


# ---------------------------------------------------------------------------
# write_note_file — lines 91-95
# ---------------------------------------------------------------------------


def test_write_note_file_creates_file(tmp_path: Path):
    dest = tmp_path / "sub" / "new-note.md"
    fm = {"id": "x", "tags": []}
    write_note_file(dest, "My Title", "Body content.", fm)

    assert dest.exists()
    content = dest.read_text(encoding="utf-8")
    assert "title: My Title" in content
    assert "Body content." in content


# ---------------------------------------------------------------------------
# build_default_frontmatter — lines 107-108
# ---------------------------------------------------------------------------


def test_build_default_frontmatter_full():
    fm = build_default_frontmatter(
        note_id="abc-123",
        title="Test Note",
        note_type="literature",
        status="active",
        tags=["tag1"],
        source_url="https://test.com",
    )
    assert fm["id"] == "abc-123"
    assert fm["title"] == "Test Note"
    assert fm["type"] == "literature"
    assert fm["status"] == "active"
    assert fm["tags"] == ["tag1"]
    assert fm["source"] == "https://test.com"
    assert fm["last_reviewed"] is None
    assert fm["links"] == []


def test_build_default_frontmatter_defaults():
    fm = build_default_frontmatter(note_id="z", title="Z")
    assert fm["type"] == "permanent"
    assert fm["status"] == "draft"
    assert fm["tags"] == []
    assert fm["source"] == ""
