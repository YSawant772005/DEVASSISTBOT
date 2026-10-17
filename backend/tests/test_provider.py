"""Groq adapter error normalization (no real network calls)."""

from __future__ import annotations

import httpx
import pytest
from groq import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from app.core.config import Settings
from app.core.errors import (
    ConfigurationError,
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
    RATE_LIMIT_MESSAGE,
)
from app.services.groq_service import GroqProvider


def _provider() -> GroqProvider:
    return GroqProvider(Settings(EMBEDDING_PRELOAD=False, GROQ_API_KEY="test-key"))


def _http_response(status: int) -> httpx.Response:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return httpx.Response(status, request=request)


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (RateLimitError("rate limited", response=_http_response(429), body=None), RateLimitedError),
        (AuthenticationError("bad key", response=_http_response(401), body=None), ProviderAuthError),
        (PermissionDeniedError("no access", response=_http_response(403), body=None), ProviderAuthError),
        (APITimeoutError(request=httpx.Request("POST", "https://api.groq.com/")), ProviderTimeoutError),
        (APIConnectionError(request=httpx.Request("POST", "https://api.groq.com/")), ProviderUnavailableError),
        (NotFoundError("no model", response=_http_response(404), body=None), ProviderError),
        (BadRequestError("bad", response=_http_response(400), body=None), ProviderError),
    ],
)
def test_provider_errors_map_to_safe_app_errors(exception, expected):
    normalized = _provider()._normalize_error(exception)  # noqa: SLF001

    assert isinstance(normalized, expected)
    assert normalized.message
    assert "traceback" not in normalized.message.lower()
    assert "test-key" not in normalized.message


def test_rate_limit_uses_the_required_message():
    error = _provider()._normalize_error(
        RateLimitError("rate limited", response=_http_response(429), body=None)  # noqa: SLF001
    )

    assert error.code == "RATE_LIMITED"
    assert error.message == "Traffic is high. Please wait 10 seconds before asking again."
    assert error.message == RATE_LIMIT_MESSAGE


def test_unknown_error_becomes_generic_provider_error():
    error = _provider()._normalize_error(ValueError("internal detail: /secret/path"))  # noqa: SLF001

    assert isinstance(error, ProviderError)
    assert "/secret/path" not in error.message


async def test_missing_api_key_raises_configuration_error():
    provider = GroqProvider(Settings(EMBEDDING_PRELOAD=False, GROQ_API_KEY=""))

    assert provider.is_configured is False
    with pytest.raises(ConfigurationError):
        async for _ in provider.stream([{"role": "user", "content": "hi"}]):
            pass


def test_placeholder_key_is_not_treated_as_configured():
    provider = GroqProvider(
        Settings(EMBEDDING_PRELOAD=False, GROQ_API_KEY="replace_with_your_groq_api_key")
    )
    assert provider.is_configured is False
