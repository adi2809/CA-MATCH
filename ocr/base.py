# ocr/base.py

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol


class OCRBackend(ABC):
    """Abstract base class for OCR backends."""

    @abstractmethod
    def extract_text(self, *, file_path: str) -> str:
        """Extract text from a document at file_path."""
        raise NotImplementedError


class OCRBackendProtocol(Protocol):
    """Structural type you can use for typing without inheritance."""

    def extract_text(self, *, file_path: str) -> str: ...
