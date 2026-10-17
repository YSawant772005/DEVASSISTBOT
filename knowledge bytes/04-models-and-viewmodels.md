# 04 — Models and ViewModels

**Overview:** Data crosses three representation layers in this project: backend domain records (dataclasses), wire contracts (Pydantic models), and frontend interfaces (TypeScript). There is no ORM and no classic ViewModel pattern — the closest equivalents are Pydantic response models on the server and the mirrored interfaces in `frontend/src/types/chat.ts`, plus the richer client-side `ChatMessage` shape that accumulates UI-only state.

**Scope:** Domain models, Pydantic request/response/event schemas, frontend types, serialization, and how data is mapped between layers. True ORM entities and MVVM ViewModels do not exist here and are explicitly noted as such.

**Prerequisites:** [03 — Data layer and database](03-data-layer-and-database.md).

**Important source files:**
- `backend/app/schemas/chat.py`, `backend/app/schemas/upload.py`
- `backend/app/services/vector_store.py`
- `frontend/src/types/chat.ts`
- `backend/app/services/chat_service.py`

---

### Byte 1: The three representation layers

**Builds on:** [03 — Data layer and database](03-data-layer-and-database.md), Byte 2

**Source files:** `backend/app/services/vector_store.py`, `backend/app/schemas/upload.py`, `frontend/src/types/chat.ts`

**In plain terms:**

Internal records describe data *inside* a process; Pydantic models describe data *on the wire*; TypeScript interfaces describe data *in the UI*. The same conceptual document appears once in each layer with different fields.

**The code:**

```python
# Internal (backend/app/services/vector_store.py)
@dataclass
class DocumentRecord:
    doc_id: str
    filename: str
    extension: str
    size_bytes: int
    chunk_count: int
    uploaded_at: str
    sequence: int = 0

# Wire (backend/app/schemas/upload.py)
class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    extension: str
    size_bytes: int
    chunks: int                      # renamed from chunk_count
    uploaded_at: str = Field(description="ISO-8601 UTC timestamp of successful indexing")
```

```typescript
// UI (frontend/src/types/chat.ts)
export interface UploadedDocument {
  doc_id: string
  filename: string
  extension: string
  size_bytes: number
  chunks: number
  uploaded_at: string
}
```

**What's happening:**

`GET /documents` in `backend/app/api/upload.py` manually maps each `DocumentRecord` → `DocumentInfo` field by field (that is the "data mapping" step — there is no automapper). The response serializes as JSON, and TypeScript consumes it through the identical interface.

**Why it matters:**

The manual mapping in `list_documents()` is where renames happen (`chunk_count` → `chunks`). Because the frontend mirrors the JSON exactly, an unrenamed field would surface as `undefined` in the UI rather than a compile error — the mirrors are conventions, not enforced links.

**Trace it further:** Byte 2 covers the domain records in full.

---

### Byte 2: Domain records (the closest thing to entities)

**Builds on:** Byte 1

**Source files:** `backend/app/services/vector_store.py`

**In plain terms:**

The only domain objects are three frozen-or-mutable dataclasses: `ChunkRecord` (one embedded text piece), `DocumentRecord` (one uploaded file), and `SearchHit` (a chunk plus its similarity score).

**The code:**

```python
@dataclass(frozen=True)
class ChunkRecord:
    doc_id: str
    filename: str
    chunk_index: int
    text: str

@dataclass
class SearchHit:
    record: ChunkRecord
    score: float
```

**What's happening:**

`ChunkRecord` is immutable (frozen) because chunks are never edited after indexing — only wholesale removed with their document. `SearchHit` pairs a record with a score produced by `search()`; `ChatService.to_sources()` then converts hits into the wire model `SourceReference`, clamping the score to `[0, 1]` and truncating text to a 240-character preview.

**Why it matters:**

These are plain dataclasses rather than Pydantic models because they never leave the process — no validation cost is paid until data actually crosses the wire. This is the layer an ORM would replace if the project gained a database (see [03 — Data layer and database](03-data-layer-and-database.md), Byte 6).

**Trace it further:** Byte 3 covers the WebSocket message contract.

---

### Byte 3: WebSocket protocol models

**Builds on:** Byte 1

**Source files:** `backend/app/schemas/chat.py`, `frontend/src/types/chat.ts`

**In plain terms:**

Every frame on `/ws/chat` is validated by a Pydantic model on arrival, and the frontend declares the same frames as a discriminated TypeScript union keyed on `type`.

**The code:**

```python
# backend/app/schemas/chat.py
class ClientChatMessage(BaseModel):
    type: Literal["message"] = "message"
    request_id: str = Field(min_length=1, max_length=128)
    message: str

class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    request_id: str
    token: str
```

```typescript
// frontend/src/types/chat.ts
export type ServerEvent =
  | ServerStatusEvent | ServerSourcesEvent | ServerTokenEvent
  | ServerDoneEvent | ServerErrorEvent
```

**What's happening:**

The `type: Literal[...]` fields make validation self-describing: a frame with `"type": "messag"` fails `model_validate` and the handler converts the `ValidationError` into an `INVALID_MESSAGE` event without closing the socket. `request_id` is capped at 128 characters to bound abuse. On the client, the `switch (event.type)` in `stores/chat.ts` exhaustively handles the union.

**Why it matters:**

