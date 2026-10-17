# 02 — Application Startup and Request Flow

**Overview:** This document traces what happens when the backend boots, when the frontend loads, and what occurs step-by-step inside one real user action: asking a question that is answered from an uploaded document.

**Scope:** Application entry points, the `lifespan` startup hook, configuration loading, middleware, routing, the WebSocket request lifecycle, and one complete end-to-end example.

**Prerequisites:** [00 — Project architecture](00-project-architecture.md) and [01 — Project structure](01-project-structure.md).

**Important source files:**
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/api/chat_ws.py`
- `backend/app/services/chat_service.py`
- `frontend/src/main.ts`, `frontend/src/App.vue`
- `frontend/src/stores/chat.ts`

---

### Byte 1: Backend entry point and configuration loading

**Builds on:** [00 — Project architecture](00-project-architecture.md), Byte 2

**Source files:** `backend/app/main.py`, `backend/app/core/config.py`

**In plain terms:**

Running `uvicorn app.main:app` imports `backend/app/main.py`, which builds the FastAPI app via `create_app()` and reads all settings once through a cached `Settings` object.

**The code:**

```python
# backend/app/core/config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),          # backend/.env, resolved from the file path
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    frontend_origin: str = Field(default="http://localhost:5173", alias="FRONTEND_ORIGIN")
    chunk_size: int = Field(default=500, alias="CHUNK_SIZE")
    # …

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**What's happening:**

`pydantic-settings` reads real environment variables first, then falls back to `backend/.env` — and the `.env` path is computed from `config.py`'s own location (`parents[2]`), so `uvicorn app.main:app` works from any working directory. `@lru_cache` guarantees one shared `Settings` instance; `reset_settings_cache()` (used only by tests) clears it.

**Why it matters:**

Because settings are typed and validated, a bad value such as `CHUNK_OVERLAP=600` with `CHUNK_SIZE=500` fails *at startup* with a clear message instead of misbehaving later. `get_settings()` is also the seam tests use to swap configuration.

**Trace it further:** Byte 2 covers what happens after settings load.

---

### Byte 2: Startup lifespan — loading the model and index

**Builds on:** Byte 1

**Source files:** `backend/app/main.py`

**In plain terms:**

Before serving the first request, the app loads the embedding model, creates the empty vector index, and logs its effective configuration. If the model cannot load, the server *still starts* so diagnostics remain available.

**The code:**

```python
# backend/app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    # …
    embedding = get_embedding_service()
    if settings.embedding_preload and not embedding.is_loaded:
        try:
            embedding.load()
        except AppError as exc:
            # The server still starts so /health and the UI can report the problem.
            logger.error("Embedding model unavailable: %s", exc.message)

    # Make sure the vector store matches the embedding dimension actually in use.
    set_vector_store(VectorStore(dimension=embedding.dimension))
    yield
```

**What's happening:**

Three things happen in order: logging is configured, `EmbeddingService.load()` downloads (first run only, ~90 MB) and loads `all-MiniLM-L6-v2`, and a fresh `VectorStore` singleton is created with the model's actual dimension (384 for the default model). The `yield` marks the end of startup; the log line after it runs at shutdown.

**Why it matters:**

This is where the "single worker" rule comes from — the index and model are process-global singletons. It is also why the app degrades gracefully: if the model fails to load, `/health` reports `embedding_loaded: false` and uploads return `EMBEDDING_UNAVAILABLE` instead of the server refusing to boot.

**Trace it further:** Byte 3 covers the middleware and routes registered by `create_app()`.

---

### Byte 3: Middleware, routes, and error handlers

**Builds on:** Byte 2

**Source files:** `backend/app/main.py`

**In plain terms:**

`create_app()` registers exactly one middleware (CORS), two routers (documents and chat), two exception handlers (safe app errors and validation errors), and two system routes (`/` and `/health`).

**The code:**

```python
# backend/app/main.py
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
```

**What's happening:**

CORS is locked to a single origin (`FRONTEND_ORIGIN`, default `http://localhost:5173`) with credentials disabled and only the app's four HTTP methods allowed. The `AppError` handler is the funnel that turns every domain error (`EMPTY_FILE`, `FILE_TOO_LARGE`, `PROVIDER_TIMEOUT`, …) into the single documented error envelope `{"status": "error", "code": ..., "message": ...}`.

**Why it matters:**

CORS is the *only* request boundary in this application (there is no authentication — see [10 — Authentication and authorization](10-authentication-and-authorization.md)). If you move the frontend to another port, chat and uploads are blocked until `FRONTEND_ORIGIN` matches — a classic first-run failure.

**Trace it further:** Byte 4 moves to the frontend entry point.

---

### Byte 4: Frontend boot sequence

**Builds on:** Byte 3

**Source files:** `frontend/src/main.ts`, `frontend/src/App.vue`, `frontend/src/config.ts`

**In plain terms:**

