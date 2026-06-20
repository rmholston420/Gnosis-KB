"""Tests for gnosis/services/document_parser.py.

Real public API:
  ParsedDocument   (dataclass)
  EXTENSION_MAP    (dict)
  detect_format(filename) -> Optional[str]   -- returns None for unknown
  parse_pdf(path)   -> ParsedDocument
  parse_docx(path)  -> ParsedDocument
  parse_pptx(path)  -> ParsedDocument
  parse_xlsx(path)  -> ParsedDocument
  parse_image(path) -> ParsedDocument
  parse_url(url)    -> ParsedDocument  (async; httpx imported inside function)
  parse_file(path)  -> ParsedDocument  (sync dispatcher)

NOTE: httpx is imported with a bare `import httpx` INSIDE parse_url, so it
must be patched via sys.modules, not as a module-level attribute.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import pytest


# ---------------------------------------------------------------------------
# ParsedDocument
# ---------------------------------------------------------------------------

def test_parsed_document_defaults():
    from gnosis.services.document_parser import ParsedDocument
    doc = ParsedDocument(title="T", text="body")
    assert doc.author == ""
    assert doc.page_count == 0
    assert doc.raw_format == ""
    assert doc.metadata == {}
    assert doc.source == ""


def test_parsed_document_full_fields():
    from gnosis.services.document_parser import ParsedDocument
    doc = ParsedDocument(
        title="T", text="b", source="s", author="A",
        page_count=3, raw_format="pdf", metadata={"k": "v"}
    )
    assert doc.author == "A"
    assert doc.page_count == 3
    assert doc.metadata["k"] == "v"


# ---------------------------------------------------------------------------
# EXTENSION_MAP
# ---------------------------------------------------------------------------

def test_extension_map_contains_common_formats():
    from gnosis.services.document_parser import EXTENSION_MAP
    assert EXTENSION_MAP[".pdf"] == "pdf"
    assert EXTENSION_MAP[".docx"] == "docx"
    assert EXTENSION_MAP[".pptx"] == "pptx"
    assert EXTENSION_MAP[".xlsx"] == "xlsx"
    assert EXTENSION_MAP[".png"] == "image"


# ---------------------------------------------------------------------------
# detect_format
# ---------------------------------------------------------------------------

def test_detect_format_pdf():
    from gnosis.services.document_parser import detect_format
    assert detect_format("report.pdf") == "pdf"


def test_detect_format_docx():
    from gnosis.services.document_parser import detect_format
    assert detect_format("doc.docx") == "docx"
    assert detect_format("doc.doc") == "docx"


def test_detect_format_pptx():
    from gnosis.services.document_parser import detect_format
    assert detect_format("slides.pptx") == "pptx"


def test_detect_format_xlsx():
    from gnosis.services.document_parser import detect_format
    assert detect_format("sheet.xlsx") == "xlsx"


def test_detect_format_image():
    from gnosis.services.document_parser import detect_format
    assert detect_format("photo.png") == "image"
    assert detect_format("photo.jpg") == "image"
    assert detect_format("photo.webp") == "image"


def test_detect_format_case_insensitive():
    from gnosis.services.document_parser import detect_format
    assert detect_format("DOC.PDF") == "pdf"
    assert detect_format("PHOTO.JPG") == "image"


def test_detect_format_unknown_returns_none():
    from gnosis.services.document_parser import detect_format
    assert detect_format("file.txt") is None
    assert detect_format("note.md") is None
    assert detect_format("archive.zip") is None


def test_detect_format_no_extension_returns_none():
    from gnosis.services.document_parser import detect_format
    assert detect_format("Makefile") is None


# ---------------------------------------------------------------------------
# parse_pdf — fitz (PyMuPDF) patched via sys.modules
# ---------------------------------------------------------------------------

def test_parse_pdf_raises_without_fitz(tmp_path):
    from gnosis.services.document_parser import parse_pdf
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4")
    with patch.dict(sys.modules, {"fitz": None}):
        with pytest.raises((RuntimeError, ImportError, TypeError)):
            parse_pdf(f)


def test_parse_pdf_with_mocked_fitz(tmp_path):
    from gnosis.services.document_parser import parse_pdf

    fake_page = MagicMock()
    fake_page.get_text.return_value = "Page one content."

    fake_doc = MagicMock()
    fake_doc.__iter__ = MagicMock(return_value=iter([fake_page]))
    fake_doc.__len__ = MagicMock(return_value=1)
    fake_doc.metadata = {"title": "My PDF", "author": "Alice"}

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = fake_doc

    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4")

    with patch.dict(sys.modules, {"fitz": fake_fitz}):
        doc = parse_pdf(f)

    assert doc.title == "My PDF"
    assert "Page one" in doc.text
    assert doc.raw_format == "pdf"


# ---------------------------------------------------------------------------
# parse_docx — python-docx patched via sys.modules
# ---------------------------------------------------------------------------

def test_parse_docx_raises_without_docx(tmp_path):
    from gnosis.services.document_parser import parse_docx
    f = tmp_path / "doc.docx"
    f.write_bytes(b"dummy")
    with patch.dict(sys.modules, {"docx": None}):
        with pytest.raises((RuntimeError, ImportError, TypeError)):
            parse_docx(f)


def test_parse_docx_with_mocked_docx(tmp_path):
    from gnosis.services.document_parser import parse_docx

    fake_para1 = MagicMock()
    fake_para1.text = "Introduction paragraph."
    fake_para2 = MagicMock()
    fake_para2.text = "Second paragraph."
    fake_para_empty = MagicMock()
    fake_para_empty.text = ""

    fake_doc_obj = MagicMock()
    fake_doc_obj.paragraphs = [fake_para1, fake_para2, fake_para_empty]
    fake_doc_obj.sections = [MagicMock()]

    fake_docx_module = MagicMock()
    fake_docx_module.Document.return_value = fake_doc_obj

    f = tmp_path / "doc.docx"
    f.write_bytes(b"PK")

    with patch.dict(sys.modules, {"docx": fake_docx_module}):
        doc = parse_docx(f)

    assert "Introduction" in doc.text
    assert doc.raw_format == "docx"


# ---------------------------------------------------------------------------
# parse_url — async; httpx imported INSIDE the function body
# Must be patched via sys.modules["httpx"], not as a module attribute.
# Also needs bs4 patched so BeautifulSoup import succeeds.
# ---------------------------------------------------------------------------

def _make_fake_httpx(html: str, raise_on_get=False):
    """Return a fake httpx module whose AsyncClient yields html."""
    fake_resp = MagicMock()
    fake_resp.text = html
    fake_resp.raise_for_status = MagicMock()

    fake_client = MagicMock()
    if raise_on_get:
        fake_client.get = AsyncMock(side_effect=Exception("connection refused"))
    else:
        fake_client.get = AsyncMock(return_value=fake_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    fake_httpx = MagicMock()
    fake_httpx.AsyncClient.return_value = fake_client
    return fake_httpx


def _make_fake_bs4(title_text: str | None, body_text: str):
    """Return a fake bs4 module."""
    fake_title_tag = MagicMock()
    fake_title_tag.get_text.return_value = title_text or ""

    fake_body = MagicMock()
    fake_body.get_text.return_value = body_text

    fake_soup = MagicMock()
    fake_soup.find.side_effect = lambda tag, **kw: (
        fake_title_tag if tag == "title" else
        fake_body if tag == "body" else
        None
    )
    fake_soup.find_all.return_value = []
    fake_soup.get_text.return_value = body_text

    fake_bs4 = MagicMock()
    fake_bs4.BeautifulSoup.return_value = fake_soup
    return fake_bs4


@pytest.mark.asyncio
async def test_parse_url_extracts_title_and_text():
    from gnosis.services.document_parser import parse_url

    html = "<html><head><title>Test Page</title></head><body><p>Hello world content.</p></body></html>"
    fake_httpx = _make_fake_httpx(html)
    fake_bs4 = _make_fake_bs4("Test Page", "Hello world content.")

    with patch.dict(sys.modules, {"httpx": fake_httpx, "bs4": fake_bs4}):
        doc = await parse_url("https://example.com/page")

    assert doc.title == "Test Page"
    assert "Hello world" in doc.text
    assert doc.raw_format == "url"


@pytest.mark.asyncio
async def test_parse_url_handles_http_error():
    from gnosis.services.document_parser import parse_url

    fake_httpx = _make_fake_httpx("", raise_on_get=True)

    with patch.dict(sys.modules, {"httpx": fake_httpx}):
        with pytest.raises(Exception):
            await parse_url("https://example.com/broken")


@pytest.mark.asyncio
async def test_parse_url_no_bs4_falls_back_to_raw_text():
    """When bs4 is absent the parser falls back to raw HTML text."""
    from gnosis.services.document_parser import parse_url

    html = "<html><body><p>Raw content fallback.</p></body></html>"
    fake_httpx = _make_fake_httpx(html)

    # Simulate bs4 not installed by removing it from sys.modules
    with patch.dict(sys.modules, {"httpx": fake_httpx, "bs4": None}):
        doc = await parse_url("https://example.com/no-bs4")

    assert doc.raw_format == "url"
    assert isinstance(doc.title, str)


# ---------------------------------------------------------------------------
# parse_file — sync dispatcher
# ---------------------------------------------------------------------------

def test_parse_file_raises_on_unsupported_extension(tmp_path):
    from gnosis.services.document_parser import parse_file
    f = tmp_path / "file.xyz"
    f.write_text("data")
    with pytest.raises(ValueError):
        parse_file(f)


def test_parse_file_raises_on_txt(tmp_path):
    from gnosis.services.document_parser import parse_file
    f = tmp_path / "readme.txt"
    f.write_text("hello")
    with pytest.raises(ValueError):
        parse_file(f)


def test_parse_file_raises_on_markdown(tmp_path):
    from gnosis.services.document_parser import parse_file
    f = tmp_path / "note.md"
    f.write_text("# heading")
    with pytest.raises(ValueError):
        parse_file(f)


def test_parse_file_dispatches_to_pdf(tmp_path):
    from gnosis.services.document_parser import parse_file, ParsedDocument
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4")
    mock_result = ParsedDocument(title="PDF", text="content", raw_format="pdf")
    with patch("gnosis.services.document_parser.parse_pdf", return_value=mock_result):
        doc = parse_file(f)
    assert doc.raw_format == "pdf"


def test_parse_file_dispatches_to_docx(tmp_path):
    from gnosis.services.document_parser import parse_file, ParsedDocument
    f = tmp_path / "doc.docx"
    f.write_bytes(b"PK")
    mock_result = ParsedDocument(title="DOCX", text="content", raw_format="docx")
    with patch("gnosis.services.document_parser.parse_docx", return_value=mock_result):
        doc = parse_file(f)
    assert doc.raw_format == "docx"


def test_parse_file_dispatches_to_image(tmp_path):
    from gnosis.services.document_parser import parse_file, ParsedDocument
    f = tmp_path / "photo.png"
    f.write_bytes(b"PNG")
    mock_result = ParsedDocument(title="Image", text="ocr text", raw_format="image")
    with patch("gnosis.services.document_parser.parse_image", return_value=mock_result):
        doc = parse_file(f)
    assert doc.raw_format == "image"
