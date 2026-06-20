"""Tests for gnosis/services/markdown_parser.py.

Real public API:
  parse_note_file(path)           -> dict
  parse_markdown_file             -> alias for parse_note_file
  extract_wikilinks(body)         -> list[str]
  write_note_file(path, title, body, fm)
  build_default_frontmatter(...)  -> dict
  generate_note_id(dt=None)       -> str
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import pytest


# ---------------------------------------------------------------------------
# generate_note_id
# ---------------------------------------------------------------------------

def test_generate_note_id_format():
    from gnosis.services.markdown_parser import generate_note_id
    nid = generate_note_id()
    assert len(nid) == 15
    assert nid[8] == "-"


def test_generate_note_id_deterministic():
    from gnosis.services.markdown_parser import generate_note_id
    dt = datetime(2025, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
    assert generate_note_id(dt) == "20250115-123045"


def test_generate_note_id_no_arg_uses_utc_now():
    from gnosis.services.markdown_parser import generate_note_id
    nid = generate_note_id()
    # Format: YYYYMMDD-HHmmss
    assert nid[:4].isdigit()
    assert nid[8] == "-"


# ---------------------------------------------------------------------------
# extract_wikilinks
# ---------------------------------------------------------------------------

def test_extract_wikilinks_basic():
    from gnosis.services.markdown_parser import extract_wikilinks
    links = extract_wikilinks("See [[Note One]] and [[Another Note|alias]].")
    assert "Note One" in links
    assert "Another Note" in links


def test_extract_wikilinks_no_links():
    from gnosis.services.markdown_parser import extract_wikilinks
    assert extract_wikilinks("No links here.") == []


def test_extract_wikilinks_deduplicates():
    from gnosis.services.markdown_parser import extract_wikilinks
    links = extract_wikilinks("[[A]] and [[A]] again")
    assert links.count("A") == 1


def test_extract_wikilinks_ignores_alias():
    from gnosis.services.markdown_parser import extract_wikilinks
    links = extract_wikilinks("[[Target|Display Name]]")
    assert "Target" in links
    assert "Display Name" not in links


# ---------------------------------------------------------------------------
# build_default_frontmatter
# ---------------------------------------------------------------------------

def test_build_default_frontmatter_required_keys():
    from gnosis.services.markdown_parser import build_default_frontmatter
    fm = build_default_frontmatter("20250115-120000", "My Note")
    for key in ("id", "title", "type", "status", "tags", "created", "modified"):
        assert key in fm, f"Missing key: {key}"


def test_build_default_frontmatter_defaults():
    from gnosis.services.markdown_parser import build_default_frontmatter
    fm = build_default_frontmatter("id-1", "Title")
    assert fm["type"] == "permanent"
    assert fm["status"] == "draft"
    assert fm["tags"] == []


def test_build_default_frontmatter_custom_values():
    from gnosis.services.markdown_parser import build_default_frontmatter
    fm = build_default_frontmatter(
        "id-1", "Title",
        note_type="fleeting",
        status="active",
        tags=["ml", "python"],
        source_url="https://example.com",
    )
    assert fm["type"] == "fleeting"
    assert "ml" in fm["tags"]
    assert fm["source"] == "https://example.com"


# ---------------------------------------------------------------------------
# parse_note_file / parse_markdown_file
# ---------------------------------------------------------------------------

def test_parse_note_file_basic(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file
    md = tmp_path / "my-note.md"
    md.write_text("---\ntitle: Test Note\ntags: [python, ml]\ntype: permanent\nstatus: active\n---\n# Hello\n\nBody text here.")
    r = parse_note_file(md)
    assert r["title"] == "Test Note"
    assert "python" in r["tags"]
    assert "Body text" in r["body"]
    assert r["note_type"] == "permanent"
    assert r["word_count"] >= 3


def test_parse_note_file_alias_is_same_function(tmp_path):
    from gnosis.services.markdown_parser import parse_markdown_file, parse_note_file
    assert parse_markdown_file is parse_note_file


def test_parse_note_file_no_frontmatter(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file
    md = tmp_path / "bare.md"
    md.write_text("# Just a heading\nSome body text.")
    r = parse_note_file(md)
    assert r["title"] == "bare"
    assert r["status"] == "draft"


def test_parse_note_file_wikilinks(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file
    md = tmp_path / "linked.md"
    md.write_text("---\ntitle: Linked\n---\nSee [[Related Note]] for more.")
    r = parse_note_file(md)
    assert "Related Note" in r["wikilinks"]


def test_parse_note_file_body_html_present(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file
    md = tmp_path / "html.md"
    md.write_text("---\ntitle: HTML\n---\n**bold text**")
    r = parse_note_file(md)
    assert "<" in r["body_html"]  # rendered to HTML


def test_parse_note_file_slug_generated(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file
    md = tmp_path / "my-note.md"
    md.write_text("---\ntitle: My Note\n---\nbody")
    r = parse_note_file(md)
    assert r["slug"] != ""


def test_parse_note_file_source_url_parsed(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file
    md = tmp_path / "sourced.md"
    md.write_text("---\ntitle: Sourced\nsource: https://example.com\n---\nbody")
    r = parse_note_file(md)
    assert r["source_url"] == "https://example.com"


def test_parse_note_file_returns_all_expected_keys(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file
    md = tmp_path / "complete.md"
    md.write_text("---\ntitle: Complete\n---\nbody")
    r = parse_note_file(md)
    for key in ("id", "title", "slug", "body", "body_html", "note_type",
                "status", "folder", "tags", "wikilinks", "word_count"):
        assert key in r, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# write_note_file
# ---------------------------------------------------------------------------

def test_write_note_file_roundtrip(tmp_path):
    from gnosis.services.markdown_parser import write_note_file, parse_note_file, build_default_frontmatter
    fm = build_default_frontmatter("20250101-120000", "Round Trip")
    out = tmp_path / "round_trip.md"
    write_note_file(out, "Round Trip", "Body content.", fm)
    assert out.exists()
    parsed = parse_note_file(out)
    assert parsed["title"] == "Round Trip"
    assert "Body content." in parsed["body"]


def test_write_note_file_creates_parent_dirs(tmp_path):
    from gnosis.services.markdown_parser import write_note_file, build_default_frontmatter
    fm = build_default_frontmatter("id-1", "Nested")
    out = tmp_path / "sub" / "dir" / "note.md"
    write_note_file(out, "Nested", "body", fm)
    assert out.exists()


def test_write_note_file_contains_frontmatter(tmp_path):
    from gnosis.services.markdown_parser import write_note_file, build_default_frontmatter
    fm = build_default_frontmatter("id-2", "FM Test", tags=["x", "y"])
    out = tmp_path / "fm_test.md"
    write_note_file(out, "FM Test", "body", fm)
    content = out.read_text()
    assert "FM Test" in content
    assert "---" in content
