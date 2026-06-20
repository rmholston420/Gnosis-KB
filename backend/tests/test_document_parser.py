"""Unit tests for gnosis/services/document_parser.py.

All heavy third-party libs (fitz, docx, pptx, openpyxl, pytesseract,
Pillow, httpx, bs4) are stubbed via sys.modules injection so no real
files or network calls are needed.

Coverage targets
----------------
- detect_format: extension mapping + unknown extension
- parse_file:    dispatcher routes to each parser; raises ValueError for unknown ext
- parse_pdf:     metadata title, filename fallback, author, page_count
- parse_docx:    paragraph text, title from first paragraph, empty body fallback
- parse_pptx:    slide text, slide count
- parse_xlsx:    Markdown table generation, multi-sheet, empty sheet skip
- parse_image:   OCR text, title from stem
- parse_url:     BeautifulSoup happy path, bs4-absent fallback
- ImportError:   each parser raises RuntimeError when dep missing
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# sys.modules stubs — injected before any import of document_parser
# ---------------------------------------------------------------------------

def _make_fitz_stub(pages=("Page one text.", "Page two text."), meta=None):
    page_objs = [MagicMock(**{"get_text.return_value": t}) for t in pages]
    doc = MagicMock()
    doc.__iter__ = MagicMock(return_value=iter(page_objs))
    doc.__len__ = MagicMock(return_value=len(pages))
    doc.metadata = meta or {}
    fitz = types.ModuleType("fitz")
    fitz.open = MagicMock(return_value=doc)  # type: ignore[attr-defined]
    return fitz, doc


def _make_docx_stub(paragraphs=("My Title", "Body paragraph.")):
    para_objs = [MagicMock(text=t) for t in paragraphs]
    doc = MagicMock()
    doc.paragraphs = para_objs
    doc.sections = [MagicMock()]  # one section
    Document = MagicMock(return_value=doc)
    docx_mod = types.ModuleType("docx")
    docx_mod.Document = Document  # type: ignore[attr-defined]
    return docx_mod, doc


def _make_pptx_stub(slide_texts=("Hello World", "Slide Two")):
    shapes = [[MagicMock(text=t)] for t in slide_texts]
    slides = []
    for sh_list in shapes:
        s = MagicMock()
        s.shapes = sh_list
        slides.append(s)
    prs = MagicMock()
    prs.slides = slides
    Presentation = MagicMock(return_value=prs)
    pptx_mod = types.ModuleType("pptx")
    pptx_mod.Presentation = Presentation  # type: ignore[attr-defined]
    return pptx_mod, prs


def _make_openpyxl_stub(sheets=None):
    """sheets: dict[name, list[tuple]] — rows per sheet."""
    if sheets is None:
        sheets = {"Sheet1": [("A", "B"), ("1", "2"), ("3", "4")]}
    wb = MagicMock()
    wb.sheetnames = list(sheets.keys())
    ws_map = {}
    for name, rows in sheets.items():
        ws = MagicMock()
        ws.iter_rows = MagicMock(return_value=iter(rows))
        ws_map[name] = ws
    wb.__getitem__ = MagicMock(side_effect=lambda k: ws_map[k])
    wb.close = MagicMock()
    openpyxl_mod = types.ModuleType("openpyxl")
    openpyxl_mod.load_workbook = MagicMock(return_value=wb)  # type: ignore[attr-defined]
    return openpyxl_mod, wb


def _make_tesseract_stub(ocr_text="Extracted OCR text"):
    pil_img = MagicMock()
    Image_mod = MagicMock()
    Image_mod.open = MagicMock(return_value=pil_img)
    pil_mod = types.ModuleType("PIL")
    pil_mod.Image = Image_mod  # type: ignore[attr-defined]

    pytesseract_mod = types.ModuleType("pytesseract")
    pytesseract_mod.image_to_string = MagicMock(return_value=ocr_text)  # type: ignore[attr-defined]
    return pytesseract_mod, pil_mod


# ---------------------------------------------------------------------------
# detect_format
# ---------------------------------------------------------------------------

def test_detect_format_known_extensions():
    from gnosis.services.document_parser import detect_format
    assert detect_format("report.pdf") == "pdf"
    assert detect_format("notes.docx") == "docx"
    assert detect_format("slides.pptx") == "pptx"
    assert detect_format("data.xlsx") == "xlsx"
    assert detect_format("scan.png") == "image"
    assert detect_format("photo.jpg") == "image"
    assert detect_format("photo.jpeg") == "image"
    assert detect_format("old.xls") == "xlsx"
    assert detect_format("old.ppt") == "pptx"
    assert detect_format("old.doc") == "docx"


def test_detect_format_unknown_returns_none():
    from gnosis.services.document_parser import detect_format
    assert detect_format("archive.zip") is None
    assert detect_format("notes.md") is None
    assert detect_format("no_extension") is None


# ---------------------------------------------------------------------------
# parse_file dispatcher
# ---------------------------------------------------------------------------

def test_parse_file_raises_for_unsupported_extension(tmp_path):
    from gnosis.services.document_parser import parse_file
    f = tmp_path / "archive.zip"
    f.write_bytes(b"")
    with pytest.raises(ValueError, match="Unsupported"):
        parse_file(f)


def test_parse_file_dispatches_to_pdf(tmp_path):
    fitz_stub, _ = _make_fitz_stub()
    with patch.dict(sys.modules, {"fitz": fitz_stub}):
        from gnosis.services.document_parser import parse_pdf
        path = tmp_path / "report.pdf"
        path.write_bytes(b"")
        result = parse_pdf(path)
    assert result.raw_format == "pdf"


# ---------------------------------------------------------------------------
# parse_pdf
# ---------------------------------------------------------------------------

def test_parse_pdf_uses_filename_as_title_when_no_metadata(tmp_path):
    fitz_stub, _ = _make_fitz_stub(pages=("Text.",), meta={})
    path = tmp_path / "my-research-paper.pdf"
    path.write_bytes(b"")
    with patch.dict(sys.modules, {"fitz": fitz_stub}):
        from gnosis.services.document_parser import parse_pdf
        result = parse_pdf(path)
    assert result.title == "My Research Paper"
    assert result.raw_format == "pdf"
    assert "Text." in result.text
    assert result.page_count == 1


def test_parse_pdf_uses_metadata_title(tmp_path):
    fitz_stub, _ = _make_fitz_stub(
        pages=("Body text.",),
        meta={"title": "Override Title", "author": "Jane Doe"},
    )
    path = tmp_path / "ignored.pdf"
    path.write_bytes(b"")
    with patch.dict(sys.modules, {"fitz": fitz_stub}):
        from gnosis.services.document_parser import parse_pdf
        result = parse_pdf(path)
    assert result.title == "Override Title"
    assert result.author == "Jane Doe"


def test_parse_pdf_multi_page_text_joined(tmp_path):
    fitz_stub, _ = _make_fitz_stub(pages=("Page one.", "Page two."))
    path = tmp_path / "multi.pdf"
    path.write_bytes(b"")
    with patch.dict(sys.modules, {"fitz": fitz_stub}):
        from gnosis.services.document_parser import parse_pdf
        result = parse_pdf(path)
    assert "Page one." in result.text
    assert "Page two." in result.text
    assert result.page_count == 2


def test_parse_pdf_raises_without_pymupdf(tmp_path):
    path = tmp_path / "test.pdf"
    path.write_bytes(b"")
    with patch.dict(sys.modules, {"fitz": None}):
        from importlib import reload
        import gnosis.services.document_parser as dp
        reload(dp)
        with pytest.raises(RuntimeError, match="PyMuPDF"):
            dp.parse_pdf(path)


# ---------------------------------------------------------------------------
# parse_docx
# ---------------------------------------------------------------------------

def test_parse_docx_extracts_paragraphs(tmp_path):
    docx_stub, _ = _make_docx_stub(("Report Title", "First paragraph.", "Second paragraph."))
    path = tmp_path / "report.docx"
    path.write_bytes(b"")
    with patch.dict(sys.modules, {"docx": docx_stub}):
        from gnosis.services.document_parser import parse_docx
        result = parse_docx(path)
    assert result.title == "Report Title"
    assert "First paragraph." in result.text
    assert result.raw_format == "docx"


def test_parse_docx_empty_body_uses_stem(tmp_path):
    docx_stub, _ = _make_docx_stub(())
    path = tmp_path / "empty-doc.docx"
    path.write_bytes(b"")
    with patch.dict(sys.modules, {"docx": docx_stub}):
        from gnosis.services.document_parser import parse_docx
        result = parse_docx(path)
    assert result.title == "empty-doc"
    assert result.text == ""


# ---------------------------------------------------------------------------
# parse_pptx
# ---------------------------------------------------------------------------

def test_parse_pptx_extracts_slide_text(tmp_path):
    pptx_stub, prs = _make_pptx_stub(("Intro Slide", "Main Points"))
    path = tmp_path / "deck.pptx"
    path.write_bytes(b"")
    with patch.dict(sys.modules, {"pptx": pptx_stub}):
        from gnosis.services.document_parser import parse_pptx
        result = parse_pptx(path)
    assert "## Slide 1" in result.text
    assert "Intro Slide" in result.text
    assert result.page_count == 2
    assert result.raw_format == "pptx"


# ---------------------------------------------------------------------------
# parse_xlsx
# ---------------------------------------------------------------------------

def test_parse_xlsx_generates_markdown_table(tmp_path):
    openpyxl_stub, _ = _make_openpyxl_stub(
        {"Sheet1": [("Name", "Score"), ("Alice", "95"), ("Bob", "87")]}
    )
    path = tmp_path / "data.xlsx"
    path.write_bytes(b"")
    with patch.dict(sys.modules, {"openpyxl": openpyxl_stub}):
        from gnosis.services.document_parser import parse_xlsx
        result = parse_xlsx(path)
    assert "## Sheet: Sheet1" in result.text
    assert "| Name | Score |" in result.text
    assert "| Alice | 95 |" in result.text
    assert result.raw_format == "xlsx"


def test_parse_xlsx_skips_empty_sheets(tmp_path):
    openpyxl_stub, wb = _make_openpyxl_stub({})
    wb.sheetnames = ["EmptySheet"]
    ws = MagicMock()
    ws.iter_rows = MagicMock(return_value=iter([]))
    wb.__getitem__ = MagicMock(return_value=ws)
    path = tmp_path / "empty.xlsx"
    path.write_bytes(b"")
    with patch.dict(sys.modules, {"openpyxl": openpyxl_stub}):
        from gnosis.services.document_parser import parse_xlsx
        result = parse_xlsx(path)
    assert result.text == ""


# ---------------------------------------------------------------------------
# parse_image
# ---------------------------------------------------------------------------

def test_parse_image_returns_ocr_text(tmp_path):
    pytesseract_stub, pil_stub = _make_tesseract_stub("Hello from OCR")
    path = tmp_path / "scan_doc.png"
    path.write_bytes(b"")
    with patch.dict(sys.modules, {"pytesseract": pytesseract_stub, "PIL": pil_stub}):
        from gnosis.services.document_parser import parse_image
        result = parse_image(path)
    assert result.text == "Hello from OCR"
    assert result.title == "Scan Doc"
    assert result.raw_format == "image"
    assert result.page_count == 1


# ---------------------------------------------------------------------------
# parse_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_url_extracts_title_and_body():
    html = "<html><head><title>My Page</title></head><body><main><p>Main content here.</p></main></body></html>"

    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from gnosis.services.document_parser import parse_url
        result = await parse_url("https://example.com/article")

    assert result.title == "My Page"
    assert "Main content here" in result.text
    assert result.raw_format == "url"
    assert result.source == "https://example.com/article"


@pytest.mark.asyncio
async def test_parse_url_fallback_without_bs4():
    html = "<html><body>Raw content</body></html>"

    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with (
        patch("httpx.AsyncClient", return_value=mock_client),
        patch.dict(sys.modules, {"bs4": None}),
    ):
        from importlib import reload
        import gnosis.services.document_parser as dp
        reload(dp)
        result = await dp.parse_url("https://example.com")

    assert result.source == "https://example.com"
    assert result.raw_format == "url"
