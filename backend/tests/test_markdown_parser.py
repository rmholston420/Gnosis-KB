"""Tests for gnosis/services/markdown_parser.py."""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# generate_note_id
# ---------------------------------------------------------------------------


def test_generate_note_id_format():
    from gnosis.services.markdown_parser import generate_note_id

    nid = generate_note_id()
    assert len(nid) == 15  # YYYYMMDD-HHmmss
    assert nid[8] == "-"


def test_generate_note_id_deterministic_with_dt():
    from gnosis.services.markdown_parser import generate_note_id

    dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
    assert generate_note_id(dt) == "20240115-103045"


# ---------------------------------------------------------------------------
# extract_wikilinks
# ---------------------------------------------------------------------------


def test_extract_wikilinks_basic():
    from gnosis.services.markdown_parser import extract_wikilinks

    result = extract_wikilinks("See [[Note A]] and [[Note B]].")
    assert result == ["Note A", "Note B"]


def test_extract_wikilinks_with_alias():
    from gnosis.services.markdown_parser import extract_wikilinks

    result = extract_wikilinks("See [[Note A|Alias]].")
    assert result == ["Note A"]


def test_extract_wikilinks_deduplicates():
    from gnosis.services.markdown_parser import extract_wikilinks

    result = extract_wikilinks("[[A]] and [[A]] again.")
    assert result == ["A"]


def test_extract_wikilinks_empty():
    from gnosis.services.markdown_parser import extract_wikilinks

    assert extract_wikilinks("") == []
    assert extract_wikilinks("No links here.") == []


# ---------------------------------------------------------------------------
# parse_note_file
# ---------------------------------------------------------------------------


def test_parse_note_file_basic(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file

    note = tmp_path / "my-note.md"
    note.write_text(
        textwrap.dedent("""\
        ---
        title: My Note
        type: permanent
        status: draft
        tags:
          - foo
          - bar
        ---
        Body text here.
        """),
        encoding="utf-8",
    )
    result = parse_note_file(note)
    assert result["title"] == "My Note"
    assert result["note_type"] == "permanent"
    assert result["status"] == "draft"
    assert "foo" in result["tags"]
    assert "Body text" in result["body"]


def test_parse_note_file_no_frontmatter(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file

    note = tmp_path / "plain.md"
    note.write_text("Just a plain note.", encoding="utf-8")
    result = parse_note_file(note)
    assert result["title"] == "plain"  # falls back to stem
    assert result["body"] == "Just a plain note."


def test_parse_note_file_returns_word_count(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file

    note = tmp_path / "words.md"
    note.write_text("one two three four five", encoding="utf-8")
    result = parse_note_file(note)
    assert result["word_count"] == 5


def test_parse_note_file_extracts_wikilinks(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file

    note = tmp_path / "links.md"
    note.write_text("See [[Alpha]] and [[Beta]].", encoding="utf-8")
    result = parse_note_file(note)
    assert "Alpha" in result["wikilinks"]
    assert "Beta" in result["wikilinks"]


def test_parse_note_file_body_html(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file

    note = tmp_path / "html.md"
    note.write_text("# Heading\n\nParagraph.", encoding="utf-8")
    result = parse_note_file(note)
    assert "<h1" in result["body_html"] or "Heading" in result["body_html"]


# ---------------------------------------------------------------------------
# build_default_frontmatter
# ---------------------------------------------------------------------------


def test_build_default_frontmatter_required_keys():
    from gnosis.services.markdown_parser import build_default_frontmatter

    fm = build_default_frontmatter(note_id="20240101-000000", title="Test")
    assert fm["id"] == "20240101-000000"
    assert fm["title"] == "Test"
    assert fm["type"] == "permanent"
    assert fm["status"] == "draft"
    assert isinstance(fm["tags"], list)
    assert "created" in fm
    assert "modified" in fm


def test_build_default_frontmatter_custom_values():
    from gnosis.services.markdown_parser import build_default_frontmatter

    fm = build_default_frontmatter(
        note_id="id",
        title="T",
        note_type="fleeting",
        status="published",
        tags=["a", "b"],
        source_url="https://example.com",
    )
    assert fm["type"] == "fleeting"
    assert fm["status"] == "published"
    assert fm["tags"] == ["a", "b"]
    assert fm["source"] == "https://example.com"


# ---------------------------------------------------------------------------
# write_note_file (round-trip)
# ---------------------------------------------------------------------------


def test_write_note_file_roundtrip(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file, write_note_file

    fm = {"id": "20240101-000000", "type": "permanent", "status": "draft", "tags": []}
    path = tmp_path / "output.md"
    write_note_file(path, "Round Trip", "Body content.", fm)
    result = parse_note_file(path)
    assert result["title"] == "Round Trip"
    assert result["body"] == "Body content."


def test_write_note_file_creates_parent_dirs(tmp_path):
    from gnosis.services.markdown_parser import write_note_file

    path = tmp_path / "deep" / "nested" / "note.md"
    write_note_file(path, "Nested", "content", {})
    assert path.exists()


# ---------------------------------------------------------------------------
# parse_markdown_file alias
# ---------------------------------------------------------------------------


def test_parse_markdown_file_alias(tmp_path):
    from gnosis.services.markdown_parser import parse_markdown_file, parse_note_file

    assert parse_markdown_file is parse_note_file
