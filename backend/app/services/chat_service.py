"""Chat orchestration: policy check, retrieval, prompt assembly, streaming."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import AsyncIterator

from app.core.config import Settings, get_settings
from app.prompts.system_prompt import build_messages
from app.schemas.chat import SourceReference
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.groq_service import GroqProvider, get_provider
from app.services.policy_service import evaluate_policy
from app.services.vector_store import SearchHit, VectorStore, get_vector_store

logger = logging.getLogger(__name__)

PREVIEW_CHARS = 240


@dataclass
class PreparedAnswer:
    """Everything needed to stream an answer for one validated question."""

    question: str
    messages: list[dict[str, str]]
    sources: list[SourceReference] = field(default_factory=list)
    refusal: str | None = None

    @property
    def used_documents(self) -> bool:
        return bool(self.sources)


class ChatService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        embedding: EmbeddingService | None = None,
        store: VectorStore | None = None,
        provider: GroqProvider | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._embedding = embedding
        self._store = store
        self._provider = provider

    # Lazily resolved so tests can swap the singletons after construction.
    @property
    def embedding(self) -> EmbeddingService:
        return self._embedding or get_embedding_service()

    @property
    def store(self) -> VectorStore:
        return self._store or get_vector_store()

    @property
    def provider(self) -> GroqProvider:
        return self._provider or get_provider()

    # -- retrieval ---------------------------------------------------------
    def retrieve(self, question: str) -> list[SearchHit]:
        """Embed the question and return up to ``TOP_K`` relevant chunks.

        The context budget is enforced here so the assembled prompt stays
        under ``MAX_CONTEXT_TOKENS`` (approximated at 4 characters per token).
        """
        if self.store.is_empty():
            return []

        query_vector = self.embedding.encode_one(question)
        hits = self.store.search(query_vector, top_k=self.settings.top_k)

        char_budget = max(self.settings.max_context_tokens, 256) * 4
        kept: list[SearchHit] = []
        used = 0
        for hit in hits:
            text = hit.record.text
            if kept and used + len(text) > char_budget:
                break
            used += len(text)
            kept.append(hit)

        logger.info(
            "Retrieved %d chunk(s) for a %d-character question.",
            len(kept),
            len(question),
        )
        return kept

    @staticmethod
    def to_sources(hits: list[SearchHit]) -> list[SourceReference]:
        return [
            SourceReference(
                doc_id=hit.record.doc_id,
                filename=hit.record.filename,
                chunk_index=hit.record.chunk_index,
                score=round(max(0.0, min(1.0, hit.score)), 4),
                preview=hit.record.text[:PREVIEW_CHARS].strip(),
            )
            for hit in hits
        ]

    # -- orchestration -----------------------------------------------------
    def prepare(self, question: str) -> PreparedAnswer:
        """Validate policy, retrieve context and assemble the provider prompt."""
        decision = evaluate_policy(question)
        if not decision.allowed:
            return PreparedAnswer(
                question=question,
                messages=[],
                sources=[],
                refusal=decision.refusal,
            )

        hits = self.retrieve(question)
        excerpts = [(h.record.filename, h.record.chunk_index, h.record.text) for h in hits]
        messages = build_messages(question, excerpts)
        return PreparedAnswer(
            question=question,
            messages=messages,
            sources=self.to_sources(hits),
        )

    async def stream(self, prepared: PreparedAnswer) -> AsyncIterator[str]:
        """Yield the answer text deltas (or the local refusal message)."""
        if prepared.refusal is not None:
            yield prepared.refusal
            return
        async for delta in self.provider.stream(prepared.messages):
            yield delta


_service: ChatService | None = None


def get_chat_service() -> ChatService:
    global _service
    if _service is None:
        _service = ChatService()
    return _service


def set_chat_service(service: ChatService | None) -> None:
    global _service
    _service = service
