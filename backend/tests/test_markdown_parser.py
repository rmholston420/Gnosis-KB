"""Tests for gnosis/services/markdown_parser.py."""
from __future__ import annotations

import pytest


def test_parse_frontmatter_basic():
    from gnosis.services.markdown_parser import parse_frontmatter
    md = "---\ntitle: Hello\ntags: [a, b]\n---\n# Body"
    meta, body = parse_frontmatter(md)
    assert meta["title"] == "Hello"
    assert meta["tags"] == ["a", "b"]
    assert "Body" in body


def test_parse_frontmatter_no_frontmatter():
    from gnosis.services.markdown_parser import parse_frontmatter
    md = "# Just markdown\nNo YAML here."
    meta, body = parse_frontmatter(md)
    assert meta == {}
    assert "Just markdown" in body


def test_parse_frontmatter_empty_string():
    from gnosis.services.markdown_parser import parse_frontmatter
    meta, body = parse_frontmatter("")
    assert meta == {}
    assert body == ""


def test_extract_tags_from_frontmatter():
    from gnosis.services.markdown_parser import extract_tags
    md = "---\ntags: [python, ml]\n---\nBody text"
    tags = extract_tags(md)
    assert "python" in tags
    assert "ml" in tags


def test_extract_tags_inline_hashtags():
    from gnosis.services.markdown_parser import extract_tags
    md = "Some text with #python and #ml tags."
    tags = extract_tags(md)
    assert "python" in tags
    assert "ml" in tags


def test_extract_tags_empty():
    from gnosis.services.markdown_parser import extract_tags
    tags = extract_tags("No tags here.")
    assert isinstance(tags, list)


def test_extract_wikilinks():
    from gnosis.services.markdown_parser import extract_wikilinks
    md = "See [[Note One]] and [[Another Note|alias]]."
    links = extract_wikilinks(md)
    assert "Note One" in links
    assert "Another Note" in links


def test_extract_wikilinks_no_links():
    from gnosis.services.markdown_parser import extract_wikilinks
    links = extract_wikilinks("No links.")
    assert links == []


def test_extract_word_count():
    from gnosis.services.markdown_parser import extract_word_count
    md = "---\ntitle: T\n---\nHello world this is four"
    count = extract_word_count(md)
    assert count >= 4


def test_extract_word_count_empty():
    from gnosis.services.markdown_parser import extract_word_count
    assert extract_word_count("") == 0
