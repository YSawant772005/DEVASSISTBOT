"""Local Sentence Transformers embedding service.

The model is loaded once (during application startup) and reused for both
document chunks and user queries, which keeps vectors in the same space.
"""

from __future__ import annotations

import logging
import threading

import numpy as np

from app.core.config import get_settings
from app.core.errors import EmbeddingUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_DIMENSION = 384  # all-MiniLM-L6-v2


class EmbeddingService:
    """Wraps a SentenceTransformer model with lazy, thread-safe loading."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()
        self._dimension = DEFAULT_DIMENSION

    # -- lifecycle ---------------------------------------------------------
    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def dimension(self) -> int:
        return self._dimension

    def load(self) -> None:
        """Download/load the model. Raises EmbeddingUnavailableError on failure."""
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            try:
                from sentence_transformers import SentenceTransformer

                logger.info("Loading embedding model '%s' (first run downloads it)...", self.model_name)
                model = SentenceTransformer(self.model_name)
                # Method renamed in sentence-transformers 5.x; support both.
                get_dimension = getattr(model, "get_embedding_dimension", None) or getattr(
                    model, "get_sentence_embedding_dimension", None
                )
                dimension = int(get_dimension() or DEFAULT_DIMENSION) if get_dimension else DEFAULT_DIMENSION
                self._model = model
                self._dimension = dimension
                logger.info("Embedding model ready (dimension=%d).", dimension)
            except Exception as exc:  # pragma: no cover - environment dependent
                logger.error(
                    "Failed to load embedding model '%s': %s: %s",
                    self.model_name,
                    type(exc).__name__,
                    exc,
                )
                raise EmbeddingUnavailableError() from exc

    # -- inference ---------------------------------------------------------
    def encode(self, texts: list[str]) -> np.ndarray:
        """Return L2-normalized float32 embeddings shaped (n, dimension)."""
        if not texts:
            return np.zeros((0, self._dimension), dtype="float32")
        if self._model is None:
            raise EmbeddingUnavailableError()
        vectors = self._model.encode(
            texts,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype="float32")

    def encode_one(self, text: str) -> np.ndarray:
        """Return a single L2-normalized embedding shaped (dimension,)."""
        return self.encode([text])[0]


_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _service
    if _service is None:
        _service = EmbeddingService(get_settings().embedding_model)
    return _service


def set_embedding_service(service: EmbeddingService | None) -> None:
    """Replace the singleton (used by tests to inject a deterministic fake)."""
    global _service
    _service = service
