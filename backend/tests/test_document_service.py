"""Validation, extraction and normalization of uploaded documents."""

from __future__ import annotations

import pytest

from app.core.errors import ExtractionError, NoTextError, UnsupportedFileTypeError
from app.services.document_service import (
    ALLOWED_EXTENSIONS,
    extract_text,
    get_extension,
    normalize_text,
    validate_filename,
)
from tests.pdf_factory import build_pdf


def test_allowed_extensions():
    assert ALLOWED_EXTENSIONS == {".pdf", ".txt", ".md", ".markdown"}


@pytest.mark.parametrize("name", ["a.pdf", "A.PDF", "notes.txt", "doc.md", "readme.markdown"])
def test_valid_filenames(name):
    assert validate_filename(name) in ALLOWED_EXTENSIONS


@pytest.mark.parametrize("name", ["a.docx", "a.exe", "noext", "", "a.pdf.txt.exe"])
def test_invalid_filenames(name):
    with pytest.raises(UnsupportedFileTypeError):
        validate_filename(name)


def test_get_extension_handles_paths_and_case():
    assert get_extension("C:/Users/x/Notes.MD") == ".md"


def test_extract_plain_text_utf8():
    data = "Git rebase moves commits.\r\n\r\n\r\n\r\nUse --interactive.".encode("utf-8")
    text = extract_text("notes.txt", data)
    assert "Git rebase moves commits." in text
    assert "\r" not in text
    assert "\n\n\n" not in text  # excessive blank lines collapsed


def test_extract_text_with_bom():
    data = "BOM here".encode("utf-8-sig")
    assert extract_text("notes.txt", data) == "BOM here"


def test_extract_windows_1252_fallback():
    data = "caf\xe9 compiler".encode("cp1252")
    assert "café compiler" == extract_text("notes.txt", data)


def test_extract_binary_text_file_raises_extraction_error():
    with pytest.raises(ExtractionError):
        extract_text("notes.txt", bytes(range(0x80, 0x100)) * 4)


def test_extract_markdown_preserves_code_indentation():
    data = b"```python\ndef f():\n    return 1\n```\n"
    assert "    return 1" in extract_text("readme.md", data)


def test_extract_pdf():
    pdf = build_pdf(["DevAssist retrieval uses cosine similarity.", "Chunk size is 500."])
    text = extract_text("spec.pdf", pdf)
    assert "cosine similarity" in text
    assert "Chunk size is 500" in text


def test_extract_pdf_without_text_raises_no_text_error():
    with pytest.raises(NoTextError):
        extract_text("scanned.pdf", build_pdf([]))


def test_extract_corrupt_pdf_raises_extraction_error():
    with pytest.raises(ExtractionError):
        extract_text("broken.pdf", b"%PDF-1.4 not really a pdf")


def test_empty_text_file_raises_no_text_error():
    with pytest.raises(NoTextError):
        extract_text("empty.txt", b"   \n  \n")


def test_normalize_text_strips_nulls_and_outer_whitespace():
    assert normalize_text("\x00hello\x00\n") == "hello"


def test_normalize_text_keeps_meaningful_blank_lines():
    assert normalize_text("a\n\nb") == "a\n\nb"
