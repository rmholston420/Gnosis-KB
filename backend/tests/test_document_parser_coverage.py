"""Coverage tests for gnosis/services/document_parser.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gnosis.services.document_parser import ParsedDocument, detect_format


# ---------------------------------------------------------------------------
# parse_pdf — covered via sys.modules mock (same pattern as test_document_parser)
# ---------------------------------------------------------------------------

def test_parse_pdf_returns_parsed_document():
    fake_fitz = MagicMock()
    mock_doc = MagicMock()
    mock_doc.metadata = {"title": "Coverage PDF", "author": "Tester"}
    mock_doc.__iter__ = lambda self: iter([])
    mock_doc.__len__ = lambda self: 0
    fake_fitz.open.return_value = mock_doc

    with patch.dict(sys.modules, {"fitz": fake_fitz}):
        from gnosis.services import document_parser as dp
        result = dp.parse_pdf(Path("/vault/coverage.pdf"))

    assert isinstance(result, ParsedDocument)
    assert result.raw_format == "pdf"
    assert result.title == "Coverage PDF"


def test_parse_pdf_no_meta_derives_title_from_stem():
    fake_fitz = MagicMock()
    mock_doc = MagicMock()
    mock_doc.metadata = {}
    mock_doc.__iter__ = lambda self: iter([])
    mock_doc.__len__ = lambda self: 0
    fake_fitz.open.return_value = mock_doc

    with patch.dict(sys.modules, {"fitz": fake_fitz}):
        from gnosis.services import document_parser as dp
        result = dp.parse_pdf(Path("/vault/my-report.pdf"))

    assert result.title == "My Report"


# ---------------------------------------------------------------------------
# parse_url — async, module-level function
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_url_returns_parsed_document():
    html = "<html><head><title>Hello</title></head><body><main><p>World</p></main></body></html>"
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("gnosis.services.document_parser.httpx") as mock_httpx:
        mock_httpx.AsyncClient.return_value = mock_client
        from gnosis.services import document_parser as dp
        result = await dp.parse_url("http://example.com")

    assert isinstance(result, ParsedDocument)
    assert result.raw_format == "url"
    assert result.source == "http://example.com"


@pytest.mark.asyncio
async def test_parse_url_sets_title():
    html = "<html><head><title>  Stripped Title  </title></head><body><p>content</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("gnosis.services.document_parser.httpx") as mock_httpx:
        mock_httpx.AsyncClient.return_value = mock_client
        from gnosis.services import document_parser as dp
        result = await dp.parse_url("http://example.com/page")

    assert result.title == "Stripped Title"


# ---------------------------------------------------------------------------
# parse_image — mocked pytesseract / PIL
# ---------------------------------------------------------------------------

def test_parse_image_returns_parsed_document():
    fake_pil = MagicMock()
    fake_pil.Image.open.return_value = MagicMock()
    fake_tesseract = MagicMock()
    fake_tesseract.image_to_string.return_value = "OCR text here"

    with patch.dict(sys.modules, {"pytesseract": fake_tesseract, "PIL": fake_pil}):
        from gnosis.services import document_parser as dp
        result = dp.parse_image(Path("/vault/scan.png"))

    assert isinstance(result, ParsedDocument)
    assert result.raw_format == "image"
    assert result.text == "OCR text here"


# ---------------------------------------------------------------------------
# detect_format edge cases
# ---------------------------------------------------------------------------

def test_detect_format_unknown_returns_none():
    assert detect_format("file.xyz") is None


def test_detect_format_case_insensitive():
    assert detect_format("REPORT.PDF") == "pdf"
    assert detect_format("data.XLSX") == "xlsx"
