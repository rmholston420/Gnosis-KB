"""
Unit tests for document_parser.py.

Tests cover the pure-Python helpers and the format dispatcher.
All heavy optional dependencies (fitz, docx, pptx, openpyxl, pytesseract)
are mocked so no binaries are required.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gnosis.services.document_parser import (
    ParsedDocument,
    detect_format,
    parse_file,
)


# ---------------------------------------------------------------------------
# ParsedDocument dataclass
# ---------------------------------------------------------------------------

def test_parsed_document_defaults():
    doc = ParsedDocument(title="T", text="body")
    assert doc.source == ""
    assert doc.author == ""
    assert doc.page_count == 0
    assert doc.raw_format == ""
    assert doc.metadata == {}


def test_parsed_document_fields():
    doc = ParsedDocument(
        title="My PDF",
        text="hello world",
        source="report.pdf",
        author="Alice",
        page_count=5,
        raw_format="pdf",
        metadata={"producer": "LaTeX"},
    )
    assert doc.title == "My PDF"
    assert doc.page_count == 5
    assert doc.metadata["producer"] == "LaTeX"


# ---------------------------------------------------------------------------
# detect_format
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,expected", [
    ("report.pdf", "pdf"),
    ("thesis.PDF", "pdf"),
    ("notes.docx", "docx"),
    ("notes.doc", "docx"),
    ("deck.pptx", "pptx"),
    ("deck.ppt", "pptx"),
    ("data.xlsx", "xlsx"),
    ("data.xls", "xlsx"),
    ("photo.png", "image"),
    ("photo.jpg", "image"),
    ("photo.jpeg", "image"),
    ("photo.webp", "image"),
    ("scan.tiff", "image"),
    ("scan.tif", "image"),
    ("README.md", None),
    ("archive.zip", None),
    ("no_extension", None),
])
def test_detect_format(filename, expected):
    assert detect_format(filename) == expected


# ---------------------------------------------------------------------------
# parse_file dispatcher — unsupported raises ValueError
# ---------------------------------------------------------------------------

def test_parse_file_unsupported_raises():
    with pytest.raises(ValueError, match="Unsupported file format"):
        parse_file(Path("archive.zip"))


# ---------------------------------------------------------------------------
# parse_pdf (mocked fitz)
# ---------------------------------------------------------------------------

def test_parse_pdf_uses_filename_as_title_when_no_meta():
    fake_fitz = MagicMock()
    mock_doc = MagicMock()
    mock_doc.metadata = {}
    mock_doc.__iter__ = lambda self: iter([])
    mock_doc.__len__ = lambda self: 0
    fake_fitz.open.return_value = mock_doc

    with patch.dict(sys.modules, {"fitz": fake_fitz}):
        from gnosis.services import document_parser as dp
        result = dp.parse_pdf(Path("/vault/my-great-report.pdf"))

    assert result.raw_format == "pdf"
    assert result.title == "My Great Report"


def test_parse_pdf_uses_metadata_title():
    fake_fitz = MagicMock()
    mock_doc = MagicMock()
    mock_doc.metadata = {"title": "Executive Summary", "author": "Bob"}
    mock_doc.__iter__ = lambda self: iter([])
    mock_doc.__len__ = lambda self: 0
    fake_fitz.open.return_value = mock_doc

    with patch.dict(sys.modules, {"fitz": fake_fitz}):
        from gnosis.services import document_parser as dp
        result = dp.parse_pdf(Path("/vault/anything.pdf"))

    assert result.title == "Executive Summary"
    assert result.author == "Bob"


def test_parse_pdf_missing_fitz_raises_runtime():
    with patch.dict(sys.modules, {"fitz": None}):
        from gnosis.services import document_parser as dp
        with pytest.raises((RuntimeError, ImportError)):
            dp.parse_pdf(Path("/vault/file.pdf"))


# ---------------------------------------------------------------------------
# parse_docx (mocked python-docx)
# ---------------------------------------------------------------------------

def test_parse_docx_extracts_paragraphs():
    p1, p2 = MagicMock(), MagicMock()
    p1.text = "Introduction"
    p2.text = "Body paragraph here."

    mock_doc = MagicMock()
    mock_doc.paragraphs = [p1, p2]
    mock_doc.sections = [MagicMock()]  # 1 section

    fake_docx_module = MagicMock()
    fake_docx_module.Document.return_value = mock_doc

    with patch.dict(sys.modules, {"docx": fake_docx_module}):
        from gnosis.services import document_parser as dp
        result = dp.parse_docx(Path("/vault/essay.docx"))

    assert result.raw_format == "docx"
    assert "Introduction" in result.text
    assert result.title == "Introduction"
    assert result.page_count == 1


def test_parse_docx_empty_doc_uses_stem_as_title():
    mock_doc = MagicMock()
    mock_doc.paragraphs = []
    mock_doc.sections = []

    fake_docx_module = MagicMock()
    fake_docx_module.Document.return_value = mock_doc

    with patch.dict(sys.modules, {"docx": fake_docx_module}):
        from gnosis.services import document_parser as dp
        result = dp.parse_docx(Path("/vault/my-notes.docx"))

    assert result.title == "my-notes"


# ---------------------------------------------------------------------------
# parse_pptx (mocked python-pptx)
# ---------------------------------------------------------------------------

def test_parse_pptx_extracts_slide_text():
    shape = MagicMock()
    shape.text = "  Hello Slide  "
    slide = MagicMock()
    slide.shapes = [shape]

    prs = MagicMock()
    prs.slides = [slide]

    fake_pptx = MagicMock()
    fake_pptx.Presentation.return_value = prs

    with patch.dict(sys.modules, {"pptx": fake_pptx}):
        from gnosis.services import document_parser as dp
        result = dp.parse_pptx(Path("/vault/deck.pptx"))

    assert result.raw_format == "pptx"
    assert "Hello Slide" in result.text
    assert result.page_count == 1


# ---------------------------------------------------------------------------
# parse_xlsx (mocked openpyxl)
# ---------------------------------------------------------------------------

def test_parse_xlsx_builds_markdown_table():
    header_row = ("Name", "Age", "Score")
    data_row = ("Alice", 30, 95)

    ws = MagicMock()
    ws.iter_rows.return_value = [header_row, data_row]

    wb = MagicMock()
    wb.sheetnames = ["Sheet1"]
    wb.__getitem__ = lambda self, key: ws
    wb.close = MagicMock()

    fake_openpyxl = MagicMock()
    fake_openpyxl.load_workbook.return_value = wb

    with patch.dict(sys.modules, {"openpyxl": fake_openpyxl}):
        from gnosis.services import document_parser as dp
        result = dp.parse_xlsx(Path("/vault/data.xlsx"))

    assert result.raw_format == "xlsx"
    assert "Name" in result.text
    assert "Alice" in result.text


def test_parse_xlsx_skips_empty_sheet():
    ws = MagicMock()
    ws.iter_rows.return_value = []  # empty

    wb = MagicMock()
    wb.sheetnames = ["Empty"]
    wb.__getitem__ = lambda self, key: ws
    wb.close = MagicMock()

    fake_openpyxl = MagicMock()
    fake_openpyxl.load_workbook.return_value = wb

    with patch.dict(sys.modules, {"openpyxl": fake_openpyxl}):
        from gnosis.services import document_parser as dp
        result = dp.parse_xlsx(Path("/vault/empty.xlsx"))

    assert result.text == ""


# ---------------------------------------------------------------------------
# parse_image (mocked pytesseract / Pillow)
# ---------------------------------------------------------------------------

def test_parse_image_extracts_ocr_text():
    fake_pil = MagicMock()
    fake_pil.Image.open.return_value = MagicMock()

    fake_pytesseract = MagicMock()
    fake_pytesseract.image_to_string.return_value = "  Hello OCR  "

    with patch.dict(sys.modules, {"pytesseract": fake_pytesseract, "PIL": fake_pil}):
        from gnosis.services import document_parser as dp
        result = dp.parse_image(Path("/vault/scan.png"))

    assert result.raw_format == "image"
    assert result.text == "Hello OCR"
    assert result.page_count == 1


# ---------------------------------------------------------------------------
# parse_url — httpx imported inside parse_url body, so patch the global name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_url_extracts_title_and_text():
    html = """<html><head><title>Test Page</title></head>
    <body><main><p>Main content here.</p></main></body></html>"""

    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from gnosis.services import document_parser as dp
        result = await dp.parse_url("https://example.com")

    assert result.raw_format == "url"
    assert result.title == "Test Page"
    assert "content" in result.text.lower()


@pytest.mark.asyncio
async def test_parse_url_fallback_without_bs4():
    html = "<html><body>raw html</body></html>"
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client), \
         patch.dict(sys.modules, {"bs4": None}):
        from gnosis.services import document_parser as dp
        result = await dp.parse_url("https://example.com")

    assert result.raw_format == "url"
    assert result.source == "https://example.com"


# ---------------------------------------------------------------------------
# parse_file dispatcher — routes to correct sub-parser
# ---------------------------------------------------------------------------

def test_parse_file_routes_pdf():
    with patch("gnosis.services.document_parser.parse_pdf") as mock_pdf:
        mock_pdf.return_value = ParsedDocument(title="T", text="t", raw_format="pdf")
        result = parse_file(Path("/vault/file.pdf"))
    mock_pdf.assert_called_once()
    assert result.raw_format == "pdf"


def test_parse_file_routes_docx():
    with patch("gnosis.services.document_parser.parse_docx") as mock_docx:
        mock_docx.return_value = ParsedDocument(title="T", text="t", raw_format="docx")
        result = parse_file(Path("/vault/file.docx"))
    mock_docx.assert_called_once()


def test_parse_file_routes_pptx():
    with patch("gnosis.services.document_parser.parse_pptx") as mock_pptx:
        mock_pptx.return_value = ParsedDocument(title="T", text="t", raw_format="pptx")
        parse_file(Path("/vault/file.pptx"))
    mock_pptx.assert_called_once()


def test_parse_file_routes_xlsx():
    with patch("gnosis.services.document_parser.parse_xlsx") as mock_xlsx:
        mock_xlsx.return_value = ParsedDocument(title="T", text="t", raw_format="xlsx")
        parse_file(Path("/vault/file.xlsx"))
    mock_xlsx.assert_called_once()


def test_parse_file_routes_image():
    with patch("gnosis.services.document_parser.parse_image") as mock_img:
        mock_img.return_value = ParsedDocument(title="T", text="t", raw_format="image")
        parse_file(Path("/vault/photo.png"))
    mock_img.assert_called_once()
