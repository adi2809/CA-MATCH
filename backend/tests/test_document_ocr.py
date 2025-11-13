from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.document_ocr import extract_text_from_document


SAMPLE_PDF = b"""%PDF-1.1\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n4 0 obj\n<< /Length 73 >>\nstream\nBT\n/F1 24 Tf\n72 720 Td\n(CA Match Resume Skills) Tj\nET\nendstream\nendobj\n5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\nxref\n0 6\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000115 00000 n\n0000000278 00000 n\n0000000371 00000 n\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n430\n%%EOF\n"""


def test_extract_text_from_pdf(tmp_path):
    document = tmp_path / "resume.pdf"
    document.write_bytes(SAMPLE_PDF)

    text = extract_text_from_document(document)

    assert "CA Match Resume Skills" in text


def test_extract_text_missing_file(tmp_path):
    missing = tmp_path / "missing.txt"

    try:
        extract_text_from_document(missing)
    except FileNotFoundError as exc:
        assert "Document not found" in str(exc)
    else:  # pragma: no cover - ensures failure if exception not raised
        raise AssertionError("Expected FileNotFoundError to be raised")


def test_rejects_non_pdf_documents(tmp_path):
    document = tmp_path / "resume.txt"
    document.write_text("hello world")

    with pytest.raises(ValueError):
        extract_text_from_document(document)
