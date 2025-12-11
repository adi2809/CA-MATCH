# ocr/api_backend.py

from __future__ import annotations

import os
from typing import Dict, Any

import requests

from .base import OCRBackend


class APIOCRBackend(OCRBackend):
    """
    OCR backend that sends the document to an external HTTP API.
    The API is assumed to:
      - accept multipart/form-data with a 'file' upload
      - return JSON with a 'text' field.
    """

    def __init__(self, *, endpoint: str, api_key: str | None = None) -> None:
        self.endpoint = endpoint
        self.api_key = api_key

    def extract_text(self, *, file_path: str) -> str:
        if not file_path:
            raise ValueError("file_path is empty")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        headers: Dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/pdf")}
            resp = requests.post(self.endpoint, headers=headers, files=files, timeout=60)

        if resp.status_code != 200:
            raise RuntimeError(f"OCR API error {resp.status_code}: {resp.text}")

        data: Dict[str, Any] = resp.json()
        text = data.get("text")
        if not isinstance(text, str):
            raise RuntimeError("OCR API response missing 'text' field")

        return text.strip()
