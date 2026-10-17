"""``/ws/chat`` WebSocket handler implementing the streaming protocol.

Client messages:
    {"type": "message", "request_id": "<id>", "message": "<question>"}
    {"type": "cancel",  "request_id": "<id>"}

Server events: ``status``, ``sources``, ``token``, ``done``, ``error``.
See ``backend/README.md`` for the full contract.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.errors import (
    AppError,
    BusyError,
    InvalidMessageError,
    MessageTooLongError,
    ProviderError,
)
from app.schemas.chat import (
    ClientCancelMessage,
    ClientChatMessage,
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    StatusEvent,
    TokenEvent,
)
from app.services.chat_service import get_chat_service

logger = logging.getLogger(__name__)
router = APIRouter()

TOKEN_GROUP_SIZE = 24  # group small deltas to avoid one websocket frame per character
DEFAULT_REQUEST_ID = "server"


@router.websocket("/ws/chat")
async def chat_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = get_settings()
    logger.info("WebSocket connected.")

    generation: asyncio.Task[None] | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            request_id = DEFAULT_REQUEST_ID

            # --- parse & validate -----------------------------------------
            try:
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise InvalidMessageError()
                request_id = str(payload.get("request_id") or DEFAULT_REQUEST_ID)

                if payload.get("type") == "cancel":
                    ClientCancelMessage.model_validate(payload)
                    if generation and not generation.done():
                        generation.cancel()
                        logger.info("Cancelled request %s on client request.", request_id)
                    continue

                client_message = ClientChatMessage.model_validate(payload)
                question = client_message.message.strip()
                if not question:
                    raise InvalidMessageError()
                if len(question) > settings.max_question_chars:
                    raise MessageTooLongError(settings.max_question_chars)
            except ValidationError as exc:
                await _send_error(websocket, request_id, InvalidMessageError(_validation_message(exc)))
                continue
            except json.JSONDecodeError:
                await _send_error(
                    websocket, request_id, InvalidMessageError("Messages must be valid JSON.")
                )
                continue
            except AppError as exc:
                await _send_error(websocket, request_id, exc)
                continue

            # --- one in-flight generation per connection -------------------
            if generation and not generation.done():
                await _send_error(websocket, request_id, BusyError())
                continue

            generation = asyncio.create_task(_handle_question(websocket, question, request_id))
            generation.add_done_callback(_consume_task_result)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected.")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected WebSocket failure: %s", type(exc).__name__)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if generation and not generation.done():
            generation.cancel()
            try:
                await generation
            except (asyncio.CancelledError, Exception):  # pragma: no cover - shutdown path
                pass


def _consume_task_result(task: asyncio.Task[None]) -> None:
    """Absorb task exceptions (they are already reported to the client)."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:  # pragma: no cover - defensive
        logger.error("Generation task ended with %s", type(exc).__name__)


def _validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if errors:
        field = ".".join(str(part) for part in errors[0].get("loc", ()))
        return f"Invalid message payload ({field or 'body'}): {errors[0].get('msg', 'invalid')}"
    return "Invalid message payload."


async def _handle_question(websocket: WebSocket, question: str, request_id: str) -> None:
    service = get_chat_service()

    try:
        await _send_json(websocket, StatusEvent(request_id=request_id, stage="retrieving"))
        prepared = service.prepare(question)

        if prepared.sources:
            await _send_json(
                websocket, SourcesEvent(request_id=request_id, sources=prepared.sources)
            )

        await _send_json(websocket, StatusEvent(request_id=request_id, stage="generating"))

        buffer: list[str] = []
        buffered_chars = 0
        async for delta in service.stream(prepared):
            if not delta:
                continue
            buffer.append(delta)
            buffered_chars += len(delta)
            if buffered_chars >= TOKEN_GROUP_SIZE:
                await _send_json(
                    websocket, TokenEvent(request_id=request_id, token="".join(buffer))
                )
                buffer.clear()
                buffered_chars = 0
        if buffer:
            await _send_json(websocket, TokenEvent(request_id=request_id, token="".join(buffer)))

        await _send_json(websocket, DoneEvent(request_id=request_id))
        logger.info("Completed request %s (sources=%d).", request_id, len(prepared.sources))

    except asyncio.CancelledError:
        logger.info("Request %s cancelled by client.", request_id)
        raise
    except AppError as exc:
        logger.warning("Chat request %s failed: %s", request_id, exc.code)
        await _send_error(websocket, request_id, exc)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Chat request %s failed unexpectedly: %s", request_id, type(exc).__name__)
        await _send_error(websocket, request_id, ProviderError())


async def _send_json(websocket: WebSocket, event) -> None:
    await websocket.send_json(event.model_dump(mode="json"))


async def _send_error(websocket: WebSocket, request_id: str, error: AppError) -> None:
    """Send one terminal error event. Never leaks internal details."""
    try:
        await _send_json(
            websocket,
            ErrorEvent(request_id=request_id, code=error.code, message=error.message),
        )
    except Exception:  # pragma: no cover - client already gone
        logger.debug("Could not deliver error event for %s.", request_id)