The contract is *duplicated on purpose* in two languages. It is the single most important thing to keep in sync: adding a new event requires touching `backend/app/schemas/chat.py`, `frontend/src/types/chat.ts`, the handler switch in `stores/chat.ts`, and the backend `README.md` protocol table.

**Trace it further:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md), Byte 5 shows these frames in flight.

---

### Byte 4: ChatMessage — the client-side ViewModel

**Builds on:** Byte 3

**Source files:** `frontend/src/types/chat.ts`, `frontend/src/stores/chat.ts`

**In plain terms:**

`ChatMessage` is more than a mirror of server data: it blends wire-derived content with UI-only state (streaming status, stage, error object), which makes it the project's closest equivalent to a ViewModel.

**The code:**

```typescript
// frontend/src/types/chat.ts
export interface ChatMessage {
  id: string              // for assistant messages: the WS request_id
  role: Role              // 'user' | 'assistant'
  content: string         // grows as token events arrive
  createdAt: number
  status: MessageStatus    // 'streaming' | 'complete' | 'error' | 'stopped'
  sources?: SourceReference[]
  error?: { code: string; message: string }
  stage?: string          // 'retrieving' | 'generating' while waiting
}
```

**What's happening:**

The server never sends this shape — it sends discrete events. `stores/chat.ts` assembles them: `status` sets `stage`, `sources` fills `sources` and pins inspection, `token` appends to `content`, `done` flips `status` to `complete`, `error` stores the coded error. The `id` doubling as `request_id` is the join key that makes this assembly possible.

**Why it matters:**

This is the pattern to understand before touching any chat UI code: rendering reads `status`/`stage`/`content`, not raw events. A regression here (e.g., an event that never matches an id) silently drops tokens while the protocol itself stays healthy.

**Trace it further:** [11 — Orders and order history](11-orders-and-order-history.md) covers how these messages are grouped into conversations.

---

### Byte 5: Response models and the error envelope

**Builds on:** Byte 1

**Source files:** `backend/app/schemas/upload.py`, `backend/app/core/errors.py`, `backend/app/main.py`

**In plain terms:**

Successful HTTP responses are typed Pydantic models with a `status: "success"` discriminator; errors share one hand-built envelope with stable string codes.

**The code:**

```python
# backend/app/schemas/upload.py
class UploadResponse(BaseModel):
    status: Literal["success"] = "success"
    doc_id: str
    filename: str
    chunks_processed: int
    characters_extracted: int

# errors arrive as (backend/app/main.py exception handler)
{ "status": "error", "code": "UNSUPPORTED_FILE_TYPE", "message": "…" }
```

**What's happening:**

`response_model=UploadResponse` makes FastAPI validate and shape the outgoing JSON. The error side bypasses Pydantic response models: the `AppError` handler in `main.py` builds the dict directly from `exc.code` / `exc.message`. The frontend's `api.ts` reads exactly these two fields (`body.code`, `body.message`) and falls back to a generic message for non-JSON bodies (e.g., proxy HTML error pages).

**Why it matters:**

The `status` discriminator plus stable `code` strings are what makes error handling reliable on both ends — `stores/chat.ts` special-cases `INVALID_MESSAGE` and `MESSAGE_TOO_LONG` (they clear retry state) while leaving provider errors retryable. Codes must never be renamed without updating both sides.

**Trace it further:** [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) inventories every code.

---

### Byte 6: Where mapping happens (and where it does not)

**Builds on:** Byte 1, Byte 4

**Source files:** `backend/app/api/upload.py`, `backend/app/services/chat_service.py`, `frontend/src/services/api.ts`

**In plain terms:**

There are exactly three mapping sites: `list_documents()` (records → `DocumentInfo`), `to_sources()` (hits → `SourceReference`), and the frontend `request<T>()` (JSON → interface, unchecked at runtime).

**The code:**

```python
# backend/app/services/chat_service.py — hit → wire model with clamped score/preview
def to_sources(hits: list[SearchHit]) -> list[SourceReference]:
    return [
        SourceReference(
            doc_id=hit.record.doc_id,
            filename=hit.record.filename,
            chunk_index=hit.record.chunk_index,
            score=round(max(0.0, min(1.0, hit.score)), 4),
            preview=hit.record.text[:PREVIEW_CHARS].strip(),
        )
        for hit in hits
    ]
```

```typescript
// frontend/src/services/api.ts — runtime-unchecked cast
return (await response.json()) as T
```

**What's happening:**

Server-side mapping is explicit and defensive (scores clamped, previews truncated before leaving the process). Client-side "mapping" is a type assertion: `as T` trusts the server. Pydantic guarantees the server side of HTTP responses; the WebSocket side relies on `JSON.parse` plus the store's switch.

**Why it matters:**

Asymmetry to remember: a backend field rename breaks *silently* on the client (no runtime check), so contract changes need a coordinated frontend update and a run of `npm run typecheck` plus the protocol tests. `preview` also demonstrates data minimization — full chunk text never crosses the wire in a sources event, only a 240-character excerpt.

**Trace it further:** [18 — Testing and verification](18-testing-and-verification.md) shows the tests that pin these contracts.

---

## Continue learning

- [05 — Product catalog](05-product-catalog.md) — how document records reach the UI (the catalog equivalent).
- [11 — Orders and order history](11-orders-and-order-history.md) — conversation/message models on the client.
- [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) — what validates each model.
