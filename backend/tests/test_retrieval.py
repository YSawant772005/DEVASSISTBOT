"""Vector store behaviour and retrieval quality."""

from __future__ import annotations

import numpy as np
import pytest

from app.services.vector_store import VectorStore


def _vectors(*rows: list[float]) -> np.ndarray:
    return np.asarray(rows, dtype="float32")


def test_empty_store_search_returns_nothing():
    store = VectorStore(dimension=4)
    assert store.is_empty()
    assert store.search(_vectors([1, 0, 0, 0]), top_k=3) == []


def test_add_document_stores_chunks_and_metadata():
    store = VectorStore(dimension=4)
    vectors = np.asarray([[1, 0, 0, 0], [0, 1, 0, 0]], dtype="float32")

    doc_id = store.add_document(
        filename="notes.md",
        extension=".md",
        size_bytes=42,
        chunks=["first chunk", "second chunk"],
        vectors=vectors,
    )

    assert store.size == 2
    documents = store.documents()
    assert len(documents) == 1
    assert documents[0].doc_id == doc_id
    assert documents[0].chunk_count == 2
    assert documents[0].filename == "notes.md"
    records = {record.chunk_index: record for record in store._records}  # noqa: SLF001
    assert records[1].text == "second chunk"
    assert all(record.doc_id == doc_id for record in store._records)  # noqa: SLF001


def test_add_document_rejects_mismatched_shapes():
    store = VectorStore(dimension=4)
    with pytest.raises(ValueError):
        store.add_document(
            filename="a.md",
            extension=".md",
            size_bytes=1,
            chunks=["one", "two"],
            vectors=np.asarray([[1, 0, 0, 0]], dtype="float32"),
        )
    with pytest.raises(ValueError):
        store.add_document(
            filename="a.md",
            extension=".md",
            size_bytes=1,
            chunks=["one"],
            vectors=np.asarray([[1, 0]], dtype="float32"),
        )


def test_search_returns_top_k_in_score_order():
    store = VectorStore(dimension=3)
    store.add_document(
        filename="docs.md",
        extension=".md",
        size_bytes=3,
        chunks=["a", "b", "c"],
        vectors=_vectors([1, 0, 0], [0.9, 0.1, 0], [0, 0, 1]),
    )

    hits = store.search(_vectors([1, 0, 0]), top_k=2)

    assert [hit.record.text for hit in hits] == ["a", "b"]
    assert hits[0].score > hits[1].score
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)
    assert hits[0].record.filename == "docs.md"
    assert hits[0].record.chunk_index == 0


def test_search_never_returns_more_than_available():
    store = VectorStore(dimension=2)
    store.add_document(
        filename="one.md", extension=".md", size_bytes=1, chunks=["only"], vectors=_vectors([1, 0])
    )
    assert len(store.search(_vectors([1, 0]), top_k=3)) == 1


def test_remove_document_keeps_index_and_metadata_consistent():
    store = VectorStore(dimension=2)
    first = store.add_document(
        filename="a.md", extension=".md", size_bytes=1, chunks=["a1", "a2"], vectors=_vectors([1, 0], [1, 0])
    )
    second = store.add_document(
        filename="b.md", extension=".md", size_bytes=1, chunks=["b1"], vectors=_vectors([0, 1])
    )

    removed = store.remove_document(first)

    assert removed == 2
    assert store.size == 1
    assert [doc.doc_id for doc in store.documents()] == [second]
    hits = store.search(_vectors([0, 1]), top_k=3)
    assert [hit.record.text for hit in hits] == ["b1"]


def test_clear_empties_store_and_index():
    store = VectorStore(dimension=2)
    store.add_document(
        filename="a.md", extension=".md", size_bytes=1, chunks=["a"], vectors=_vectors([1, 0])
    )
    assert store.clear() == 1
    assert store.is_empty()
    assert store.documents() == []
    assert store.search(_vectors([1, 0])) == []


def test_documents_sorted_newest_first():
    store = VectorStore(dimension=2)
    store.add_document(
        filename="old.md", extension=".md", size_bytes=1, chunks=["x"], vectors=_vectors([1, 0]), doc_id="old"
    )
    store.add_document(
        filename="new.md", extension=".md", size_bytes=1, chunks=["y"], vectors=_vectors([1, 0]), doc_id="new"
    )
    assert [doc.doc_id for doc in store.documents()] == ["new", "old"]


# ---------------------------------------------------------------------------
# Retrieval through the chat service (deterministic fake embeddings)
# ---------------------------------------------------------------------------


def test_retrieval_ranks_the_relevant_chunk_first(chat_service):
    from tests.conftest import FakeEmbeddingService

    embedding = FakeEmbeddingService()
    store = chat_service.store
    chats = [
        "The retry policy retries a failed request at most three times with 250ms backoff.",
        "Bananas are yellow and grow in tropical climates.",
        "Docker containers isolate processes using namespaces and cgroups.",
    ]
    store.add_document(
        filename="gateway.md",
        extension=".md",
        size_bytes=100,
        chunks=chats,
        vectors=embedding.encode(chats),
    )

    hits = chat_service.retrieve("How many times does the retry policy retry a failed request?")

    assert hits, "expected at least one retrieved chunk"
    assert hits[0].record.text == chats[0]
    assert hits[0].record.filename == "gateway.md"
    assert hits[0].record.chunk_index == 0


def test_retrieval_returns_empty_list_without_documents(chat_service):
    assert chat_service.retrieve("What is the retry policy?") == []


def test_sources_include_filename_chunk_index_score_and_preview(chat_service):
    from tests.conftest import FakeEmbeddingService

    embedding = FakeEmbeddingService()
    long_text = "kubernetes pod scheduling " + ("details " * 60)
    chat_service.store.add_document(
        filename="k8s.md",
        extension=".md",
        size_bytes=10,
        chunks=[long_text],
        vectors=embedding.encode([long_text]),
    )

    sources = chat_service.to_sources(chat_service.retrieve("how does kubernetes pod scheduling work?"))

    assert len(sources) == 1
    source = sources[0]
    assert source.filename == "k8s.md"
    assert source.chunk_index == 0
    assert 0.0 <= source.score <= 1.0
    assert len(source.preview) <= 240


def test_retrieval_respects_context_budget():
    from app.core.config import Settings
    from app.services.chat_service import ChatService
    from tests.conftest import FakeEmbeddingService, FakeProvider

    settings = Settings(EMBEDDING_PRELOAD=False, GROQ_API_KEY="k", MAX_CONTEXT_TOKENS=300, TOP_K=3)
    embedding = FakeEmbeddingService()
    service = ChatService(
        settings=settings,
        embedding=embedding,
        store=VectorStore(dimension=embedding.dimension),
        provider=FakeProvider(),
    )
    chunks = ["python threading " + ("x" * 1100), "python threading two " + ("y" * 1100)]
    service.store.add_document(
        filename="big.md", extension=".md", size_bytes=1, chunks=chunks, vectors=embedding.encode(chunks)
    )

    hits = service.retrieve("python threading")

    assert len(hits) == 1  # 300 tokens * 4 chars budget only fits one 1100-char chunk
