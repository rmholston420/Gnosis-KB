"""
Gap coverage for gnosis/services/document_parser.py

Key insight: ALL optional imports in document_parser are LOCAL (inside the
function body), not at module level.  This means:
  - `patch('gnosis.services.document_parser.fitz')` does NOT work.
  - `patch('gnosis.services.document_parser.pptx')` does NOT work.
  - `patch('gnosis.services.document_parser.httpx.AsyncClient')` does NOT work
    because httpx is also imported locally.

Correct approach per case:
  ImportError blocks  : insert None (or a sentinel) into sys.modules so the
                        local `from X import Y` raises ImportError.
  Happy-path mocking  : insert a fake module object into sys.modules so the
                        local import succeeds and returns the mock.
  parse_url           : httpx IS in sys.modules already (installed); patch
                        'httpx.AsyncClient' on the real httpx module.

Uncovered lines
---------------
  61       : pages.append(get_text()) - fitz doc iteration
  97-98    : except ImportError → raise (python-docx absent)
  133-134  : except ImportError → raise (python-pptx absent)
  143->142 : shape no-text / empty-text False branch
  145->140 : empty slide False branch
  177-178  : except ImportError → raise (openpyxl absent)
  235-236  : except ImportError → raise (pytesseract absent)
  287      : tag.decompose() loop body (boilerplate HTML tags present)
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _BlockImport:
    """Context manager: makes `import <name>` raise ImportError."""
    def __init__(self, name: str):
        self._name = name
        self._saved = None
        self._was_present = False

    def __enter__(self):
        self._was_present = self._name in sys.modules
        self._saved = sys.modules.get(self._name)
        sys.modules[self._name] = None  # type: ignore[assignment]
        return self

    def __exit__(self, *_):
        if self._was_present and self._saved is not None:
            sys.modules[self._name] = self._saved
        else:
            sys.modules.pop(self._name, None)


def _inject_module(name: str, obj) -> dict:
    """Insert obj into sys.modules[name]; return {name: prior_value, was_present}."""
    prior = sys.modules.get(name, _SENTINEL)
    sys.modules[name] = obj
    return {"name": name, "prior": prior}


def _restore_module(snapshot: dict):
    name, prior = snapshot["name"], snapshot["prior"]
    if prior is _SENTINEL:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = prior


_SENTINEL = object()


# ---------------------------------------------------------------------------
# parse_pdf — line 61: for-page loop body
# ---------------------------------------------------------------------------

class TestParsePdfLoop:
    """
    parse_pdf does: `import fitz` (local).  To mock it we inject a fake fitz
    module into sys.modules so the local import succeeds and returns our mock.
    """

    def test_parse_pdf_iterates_pages(self, tmp_path):
        from gnosis.services.document_parser import parse_pdf

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page one text"

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.metadata = {"title": ""}

        fake_fitz = ModuleType("fitz")
        fake_fitz.open = MagicMock(return_value=mock_doc)  # type: ignore[attr-defined]

        snap = _inject_module("fitz", fake_fitz)
        try:
            result = parse_pdf(pdf)
        finally:
            _restore_module(snap)

        assert "Page one text" in result.text
        mock_page.get_text.assert_called_once()

    def test_parse_pdf_no_fitz_raises(self, tmp_path):
        """lines 53-56: local `import fitz` raises ImportError."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        with _BlockImport("fitz"):
            with pytest.raises(RuntimeError, match="PyMuPDF"):
                from gnosis.services.document_parser import parse_pdf
                parse_pdf(pdf)


# ---------------------------------------------------------------------------
# parse_docx — lines 97-98: ImportError
# ---------------------------------------------------------------------------

class TestParseDocxImportError:
    def test_parse_docx_no_docx_raises(self, tmp_path):
        docx = tmp_path / "test.docx"
        docx.write_bytes(b"PK fake docx")
        with _BlockImport("docx"):
            with pytest.raises(RuntimeError, match="python-docx"):
                from gnosis.services.document_parser import parse_docx
                parse_docx(docx)


# ---------------------------------------------------------------------------
# parse_pptx — lines 133-134: ImportError + branch arcs 143->142, 145->140
# ---------------------------------------------------------------------------

class TestParsePptxImportError:
    def test_parse_pptx_no_pptx_raises(self, tmp_path):
        pptx_file = tmp_path / "test.pptx"
        pptx_file.write_bytes(b"PK fake pptx")
        with _BlockImport("pptx"):
            with pytest.raises(RuntimeError, match="python-pptx"):
                from gnosis.services.document_parser import parse_pptx
                parse_pptx(pptx_file)


