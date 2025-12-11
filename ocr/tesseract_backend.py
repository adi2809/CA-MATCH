# ocr/tesseract_backend.py

from __future__ import annotations

import os
from typing import List

from pdf2image import convert_from_path
from PIL import Image
import pytesseract

from .base import OCRBackend


class TesseractOCRBackend(OCRBackend):
    """
    OCR backend using local Tesseract + pdf2image.
    """

    def __init__(self, *, dpi: int = 300, lang: str = "eng") -> None:
        self.dpi = dpi
        self.lang = lang

    def extract_text(self, *, file_path: str) -> str:
        if not file_path:
            raise ValueError("file_path is empty")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Convert PDF pages to images
        pages: List[Image.Image] = convert_from_path(file_path, dpi=self.dpi)

        chunks: List[str] = []
        for page in pages:
            text = pytesseract.image_to_string(page, lang=self.lang)
            chunks.append(text)

        full = "\n\n===== PAGE BREAK =====\n\n".join(chunks)
        return full.replace("\r\n", "\n").strip()
