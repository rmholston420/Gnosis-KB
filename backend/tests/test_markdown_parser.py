"""Tests for gnosis/services/markdown_parser.py.

The real public API is:
  parse_note_file(path)  -> dict
  parse_markdown_file    -> alias for parse_note_file
  extract_wikilinks(body) -> list[str]
  write_note_file(path, title, body, fm)
  build_default_frontmatter(...) -> dict
  generate_note_id(dt=None) -> str

Dependencies: python-frontmatter, mistune, python-slugify — all available
in the venv, so no mocking needed here.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# generate_note_id
# ---------------------------------------------------------------------------

def test_generate_note_id_format():
    from gnosis.services.markdown_parser import generate_note_id
    nid = generate_note_id()
    assert len(nid) == 15  # YYYYMMDD-HHmmss
    assert nid[8] == "-"


def test_generate_note_id_deterministic():
    from gnosis.services.markdown_parser import generate_note_id
    from datetime import datetime, timezone
    dt = datetime(2025, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
    assert generate_note_id(dt) == "20250115-123045"


# ---------------------------------------------------------------------------
# extract_wikilinks
# ---------------------------------------------------------------------------

def test_extract_wikilinks_basic():
    from gnosis.services.markdown_parser import extract_wikilinks
    body = "See [[Note One]] and [[Another Note|alias]]."
    links = extract_wikilinks(body)
    assert "Note One" in links
    assert "Another Note" in links


def test_extract_wikilinks_no_links():
    from gnosis.services.markdown_parser import extract_wikilinks
    assert extract_wikilinks("No links here.") == []


def test_extract_wikilinks_deduplicated():
    from gnosis.services.markdown_parser import extract_wikilinks
    body = "[[A]] and [[A]] again"
    links = extract_wikilinks(body)
    assert links.count("A") == 1


# ---------------------------------------------------------------------------
# build_default_frontmatter
# ---------------------------------------------------------------------------

def test_build_default_frontmatter_required_keys():
    from gnosis.services.markdown_parser import build_default_frontmatter
    fm = build_default_frontmatter("20250115-120000", "My Note")
    assert fm["id"] == "20250115-120000"
    assert fm["title"] == "My Note"
    assert fm["status"] == "draft"
    assert isinstance(fm["tags"], list)


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
    result = parse_note_file(md)
    assert result["title"] == "Test Note"
    assert "python" in result["tags"]
    assert "Body text" in result["body"]
    assert result["note_type"] == "permanent"
    assert result["word_count"] >= 3


def test_parse_note_file_alias(tmp_path):
    from gnosis.services.markdown_parser import parse_markdown_file, parse_note_file
    assert parse_markdown_file is parse_note_file


def test_parse_note_file_no_frontmatter(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file
    md = tmp_path / "bare.md"
    md.write_text("# Just a heading\nSome body text.")
    result = parse_note_file(md)
    assert result["title"] == "bare"  # falls back to stem
    assert result["status"] == "draft"


def test_parse_note_file_wikilinks(tmp_path):
    from gnosis.services.markdown_parser import parse_note_file
    md = tmp_path / "linked.md"
    md.write_text("---\ntitle: Linked\n---\nSee [[Related Note]] for more.")
    result = parse_note_file(md)
    assert "Related Note" in result["wikilinks"]


# ---------------------------------------------------------------------------
# write_note_file
# ---------------------------------------------------------------------------

def test_write_note_file_roundtrip(tmp_path):
    from gnosis.services.markdown_parser import write_note_file, parse_note_file, build_default_frontmatter
    note_id = "20250101-120000"
    fm = build_default_frontmatter(note_id, "Round Trip")
    out = tmp_path / "round_trip.md"
    write_note_file(out, "Round Trip", "Body content.", fm)
    assert out.exists()
    parsed = parse_note_file(out)
    assert parsed["title"] == "Round Trip"
    assert "Body content." in parsed["body"]
