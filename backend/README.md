# DevAssist Backend

FastAPI + uvicorn service for DevAssist. It extracts text from uploads, chunks
and embeds it locally, keeps a FAISS index in memory, and streams answers from
Groq over a WebSocket.

See the [root README](../README.md) for full setup and run instructions. This
file is the contract reference.

## Run

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Run **one worker only**: the index lives in process memory.

## Layers

| Module | Responsibility |
|--------|----------------|
| `app/api/upload.py` | `POST /upload`, `GET /documents`, `DELETE /documents[/{id}]` |
| `app/api/chat_ws.py` | `WS /ws/chat` streaming protocol, cancel, one in-flight generation |
| `app/core/config.py` | Typed settings from `backend/.env` (secrets stay here) |
| `app/core/errors.py` | `AppError` types with stable, user-safe codes |
| `app/prompts/system_prompt.py` | The single programming-only system prompt + prompt assembly |
| `app/services/chunking_service.py` | Deterministic 500/50 character chunking |
| `app/services/document_service.py` | Extension validation + PDF/TXT/MD text extraction |
| `app/services/embedding_service.py` | Lazy `all-MiniLM-L6-v2`, normalized 384-d vectors |
| `app/services/vector_store.py` | FAISS `IndexFlatIP` + parallel metadata; rebuild on delete |
| `app/services/policy_service.py` | Best-effort off-topic short-circuit (no provider needed) |
| `app/services/groq_service.py` | Streaming adapter; maps SDK errors to safe codes |
| `app/services/chat_service.py` | Policy → retrieval → prompt → stream orchestration |

## HTTP endpoints

- `GET /health` — component readiness, index size, effective limits, warnings.
- `POST /upload` — `multipart/form-data`, field `file`; `.pdf`/`.txt`/`.md`/`.markdown`, ≤ 5 MB.
- `GET /documents` — list indexed documents.
- `DELETE /documents/{doc_id}` — remove one document.
- `DELETE /documents` — clear the index.
- `GET /` — service banner; `GET /docs` — OpenAPI UI.

Errors are always `{"status": "error", "code": "...", "message": "..."}`.

## WebSocket protocol — `ws://localhost:8000/ws/chat`

### Client → server

```json
{ "type": "message", "request_id": "req-1", "message": "How do I chunk text?" }
{ "type": "cancel",  "request_id": "req-1" }
```

`request_id` is echoed on every server event. `message` is trimmed and rejected
when empty or longer than `MAX_QUESTION_CHARS`.

### Server → client

Success, in order (`sources` only when chunks matched):

```json
{ "type": "status",  "request_id": "req-1", "stage": "retrieving" }
{ "type": "sources", "request_id": "req-1", "sources": [
    { "doc_id": "…", "filename": "notes.md", "chunk_index": 0,
      "score": 0.7296, "preview": "…" } ] }
{ "type": "status",  "request_id": "req-1", "stage": "generating" }
{ "type": "token",   "request_id": "req-1", "token": "Based on the " }
{ "type": "done",    "request_id": "req-1" }
```

Failure, terminal:

```json
{ "type": "error", "request_id": "req-1", "code": "PROVIDER_TIMEOUT", "message": "…" }
```

The local policy refusal is delivered as normal `token` events followed by
`done` — it never reaches the provider.

### Guarantees

- `status` events always precede `sources`, `token` and `error`.
- `sources`, when present, always precede the first `token`.
- Tokens are grouped at ~24 characters.
- One generation per connection: a second `message` is rejected with `BUSY`
  while the first continues.
- `cancel` stops the stream and suppresses `done`; the socket stays open.
- Bad frames return `INVALID_MESSAGE` and do not close the socket.

### Error codes

`INVALID_MESSAGE`, `MESSAGE_TOO_LONG`, `BUSY`, `CONFIG_ERROR`,
`PROVIDER_AUTH_ERROR`, `PROVIDER_TIMEOUT`, `PROVIDER_UNAVAILABLE`,
`PROVIDER_ERROR`, `RATE_LIMITED`.

`RATE_LIMITED` uses the exact message
`"Traffic is high. Please wait 10 seconds before asking again."`

## Tests

```powershell
pytest                  # full suite, no Groq calls
pytest -m real_model    # only the real embedding-model test
pytest -m "not real_model"
```

End-to-end checks against a running server live in `../scripts/`.
