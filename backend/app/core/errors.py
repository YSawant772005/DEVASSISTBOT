"""Application error types with stable, user-safe codes.

Only :class:`AppError` messages ever reach the browser. Unexpected exceptions
are converted into a generic message and logged server-side.
"""

from __future__ import annotations

from dataclasses import dataclass

RATE_LIMIT_MESSAGE = "Traffic is high. Please wait 10 seconds before asking again."


@dataclass
class AppError(Exception):
    """An error that is safe to return to the client."""

    code: str
    message: str
    status_code: int = 400

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.message}"


# --- Upload / ingestion ------------------------------------------------------
class EmptyFileError(AppError):
    def __init__(self) -> None:
        super().__init__("EMPTY_FILE", "The uploaded file is empty.", 400)


class UnsupportedFileTypeError(AppError):
    def __init__(self, ext: str) -> None:
        super().__init__(
            "UNSUPPORTED_FILE_TYPE",
            f"Unsupported file type '{ext}'. Allowed types: .pdf, .txt, .md, .markdown.",
            400,
        )


class FileTooLargeError(AppError):
    def __init__(self, limit_mb: float) -> None:
        super().__init__(
            "FILE_TOO_LARGE",
            f"File must be smaller than {limit_mb:g} MB.",
            413,
        )


class ExtractionError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("EXTRACTION_FAILED", message, 422)


class NoTextError(AppError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            "NO_TEXT_CONTENT",
            message
            or (
                "No readable text was found in this file. Scanned or image-only "
                "PDFs are not supported."
            ),
            422,
        )


class EmbeddingUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "EMBEDDING_UNAVAILABLE",
            "The local embedding model is not available on the server. "
            "Check the backend logs and restart the server.",
            503,
        )


class IndexingError(AppError):
    def __init__(self, message: str = "The document could not be indexed.") -> None:
        super().__init__("INDEXING_FAILED", message, 500)


# --- Chat / provider ---------------------------------------------------------
class InvalidMessageError(AppError):
    def __init__(self, message: str = "The message must be a non-empty string.") -> None:
        super().__init__("INVALID_MESSAGE", message, 400)


class MessageTooLongError(AppError):
    def __init__(self, limit: int) -> None:
        super().__init__(
            "MESSAGE_TOO_LONG",
            f"Your message is too long. Please keep questions under {limit} characters.",
            400,
        )


class RateLimitedError(AppError):
    def __init__(self) -> None:
        super().__init__("RATE_LIMITED", RATE_LIMIT_MESSAGE, 429)


class ProviderAuthError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "PROVIDER_AUTH_ERROR",
            "The AI provider rejected the server credentials. "
            "Check GROQ_API_KEY in backend/.env.",
            502,
        )


class ProviderTimeoutError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "PROVIDER_TIMEOUT",
            "The AI provider took too long to respond. Please try again.",
            504,
        )


class ProviderUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "PROVIDER_UNAVAILABLE",
            "Could not reach the AI provider. Check your network connection and try again.",
            503,
        )


class ProviderError(AppError):
    def __init__(self, message: str = "The AI provider returned an unexpected error.") -> None:
        super().__init__("PROVIDER_ERROR", message, 502)


class ConfigurationError(AppError):
    def __init__(self, message: str = "The server is missing required configuration.") -> None:
        super().__init__("CONFIG_ERROR", message, 503)


class BusyError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "BUSY",
            "A response is already being generated on this connection. "
            "Wait for it to finish or stop it first.",
            409,
        )
