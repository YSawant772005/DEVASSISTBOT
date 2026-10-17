"""Application configuration loaded from environment / backend/.env.

All secrets live here and are never imported by frontend code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Typed application settings.

    Values are read from real environment variables first, then from
    ``backend/.env`` so that ``uvicorn app.main:app`` works no matter which
    directory it is launched from.
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM provider (Groq) -------------------------------------------------
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    groq_temperature: float = Field(default=0.2, alias="GROQ_TEMPERATURE")
    groq_max_output_tokens: int = Field(default=1024, alias="GROQ_MAX_OUTPUT_TOKENS")
    groq_timeout_seconds: float = Field(default=60.0, alias="GROQ_TIMEOUT_SECONDS")

    # --- HTTP -----------------------------------------------------------------
    frontend_origin: str = Field(default="http://localhost:5173", alias="FRONTEND_ORIGIN")

    # --- Upload / RAG limits --------------------------------------------------
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")
    chunk_size: int = Field(default=500, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, alias="CHUNK_OVERLAP")
    top_k: int = Field(default=3, alias="TOP_K")
    max_context_tokens: int = Field(default=4000, alias="MAX_CONTEXT_TOKENS")
    max_question_chars: int = Field(default=4000, alias="MAX_QUESTION_CHARS")

    # --- Embeddings -----------------------------------------------------------
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL"
    )
    embedding_preload: bool = Field(default=True, alias="EMBEDDING_PRELOAD")

    # --- Misc ------------------------------------------------------------------
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("chunk_overlap")
    @classmethod
    def _validate_overlap(cls, value: int, info) -> int:
        size = info.data.get("chunk_size", 500)
        if value < 0:
            raise ValueError("CHUNK_OVERLAP must be >= 0")
        if value >= size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return value

    @field_validator("chunk_size", "top_k")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @property
    def groq_configured(self) -> bool:
        """True when a usable (non-placeholder) Groq key is present."""
        key = (self.groq_api_key or "").strip()
        if not key or key.lower().startswith("replace_with"):
            return False
        return True

    @property
    def health_warnings(self) -> list[str]:
        warnings: list[str] = []
        if not self.groq_configured:
            warnings.append(
                "GROQ_API_KEY is not configured. Chat requests will fail with a "
                "configuration error until backend/.env contains a valid key."
            )
        return warnings


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Clear the settings cache (used by tests)."""
    get_settings.cache_clear()
