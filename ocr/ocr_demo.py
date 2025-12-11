# ocr/factory.py

from __future__ import annotations

import os

from .base import OCRBackend, OCRBackendProtocol
from .tesseract_backend import TesseractOCRBackend
from .api_backend import APIOCRBackend


def create_ocr_backend() -> OCRBackendProtocol:
    """
    Factory that chooses which OCR backend to use based on env vars.

    OCR_BACKEND = "tesseract" | "api"
    If OCR_BACKEND is not set, defaults to "tesseract".
    """
    backend = os.getenv("OCR_BACKEND", "tesseract").lower()

    if backend == "tesseract":
        lang = os.getenv("OCR_LANG", "eng")
        dpi = int(os.getenv("OCR_DPI", "300"))
        return TesseractOCRBackend(lang=lang, dpi=dpi)

    if backend == "api":
        endpoint = os.environ["OCR_API_ENDPOINT"]  # required
        api_key = os.getenv("OCR_API_KEY")
        return APIOCRBackend(endpoint=endpoint, api_key=api_key)

    raise ValueError(f"Unknown OCR_BACKEND: {backend}")
