"""In-memory FAISS vector store with parallel chunk metadata.

Vectors are L2-normalized and the index uses inner product, which is
equivalent to cosine similarity. Documents can be removed safely: since the
MVP keeps every record in memory, the index is rebuilt from the surviving
records, guaranteeing that vectors and metadata never drift apart.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChunkRecord:
    doc_id: str
    filename: str
    chunk_index: int
    text: str


@dataclass
class DocumentRecord:
    doc_id: str
    filename: str
    extension: str
    size_bytes: int
    chunk_count: int
    uploaded_at: str
    sequence: int = 0


@dataclass
class SearchHit:
    record: ChunkRecord
    score: float


@dataclass
class VectorStore:
    """Thread-safe in-memory vector store.

    ``vectors`` and ``records`` are always appended together under a lock, and
    removals rebuild the FAISS index from the retained data.
    """

    dimension: int = 384
    _index: object | None = field(default=None, init=False, repr=False)
    _records: list[ChunkRecord] = field(default_factory=list, init=False)
    _vectors: np.ndarray | None = field(default=None, init=False, repr=False)
    _docs: dict[str, DocumentRecord] = field(default_factory=dict, init=False)
    _sequence: int = field(default=0, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._index = self._new_index()
        self._vectors = np.zeros((0, self.dimension), dtype="float32")

    # -- internals ---------------------------------------------------------
    def _new_index(self):
        import faiss

        return faiss.IndexFlatIP(self.dimension)

    def _rebuild(self) -> None:
        """Rebuild the FAISS index from the retained vectors (call under lock)."""
        self._index = self._new_index()
        if self._vectors is not None and self._vectors.shape[0] > 0:
            self._index.add(self._vectors)  # type: ignore[attr-defined]

    # -- writes ------------------------------------------------------------
    def add_document(
        self,
        *,
        filename: str,
        extension: str,
        size_bytes: int,
        chunks: list[str],
        vectors: np.ndarray,
        doc_id: str | None = None,
    ) -> str:
        """Index a document atomically. Returns its doc_id."""
        if len(chunks) != int(vectors.shape[0]):
            raise ValueError("chunks and vectors must have the same length")
        if vectors.shape[1] != self.dimension:
            raise ValueError(
                f"vector dimension {vectors.shape[1]} does not match store dimension {self.dimension}"
            )

        doc_id = doc_id or uuid.uuid4().hex
        records = [
            ChunkRecord(doc_id=doc_id, filename=filename, chunk_index=i, text=text)
            for i, text in enumerate(chunks)
        ]
        vectors = np.asarray(vectors, dtype="float32")

        with self._lock:
            # Build the new state first so a failure cannot leave a half-updated index.
            new_vectors = np.vstack([self._vectors, vectors]) if self._vectors is not None and self._vectors.size else vectors
            new_records = [*self._records, *records]
            index = self._new_index()
            if new_vectors.shape[0]:
                index.add(new_vectors)

            self._vectors = new_vectors
            self._records = new_records
            self._index = index
            self._sequence += 1
            self._docs[doc_id] = DocumentRecord(
                doc_id=doc_id,
                filename=filename,
                extension=extension,
                size_bytes=size_bytes,
                chunk_count=len(chunks),
                uploaded_at=datetime.now(timezone.utc).isoformat(),
                sequence=self._sequence,
            )
        logger.info("Indexed document '%s' (%d chunks).", filename, len(chunks))
        return doc_id

    def remove_document(self, doc_id: str) -> int:
        """Remove a document and return the number of chunks removed."""
        with self._lock:
            doc = self._docs.pop(doc_id, None)
            if doc is None:
                return 0
            keep = [i for i, record in enumerate(self._records) if record.doc_id != doc_id]
            self._records = [self._records[i] for i in keep]
            if self._vectors is not None and self._vectors.shape[0]:
                self._vectors = self._vectors[keep] if keep else np.zeros((0, self.dimension), dtype="float32")
            self._rebuild()
            return doc.chunk_count

    def clear(self) -> int:
        """Remove every document and return the number of chunks removed."""
        with self._lock:
            removed = len(self._records)
            self._docs.clear()
            self._records = []
            self._vectors = np.zeros((0, self.dimension), dtype="float32")
            self._rebuild()
            return removed

    # -- reads -------------------------------------------------------------
    @property
    def size(self) -> int:
        with self._lock:
            return len(self._records)

    def is_empty(self) -> bool:
        return self.size == 0

    def documents(self) -> list[DocumentRecord]:
        with self._lock:
            # Most recently uploaded first; the sequence breaks timestamp ties.
            return sorted(
                self._docs.values(), key=lambda d: (d.uploaded_at, d.sequence), reverse=True
            )

    def has_document(self, doc_id: str) -> bool:
        with self._lock:
            return doc_id in self._docs

    def search(self, query_vector: np.ndarray, top_k: int = 3) -> list[SearchHit]:
        """Return the ``top_k`` most similar chunks (empty when the index is empty)."""
        with self._lock:
            if not self._records:
                return []
            query = np.asarray(query_vector, dtype="float32").reshape(1, -1)
            if query.shape[1] != self.dimension:
                raise ValueError("query embedding dimension mismatch")
            k = max(1, min(top_k, len(self._records)))
            scores, indices = self._index.search(query, k)  # type: ignore[attr-defined]
            hits: list[SearchHit] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                hits.append(SearchHit(record=self._records[int(idx)], score=float(score)))
            return hits


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore(dimension=get_embedding_dimension())
    return _store


def get_embedding_dimension() -> int:
    from app.services.embedding_service import get_embedding_service

    return get_embedding_service().dimension


def set_vector_store(store: VectorStore | None) -> None:
    """Replace the singleton (used by tests)."""
    global _store
    _store = store
