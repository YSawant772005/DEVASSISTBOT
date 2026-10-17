"""Groq provider adapter.

The Groq SDK is used only here. ``stream()`` yields plain text deltas and
normalizes provider failures into safe application errors that never contain
stack traces, headers or credentials.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from app.core.config import Settings, get_settings
from app.core.errors import (
    ConfigurationError,
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)

logger = logging.getLogger(__name__)


class GroqProvider:
    """Streaming chat-completion adapter for Groq Cloud."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None

    # -- lifecycle ---------------------------------------------------------
    @property
    def is_configured(self) -> bool:
        return self.settings.groq_configured

    def _get_client(self):
        if not self.is_configured:
            raise ConfigurationError(
                "The AI provider is not configured. Add GROQ_API_KEY to backend/.env "
                "and restart the server."
            )
        if self._client is None:
            from groq import AsyncGroq

            self._client = AsyncGroq(
                api_key=self.settings.groq_api_key,
                timeout=self.settings.groq_timeout_seconds,
                max_retries=0,  # rate limits are surfaced to the user, never retried in a tight loop
            )
        return self._client

    # -- inference ---------------------------------------------------------
    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Yield text deltas from the configured Groq model."""
        client = self._get_client()
        model = self.settings.groq_model

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=self.settings.groq_temperature,
                max_tokens=self.settings.groq_max_output_tokens,
                stream=True,
            )
        except Exception as exc:
            raise self._normalize_error(exc) from exc

        try:
            async for chunk in stream:
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                text = getattr(delta, "content", None)
                if text:
                    yield text
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    def _normalize_error(self, exc: Exception):
        """Map provider/SDK exceptions onto safe application errors."""
        name = type(exc).__name__
        status = getattr(exc, "status_code", None)

        try:
            import groq
        except Exception:  # pragma: no cover - groq is a hard dependency
            groq = None

        if groq is not None:
            rate_limit = getattr(groq, "RateLimitError", ())
            auth = getattr(groq, "AuthenticationError", ())
            permission = getattr(groq, "PermissionDeniedError", ())
            timeout = getattr(groq, "APITimeoutError", ())
            connection = getattr(groq, "APIConnectionError", ())
            bad_request = getattr(groq, "BadRequestError", ())
            not_found = getattr(groq, "NotFoundError", ())
            if rate_limit and isinstance(exc, rate_limit):
                return RateLimitedError()
            if auth and isinstance(exc, auth):
                return ProviderAuthError()
            if permission and isinstance(exc, permission):
                return ProviderAuthError()
            if timeout and isinstance(exc, timeout):
                return ProviderTimeoutError()
            if connection and isinstance(exc, connection):
                return ProviderUnavailableError()
            if not_found and isinstance(exc, not_found):
                return ProviderError(
                    "The configured Groq model is not available. Check GROQ_MODEL in backend/.env."
                )
            if bad_request and isinstance(exc, bad_request):
                return ProviderError(
                    "The AI provider rejected the request. Check GROQ_MODEL in backend/.env."
                )

        message = str(exc).lower()
        if status == 429 or "rate limit" in message:
            return RateLimitedError()
        if status in (401, 403) or "authentication" in message or "api key" in message:
            return ProviderAuthError()
        if "timeout" in message or "timed out" in message or name in {"APITimeoutError", "TimeoutException", "ReadTimeout"}:
            return ProviderTimeoutError()
        if status in (502, 503, 504) or "connection" in message or name in {"APIConnectionError", "ConnectError"}:
            return ProviderUnavailableError()

        logger.error("Unhandled provider error (%s): %s", name, exc)
        return ProviderError()


_provider: GroqProvider | None = None


def get_provider() -> GroqProvider:
    global _provider
    if _provider is None:
        _provider = GroqProvider()
    return _provider


def set_provider(provider: GroqProvider | None) -> None:
    """Replace the singleton (used by tests to inject a fake streaming provider)."""
    global _provider
    _provider = provider
