"""Utility helpers to perform text extraction on uploaded PDF documents."""
from __future__ import annotations

import re
from pathlib import Path

try:  # pragma: no cover - optional dependency
    from pdfminer.high_level import extract_text as pdf_extract_text
except Exception:  # pragma: no cover - fallback when pdfminer isn't available
    pdf_extract_text = None  # type: ignore

SUPPORTED_EXTENSIONS = {".pdf"}
_TEXT_BLOCK_PATTERN = re.compile(rb"BT(.*?)ET", re.DOTALL)
_STRING_PATTERN = re.compile(rb"\(([^()]*)\)")


class PDFTextExtractionError(ValueError):
    """Raised when a PDF cannot be parsed by any of the supported backends."""


def _extract_with_pdfminer(path: Path) -> str:
    if pdf_extract_text is None:
        raise PDFTextExtractionError("PDF support is unavailable; install pdfminer.six")

    text = pdf_extract_text(str(path))
    return text.strip()


def _extract_with_fallback(path: Path) -> str:
    raw = path.read_bytes()
    segments: list[str] = []
    for block in _TEXT_BLOCK_PATTERN.findall(raw):
        for match in _STRING_PATTERN.finditer(block):
            fragment = match.group(1)
            if not fragment:
                continue
            decoded = (
                fragment.decode("utf-8", errors="ignore")
                .replace(r"\(", "(")
                .replace(r"\)", ")")
                .replace(r"\\", "\\")
            )
            if decoded:
                segments.append(decoded)
    return "\n".join(segments).strip()


def extract_text_from_document(file_path: str | Path) -> str:
    """Return extracted text from the provided PDF path."""

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only PDF documents are supported for OCR")

    text = ""
    if pdf_extract_text is not None:
        try:
            text = _extract_with_pdfminer(path)
        except PDFTextExtractionError:
            text = ""

    if not text:
        text = _extract_with_fallback(path)

    if text:
        return text

    raise PDFTextExtractionError("Unable to extract text from PDF document")