class TestParsePptxBranchArcs:
    """
    parse_pptx does `from pptx import Presentation` locally.
    Inject a fake pptx module so Presentation returns our mock.

    143->142: shape has no 'text' attr OR text.strip() == ''
    145->140: slide_texts is empty (no text shapes on slide)
    """

    def _fake_pptx_module(self, slides_spec):
        """
        slides_spec: list of lists of (has_text_attr: bool, text_value: str)
        Returns a fake pptx module whose Presentation() returns a mock with
        .slides iterating the specified mock slides.
        """
        mock_slides = []
        for shapes_spec in slides_spec:
            shapes = []
            for has_text, text_val in shapes_spec:
                if has_text:
                    shape = MagicMock()
                    shape.text = text_val
                    # Ensure hasattr(shape, 'text') -> True
                    type(shape).text = property(lambda s, v=text_val: v)
                else:
                    # spec=[] means hasattr(shape, 'text') -> False
                    shape = MagicMock(spec=[])
                shapes.append(shape)
            slide = MagicMock()
            slide.shapes = shapes
            mock_slides.append(slide)

        mock_prs = MagicMock()
        mock_prs.slides = mock_slides

        fake_pptx = ModuleType("pptx")
        fake_pptx.Presentation = MagicMock(return_value=mock_prs)  # type: ignore[attr-defined]
        return fake_pptx, mock_prs

    def test_parse_pptx_shape_without_text_attr(self, tmp_path):
        """143->142: hasattr(shape,'text') is False."""
        from gnosis.services.document_parser import parse_pptx
        pptx_file = tmp_path / "deck.pptx"
        pptx_file.write_bytes(b"PK fake")

        fake_mod, _ = self._fake_pptx_module([[(False, "")]])
        snap = _inject_module("pptx", fake_mod)
        try:
            result = parse_pptx(pptx_file)
        finally:
            _restore_module(snap)

        assert result.text == ""

    def test_parse_pptx_shape_with_empty_text(self, tmp_path):
        """143->142: shape.text.strip() == '' (whitespace only)."""
        from gnosis.services.document_parser import parse_pptx
        pptx_file = tmp_path / "deck.pptx"
        pptx_file.write_bytes(b"PK fake")

        fake_mod, _ = self._fake_pptx_module([[(True, "   ")]])
        snap = _inject_module("pptx", fake_mod)
        try:
            result = parse_pptx(pptx_file)
        finally:
            _restore_module(snap)

        assert result.text == ""

    def test_parse_pptx_slide_with_no_text_shapes(self, tmp_path):
        """145->140: slide_texts empty → skip slides.append → loop continues."""
        from gnosis.services.document_parser import parse_pptx
        pptx_file = tmp_path / "deck.pptx"
        pptx_file.write_bytes(b"PK fake")

        fake_mod, _ = self._fake_pptx_module([
            [(False, "")],            # slide 1: no text shapes -> skip
            [(True, "Real content")], # slide 2: has text -> include
        ])
        snap = _inject_module("pptx", fake_mod)
        try:
            result = parse_pptx(pptx_file)
        finally:
            _restore_module(snap)

        assert "Real content" in result.text
        assert "Slide 1" not in result.text
        assert "Slide 2" in result.text


# ---------------------------------------------------------------------------
# parse_xlsx — lines 177-178: ImportError
# ---------------------------------------------------------------------------

class TestParseXlsxImportError:
    def test_parse_xlsx_no_openpyxl_raises(self, tmp_path):
        xlsx = tmp_path / "test.xlsx"
        xlsx.write_bytes(b"PK fake xlsx")
        with _BlockImport("openpyxl"):
            with pytest.raises(RuntimeError, match="openpyxl"):
                from gnosis.services.document_parser import parse_xlsx
                parse_xlsx(xlsx)


# ---------------------------------------------------------------------------
# parse_image — lines 235-236: ImportError
# ---------------------------------------------------------------------------

class TestParseImageImportError:
    def test_parse_image_no_pytesseract_raises(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG fake")
        with _BlockImport("pytesseract"):
            with pytest.raises(RuntimeError, match="pytesseract"):
                from gnosis.services.document_parser import parse_image
                parse_image(img)


# ---------------------------------------------------------------------------
# parse_url — line 287: tag.decompose() loop body
# ---------------------------------------------------------------------------

class TestParseUrlDecompose:
    """
    parse_url does `import httpx` locally AND `from bs4 import BeautifulSoup`
    locally.  httpx IS in sys.modules; patch httpx.AsyncClient directly.
    bs4 IS installed; no need to fake it.
    Line 287 fires when the HTML contains script/style/nav/footer/header/aside.
    """

    @pytest.mark.asyncio
    async def test_parse_url_decomposes_boilerplate_tags(self):
        import httpx
        from gnosis.services.document_parser import parse_url

        html = (
            "<html><head><title>Test Page</title>"
            "<style>body{margin:0}</style></head>"
            "<body>"
            "<nav>Navigation</nav>"
            "<main><p>Main content here.</p></main>"
            "<footer>Footer text</footer>"
            "</body></html>"
        )

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        # httpx is installed and imported locally inside parse_url.
        # Patch AsyncClient on the real httpx module.
        with patch.object(httpx, "AsyncClient", return_value=mock_ctx):
            result = await parse_url("https://example.com")

        assert "Main content" in result.text
        assert result.title == "Test Page"
        # Boilerplate should have been removed by decompose()
        assert "Navigation" not in result.text
        assert "Footer text" not in result.text
