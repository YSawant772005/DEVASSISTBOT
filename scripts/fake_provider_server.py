"""Serve the real FastAPI app with a deterministic fake streaming provider.

This exercises the complete WebSocket streaming path
(``status -> sources -> token -> done``) over a genuine TCP socket without
needing a Groq API key. It only uses the public ``set_provider()`` seam that the
test-suite already relies on, so no production code is modified.

Usage: python scripts/fake_provider_server.py [port]
"""

from __future__ import annotations

import asyncio
import sys
from typing import AsyncIterator

from app.services.groq_service import GroqProvider, set_provider

REPLY = (
    "Based on the uploaded notes, retrieval uses a chunk size of 500 characters with a "
    "50 character overlap and returns the top 3 chunks. Embeddings come from the "
    "all-MiniLM-L6-v2 model, and the index is a normalized cosine FAISS index that is "
    "rebuilt whenever a document is deleted. Chat generation streams from Groq with a "
    "temperature of 0.2 and a maximum of 1024 output tokens, and the whole pipeline keeps "
    "the assembled context under 4000 tokens so answers stay grounded in your documents."
)


class FakeStreamingProvider(GroqProvider):
    """Streams a canned answer word by word, mimicking Groq's deltas."""

    @property
    def is_configured(self) -> bool:  # noqa: D102 - trivial override
        return True

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:  # noqa: ARG002
        delay = 0.02
        # The cancellation test asks for a deliberately slow answer so the client
        # has a wide window in which to send its cancel frame.
        last = messages[-1].get("content", "") if messages else ""
        if "very slowly" in last.lower():
            delay = 0.05
        for word in REPLY.split(" "):
            await asyncio.sleep(delay)
            yield word + " "


def main() -> None:
    import uvicorn

    from app.main import app

    set_provider(FakeStreamingProvider())
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    print(f"fake-provider server on http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, workers=1, log_level="info")


if __name__ == "__main__":
    main()
