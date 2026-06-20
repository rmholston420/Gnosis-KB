"""Coverage tests for gnosis/services/document_parser.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_parser():
    with patch("gnosis.services.document_parser.settings") as s:
        s.FIRECRAWL_API_KEY = None
        s.JINA_API_KEY = None
        from gnosis.services.document_parser import DocumentParser
        return DocumentParser()


def test_document_parser_instantiates():
    parser = _make_parser()
    assert parser is not None


@pytest.mark.asyncio
async def test_parse_url_basic():
    import httpx
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.text = "<html><head><title>Test</title></head><body><p>Content</p></body></html>"
    mock_resp.raise_for_status = MagicMock()

    with patch("gnosis.services.document_parser.settings") as s, \
         patch("httpx.AsyncClient") as mock_client_cls:
        s.FIRECRAWL_API_KEY = None
        s.JINA_API_KEY = None
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from gnosis.services.document_parser import DocumentParser
        parser = DocumentParser()
        result = await parser.parse_url("http://example.com")
        assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_parse_text_returns_dict():
    from gnosis.services.document_parser import DocumentParser
    with patch("gnosis.services.document_parser.settings") as s:
        s.FIRECRAWL_API_KEY = None
        s.JINA_API_KEY = None
        parser = DocumentParser()
        result = await parser.parse_text("Test Title", "This is some body text.")
        assert isinstance(result, dict)
        assert result.get("title") == "Test Title"


@pytest.mark.asyncio
async def test_parse_pdf_returns_dict(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content")

    with patch("gnosis.services.document_parser.settings") as s, \
         patch("gnosis.services.document_parser.PdfReader") as mock_reader:
        s.FIRECRAWL_API_KEY = None
        s.JINA_API_KEY = None
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page content"
        mock_reader.return_value.pages = [mock_page]

        from gnosis.services.document_parser import DocumentParser
        parser = DocumentParser()
        result = await parser.parse_pdf(str(pdf_path))
        assert isinstance(result, dict)
