"""Tests for the markdown parser service."""

import tempfile
from pathlib import Path

from gnosis.services.markdown_parser import (
    build_default_frontmatter,
    extract_wikilinks,
    generate_note_id,
    parse_note_file,
    write_note_file,
)


def test_generate_note_id():
    """Note ID should be in YYYYMMDD-HHmmss format."""
    note_id = generate_note_id()
    assert len(note_id) == 15
    assert note_id[8] == "-"


def test_extract_wikilinks_basic():
    """Basic [[WikiLink]] extraction."""
    body = "This links to [[Another Note]] and also [[Yet Another]]."
    links = extract_wikilinks(body)
    assert "Another Note" in links
    assert "Yet Another" in links
    assert len(links) == 2


def test_extract_wikilinks_with_alias():
    """[[Title|Alias]] should extract 'Title', not 'Alias'."""
    body = "See [[Zettelkasten|ZK method]] for details."
    links = extract_wikilinks(body)
    assert "Zettelkasten" in links
    assert "ZK method" not in links


def test_extract_wikilinks_deduplication():
    """Duplicate wikilinks should appear only once."""
    body = "[[Note A]] and [[Note A]] again."
    links = extract_wikilinks(body)
    assert links.count("Note A") == 1


def test_write_and_parse_roundtrip():
    """Write a note file and parse it back; content should match."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "10-zettelkasten" / "test-note.md"
        path.parent.mkdir()
        note_id = generate_note_id()
        fm = build_default_frontmatter(note_id, "Test Note", tags=["test"])
        body = "This is the body with [[A Link]]."
        write_note_file(path, "Test Note", body, fm)

        assert path.exists()

        parsed = parse_note_file(path)
        assert parsed["title"] == "Test Note"
        assert parsed["body"].strip() == body.strip()
        assert "A Link" in parsed["wikilinks"]
        assert "test" in parsed["tags"]


def test_parse_note_file_defaults():
    """Parsing a minimal note file should fill in defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "00-inbox" / "minimal.md"
        path.parent.mkdir()
        path.write_text("---\ntitle: Minimal\n---\nJust a body.\n", encoding="utf-8")
        parsed = parse_note_file(path)
        assert parsed["title"] == "Minimal"
        assert "body" in parsed
