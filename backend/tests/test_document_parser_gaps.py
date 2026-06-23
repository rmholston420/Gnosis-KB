"""
Gap coverage for gnosis/services/document_parser.py

Uncovered lines
---------------
61       : pages.append(get_text()) inside for-page loop — fitz IS installed;
           the loop body line is marked because fitz.open() is mocked and
           the mock doesn't iterate. Fix: make the mock iterable.
97-98    : except ImportError -> raise RuntimeError (python-docx absent)
133-134  : except ImportError -> raise RuntimeError (python-pptx absent)
143->142 : `if hasattr(shape,'text') and shape.text.strip():` False branch
           — shape has no text or text is empty
145->140 : `if slide_texts:` False branch — no text shapes on a slide
177-178  : except ImportError -> raise RuntimeError (openpyxl absent)
235-236  : except ImportError -> raise RuntimeError (pytesseract/Pillow absent)
287      : tag.decompose() inside for-tag loop (bs4 remove-boilerplate loop)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _block_import(name: str):
    """Context manager that makes `import <name>` raise ImportError."""
    import builtins
    real_import = builtins.__import__

    def _fake_import(mod_name, *args, **kwargs):
        if mod_name == name or mod_name.startswith(name + "."):
            raise ImportError(f"Mocked absence of {name}")
        return real_import(mod_name, *args, **kwargs)

    return patch("builtins.__import__", side_effect=_fake_import)


# ---------------------------------------------------------------------------
# parse_pdf — line 61: for-page loop body
# ---------------------------------------------------------------------------

class TestParsePdfLoop:
    """
    Line 61: pages.append(page.get_text()).
    fitz IS installed in the test env so the ImportError block won't fire;
    we need to ensure the mock doc is iterable so the loop body executes.
    """

    def test_parse_pdf_iterates_pages(self, tmp_path):
        from gnosis.services.document_parser import parse_pdf

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page text"

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.metadata = {"title": ""}

        with patch("gnosis.services.document_parser.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            result = parse_pdf(pdf)

        assert "Page text" in result.text
        mock_page.get_text.assert_called_once()

    def test_parse_pdf_no_fitz_raises(self, tmp_path):
        """lines 53-56: ImportError path — fitz absent."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        import gnosis.services.document_parser as dp
        saved = getattr(dp, "fitz", None)
        try:
            dp.fitz = None  # type: ignore[attr-defined]
            # Patch fitz to not exist by blocking the local import
            with _block_import("fitz"):
                # Need to reload so the try/except at function entry fires
                with pytest.raises(RuntimeError, match="PyMuPDF"):
                    # Force re-execution of the local import block
                    import importlib
                    import gnosis.services.document_parser as dp2
                    # Remove cached fitz from the module so local import fires
                    dp2_fitz = sys.modules.pop("fitz", None)
                    try:
                        dp2.parse_pdf(pdf)
                    finally:
                        if dp2_fitz is not None:
                            sys.modules["fitz"] = dp2_fitz
        finally:
            if saved is not None:
                dp.fitz = saved


# ---------------------------------------------------------------------------
# parse_docx — lines 97-98: ImportError
# ---------------------------------------------------------------------------

class TestParseDocxImportError:
    def test_parse_docx_no_docx_raises(self, tmp_path):
        docx = tmp_path / "test.docx"
        docx.write_bytes(b"PK fake docx")
        with _block_import("docx"):
            with pytest.raises(RuntimeError, match="python-docx"):
                from gnosis.services.document_parser import parse_docx
                parse_docx(docx)


# ---------------------------------------------------------------------------
# parse_pptx — lines 133-134: ImportError + branch arcs 143->142, 145->140
# ---------------------------------------------------------------------------

class TestParsePptxImportError:
    def test_parse_pptx_no_pptx_raises(self, tmp_path):
        pptx = tmp_path / "test.pptx"
        pptx.write_bytes(b"PK fake pptx")
        with _block_import("pptx"):
            with pytest.raises(RuntimeError, match="python-pptx"):
                from gnosis.services.document_parser import parse_pptx
                parse_pptx(pptx)