The SPA boots in four steps: mount `App.vue`, restore the theme, fetch the document list, and probe backend health — all on first render.

**The code:**

```typescript
// frontend/src/App.vue
onMounted(() => {
  ui.initTheme()                 // read localStorage 'devassist-theme'
  void documents.refresh()        // GET /documents
  void documents.checkHealth()    // GET /health
  document.addEventListener('keydown', onKeydown)  // Escape closes panels
})
```

**What's happening:**

`initTheme()` defaults to dark and applies `html.light`/`html.dark` classes. `refresh()` populates the document count shown in the sidebar and chat header; `checkHealth()` sets the connection pill to `online`, `degraded`, or `offline` — it never throws, so a dead backend leaves the UI usable. Backend URLs come from `config.ts`: `API_BASE_URL` defaults to an empty string, meaning *same-origin* requests, which the Vite dev server proxies to `127.0.0.1:8000`.

**Why it matters:**

Health probing at mount is why the UI can honestly say "Disconnected" before you send anything. The same-origin default is why the app works in dev without a `frontend/.env` file at all.

**Trace it further:** Byte 5 follows one user action through both processes.

---

### Byte 5: End-to-end trace — asking a question

**Builds on:** Byte 4

**Source files:** `frontend/src/components/ChatComposer.vue`, `frontend/src/stores/chat.ts`, `backend/app/api/chat_ws.py`, `backend/app/services/chat_service.py`

**In plain terms:**

Pressing Enter on a question crosses seven hops: composer → chat store → WebSocket client → WS handler → `ChatService.prepare()` → `ChatService.stream()` → events back to the message bubble.

**The code:**

```typescript
// frontend/src/stores/chat.ts — sendMessage()
const requestId = uid('msg')
// … push user message + empty assistant message with id = requestId
await getSocket().send({ type: 'message', request_id: requestId, message: question })
```

```python
# backend/app/api/chat_ws.py — the server half
async def _handle_question(websocket: WebSocket, question: str, request_id: str) -> None:
    service = get_chat_service()
    await _send_json(websocket, StatusEvent(request_id=request_id, stage="retrieving"))
    prepared = service.prepare(question)
    if prepared.sources:
        await _send_json(websocket, SourcesEvent(request_id=request_id, sources=prepared.sources))
    await _send_json(websocket, StatusEvent(request_id=request_id, stage="generating"))
    async for delta in service.stream(prepared):
        # … buffer deltas, flush every ~24 characters as a token event
    await _send_json(websocket, DoneEvent(request_id=request_id))
```

**What's happening:**

The assistant message's client-side `id` *is* the `request_id`, so every server event (`status`, `sources`, `token`, `done`, `error`) is routed to exactly one message in the store. Server-side, `prepare()` runs the policy check, retrieves the top-3 chunks, and assembles the prompt; `stream()` yields either the local refusal text or Groq's deltas. The handler buffers deltas and flushes a `token` event roughly every 24 characters to avoid one WebSocket frame per character.

**Why it matters:**

This single flow *is* the product. If any hop breaks, the failure mode is visible and specific: no backend → `CONNECTION_FAILED` on the message; no API key → `CONFIG_ERROR` event; off-topic question → refusal streamed as ordinary tokens followed by `done` (never an error).

**Trace it further:** [09 — Checkout and coupons](09-checkout-and-coupons.md) documents this same pipeline as the "closest equivalent" to a checkout flow; [11 — Orders and order history](11-orders-and-order-history.md) covers how the result is stored.

---

### Byte 6: Startup commands and process roles

**Builds on:** Byte 5

**Source files:** `README.md`, `frontend/package.json`, `frontend/vite.config.ts`

**In plain terms:**

Two terminals start the app: `uvicorn app.main:app --reload --port 8000` for the backend and `npm run dev` for the frontend. A third (optional) layer of cloudflared tunnels exposes the demo publicly.

**The code:**

```powershell
# Terminal 1 (backend/)
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Terminal 2 (frontend/)
npm run dev        # http://localhost:5173, strictPort
```

**What's happening:**

Vite's dev server runs on the fixed port 5173 (`strictPort: true`) and proxies `/health`, `/upload`, `/documents`, and `/ws` (WebSocket upgrade included) to `VITE_DEV_BACKEND` — default `http://127.0.0.1:8000`. For a demo, `start-demo.ps1`/`start-demo.bat` launch cloudflared Quick Tunnels in front of the backend (8000) and the production preview (4173).

**Why it matters:**

`--reload` is fine for development because reload restarts a *single* worker and clears the in-memory index — a surprise many first-time users hit ("my documents vanished"). Production-ish runs use `npm run build` + `npm run preview` (see [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md)).

**Trace it further:** [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md) covers ports, tunnels, and failure recovery.

---

## Continue learning

- [03 — Data layer and database](03-data-layer-and-database.md) — what `prepare()` reads from.
- [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) — every check the request passes through.
- [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md) — running it outside your machine.
