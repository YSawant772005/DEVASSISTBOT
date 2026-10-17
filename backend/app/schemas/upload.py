"""Request/response schemas for document upload endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    status: Literal["success"] = "success"
    doc_id: str
    filename: str
    extension: str
    size_bytes: int
    chunks_processed: int
    characters_extracted: int


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    extension: str
    size_bytes: int
    chunks: int
    uploaded_at: str = Field(description="ISO-8601 UTC timestamp of successful indexing")


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    total_documents: int
    total_chunks: int


class DeleteResponse(BaseModel):
    status: Literal["success"] = "success"
    doc_id: str | None = None
    chunks_removed: int


class ErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    code: str
    message: str
