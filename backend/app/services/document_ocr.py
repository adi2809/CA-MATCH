"""Utility helpers to perform lightweight OCR/text extraction on uploaded documents."""
from __future__ import annotations

from pathlib import Path

try:  # pragma: no cover - optional dependency
    from pdfminer.high_level import extract_text as pdf_extract_text
except Exception:  # pragma: no cover - fallback when pdfminer isn't available
    pdf_extract_text = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore

TEXT_EXTENSIONS = {".txt", ".md", ".rtf"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


def extract_text_from_document(file_path: str | Path) -> str:
    """Return extracted text from the provided document path.

    The helper attempts to read plain text files directly, extract text from PDFs
    when ``pdfminer.six`` is available, and falls back to ``pytesseract`` for
    common image formats. Missing files or unsupported formats raise a
    ``ValueError`` to simplify upstream error handling.
    """

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    suffix = path.suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        return path.read_text(encoding="utf-8", errors="ignore").strip()

    if suffix in PDF_EXTENSIONS:
        if pdf_extract_text is None:
            raise ValueError("PDF support is unavailable; install pdfminer.six")
        text = pdf_extract_text(str(path))
        return text.strip()

    if suffix in IMAGE_EXTENSIONS:
        if pytesseract is None or Image is None:
            raise ValueError("Image OCR requires pillow and pytesseract")
        with Image.open(path) as image:
            text = pytesseract.image_to_string(image)
        return text.strip()

    # Fallback: attempt to decode as UTF-8 regardless of extension.
    raw = path.read_bytes()
    decoded = raw.decode("utf-8", errors="ignore").strip()
    if not decoded:
        raise ValueError(f"Unsupported document format: {suffix or 'unknown'}")
    return decoded
