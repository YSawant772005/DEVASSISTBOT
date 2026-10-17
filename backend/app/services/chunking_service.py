"""Deterministic character chunking (500 chars, 50 overlap by default)."""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split ``text`` into overlapping chunks.

    The loop always advances by at least one character, so it can never spin
    forever even with pathological overlap settings. Whitespace-only chunks are
    skipped; the returned chunk text keeps its original characters (including
    indentation) so code stays readable.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")

    overlap = min(overlap, chunk_size // 2)
    length = len(text)
    if length == 0:
        return []

    chunks: list[str] = []
    start = 0
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - overlap, start + 1)

    return chunks
