from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.document_ocr import extract_text_from_document


def test_extract_text_from_plain_text(tmp_path):
    document = tmp_path / "resume.txt"
    document.write_text("CA Match Resume")

    text = extract_text_from_document(document)

    assert "CA Match Resume" in text


def test_extract_text_missing_file(tmp_path):
    missing = tmp_path / "missing.txt"

    try:
        extract_text_from_document(missing)
    except FileNotFoundError as exc:
        assert "Document not found" in str(exc)
    else:  # pragma: no cover - ensures failure if exception not raised
        raise AssertionError("Expected FileNotFoundError to be raised")
