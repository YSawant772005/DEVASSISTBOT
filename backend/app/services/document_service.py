"""Document validation, text extraction and normalization."""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from pypdf import PdfReader

from app.core.errors import ExtractionError, NoTextError, UnsupportedFileTypeError

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".txt", ".md", ".markdown"})

_EXCESS_NEWLINES = re.compile(r"\n{3,}")


def get_extension(filename: str) -> str:
    """Return the lowercase file extension including the leading dot."""
    return Path(filename or "").suffix.lower()


def validate_filename(filename: str | None) -> str:
    """Validate the extension against the allowlist and return it."""
    extension = get_extension(filename or "")
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(extension or "(none)")
    return extension


def normalize_text(text: str) -> str:
    """Normalize line endings and excessive blank lines.

    Indentation and Markdown structure are preserved; only NUL bytes, CRLF
    endings and runs of three or more newlines are normalized.
    """
    if not text:
        return ""
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _EXCESS_NEWLINES.sub("\n\n", text)
    return text.strip()


def _extract_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # Try the common "empty password" case before giving up.
            try:
                reader.decrypt("")
            except Exception as exc:  # pragma: no cover - depends on file
                raise ExtractionError(
                    "This PDF is password-protected and cannot be read."
                ) from exc
        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:  # pragma: no cover - malformed page
                logger.warning("PDF page extraction failed: %s", type(exc).__name__)
                pages.append("")
        return "\n".join(pages)
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(
            "The PDF could not be parsed. It may be corrupted or unsupported."
        ) from exc


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    try:
        return data.decode("cp1252")
    except UnicodeDecodeError as exc:
        raise ExtractionError(
            "The file is not valid UTF-8 or Windows-1252 text."
        ) from exc


def extract_text(filename: str, data: bytes) -> str:
    """Extract raw text from an uploaded file (extension already validated)."""
    extension = get_extension(filename)
    if extension == ".pdf":
        raw = _extract_pdf(data)
    elif extension in {".txt", ".md", ".markdown"}:
        raw = _decode_text(data)
    else:  # defensive: callers validate first
        raise UnsupportedFileTypeError(extension or "(none)")

    text = normalize_text(raw)
    if not text:
        if extension == ".pdf":
            raise NoTextError(
                "No selectable text was found in this PDF. Scanned or image-only "
                "PDFs are not supported."
            )
        raise NoTextError("The file does not contain any readable text.")
    return text
