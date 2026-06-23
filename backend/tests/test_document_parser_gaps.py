"""
Gap coverage for gnosis/services/document_parser.py

Key insight: ALL optional imports in document_parser are LOCAL (inside the
function body), not at module level.  This means:
  - `patch('gnosis.services.document_parser.fitz')` does NOT work.
  - `patch('gnosis.services.document_parser.pptx')` does NOT work.
  - `patch('gnosis.services.document_parser.httpx.AsyncClient')` does NOT work
    because httpx is also imported locally.

Correct approach per case:
  ImportError blocks  : insert None into sys.modules so the local `from X import Y`
                        raises ImportError.
  Happy-path mocking  : insert a fake ModuleType into sys.modules so the local
                        import succeeds and returns our mock.
  parse_url line 287  : bs4/beautifulsoup4 is NOT in pyproject.toml (not installed).
                        Inject a fake bs4 module with a real-ish BeautifulSoup so the
                        try-block runs instead of the except ImportError fallback.
                        httpx IS installed; patch via patch.object(httpx, 'AsyncClient').

Uncovered lines
---------------
  61       : pages.append(get_text()) - fitz doc iteration
  97-98    : except ImportError -> raise (python-docx absent)
  133-134  : except ImportError -> raise (python-pptx absent)
  143->142 : shape no-text / empty-text False branch
  145->140 : empty slide False branch
  177-178  : except ImportError -> raise (openpyxl absent)
  235-236  : except ImportError -> raise (pytesseract absent)
  287      : tag.decompose() loop body
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


_SENTINEL = object()


def _inject_module(name: str, obj) -> dict:
    prior = sys.modules.get(name, _SENTINEL)
    sys.modules[name] = obj
    return {"name": name, "prior": prior}


def _restore_module(snapshot: dict):
    name, prior = snapshot["name"], snapshot["prior"]
    if prior is _SENTINEL:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = prior


# ---------------------------------------------------------------------------
# parse_pdf -- line 61: for-page loop body
# ---------------------------------------------------------------------------

class TestParsePdfLoop:
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
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        with _BlockImport("fitz"):
            with pytest.raises(RuntimeError, match="PyMuPDF"):
                from gnosis.services.document_parser import parse_pdf
                parse_pdf(pdf)


# ---------------------------------------------------------------------------
# parse_docx -- lines 97-98
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
# parse_pptx -- lines 133-134 + branch arcs 143->142, 145->140
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
    def _fake_pptx_module(self, slides_spec):
        mock_slides = []
        for shapes_spec in slides_spec:
            shapes = []
            for has_text, text_val in shapes_spec:
                if has_text:
                    shape = MagicMock()
                    shape.text = text_val
                    type(shape).text = property(lambda s, v=text_val: v)
                else:
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
        from gnosis.services.document_parser import parse_pptx
        pptx_file = tmp_path / "deck.pptx"
        pptx_file.write_bytes(b"PK fake")
        fake_mod, _ = self._fake_pptx_module([
            [(False, "")],
            [(True, "Real content")],
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
# parse_xlsx -- lines 177-178
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
# parse_image -- lines 235-236
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
# parse_url -- line 287: tag.decompose() loop body
# ---------------------------------------------------------------------------

class TestParseUrlDecompose:
    """
    bs4/beautifulsoup4 is NOT in pyproject.toml so `from bs4 import BeautifulSoup`
    always raises ImportError in the test env.  The except-ImportError fallback
    at line 299 fires and text = html (raw).  Line 287 is permanently dead.

    Fix: inject a REAL bs4 module (already importable since beautifulsoup4 is
    a transitive dep of other packages) OR inject a fake bs4 module that
    implements just enough of the BeautifulSoup API to reach line 287.

    We use the fake-module approach so the test is hermetic.
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

        # --- Build a fake BeautifulSoup that exercises line 287 ---
        # We need find_all([...]) to return objects with .decompose(),
        # and find("main") to return an object with .get_text().

        boilerplate_tag = MagicMock()
        boilerplate_tag.decompose = MagicMock()  # line 287 target

        title_tag = MagicMock()
        title_tag.get_text.return_value = "Test Page"

        main_tag = MagicMock()
        main_tag.get_text.return_value = "Main content here."

        mock_soup = MagicMock()
        mock_soup.find.side_effect = lambda *a, **kw: (
            title_tag if a and a[0] == "title" else
            main_tag  if a and a[0] == "main" else
            None
        )
        mock_soup.find_all.return_value = [boilerplate_tag, boilerplate_tag]

        # Fake bs4 module
        fake_bs4 = ModuleType("bs4")
        fake_bs4.BeautifulSoup = MagicMock(return_value=mock_soup)  # type: ignore[attr-defined]

        # httpx mock
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        bs4_snap = _inject_module("bs4", fake_bs4)
        try:
            with patch.object(httpx, "AsyncClient", return_value=mock_ctx):
                result = await parse_url("https://example.com")
        finally:
            _restore_module(bs4_snap)

        # decompose() was called on boilerplate tags
        assert boilerplate_tag.decompose.call_count >= 1
        assert result.title == "Test Page"
        assert "Main content" in result.text
