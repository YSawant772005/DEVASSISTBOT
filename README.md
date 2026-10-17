# DevAssist — Programming-Specific Assistant with RAG

DevAssist is a local, single-user programming assistant. You upload your own
documentation (PDF, TXT or Markdown), it is chunked and embedded on your machine,
and a Groq-hosted LLM answers your programming questions using the retrieved
excerpts, streaming the answer back over a WebSocket.

Everything runs on your machine except the final chat completion call:

```
Browser (Vue 3 SPA)                FastAPI (uvicorn, 1 worker)
├─ Documents / Examples views  ──►  POST /upload → extract → chunk(500/50)
└─ chat workspace              ──►  WS /ws/chat  → policy → retrieve top-3
                                                  → prompt → Groq (streamed)
```

- **No database, no auth, no Docker.** The document index and the chat history
  live in memory only.
- **No API key ever reaches the browser.** `GROQ_API_KEY` is read by the backend
  from `backend/.env` and used only server-side.
- **Real streaming.** Answers arrive token by token and can be stopped mid-stream.

---

## Contents

- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running the app](#running-the-app)
- [Project layout](#project-layout)
- [Configuration](#configuration)
- [HTTP API](#http-api)
- [WebSocket protocol](#websocket-protocol)
- [Testing](#testing)
- [Design decisions](#design-decisions)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Tool | Version used | Notes |
|------|--------------|-------|
| Python | 3.11 | 3.10+ should work; 3.11 is what this was built and tested on. |
| Node.js | 20+ | Built with Node 24 / npm 11. |
| Groq API key | — | Free keys at <https://console.groq.com/keys>. Without one the app still starts and reports `degraded` on `/health`; chat returns a safe `CONFIG_ERROR`. |

The first backend start downloads the embedding model
(`sentence-transformers/all-MiniLM-L6-v2`, ~90 MB) from Hugging Face and caches
it locally. After that, no network access is needed for retrieval.

---

## Setup

All commands are PowerShell, run from the repository root (`C:\Users\Dell\Chatbot`).

### 1. Backend

```powershell
cd backend

# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Create your local configuration from the template
Copy-Item .env.example .env
```

Open `backend\.env` and set your key:

```ini
GROQ_API_KEY=gsk_your_real_key_here
```

> If PowerShell blocks activation, run
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first.

### 2. Frontend

```powershell
cd ..\frontend
npm install
# Optional: only if your backend is not on http://localhost:8000
Copy-Item .env.example .env
```

---

## Running the app

You need two terminals.

**Terminal 1 — backend** (from `backend\`):

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

> **Run exactly one worker.** The document index is in-memory, so `--workers`
> must stay at its default of `1`. Multiple workers would give each process its
> own empty index.

**Terminal 2 — frontend** (from `frontend\`):

```powershell
npm run dev
```

Then open <http://localhost:5173>.

- Backend health: <http://localhost:8000/health>
- Interactive API docs: <http://localhost:8000/docs>

To try retrieval immediately, open the **Documents** workspace and upload
`backend\tests\fixtures\sample_notes.md` (drag-and-drop or the file picker), then
ask a question about it on the **Chat** page.

---

## Project layout

```
.
├─ backend/
│  ├─ app/
│  │  ├─ api/           upload.py (HTTP) and chat_ws.py (WebSocket) routers
│  │  ├─ core/          config.py (settings), errors.py (safe error codes), logging
│  │  ├─ prompts/       system_prompt.py — the single source of the guardrail
│  │  ├─ schemas/       Pydantic request/response and event models
│  │  ├─ services/      chunking, document, embedding, vector_store, policy,
│  │  │                 groq, chat — one responsibility each
│  │  └─ main.py        app factory, lifespan, CORS, /health
│  ├─ tests/            114 pytest tests (no network, no real Groq calls)
│  ├─ requirements.txt
│  └─ .env.example
├─ frontend/
│  ├─ src/
│  │  ├─ components/    TopNav, AppSidebar, ChatPanel, ContextPanel, dialogs, …
│  │  ├─ stores/        plain Vue reactivity stores (documents, chat, ui)
│  │  ├─ services/      api.ts (HTTP) and chatSocket.ts (WebSocket client)
│  │  ├─ utils/         markdown.ts (markdown-it + highlight.js), format.ts
│  │  ├─ style.css      Tailwind v4 design tokens + component classes
│  │  └─ App.vue
│  └─ tests/            48 Vitest tests
├─ scripts/
│  ├─ integration_check.py    end-to-end check against a running backend
│  └─ fake_provider_server.py runs the real app with a fake streaming provider
├─ design reference.png
├─ DevAssist_Chatbot_Implementation_Plan.docx   source-of-truth SRS
└─ PROJECT_STATUS.md                            build log & decisions
```

---

## Configuration

All backend settings live in `backend/.env` (see `backend/.env.example`).

| Variable | Default | Meaning |
|----------|---------|---------|
| `GROQ_API_KEY` | *(empty)* | **Required for chat.** Server-side only. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Any chat model your Groq account can access. |
| `GROQ_TEMPERATURE` | `0.2` | Sampling temperature. |
| `GROQ_MAX_OUTPUT_TOKENS` | `1024` | Maximum tokens per answer. |
| `GROQ_TIMEOUT_SECONDS` | `60` | Provider request timeout. |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | The only origin allowed by CORS. |
| `MAX_UPLOAD_BYTES` | `5242880` (5 MB) | Enforced while reading the upload stream. |
| `CHUNK_SIZE` | `500` | Characters per chunk. |
| `CHUNK_OVERLAP` | `50` | Overlap between consecutive chunks. |
| `TOP_K` | `3` | Retrieved chunks per question. |
| `MAX_CONTEXT_TOKENS` | `4000` | Approximate context budget (4 chars ≈ 1 token). |
| `MAX_QUESTION_CHARS` | `4000` | Rejected beyond this length. |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model. |
| `LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`. |

Frontend settings live in `frontend/.env` (see `frontend/.env.example`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend base URL. |
| `VITE_WS_URL` | *(derived)* | Explicit WebSocket URL; by default derived from the API base. |

Only public values belong in the frontend `.env`. Never put the Groq key there —
Vite inlines `VITE_*` variables into the shipped bundle.

---

## HTTP API

Base URL `http://localhost:8000`. Errors use a single shape:

```json
{ "status": "error", "code": "UNSUPPORTED_FILE_TYPE", "message": "…" }
```

### `GET /health`

Reports component readiness and index size.

```json
{
  "status": "ok",
  "version": "1.0.0",
  "model": "llama-3.3-70b-versatile",
  "groq_configured": true,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "embedding_loaded": true,
  "documents_indexed": 1,
  "chunks_indexed": 3,
  "limits": {
    "max_upload_bytes": 5242880,
    "chunk_size": 500,
    "chunk_overlap": 50,
    "top_k": 3,
    "max_context_tokens": 4000
  },
  "warnings": []
}
```

`status` is `ok` only when both the embedding model is loaded and a Groq key is
configured; otherwise it is `degraded` and `warnings` explains why.

### `POST /upload`

`multipart/form-data` with a single field named `file`. Accepted extensions:
`.pdf`, `.txt`, `.md`, `.markdown`. Maximum 5 MB, enforced while streaming.

```json
{
  "status": "success",
  "doc_id": "6ff74f52e74d4bd4b1ee4edab6e5b7a4",
  "filename": "sample_notes.md",
  "extension": ".md",
  "size_bytes": 981,
  "chunks_processed": 3,
  "characters_extracted": 981
}
```

Ingestion is atomic: nothing is registered unless extraction, chunking and
embedding all succeed.

### `GET /documents`

```json
{
  "documents": [
    {
      "doc_id": "6ff74f52e74d4bd4b1ee4edab6e5b7a4",
      "filename": "sample_notes.md",
      "extension": ".md",
      "size_bytes": 981,
      "chunks": 3,
      "uploaded_at": "2026-10-17T17:15:37.123456+00:00"
    }
  ],
  "total_documents": 1,
  "total_chunks": 3
}
```

### `DELETE /documents/{doc_id}` and `DELETE /documents`

Remove one document or clear the whole index. The FAISS index is rebuilt from the
surviving vectors; the response reports how many chunks were removed.

| Status | Code | When |
|--------|------|------|
| 400 | `EMPTY_FILE` | Zero-byte upload. |
| 400 | `UNSUPPORTED_FILE_TYPE` | Extension not in the allow-list. |
| 413 | `FILE_TOO_LARGE` | Over 5 MB (detected during the read). |
| 422 | `EXTRACTION_FAILED` | The file could not be parsed. |
| 422 | `NO_TEXT_CONTENT` | No readable text (for example a scanned PDF). |
| 503 | `EMBEDDING_UNAVAILABLE` | Embedding model not loaded. |

---

## WebSocket protocol

Endpoint: `ws://localhost:8000/ws/chat`

### Client → server

```json
{ "type": "message", "request_id": "req-1", "message": "How do I chunk text?" }
{ "type": "cancel",  "request_id": "req-1" }
```

### Server → client

Events carry the same `request_id` back. A successful answer is ordered
`status → sources → status → token × n → done`:

```json
{ "type": "status", "request_id": "req-1", "stage": "retrieving" }
{ "type": "sources", "request_id": "req-1", "sources": [
    { "doc_id": "6ff7…", "filename": "sample_notes.md", "chunk_index": 0,
      "score": 0.7296, "preview": "…240 characters…" } ] }
{ "type": "status", "request_id": "req-1", "stage": "generating" }
{ "type": "token", "request_id": "req-1", "token": "Based on the " }
{ "type": "done",  "request_id": "req-1" }
```

Failure is a single terminal event instead:

```json
{ "type": "error", "request_id": "req-1", "code": "RATE_LIMITED",
  "message": "Traffic is high. Please wait 10 seconds before asking again." }
```

Notes:

- `sources` is emitted only when chunks matched; it always precedes `token`.
- Tokens are grouped (~24 characters) rather than one frame per character.
- One generation runs per connection. A second `message` while one is in flight
  is rejected with code `BUSY`; the first keeps streaming.
- After `cancel`, the stream stops and no `done` event is sent.
- Malformed JSON or an invalid payload yields `INVALID_MESSAGE` without closing
  the socket.

| Error code | Meaning |
|------------|---------|
| `INVALID_MESSAGE` | Not valid JSON, or the payload failed validation. |
| `MESSAGE_TOO_LONG` | Question longer than `MAX_QUESTION_CHARS`. |
| `BUSY` | A generation is already running on this connection. |
| `CONFIG_ERROR` | `GROQ_API_KEY` missing on the server. |
| `PROVIDER_AUTH_ERROR` | Groq rejected the server credentials. |
| `PROVIDER_TIMEOUT` | The provider did not respond in time. |
| `PROVIDER_UNAVAILABLE` | The provider could not be reached. |
| `PROVIDER_ERROR` | Any other unexpected provider failure. |
| `RATE_LIMITED` | Provider rate limit (exact message in the table above). |

---

## Testing

### Backend — 114 pytest tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

Most of the suite uses fake embedding and provider adapters, so it never calls
Groq. One test (marked `real_model`) exercises the real Sentence Transformers
model; it runs as part of the default pass and is fast once the model is cached.
Select or skip it with the marker:

```powershell
pytest -m real_model        # only the real-model test
pytest -m "not real_model"  # skip it
```

### Frontend — 48 Vitest tests

```powershell
cd frontend
npm test          # single run
npm run test:watch
npm run typecheck # vue-tsc only
npm run build     # type-check + production bundle into dist/
```

### End-to-end integration check

`scripts/integration_check.py` drives a **running** backend over real HTTP and
WebSocket connections (health, upload, listing, deletion, streaming,
policy refusal, cancel, `BUSY`, malformed frames).

```powershell
# Terminal 1 — with your real key in backend\.env
cd backend; uvicorn app.main:app --port 8000

# Terminal 2
.\backend\.venv\Scripts\python.exe scripts\integration_check.py
```

To exercise the **full streaming** path without a Groq key, run the app with a
deterministic fake provider instead:

```powershell
# Terminal 1
cd backend
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe ..\scripts\fake_provider_server.py 8001

# Terminal 2
.\backend\.venv\Scripts\python.exe scripts\integration_check.py http://127.0.0.1:8001
```

---

## Design decisions

- **FAISS with normalized vectors** (`IndexFlatIP`) so inner product equals
  cosine similarity; scores are surfaced as real numbers in `[0, 1]`.
- **Rebuild-on-delete** keeps the index and its parallel metadata list in sync
  without a persistent store.
- **Prompt-only guardrail.** The single `SYSTEM_PROMPT` is the source of truth; a
  conservative keyword heuristic only short-circuits *clearly* off-topic text
  (for example "weather" with no technical signal) so it never needs a key.
- **Documents are untrusted data.** Excerpts are wrapped in delimiters and
  delivered as a separate user turn, never merged into the system message, so
  instructions inside an uploaded file cannot override the guardrail.
- **Safe markdown.** `markdown-it` runs with `html: false`; raw HTML from the
  model or a document is rendered as text, and `javascript:` links are dropped.
  Code blocks are highlighted locally with `highlight.js` and get a copy button.
- **Session-only history.** Conversations live in browser memory and are labelled
  as such; nothing is persisted server-side.

---

## Limitations

- **Transient storage.** The index is in RAM. Restarting the backend clears all
  documents, and chat history clears when the tab reloads.
- **Single worker, single shared index.** All users of one process share the same
  documents. Run one worker only.
- **Best-effort topical guardrail.** The keyword heuristic is deliberately
  narrow; the system prompt does the real work.
- **Scanned PDFs are not supported** — there is no OCR.
- **Live Groq streaming requires a key.** Without one the app starts in
  `degraded` mode and chat returns `CONFIG_ERROR`; the fake-provider server
  covers the streaming path in automated checks.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `/health` shows `groq_configured: false` | `backend\.env` is missing `GROQ_API_KEY` or still has the placeholder. Add a real key and restart. |
| Chat returns `CONFIG_ERROR` | Same as above. |
| Chat returns `PROVIDER_AUTH_ERROR` | The key is invalid or revoked; create a new one at <https://console.groq.com/keys>. |
| First start is slow | The embedding model is downloading and caching (~90 MB), one time only. |
| `EMBEDDING_UNAVAILABLE` on upload | The model failed to load; check the backend log, then restart. |
| Browser upload blocked by CORS | The frontend origin must match `FRONTEND_ORIGIN` (default `http://localhost:5173`). |
| Port 5173 already in use | Vite uses `strictPort`; stop the other process or change the port and update `FRONTEND_ORIGIN`. |
| `--workers 2` gives empty listings | Don't. The index is per-process; use a single worker. |
| Old documents still listed | The index is in memory; delete them in the UI or restart the backend. |

---

## Knowledge Bytes

A 20-part guided learning trail lives in [`knowledge bytes/`](knowledge%20bytes/). Each
document is a short read (roughly 45 seconds per byte) grounded in the actual source
files listed inside it, with cross-links between documents. Topics the repository does
not implement (cart, checkout, orders, wishlist, reviews, admin, IIS) are documented
explicitly as absences, mapped to the closest implemented equivalent — nothing is
invented.

| # | Document | Covers |
|---|----------|--------|
| 00 | [Project architecture](knowledge%20bytes/00-project-architecture.md) | Big picture: Vue 3 + FastAPI RAG chatbot, component map, request topology |
| 01 | [Project structure](knowledge%20bytes/01-project-structure.md) | Directory layout of backend and frontend, what lives where |
| 02 | [Application startup and request flow](knowledge%20bytes/02-application-startup-and-request-flow.md) | Lifespan, routing, the `/ws/chat` streaming protocol |
| 03 | [Data layer and database](knowledge%20bytes/03-data-layer-and-database.md) | In-memory FAISS store, embeddings, rebuild-on-delete (no DB) |
| 04 | [Models and viewmodels](knowledge%20bytes/04-models-and-viewmodels.md) | Pydantic schemas, TS types, store state shapes |
| 05 | [Product catalog](knowledge%20bytes/05-product-catalog.md) | *No catalog exists* — the document registry is the real equivalent |
| 06 | [Product details and variants](knowledge%20bytes/06-product-details-and-variants.md) | *Absent* — document detail (chunk metadata, sources panel) |
| 07 | [Search, filtering, sorting, pagination](knowledge%20bytes/07-search-filtering-sorting-pagination.md) | *Absent as e-commerce* — retrieval ranking, gallery/list filtering |
| 08 | [Cart and session management](knowledge%20bytes/08-cart-and-session-management.md) | *No cart* — session-only chat state and the busy/queue model |
| 09 | [Checkout and coupons](knowledge%20bytes/09-checkout-and-coupons.md) | *Absent* — the question-send pipeline end to end |
| 10 | [Authentication and authorization](knowledge%20bytes/10-authentication-and-authorization.md) | *None* — CORS origin allowlist, server-side key handling |
| 11 | [Orders and order history](knowledge%20bytes/11-orders-and-order-history.md) | *Absent* — in-memory conversation history |
| 12 | [Wishlist](knowledge%20bytes/12-wishlist.md) | *Absent* — localStorage theme as the only persistence |
| 13 | [Reviews and moderation](knowledge%20bytes/13-reviews-and-moderation.md) | *No reviews* — policy + prompt topic moderation, untrusted context |
| 14 | [Admin dashboard and management](knowledge%20bytes/14-admin-dashboard-and-management.md) | *No admin* — document management UI and `/health` diagnostics |
| 15 | [Frontend views, JavaScript, CSS](knowledge%20bytes/15-frontend-views-javascript-css.md) | Vue components, Pinia stores, Tailwind styling |
| 16 | [Validation, security, and error handling](knowledge%20bytes/16-validation-security-and-error-handling.md) | Validation map, error envelopes, implemented vs. missing controls |
| 17 | [Contact, newsletter, and static pages](knowledge%20bytes/17-contact-newsletter-and-static-pages.md) | *Absent* — welcome page, prompt gallery, settings dialog, HTML shell |
| 18 | [Testing and verification](knowledge%20bytes/18-testing-and-verification.md) | Backend pytest (fakes + `real_model`), frontend Vitest, integration script |
| 19 | [IIS deployment and troubleshooting](knowledge%20bytes/19-iis-deployment-and-troubleshooting.md) | *IIS not applicable* — uvicorn/Vite ports, CORS, cloudflared tunnels, playbook |

Suggested entry points: newcomers start at [00](knowledge%20bytes/00-project-architecture.md)
and follow the "Builds on" chain; developers fixing a specific area jump straight to the
matching document via the table above.
