"""DevAssist FastAPI application.

Startup loads the local embedding model once and prepares the in-memory FAISS
index. All provider credentials stay on the server; nothing here is exposed to
the browser beyond the documented API contract.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import chat_router, upload_router
from app.core import configure_logging
from app.core.config import get_settings
from app.core.errors import AppError
from app.services.embedding_service import get_embedding_service
from app.services.vector_store import VectorStore, get_vector_store, set_vector_store

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("Starting DevAssist backend v%s", __version__)
    for warning in settings.health_warnings:
        logger.warning(warning)

    embedding = get_embedding_service()
    if settings.embedding_preload and not embedding.is_loaded:
        try:
            embedding.load()
        except AppError as exc:
            # The server still starts so /health and the UI can report the problem.
            logger.error("Embedding model unavailable: %s", exc.message)

    # Make sure the vector store matches the embedding dimension actually in use.
    set_vector_store(VectorStore(dimension=embedding.dimension))

    logger.info(
        "Configuration: model=%s, chunk=%d/%d, top_k=%d, max_upload=%d bytes, single_worker_only=True",
        settings.groq_model,
        settings.chunk_size,
        settings.chunk_overlap,
        settings.top_k,
        settings.max_upload_bytes,
    )
    logger.info("Startup complete. Embedding model loaded=%s", embedding.is_loaded)
    yield
    logger.info("Shutting down DevAssist backend.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DevAssist API",
        description=(
            "Programming-specific assistant with retrieval-augmented generation. "
            "Uploads are transient: the in-memory index is lost on restart."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(upload_router)
    app.include_router(chat_router)

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "code": exc.code, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "INVALID_REQUEST",
                "message": "The request payload was invalid.",
                "details": [
                    {"loc": list(err.get("loc", ())), "msg": err.get("msg", "")}
                    for err in exc.errors()
                ],
            },
        )

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"service": "DevAssist API", "version": __version__, "docs": "/docs"}

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, object]:
        """Local diagnostics: reports component readiness and index size."""
        current = get_settings()
        embedding = get_embedding_service()
        store = get_vector_store()
        warnings = list(current.health_warnings)
        if not embedding.is_loaded:
            warnings.append("Embedding model is not loaded; uploads and retrieval will fail.")

        status = "ok" if (current.groq_configured and embedding.is_loaded) else "degraded"
        return {
            "status": status,
            "version": __version__,
            "model": current.groq_model,
            "groq_configured": current.groq_configured,
            "embedding_model": current.embedding_model,
            "embedding_loaded": embedding.is_loaded,
            "documents_indexed": len(store.documents()),
            "chunks_indexed": store.size,
            "limits": {
                "max_upload_bytes": current.max_upload_bytes,
                "chunk_size": current.chunk_size,
                "chunk_overlap": current.chunk_overlap,
                "top_k": current.top_k,
                "max_context_tokens": current.max_context_tokens,
            },
            "warnings": warnings,
        }

    return app


app = create_app()
