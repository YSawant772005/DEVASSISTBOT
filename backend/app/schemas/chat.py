"""Schemas for the ``/ws/chat`` WebSocket protocol.

Client -> server:
    {"type": "message", "request_id": "<id>", "message": "<question>"}

Server -> client (in order):
    {"type": "sources", "request_id": "<id>", "sources": [...]}   # only when chunks matched
    {"type": "token",   "request_id": "<id>", "token": "<delta>"} # repeated
    {"type": "done",    "request_id": "<id>"}                     # terminal, success
    {"type": "error",   "request_id": "<id>", "code": "...", "message": "..."}  # terminal, failure
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ClientChatMessage(BaseModel):
    type: Literal["message"] = "message"
    request_id: str = Field(min_length=1, max_length=128)
    message: str


class ClientCancelMessage(BaseModel):
    """Ask the server to stop the in-flight generation on this connection."""

    type: Literal["cancel"] = "cancel"
    request_id: str = Field(min_length=1, max_length=128)


class SourceReference(BaseModel):
    """A retrieved chunk that informed the answer."""

    doc_id: str
    filename: str
    chunk_index: int
    score: float = Field(description="Cosine similarity in [0, 1] from the FAISS index")
    preview: str = Field(description="Truncated chunk text for display")


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    request_id: str
    token: str


class SourcesEvent(BaseModel):
    type: Literal["sources"] = "sources"
    request_id: str
    sources: list[SourceReference]


class StatusEvent(BaseModel):
    type: Literal["status"] = "status"
    request_id: str
    stage: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    request_id: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    request_id: str
    code: str
    message: str
