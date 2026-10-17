"""``POST /upload`` plus document listing/removal endpoints.

Ingestion is atomic: nothing is registered in the vector store unless
extraction, chunking and embedding all succeed.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, UploadFile

from app.core.errors import (
    AppError,
    EmptyFileError,
    FileTooLargeError,
    IndexingError,
    NoTextError,
)
from app.schemas.upload import (
    DeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    UploadResponse,
)
from app.services.chunking_service import chunk_text
from app.services.document_service import extract_text, validate_filename
from app.services.embedding_service import get_embedding_service
from app.services.vector_store import get_vector_store
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])

READ_CHUNK_BYTES = 1024 * 1024  # 1 MiB streaming reads for accurate size enforcement


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    """Read the upload while enforcing the byte limit as data arrives."""
    buffer = bytearray()
    while True:
        block = await file.read(READ_CHUNK_BYTES)
        if not block:
            break
        buffer.extend(block)
        if len(buffer) > limit:
            raise FileTooLargeError(limit / (1024 * 1024))
    return bytes(buffer)


@router.post(
    "/upload",
    response_model=UploadResponse,
    responses={400: {"description": "Invalid file"}, 413: {"description": "File too large"}},
)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    settings = get_settings()
    filename = (file.filename or "").strip() or "unnamed"
    extension = validate_filename(filename)

    data = await _read_limited(file, settings.max_upload_bytes)
    if not data:
        raise EmptyFileError()

    text = extract_text(filename, data)
    chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise NoTextError("The file did not contain enough text to index.")

    embedding = get_embedding_service()
    try:
        vectors = embedding.encode(chunks)
    except AppError:
        raise
    except Exception as exc:  # pragma: no cover - unexpected model failure
        logger.error("Embedding failed for '%s': %s", filename, type(exc).__name__)
        raise IndexingError("The document could not be embedded for indexing.") from exc

    store = get_vector_store()
    try:
        doc_id = store.add_document(
            filename=filename,
            extension=extension,
            size_bytes=len(data),
            chunks=chunks,
            vectors=vectors,
        )
    except AppError:
        raise
    except Exception as exc:
        logger.error("Indexing failed for '%s': %s", filename, type(exc).__name__)
        raise IndexingError() from exc

    logger.info(
        "Upload complete: '%s' (%d bytes, %d chunks, doc_id=%s)",
        filename,
        len(data),
        len(chunks),
        doc_id,
    )
    return UploadResponse(
        doc_id=doc_id,
        filename=filename,
        extension=extension,
        size_bytes=len(data),
        chunks_processed=len(chunks),
        characters_extracted=len(text),
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents() -> DocumentListResponse:
    store = get_vector_store()
    documents = [
        DocumentInfo(
            doc_id=doc.doc_id,
            filename=doc.filename,
            extension=doc.extension,
            size_bytes=doc.size_bytes,
            chunks=doc.chunk_count,
            uploaded_at=doc.uploaded_at,
        )
        for doc in store.documents()
    ]
    return DocumentListResponse(
        documents=documents,
        total_documents=len(documents),
        total_chunks=sum(doc.chunks for doc in documents),
    )


@router.delete("/documents/{doc_id}", response_model=DeleteResponse)
async def delete_document(doc_id: str) -> DeleteResponse:
    removed = get_vector_store().remove_document(doc_id)
    logger.info("Removed document %s (%d chunks).", doc_id, removed)
    return DeleteResponse(doc_id=doc_id, chunks_removed=removed)


@router.delete("/documents", response_model=DeleteResponse)
async def delete_all_documents() -> DeleteResponse:
    removed = get_vector_store().clear()
    logger.info("Cleared all documents (%d chunks).", removed)
    return DeleteResponse(doc_id=None, chunks_removed=removed)
