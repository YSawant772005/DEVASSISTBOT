"""Chunking rules: 500 characters with 50 characters of overlap."""

from __future__ import annotations

import pytest

from app.services.chunking_service import chunk_text


def test_empty_input_returns_no_chunks():
    assert chunk_text("", 500, 50) == []


def test_whitespace_only_input_returns_no_chunks():
    assert chunk_text("   \n\n\t  ", 500, 50) == []


def test_short_text_is_a_single_chunk():
    assert chunk_text("git rebase", 500, 50) == ["git rebase"]


def test_exact_chunk_size_is_a_single_chunk():
    text = "a" * 500
    chunks = chunk_text(text, 500, 50)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_501_characters_produces_two_chunks_with_overlap():
    text = "".join(str(i % 10) for i in range(501))
    chunks = chunk_text(text, 500, 50)

    assert len(chunks) == 2
    assert len(chunks[0]) == 500
    assert chunks[0][-50:] == chunks[1][:50]  # overlap preserved
    assert len(chunks[1]) == 51
    assert chunks[0] + chunks[1][50:] == text  # nothing lost


def test_long_text_is_fully_covered_and_advances():
    text = "".join(str(i % 10) for i in range(5000))
    chunks = chunk_text(text, 500, 50)

    assert len(chunks) > 9
    assert all(len(chunk) <= 500 for chunk in chunks)
    # Reconstruct by removing each chunk's overlap with the previous chunk.
    rebuilt = chunks[0]
    for chunk in chunks[1:]:
        rebuilt += chunk[50:]
    assert rebuilt == text


def test_overlap_larger_than_chunk_size_still_terminates():
    chunks = chunk_text("x" * 300, 100, 500)
    assert 0 < len(chunks) <= 10
    assert all(len(chunk) <= 100 for chunk in chunks)
    rebuilt = chunks[0] + "".join(chunk[50:] for chunk in chunks[1:])
    assert rebuilt == "x" * 300


def test_invalid_arguments_raise():
    with pytest.raises(ValueError):
        chunk_text("abc", 0, 0)
    with pytest.raises(ValueError):
        chunk_text("abc", 100, -1)


def test_code_indentation_is_preserved():
    code = "def f():\n    if True:\n        return 1\n"
    assert chunk_text(code, 500, 50) == [code]
