"""Tests for gnosis/services/document_parser.py."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def test_parsed_document_defaults():
    from gnosis.services.document_parser import ParsedDocument
    doc = ParsedDocument(title="T", text="body", source="file.txt")
    assert doc.author == ""
    assert doc.page_count == 1
    assert doc.raw_format == "text"
    assert doc.metadata == {}


def test_parsed_document_full_fields():
    from gnosis.services.document_parser import ParsedDocument
    doc = ParsedDocument(title="T", text="b", source="s", author="A", page_count=3, raw_format="pdf", metadata={"k": "v"})
    assert doc.author == "A"
    assert doc.page_count == 3
    assert doc.metadata["k"] == "v"


def test_detect_format_pdf(tmp_path):
    from gnosis.services.document_parser import detect_format
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4")
    assert detect_format(f) == "pdf"


def test_detect_format_docx(tmp_path):
    from gnosis.services.document_parser import detect_format
    f = tmp_path / "doc.docx"
    f.write_bytes(b"dummy")
    assert detect_format(f) == "docx"


def test_detect_format_markdown(tmp_path):
    from gnosis.services.document_parser import detect_format
    for ext in (".md", ".markdown"):
        f = tmp_path / f"note{ext}"
        f.write_text("# heading")
        assert detect_format(f) == "markdown"


def test_detect_format_text(tmp_path):
    from gnosis.services.document_parser import detect_format
    f = tmp_path / "file.txt"
    f.write_text("hello")
    assert detect_format(f) == "text"


def test_detect_format_url():
    from gnosis.services.document_parser import detect_format
    assert detect_format("https://example.com/page") == "url"
    assert detect_format("http://example.com") == "url"


def test_parse_text_basic(tmp_path):
    from gnosis.services.document_parser import parse_text
    f = tmp_path / "hello.txt"
    f.write_text("Hello world")
    doc = parse_text(f)
    assert doc.text == "Hello world"
    assert doc.raw_format == "text"


def test_parse_text_empty(tmp_path):
    from gnosis.services.document_parser import parse_text
    f = tmp_path / "empty.txt"
    f.write_text("")
    doc = parse_text(f)
    assert doc.text == ""


def test_parse_markdown_basic(tmp_path):
    from gnosis.services.document_parser import parse_markdown
    f = tmp_path / "note.md"
    f.write_text("---\ntitle: My Note\n---\n# Heading\n\nBody text here.")
    doc = parse_markdown(f)
    assert doc.title == "My Note"
    assert "Body" in doc.text
    assert doc.raw_format == "markdown"


def test_parse_markdown_no_frontmatter(tmp_path):
    from gnosis.services.document_parser import parse_markdown
    f = tmp_path / "bare.md"
    f.write_text("# Just heading\nSome body.")
    doc = parse_markdown(f)
    assert doc.title == "bare"


def test_parse_markdown_with_author(tmp_path):
    from gnosis.services.document_parser import parse_markdown
    f = tmp_path / "auth.md"
    f.write_text("---\ntitle: T\nauthor: Alice\n---\nbody")
    doc = parse_markdown(f)
    assert doc.author == "Alice"


def test_parse_pdf_raises_without_fitz(tmp_path):
    import sys
    from gnosis.services.document_parser import parse_pdf
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4")
    with patch.dict(sys.modules, {"fitz": None}):
        with pytest.raises((RuntimeError, ImportError)):
            parse_pdf(f)


def test_parse_docx_raises_without_docx(tmp_path):
    import sys
    from gnosis.services.document_parser import parse_docx
    f = tmp_path / "doc.docx"
    f.write_bytes(b"dummy")
    with patch.dict(sys.modules, {"docx": None}):
        with pytest.raises((RuntimeError, ImportError)):
            parse_docx(f)


@pytest.mark.asyncio
async def test_parse_url_extracts_title_and_text():
    from gnosis.services.document_parser import parse_url

    html = "<html><head><title>Test Page</title></head><body><p>Hello world content here.</p></body></html>"
    fake_resp = MagicMock()
    fake_resp.text = html
    fake_resp.raise_for_status = MagicMock()

    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    fake_httpx = MagicMock()
    fake_httpx.AsyncClient.return_value = fake_client

    with patch("gnosis.services.document_parser.httpx", fake_httpx):
        doc = await parse_url("https://example.com/page")

    assert doc.title == "Test Page"
    assert "Hello world" in doc.text
    assert doc.raw_format == "url"


@pytest.mark.asyncio
async def test_parse_url_handles_http_error():
    from gnosis.services.document_parser import parse_url

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=Exception("connection refused"))
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    fake_httpx = MagicMock()
    fake_httpx.AsyncClient.return_value = fake_client

    with patch("gnosis.services.document_parser.httpx", fake_httpx):
        with pytest.raises(Exception):
            await parse_url("https://example.com/broken")


@pytest.mark.asyncio
async def test_parse_document_dispatches_url():
    from gnosis.services.document_parser import parse_document, ParsedDocument
    mock_result = ParsedDocument(title="URL Doc", text="fetched", source="https://x.com")
    with patch("gnosis.services.document_parser.parse_url", new_callable=AsyncMock, return_value=mock_result):
        doc = await parse_document("https://example.com")
    assert doc.title == "URL Doc"


@pytest.mark.asyncio
async def test_parse_document_dispatches_text(tmp_path):
    from gnosis.services.document_parser import parse_document
    f = tmp_path / "file.txt"
    f.write_text("some text content")
    doc = await parse_document(f)
    assert "some text" in doc.text


@pytest.mark.asyncio
async def test_parse_document_dispatches_markdown(tmp_path):
    from gnosis.services.document_parser import parse_document
    f = tmp_path / "note.md"
    f.write_text("---\ntitle: Dispatched MD\n---\nbody")
    doc = await parse_document(f)
    assert doc.title == "Dispatched MD"


@pytest.mark.asyncio
async def test_parse_document_raises_on_unknown_format(tmp_path):
    from gnosis.services.document_parser import parse_document
    f = tmp_path / "file.xyz"
    f.write_text("data")
    with pytest.raises(ValueError):
        await parse_document(f)
