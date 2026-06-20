"""Unit tests for gnosis/services/document_parser.py.

All heavy optional dependencies (fitz, docx, pptx, openpyxl, pytesseract,
httpx) are mocked so no binary libraries are needed in the test environment.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# ParsedDocument dataclass
# ---------------------------------------------------------------------------

def test_parsed_document_defaults():
    from gnosis.services.document_parser import ParsedDocument
    doc = ParsedDocument(title="T", text="body")
    assert doc.source == ""
    assert doc.page_count == 0
    assert doc.raw_format == ""
    assert doc.metadata == {}


# ---------------------------------------------------------------------------
# detect_format
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,expected", [
    ("report.pdf",  "pdf"),
    ("notes.docx",  "docx"),
    ("slides.pptx", "pptx"),
    ("data.xlsx",   "xlsx"),
    ("photo.png",   "image"),
    ("scan.tiff",   "image"),
    ("readme.md",   None),
    ("archive.zip", None),
])
def test_detect_format(filename, expected):
    from gnosis.services.document_parser import detect_format
    assert detect_format(filename) == expected


# ---------------------------------------------------------------------------
# parse_pdf
# ---------------------------------------------------------------------------

def test_parse_pdf_extracts_text():
    from gnosis.services.document_parser import parse_pdf

    fake_page = MagicMock()
    fake_page.get_text.return_value = "Page content."

    fake_doc = MagicMock()
    fake_doc.__iter__ = MagicMock(return_value=iter([fake_page]))
    fake_doc.metadata = {"title": "My PDF", "author": "Alice"}
    fake_doc.__len__ = MagicMock(return_value=1)

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = fake_doc

    with patch.dict("sys.modules", {"fitz": fake_fitz}):
        result = parse_pdf(Path("/tmp/test.pdf"))

    assert result.title == "My PDF"
    assert result.author == "Alice"
    assert "Page content." in result.text
    assert result.raw_format == "pdf"


def test_parse_pdf_falls_back_to_stem_title():
    from gnosis.services.document_parser import parse_pdf

    fake_page = MagicMock()
    fake_page.get_text.return_value = "body"

    fake_doc = MagicMock()
    fake_doc.__iter__ = MagicMock(return_value=iter([fake_page]))
    fake_doc.metadata = {}
    fake_doc.__len__ = MagicMock(return_value=1)

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = fake_doc

    with patch.dict("sys.modules", {"fitz": fake_fitz}):
        result = parse_pdf(Path("/tmp/my-document.pdf"))

    assert result.title == "My Document"


# ---------------------------------------------------------------------------
# parse_docx
# ---------------------------------------------------------------------------

def test_parse_docx_extracts_paragraphs():
    from gnosis.services.document_parser import parse_docx

    fake_para1 = MagicMock(); fake_para1.text = "Title paragraph"
    fake_para2 = MagicMock(); fake_para2.text = "Body text."
    fake_para3 = MagicMock(); fake_para3.text = ""

    fake_doc = MagicMock()
    fake_doc.paragraphs = [fake_para1, fake_para2, fake_para3]
    fake_doc.sections = [MagicMock()]

    fake_docx_mod = MagicMock()
    fake_docx_mod.Document.return_value = fake_doc

    with patch.dict("sys.modules", {"docx": fake_docx_mod}):
        result = parse_docx(Path("/tmp/notes.docx"))

    assert result.title == "Title paragraph"
    assert "Body text." in result.text
    assert result.raw_format == "docx"


# ---------------------------------------------------------------------------
# parse_pptx
# ---------------------------------------------------------------------------

def test_parse_pptx_extracts_slide_text():
    from gnosis.services.document_parser import parse_pptx

    fake_shape = MagicMock(); fake_shape.text = "Slide headline"
    fake_slide = MagicMock(); fake_slide.shapes = [fake_shape]

    fake_prs = MagicMock()
    fake_prs.slides = [fake_slide]

    fake_pptx_mod = MagicMock()
    fake_pptx_mod.Presentation.return_value = fake_prs

    with patch.dict("sys.modules", {"pptx": fake_pptx_mod}):
        result = parse_pptx(Path("/tmp/deck.pptx"))

    assert "Slide headline" in result.text
    assert "## Slide 1" in result.text
    assert result.raw_format == "pptx"
    assert result.page_count == 1


# ---------------------------------------------------------------------------
# parse_xlsx
# ---------------------------------------------------------------------------

def test_parse_xlsx_builds_markdown_table():
    from gnosis.services.document_parser import parse_xlsx

    header_row = ("Name", "Age")
    data_row   = ("Alice", 30)

    fake_ws = MagicMock()
    fake_ws.iter_rows.return_value = iter([header_row, data_row])

    fake_wb = MagicMock()
    fake_wb.sheetnames = ["Sheet1"]
    fake_wb.__getitem__ = MagicMock(return_value=fake_ws)
    fake_wb.close = MagicMock()

    fake_openpyxl = MagicMock()
    fake_openpyxl.load_workbook.return_value = fake_wb

    with patch.dict("sys.modules", {"openpyxl": fake_openpyxl}):
        result = parse_xlsx(Path("/tmp/data.xlsx"))

    assert "Sheet1" in result.text
    assert "Name" in result.text
    assert "Alice" in result.text
    assert result.raw_format == "xlsx"


# ---------------------------------------------------------------------------
# parse_image
# ---------------------------------------------------------------------------

def test_parse_image_returns_ocr_text():
    from gnosis.services.document_parser import parse_image

    fake_img = MagicMock()
    fake_pil = MagicMock()
    fake_pil.Image.open.return_value = fake_img

    fake_tesseract = MagicMock()
    fake_tesseract.image_to_string.return_value = "  OCR text  "

    with patch.dict("sys.modules", {"pytesseract": fake_tesseract, "PIL": fake_pil}):
        result = parse_image(Path("/tmp/scan.png"))

    assert result.text == "OCR text"
    assert result.raw_format == "image"
    assert result.page_count == 1


# ---------------------------------------------------------------------------
# parse_url
# parse_url imports httpx at call-time and uses it as an async context
# manager. We patch gnosis.services.document_parser's httpx reference
# directly so the mock is in scope when the function runs.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_url_extracts_title_and_text():
    from gnosis.services.document_parser import parse_url

    html = "<html><head><title>Test Page</title></head><body><main>Main content</main></body></html>"

    fake_resp = MagicMock()
    fake_resp.text = html
    fake_resp.raise_for_status = MagicMock()

    # Build a mock that works as `async with httpx.AsyncClient(...) as client:`
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    mock_async_client_cls = MagicMock(return_value=fake_client)

    with patch("gnosis.services.document_parser.httpx.AsyncClient", mock_async_client_cls):
        result = await parse_url("https://example.com")

    assert result.title == "Test Page"
    assert "Main content" in result.text
    assert result.source == "https://example.com"
    assert result.raw_format == "url"


@pytest.mark.asyncio
async def test_parse_url_falls_back_without_bs4():
    from gnosis.services.document_parser import parse_url

    html = "<html><body>raw</body></html>"
    fake_resp = MagicMock()
    fake_resp.text = html
    fake_resp.raise_for_status = MagicMock()

    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    mock_async_client_cls = MagicMock(return_value=fake_client)

    with patch("gnosis.services.document_parser.httpx.AsyncClient", mock_async_client_cls), \
         patch.dict("sys.modules", {"bs4": None}):
        result = await parse_url("https://example.com")

    assert result.raw_format == "url"


# ---------------------------------------------------------------------------
# parse_file dispatcher
# ---------------------------------------------------------------------------

def test_parse_file_dispatches_pdf():
    from gnosis.services.document_parser import parse_file, ParsedDocument
    mock_result = ParsedDocument(title="T", text="", raw_format="pdf")
    with patch("gnosis.services.document_parser.parse_pdf", return_value=mock_result) as m:
        result = parse_file(Path("/tmp/x.pdf"))
    m.assert_called_once()
    assert result.raw_format == "pdf"


def test_parse_file_raises_on_unsupported():
    from gnosis.services.document_parser import parse_file
    with pytest.raises(ValueError, match="Unsupported"):
        parse_file(Path("/tmp/x.csv"))
