"""Health endpoint contract."""

from __future__ import annotations


def test_health_returns_degraded_without_credentials(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"  # no Groq key configured in tests
    assert body["groq_configured"] is False
    assert body["documents_indexed"] == 0
    assert body["chunks_indexed"] == 0
    assert body["limits"]["max_upload_bytes"] == 5242880
    assert body["limits"]["chunk_size"] == 500
    assert body["limits"]["chunk_overlap"] == 50
    assert body["limits"]["top_k"] == 3
    assert any("GROQ_API_KEY" in warning for warning in body["warnings"])


def test_health_reports_index_size_after_upload(client):
    files = {"file": ("notes.md", b"Retry policy: three attempts, 250ms backoff.", "text/markdown")}
    assert client.post("/upload", files=files).status_code == 200

    body = client.get("/health").json()
    assert body["documents_indexed"] == 1
    assert body["chunks_indexed"] == 1


def test_root_endpoint(client):
    body = client.get("/").json()
    assert body["service"] == "DevAssist API"
