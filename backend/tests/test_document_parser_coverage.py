"""Coverage tests for gnosis/services/document_parser.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import gnosis.services.document_parser as dp
from gnosis.services.document_parser import ParsedDocument, detect_format


def _make_httpx_mock(html: str):
    """Return a mock suitable for patching httpx.AsyncClient."""
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    mock_instance = MagicMock()
    mock_instance.__aenter__ = AsyncMock(return_value=mock_client)
    mock_instance.__aexit__ = AsyncMock(return_value=False)

    return MagicMock(return_value=mock_instance)


# ---------------------------------------------------------------------------
# parse_pdf
# ---------------------------------------------------------------------------

def test_parse_pdf_returns_parsed_document():
    fake_fitz = MagicMock()
    mock_doc = MagicMock()
    mock_doc.metadata = {"title": "Coverage PDF", "author": "Tester"}
    mock_doc.__iter__ = lambda self: iter([])
    mock_doc.__len__ = lambda self: 0
    fake_fitz.open.return_value = mock_doc

    with patch.dict(sys.modules, {"fitz": fake_fitz}):
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
        result = dp.parse_pdf(Path("/vault/my-report.pdf"))

    assert result.title == "My Report"


# ---------------------------------------------------------------------------
# parse_url
# ---------------------------------------------------------------------------

async def test_parse_url_returns_parsed_document():
    html = "<html><head><title>Hello</title></head><body><main><p>World</p></main></body></html>"

    with patch("httpx.AsyncClient", _make_httpx_mock(html)):
        result = await dp.parse_url("http://example.com")

    assert isinstance(result, ParsedDocument)
    assert result.raw_format == "url"
    assert result.source == "http://example.com"
    assert result.title == "Hello"


async def test_parse_url_sets_title():
    html = "<html><head><title>Stripped Title</title></head><body><p>content</p></body></html>"

    with patch("httpx.AsyncClient", _make_httpx_mock(html)):
        result = await dp.parse_url("http://example.com/page")

    assert result.title == "Stripped Title"


# ---------------------------------------------------------------------------
# parse_image
# ---------------------------------------------------------------------------

def test_parse_image_returns_parsed_document():
    fake_pil = MagicMock()
    fake_pil.Image.open.return_value = MagicMock()
    fake_tesseract = MagicMock()
    fake_tesseract.image_to_string.return_value = "OCR text here"

    with patch.dict(sys.modules, {"pytesseract": fake_tesseract, "PIL": fake_pil}):
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
