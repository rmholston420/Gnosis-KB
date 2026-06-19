"""Document ingestion and parsing service.

Supports:
  - PDF: PyMuPDF (fitz)
  - DOCX: python-docx
  - PPTX: python-pptx
  - XLSX: openpyxl
  - Images (PNG, JPG, WEBP): Tesseract OCR via pytesseract
  - Plain text / Markdown: passthrough

All parsers return a plain text string suitable for AI processing.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Supported MIME types and their parser functions
SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
    "image/webp",
    "text/plain",
    "text/markdown",
}


def parse_document(file_path: Path, mime_type: str) -> str:
    """Parse a document file and return its plain text content.

    Args:
        file_path: Absolute path to the uploaded file.
        mime_type: MIME type of the file.

    Returns:
        Extracted plain text string.

    Raises:
        ValueError: If the MIME type is not supported.
    """
    if mime_type == "application/pdf":
        return _parse_pdf(file_path)
    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _parse_docx(file_path)
    elif mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        return _parse_pptx(file_path)
    elif mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        return _parse_xlsx(file_path)
    elif mime_type in {"image/png", "image/jpeg", "image/webp"}:
        return _parse_image_ocr(file_path)
    elif mime_type in {"text/plain", "text/markdown"}:
        return file_path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported MIME type: {mime_type}")


def _parse_pdf(path: Path) -> str:
    """Extract text from a PDF using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n\n".join(pages)
    except Exception as e:
        logger.error("PDF parse error: %s", e)
        return ""


def _parse_docx(path: Path) -> str:
    """Extract text from a DOCX file using python-docx."""
    try:
        import docx
        doc = docx.Document(str(path))
        return "\n".join(para.text for para in doc.paragraphs)
    except Exception as e:
        logger.error("DOCX parse error: %s", e)
        return ""


def _parse_pptx(path: Path) -> str:
    """Extract text from a PPTX file using python-pptx."""
    try:
        from pptx import Presentation
        prs = Presentation(str(path))
        lines = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    lines.append(shape.text)
        return "\n".join(lines)
    except Exception as e:
        logger.error("PPTX parse error: %s", e)
        return ""


def _parse_xlsx(path: Path) -> str:
    """Extract text from an XLSX file using openpyxl."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        lines = []
        for sheet in wb.worksheets:
            lines.append(f"Sheet: {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                row_text = "\t".join(str(c) if c is not None else "" for c in row)
                if row_text.strip():
                    lines.append(row_text)
        return "\n".join(lines)
    except Exception as e:
        logger.error("XLSX parse error: %s", e)
        return ""


def _parse_image_ocr(path: Path) -> str:
    """Extract text from an image using Tesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(str(path))
        return str(pytesseract.image_to_string(img))
    except Exception as e:
        logger.error("OCR error: %s", e)
        return ""