class TestParsePptxBranchArcs:
    """
    143->142: shape has no 'text' attr OR text.strip() == '' -> skip append
    145->140: slide_texts is empty (no text shapes) -> skip slides.append
    """

    def _make_pptx_mock(self, slides_spec):
        """
        slides_spec: list of lists of (has_text_attr, text_value)
        Returns a mock Presentation whose .slides iterates mock slides.
        """
        mock_slides = []
        for shapes_spec in slides_spec:
            shapes = []
            for has_text, text_val in shapes_spec:
                shape = MagicMock(spec=["text"] if has_text else [])
                if has_text:
                    shape.text = text_val
                shapes.append(shape)
            slide = MagicMock()
            slide.shapes = shapes
            mock_slides.append(slide)

        mock_prs = MagicMock()
        mock_prs.slides = mock_slides
        return mock_prs

    def test_parse_pptx_shape_without_text_attr(self, tmp_path):
        """143->142: shape has no 'text' attr — hasattr returns False."""
        from gnosis.services.document_parser import parse_pptx
        pptx = tmp_path / "deck.pptx"
        pptx.write_bytes(b"PK fake")

        # One slide, one shape with no text attr
        mock_prs = self._make_pptx_mock([[(False, "")]])

        with patch("gnosis.services.document_parser.pptx") as mock_pptx_mod:
            mock_pptx_mod.Presentation.return_value = mock_prs
            result = parse_pptx(pptx)

        # No text extracted, slide_texts empty -> slide not appended
        assert result.text == ""

    def test_parse_pptx_shape_with_empty_text(self, tmp_path):
        """143->142: shape.text.strip() == '' — condition is False."""
        from gnosis.services.document_parser import parse_pptx
        pptx = tmp_path / "deck.pptx"
        pptx.write_bytes(b"PK fake")

        mock_prs = self._make_pptx_mock([[(True, "   ")]])  # whitespace only

        with patch("gnosis.services.document_parser.pptx") as mock_pptx_mod:
            mock_pptx_mod.Presentation.return_value = mock_prs
            result = parse_pptx(pptx)

        assert result.text == ""

    def test_parse_pptx_slide_with_no_text_shapes(self, tmp_path):
        """145->140: slide_texts is empty -> skip slides.append -> continue loop."""
        from gnosis.services.document_parser import parse_pptx
        pptx = tmp_path / "deck.pptx"
        pptx.write_bytes(b"PK fake")

        # Two slides: first has no text shapes, second has real text
        mock_prs = self._make_pptx_mock([
            [(False, "")],           # slide 1: no text shapes
            [(True, "Real content")], # slide 2: has text
        ])

        with patch("gnosis.services.document_parser.pptx") as mock_pptx_mod:
            mock_pptx_mod.Presentation.return_value = mock_prs
            result = parse_pptx(pptx)

        assert "Real content" in result.text
        assert "Slide 1" not in result.text  # empty slide skipped
        assert "Slide 2" in result.text


# ---------------------------------------------------------------------------
# parse_xlsx — lines 177-178: ImportError
# ---------------------------------------------------------------------------

class TestParseXlsxImportError:
    def test_parse_xlsx_no_openpyxl_raises(self, tmp_path):
        xlsx = tmp_path / "test.xlsx"
        xlsx.write_bytes(b"PK fake xlsx")
        with _block_import("openpyxl"):
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
        with _block_import("pytesseract"):
            with pytest.raises(RuntimeError, match="pytesseract"):
                from gnosis.services.document_parser import parse_image
                parse_image(img)


# ---------------------------------------------------------------------------
# parse_url — line 287: tag.decompose() loop body
# ---------------------------------------------------------------------------

class TestParseUrlDecompose:
    """
    Line 287: `tag.decompose()` inside the bs4 boilerplate-removal loop.
    The existing test probably passes HTML with no script/style/nav tags.
    We need HTML that contains at least one boilerplate element.
    """

    @pytest.mark.asyncio
    async def test_parse_url_decomposes_boilerplate_tags(self):
        from gnosis.services.document_parser import parse_url

        html = (
            "<html><head><title>Test Page</title>"
            "<style>body{margin:0}</style></head>"
            "<body>"
            "<nav>Navigation</nav>"
            "<main><p>Main content here.</p></main>"
            "<footer>Footer</footer>"
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

        with patch("gnosis.services.document_parser.httpx.AsyncClient",
                   return_value=mock_ctx):
            result = await parse_url("https://example.com")

        # Boilerplate removed, main content preserved
        assert "Main content" in result.text
        assert result.title == "Test Page"
