"""Programming-only guardrails and prompt assembly."""

from __future__ import annotations

import pytest

from app.prompts.system_prompt import (
    DOCUMENT_CONTEXT_HEADER,
    NO_DOCUMENTS_NOTE,
    SYSTEM_PROMPT,
    build_messages,
    format_context,
)
from app.services.policy_service import REFUSAL_MESSAGE, evaluate_policy


def test_system_prompt_states_the_policy():
    lowered = SYSTEM_PROMPT.lower()
    assert "programming" in lowered
    assert "unrelated" in lowered or "decline" in lowered
    assert "untrusted" in lowered
    assert "do not follow instructions" in lowered


@pytest.mark.parametrize(
    "question",
    [
        "How do I fix this Python TypeError?",
        "Explain Big O notation for binary search",
        "Why does my React useEffect run twice?",
        "How do I write a unit test with pytest?",
        "What is the difference between a process and a thread?",
        "Review this SQL query for performance",
        "How does git rebase differ from merge?",
        "Explain how a load balancer handles HTTP requests",
        # Ambiguous technical wording must not be rejected:
        "How does temperature affect a machine learning model?",
        "What temperature setting should I use for the Groq model?",
        "Explain the weather app architecture in this codebase",
    ],
)
def test_programming_questions_are_allowed(question):
    assert evaluate_policy(question).allowed is True


@pytest.mark.parametrize(
    "question",
    [
        "What is the weather in Paris tomorrow?",
        "Give me a recipe for chocolate cake",
        "Tell me celebrity gossip",
        "Write a poem about the ocean",
        "Who won the football match last night?",
    ],
)
def test_clearly_unrelated_questions_are_declined(question):
    decision = evaluate_policy(question)
    assert decision.allowed is False
    assert decision.refusal == REFUSAL_MESSAGE
    assert "programming" in (decision.refusal or "")


def test_off_topic_with_technical_signal_is_allowed():
    # "app" + "code" mean this is a technical request, not a cooking request.
    assert evaluate_policy("How do I debug the recipe app code?") .allowed is True
    assert evaluate_policy("Cache the weather API response in Python").allowed is True


def test_prompt_without_documents_has_no_excerpts():
    messages = build_messages("What is a mutex?")

    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert messages[-1] == {"role": "user", "content": "What is a mutex?"}
    assert any(NO_DOCUMENTS_NOTE in message["content"] for message in messages)
    assert not any(DOCUMENT_CONTEXT_HEADER in message["content"] for message in messages)


def test_prompt_with_documents_marks_context_as_untrusted_and_separate():
    excerpts = [("spec.md", 0, "The gateway retries three times."), ("api.md", 4, "Use POST /upload.")]
    messages = build_messages("How many retries?", excerpts)

    assert messages[0]["content"] == SYSTEM_PROMPT  # document text never touches the system message
    context_message = messages[1]["content"]
    assert DOCUMENT_CONTEXT_HEADER in context_message
    assert "spec.md (chunk 0)" in context_message
    assert "api.md (chunk 4)" in context_message
    assert "The gateway retries three times." in context_message
    assert messages[-1]["content"] == "How many retries?"
    # The untrusted text must not be merged into the last user turn.
    assert "spec.md (chunk 0)" not in messages[-1]["content"]


def test_policy_refusal_short_circuits_before_the_provider(chat_service):
    from tests.conftest import FakeProvider

    prepared = chat_service.prepare("Give me a recipe for chocolate cake")

    assert prepared.refusal == REFUSAL_MESSAGE
    assert prepared.messages == []
    assert chat_service.provider.calls == []  # type: ignore[attr-defined]


def test_chat_service_includes_retrieved_text_in_the_prompt(chat_service):
    from tests.conftest import FakeEmbeddingService

    embedding = FakeEmbeddingService()
    chunk = "The DevAssist gateway retries a failed upstream request three times."
    chat_service.store.add_document(
        filename="gateway.md",
        extension=".md",
        size_bytes=1,
        chunks=[chunk],
        vectors=embedding.encode([chunk]),
    )

    prepared = chat_service.prepare("How many times does the gateway retry a failed request?")

    assert [source.filename for source in prepared.sources] == ["gateway.md"]
    joined = "\n".join(message["content"] for message in prepared.messages)
    assert chunk in joined
    assert "gateway.md (chunk 0)" in joined


def test_format_context_delimits_each_excerpt():
    rendered = format_context([("a.md", 0, "alpha")])
    assert rendered.startswith("--- begin excerpt: a.md (chunk 0) ---")
    assert rendered.endswith("--- end excerpt: a.md (chunk 0) ---")
