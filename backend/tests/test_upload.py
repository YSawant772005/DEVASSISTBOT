"""POST /upload and document lifecycle endpoints."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from tests.pdf_factory import build_pdf


def _upload(client, name: str, data: bytes, content_type: str = "application/octet-stream"):
    return client.post("/upload", files={"file": (name, data, content_type)})


def test_upload_markdown_succeeds_and_reports_real_chunk_count(client):
    body = b"# Docs\n\n" + (b"Retry policy uses 250ms backoff. " * 60)
    response = _upload(client, "notes.md", body, "text/markdown")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["filename"] == "notes.md"
    assert payload["extension"] == ".md"
    assert payload["chunks_processed"] >= 2  # ~1600 chars at 500/50
    assert payload["characters_extracted"] > 1000
    assert payload["size_bytes"] == len(body)
    assert payload["doc_id"]


def test_upload_txt_and_pdf_succeed(client):
    txt = _upload(client, "a.txt", b"def add(a, b):\n    return a + b\n", "text/plain")
    pdf = _upload(client, "b.pdf", build_pdf(["RAG notes", "top three chunks"]), "application/pdf")

    assert txt.status_code == 200
    assert pdf.status_code == 200
    assert txt.json()["extension"] == ".txt"
    assert pdf.json()["extension"] == ".pdf"


def test_upload_rejects_unsupported_extension(client):
    response = _upload(client, "malware.exe", b"MZ...")

    assert response.status_code == 400
    assert response.json()["code"] == "UNSUPPORTED_FILE_TYPE"
    assert "pdf" in response.json()["message"].lower()


def test_upload_rejects_empty_file(client):
    response = _upload(client, "empty.txt", b"")

    assert response.status_code == 400
    assert response.json()["code"] == "EMPTY_FILE"


def test_upload_rejects_file_over_5mb(client):
    limit = get_settings().max_upload_bytes
    response = _upload(client, "big.txt", b"a" * (limit + 1))

    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"
    assert "5 MB" in response.json()["message"]


def test_upload_accepts_file_exactly_at_limit(client):
    limit = get_settings().max_upload_bytes
    response = _upload(client, "limit.txt", b"a" * limit)

    assert response.status_code == 200


def test_upload_rejects_pdf_without_text(client):
    response = _upload(client, "scanned.pdf", build_pdf([]), "application/pdf")

    assert response.status_code == 422
    assert response.json()["code"] == "NO_TEXT_CONTENT"


def test_failed_upload_does_not_register_a_document(client):
    _upload(client, "scanned.pdf", build_pdf([]), "application/pdf")

    body = client.get("/documents").json()
    assert body["total_documents"] == 0
    assert body["total_chunks"] == 0


def test_documents_are_listed_then_removed(client):
    uploaded = _upload(client, "notes.md", b"chunk me " * 200, "text/markdown").json()

    listed = client.get("/documents").json()
    assert listed["total_documents"] == 1
    assert listed["total_chunks"] == uploaded["chunks_processed"]
    assert listed["documents"][0]["filename"] == "notes.md"

    removed = client.delete(f"/documents/{uploaded['doc_id']}").json()
    assert removed["chunks_removed"] == uploaded["chunks_processed"]

    after = client.get("/documents").json()
    assert after["total_documents"] == 0
    assert after["total_chunks"] == 0


def test_clear_all_documents(client):
    _upload(client, "a.md", b"alpha content " * 100, "text/markdown")
    _upload(client, "b.txt", b"beta content " * 100, "text/plain")

    cleared = client.delete("/documents").json()
    assert cleared["chunks_removed"] > 0
    assert client.get("/documents").json()["total_documents"] == 0


def test_removing_unknown_document_is_a_no_op(client):
    response = client.delete("/documents/does-not-exist")

    assert response.status_code == 200
    assert response.json()["chunks_removed"] == 0


@pytest.mark.parametrize("name", ["notes.md", "NOTES.MD", "spec.pdf", "log.txt"])
def test_uppercase_and_mixed_extensions_are_accepted(client, name):
    data = build_pdf(["text"]) if name.lower().endswith(".pdf") else b"some text"
    response = _upload(client, name, data)

    assert response.status_code == 200
    assert response.json()["extension"] == ("." + name.rsplit(".", 1)[1].lower())
