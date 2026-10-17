"""WebSocket chat protocol: tokens, done, error, cancel, disconnects."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ConfigurationError, ProviderError, RateLimitedError
from app.main import create_app
from app.services import chat_service as chat_service_module
from app.services import groq_service as groq_module
from app.services.chat_service import ChatService
from app.services.vector_store import VectorStore
from tests.conftest import EMBED_DIM, FakeEmbeddingService, FakeProvider


def _service(provider) -> ChatService:
    from app.core.config import Settings

    embedding = FakeEmbeddingService()
    return ChatService(
        settings=Settings(EMBEDDING_PRELOAD=False, GROQ_API_KEY="test-key"),
        embedding=embedding,
        store=VectorStore(dimension=EMBED_DIM),
        provider=provider,
    )


@pytest.fixture
def ws_client(monkeypatch):
    """TestClient whose chat service uses a scripted fake provider."""
    provider = FakeProvider(["Check ", "the ", "traceback."])
    service = _service(provider)
    monkeypatch.setattr(groq_module, "_provider", provider)
    monkeypatch.setattr(chat_service_module, "_service", service)
    with TestClient(create_app()) as client:
        yield client, provider, service


def _collect(websocket, limit: int = 50) -> list[dict]:
    events: list[dict] = []
    for _ in range(limit):
        event = json.loads(websocket.receive_text())
        events.append(event)
        if event["type"] in {"done", "error"}:
            break
    return events


def _terminal(websocket, limit: int = 50) -> dict:
    """Drain events (status/sources/token) until the terminal one arrives."""
    return _collect(websocket, limit)[-1]


def test_streams_tokens_then_done(ws_client):
    client, _, _ = ws_client
    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_text(
            json.dumps({"type": "message", "request_id": "req-1", "message": "Explain a traceback"})
        )
        events = _collect(websocket)

    assert [event["type"] for event in events][:2] == ["status", "status"]
    assert events[-1]["type"] == "done"
    assert events[-1]["request_id"] == "req-1"
    assert all(event["request_id"] == "req-1" for event in events)
    tokens = "".join(event["token"] for event in events if event["type"] == "token")
    assert tokens == "Check the traceback."


def test_sources_event_precedes_tokens_when_documents_match(ws_client):
    client, provider, service = ws_client
    chunk = "The retry policy retries a failed request three times with 250ms backoff."
    service.store.add_document(
        filename="gateway.md",
        extension=".md",
        size_bytes=1,
        chunks=[chunk],
        vectors=service.embedding.encode([chunk]),
    )

    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_text(
            json.dumps(
                {
                    "type": "message",
                    "request_id": "req-src",
                    "message": "How many times does the retry policy retry a failed request?",
                }
            )
        )
        events = _collect(websocket)

    sources_event = next(event for event in events if event["type"] == "sources")
    assert sources_event["sources"][0]["filename"] == "gateway.md"
    assert sources_event["sources"][0]["chunk_index"] == 0
    assert events.index(sources_event) < next(
        i for i, event in enumerate(events) if event["type"] == "token"
    )
    # Retrieved text reached the provider prompt.
    assert chunk in "\n".join(message["content"] for message in provider.calls[-1])


def test_policy_refusal_is_streamed_as_tokens(ws_client):
    client, provider, _ = ws_client
    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_text(
            json.dumps({"type": "message", "request_id": "req-off", "message": "Give me a recipe for cake"})
        )
        events = _collect(websocket)

    tokens = "".join(event["token"] for event in events if event["type"] == "token")
    assert "programming-focused" in tokens
    assert events[-1]["type"] == "done"
    assert provider.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps({"type": "message", "request_id": "r", "message": "   "}),
        json.dumps({"type": "message", "request_id": "r"}),
        json.dumps({"type": "message", "message": "no request id"}),
        json.dumps([1, 2, 3]),
    ],
)
def test_malformed_messages_return_an_error_event_without_crashing(ws_client, payload):
    client, _, _ = ws_client
    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_text(payload)
        first = json.loads(websocket.receive_text())
        assert first["type"] == "error"
        assert first["code"] == "INVALID_MESSAGE"

        # The socket must still be usable afterwards.
        websocket.send_text(
            json.dumps({"type": "message", "request_id": "ok", "message": "What is a closure?"})
        )
        events = _collect(websocket)
        assert events[-1]["type"] == "done"


def test_overlong_message_is_rejected(ws_client, monkeypatch):
    client, _, _ = ws_client
    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_text(
            json.dumps({"type": "message", "request_id": "long", "message": "x" * 5000})
        )
        event = json.loads(websocket.receive_text())

    assert event["type"] == "error"
    assert event["code"] == "MESSAGE_TOO_LONG"


def test_rate_limit_error_is_reported_with_required_message(monkeypatch):
    provider = FakeProvider(error=RateLimitedError())
    monkeypatch.setattr(groq_module, "_provider", provider)
    monkeypatch.setattr(chat_service_module, "_service", _service(provider))

    with TestClient(create_app()) as client, client.websocket_connect("/ws/chat") as websocket:
        websocket.send_text(
            json.dumps({"type": "message", "request_id": "rl", "message": "Explain decorators"})
        )
        event = _terminal(websocket)

    assert event["type"] == "error"
    assert event["code"] == "RATE_LIMITED"
    assert event["message"] == "Traffic is high. Please wait 10 seconds before asking again."


def test_unexpected_provider_failure_is_scrubbed(monkeypatch):
    provider = FakeProvider(error=RuntimeError("boom at C:\\secret\\key.txt"))
    monkeypatch.setattr(groq_module, "_provider", provider)
    monkeypatch.setattr(chat_service_module, "_service", _service(provider))

    with TestClient(create_app()) as client, client.websocket_connect("/ws/chat") as websocket:
        websocket.send_text(
            json.dumps({"type": "message", "request_id": "x", "message": "Explain indexes"})
        )
        event = _terminal(websocket)

    assert event["type"] == "error"
    assert event["code"] == "PROVIDER_ERROR"
    assert "secret" not in event["message"].lower()
    assert "boom" not in event["message"].lower()


def test_missing_configuration_is_reported_safely(monkeypatch):
    provider = FakeProvider(
        error=ConfigurationError(
            "The AI provider is not configured. Add GROQ_API_KEY to backend/.env "
            "and restart the server."
        )
    )
    monkeypatch.setattr(groq_module, "_provider", provider)
    monkeypatch.setattr(chat_service_module, "_service", _service(provider))

    with TestClient(create_app()) as client, client.websocket_connect("/ws/chat") as websocket:
        websocket.send_text(
            json.dumps({"type": "message", "request_id": "cfg", "message": "Explain ORMs"})
        )
        event = _terminal(websocket)

    assert event["type"] == "error"
    assert event["code"] == "CONFIG_ERROR"
    assert "GROQ_API_KEY" in event["message"]
    assert "backend/.env" in event["message"]


def test_second_message_while_generating_is_rejected(monkeypatch):
    import asyncio

    class SlowProvider(FakeProvider):
        async def stream(self, messages):
            self.calls.append(messages)
            await asyncio.sleep(0.4)
            yield "done"

    provider = SlowProvider()
    monkeypatch.setattr(groq_module, "_provider", provider)
    monkeypatch.setattr(chat_service_module, "_service", _service(provider))

    with TestClient(create_app()) as client, client.websocket_connect("/ws/chat") as websocket:
        websocket.send_text(
            json.dumps({"type": "message", "request_id": "a", "message": "Explain threads"})
        )
        websocket.send_text(
            json.dumps({"type": "message", "request_id": "b", "message": "Explain processes"})
        )
        events = _collect(websocket)

    assert any(event["type"] == "error" and event["code"] == "BUSY" for event in events)
    assert len(provider.calls) == 1


def test_disconnect_during_generation_does_not_break_the_server(monkeypatch):
    import asyncio

    class SlowProvider(FakeProvider):
        async def stream(self, messages):
            await asyncio.sleep(0.3)
            yield "late token"

    provider = SlowProvider()
    monkeypatch.setattr(groq_module, "_provider", provider)
    monkeypatch.setattr(chat_service_module, "_service", _service(provider))

    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws/chat") as websocket:
            websocket.send_text(
                json.dumps({"type": "message", "request_id": "d", "message": "Explain caching"})
            )
            websocket.receive_text()  # first status event
        # Socket closed mid-generation; the app must still serve requests.
        assert client.get("/health").status_code == 200


def test_websocket_does_not_leak_configuration(ws_client):
    client, _, _ = ws_client
    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_text(
            json.dumps({"type": "message", "request_id": "q", "message": "hi"})
        )
        raw = " ".join(json.dumps(json.loads(websocket.receive_text())) for _ in range(3))

    for secret in ("test-key", "GROQ_API_KEY=", "api_key", ".env"):
        assert secret not in raw
