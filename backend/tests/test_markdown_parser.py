"""Unit tests for gnosis/services/markdown_parser.py.

All tests are pure-Python — no DB, no external services.
"""
from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gnosis.services.markdown_parser import (
    build_default_frontmatter,
    extract_wikilinks,
    generate_note_id,
    parse_note_file,
    write_note_file,
)


# ---------------------------------------------------------------------------
# generate_note_id
# ---------------------------------------------------------------------------

def test_generate_note_id_format():
    nid = generate_note_id()
    assert len(nid) == 15
    assert nid[8] == "-"


def test_generate_note_id_deterministic():
    dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
    assert generate_note_id(dt) == "20240115-103045"


# ---------------------------------------------------------------------------
# extract_wikilinks
# ---------------------------------------------------------------------------

def test_extract_wikilinks_basic():
    links = extract_wikilinks("See [[Note One]] and [[Note Two]].")
    assert links == ["Note One", "Note Two"]


def test_extract_wikilinks_with_alias():
    links = extract_wikilinks("Check [[Target|Alias]] here.")
    assert links == ["Target"]


def test_extract_wikilinks_deduplicates():
    links = extract_wikilinks("[[A]] and [[A]] again.")
    assert links == ["A"]


def test_extract_wikilinks_empty():
    assert extract_wikilinks("No links here.") == []


# ---------------------------------------------------------------------------
# parse_note_file
# ---------------------------------------------------------------------------

def test_parse_note_file_full(tmp_path):
    md = textwrap.dedent("""\
        ---
        id: "20240101-120000"
        title: Test Note
        type: permanent
        status: active
        tags:
          - python
          - testing
        ---
        Body text with [[WikiLink]].
    """)
    p = tmp_path / "test.md"
    p.write_text(md, encoding="utf-8")

    note = parse_note_file(p)
    assert note["id"] == "20240101-120000"
    assert note["title"] == "Test Note"
    assert note["note_type"] == "permanent"
    assert note["status"] == "active"
    assert "python" in note["tags"]
    assert "WikiLink" in note["wikilinks"]
    assert note["word_count"] > 0
    assert "<p>" in note["body_html"]


def test_parse_note_file_defaults(tmp_path):
    """A bare file with no frontmatter uses safe defaults."""
    p = tmp_path / "bare.md"
    p.write_text("Just a body.", encoding="utf-8")
    note = parse_note_file(p)
    assert note["title"] == "bare"
    assert note["note_type"] == "permanent"
    assert note["status"] == "draft"
    assert note["tags"] == []


# ---------------------------------------------------------------------------
# write_note_file
# ---------------------------------------------------------------------------

def test_write_note_file_round_trip(tmp_path):
    p = tmp_path / "sub" / "note.md"
    fm = {"id": "20240101-000000", "status": "draft"}
    write_note_file(p, "My Note", "Body content.", fm)

    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "My Note" in content
    assert "Body content." in content


# ---------------------------------------------------------------------------
# build_default_frontmatter
# ---------------------------------------------------------------------------

def test_build_default_frontmatter_keys():
    fm = build_default_frontmatter("20240101-000000", "My Title", tags=["a", "b"])
    assert fm["id"] == "20240101-000000"
    assert fm["title"] == "My Title"
    assert fm["tags"] == ["a", "b"]
    assert "created" in fm
    assert "modified" in fm


def test_build_default_frontmatter_defaults():
    fm = build_default_frontmatter("x", "T")
    assert fm["type"] == "permanent"
    assert fm["status"] == "draft"
    assert fm["tags"] == []
    assert fm["source"] == ""
