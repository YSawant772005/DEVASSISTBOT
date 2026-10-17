"""Integration tests using the *real* local embedding model.

Marked ``real_model`` because the first run downloads
``sentence-transformers/all-MiniLM-L6-v2`` (~90 MB). Run with::

    pytest -m real_model
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import chat_service as chat_service_module
from app.services import embedding_service as embedding_module
from app.services import vector_store as store_module
from app.services.chat_service import ChatService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

pytestmark = pytest.mark.real_model

MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@pytest.fixture(scope="module")
def real_embedding() -> EmbeddingService:
    service = EmbeddingService(MODEL)
    service.load()
    return service


def test_model_produces_normalized_384_dim_vectors(real_embedding):
    import numpy as np

    vector = real_embedding.encode_one("git rebase vs merge")

    assert real_embedding.dimension == 384
    assert vector.shape == (384,)
    assert float(np.linalg.norm(vector)) == pytest.approx(1.0, abs=1e-4)


def test_real_retrieval_finds_the_matching_chunk(real_embedding, monkeypatch):
    store = VectorStore(dimension=real_embedding.dimension)
    monkeypatch.setattr(store_module, "_store", store)

    chunks = [
        "The gateway retries a failed upstream request at most three times with 250ms backoff.",
        "The design system uses a deep navy background with electric blue accents.",
        "Bananas are a good source of potassium and grow in tropical climates.",
    ]
    store.add_document(
        filename="gateway.md",
        extension=".md",
        size_bytes=1,
        chunks=chunks,
        vectors=real_embedding.encode(chunks),
    )

    service = ChatService(embedding=real_embedding)
    hits = service.retrieve("How many retry attempts does the gateway make?")

    assert hits[0].record.text == chunks[0]


def test_upload_and_search_end_to_end_with_real_embeddings(real_embedding, monkeypatch):
    # The app lifespan builds its vector store from the global embedding
    # service, so both singletons must point at the real model here.
    monkeypatch.setattr(embedding_module, "_service", real_embedding)
    monkeypatch.setattr(store_module, "_store", VectorStore(dimension=real_embedding.dimension))
    service = ChatService(embedding=real_embedding)
    monkeypatch.setattr(chat_service_module, "_service", service)

    with TestClient(create_app()) as client:
        markdown = (
            "# Deployment notes\n\n"
            "The staging cluster runs three replicas behind a load balancer.\n\n"
            "Rollbacks are triggered with `kubectl rollout undo`.\n"
        )
        response = client.post(
            "/upload", files={"file": ("deploy.md", markdown.encode(), "text/markdown")}
        )
        assert response.status_code == 200
        assert response.json()["chunks_processed"] >= 1

        service = chat_service_module.get_chat_service()
        hits = service.retrieve("How do I roll back a bad deployment?")
        assert hits
        assert hits[0].record.filename == "deploy.md"
        assert "rollout undo" in hits[0].record.text
