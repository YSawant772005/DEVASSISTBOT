"""Shared pytest fixtures.

The real embedding model is replaced with a deterministic, dependency-free
fake so unit tests are fast and reproducible. ``pytest -m real_model`` runs the
one test that exercises the actual Sentence Transformers model.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Must be set before the app package is imported.
os.environ.setdefault("EMBEDDING_PRELOAD", "False")
os.environ.setdefault("GROQ_API_KEY", "")

from app.core.config import Settings, reset_settings_cache  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import chat_service as chat_service_module  # noqa: E402
from app.services import embedding_service as embedding_module  # noqa: E402
from app.services import groq_service as groq_module  # noqa: E402
from app.services import vector_store as store_module  # noqa: E402
from app.services.chat_service import ChatService  # noqa: E402
from app.services.vector_store import VectorStore  # noqa: E402

EMBED_DIM = 64


class FakeEmbeddingService:
    """Deterministic bag-of-words embedding: cosine similarity is meaningful.

    Each token is hashed into a dimension of the vector, so texts sharing words
    are more similar. L2-normalized like the real model output.
    """

    model_name = "fake-deterministic"
    dimension = EMBED_DIM

    def __init__(self) -> None:
        self.is_loaded = True

    def load(self) -> None:  # pragma: no cover - nothing to load
        self.is_loaded = True

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype="float32")
        matrix = np.zeros((len(texts), self.dimension), dtype="float32")
        for row, text in enumerate(texts):
            for token in _tokenize(text):
                index = hash_token(token) % self.dimension
                matrix[row, index] += 1.0
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (matrix / norms).astype("float32")

    def encode_one(self, text: str) -> np.ndarray:
        return self.encode([text])[0]


def _tokenize(text: str) -> list[str]:
    return [token for token in "".join(c if c.isalnum() else " " for c in text.lower()).split() if token]


def hash_token(token: str) -> int:
    # Stable across processes (Python's hash() is salted).
    import zlib

    return zlib.crc32(token.encode("utf-8"))


class FakeProvider:
    """Streaming provider that yields scripted deltas and records the prompt."""

    def __init__(self, chunks: list[str] | None = None, error: Exception | None = None):
        self.chunks = chunks if chunks is not None else ["Hello", " from", " DevAssist."]
        self.error = error
        self.calls: list[list[dict[str, str]]] = []

    @property
    def is_configured(self) -> bool:
        return True

    async def stream(self, messages):
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        for chunk in self.chunks:
            yield chunk


@pytest.fixture
def fake_embedding() -> FakeEmbeddingService:
    return FakeEmbeddingService()


@pytest.fixture(autouse=True)
def _isolate_services(monkeypatch):
    """Give every test a fresh embedding service, vector store and provider."""
    embedding = FakeEmbeddingService()
    store = VectorStore(dimension=EMBED_DIM)
    monkeypatch.setattr(embedding_module, "_service", embedding)
    monkeypatch.setattr(store_module, "_store", store)
    monkeypatch.setattr(groq_module, "_provider", None)
    monkeypatch.setattr(chat_service_module, "_service", None)
    yield
    monkeypatch.setattr(embedding_module, "_service", None)
    monkeypatch.setattr(store_module, "_store", None)
    monkeypatch.setattr(groq_module, "_provider", None)
    monkeypatch.setattr(chat_service_module, "_service", None)


@pytest.fixture
def settings() -> Settings:
    return Settings(EMBEDDING_PRELOAD=False, GROQ_API_KEY="test-key")


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def vector_store() -> VectorStore:
    return VectorStore(dimension=EMBED_DIM)


@pytest.fixture
def chat_service(settings) -> ChatService:
    return ChatService(
        settings=settings,
        embedding=FakeEmbeddingService(),
        store=VectorStore(dimension=EMBED_DIM),
        provider=FakeProvider(),
    )


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    reset_settings_cache()
    yield
    reset_settings_cache()
