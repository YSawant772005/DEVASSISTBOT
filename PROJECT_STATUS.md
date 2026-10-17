# DevAssist Chatbot — Project Status

**Workspace:** `C:\Users\Dell\Chatbot`
**Source of truth:** `DevAssist_Chatbot_Implementation_Plan.docx` (SRS + architecture plan, v1.0)
**Build started:** 17 October 2026
**Last updated:** 17 October 2026

---

## 1. Requirements checklist (from the implementation plan)

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Vue 3 + Composition API + TypeScript + Tailwind frontend | DONE |
| 2 | Four-area app shell (Chat / Documents / Examples / Settings), compact top nav + collapsible left nav, optional context panel, responsive | DONE |
| 3 | Markdown rendering + syntax-highlighted code + copy buttons | DONE |
| 4 | Drag & drop + file picker upload with status/error states | DONE |
| 5 | Session-only chat history, welcome/empty state, stop generation | DONE |
| 6 | FastAPI async backend, Pydantic validation, layered services | DONE |
| 7 | `POST /upload`, `GET /health`, `WS /ws/chat` contracts (+ `GET`/`DELETE /documents`) | DONE |
| 8 | PDF / TXT / MD uploads, 5 MB server-enforced limit | DONE |
| 9 | 500-char chunks, 50-char overlap, metadata preserved | DONE |
| 10 | Local `sentence-transformers/all-MiniLM-L6-v2` embeddings | DONE |
| 11 | FAISS CPU in-memory index + parallel chunk metadata | DONE |
| 12 | Top-3 retrieval, context < 4000 tokens | DONE |
| 13 | Groq streaming inference, key server-side only | DONE (live call needs a key) |
| 14 | Programming-only system prompt + polite refusal | DONE |
| 15 | Rate-limit message: "Traffic is high. Please wait 10 seconds before asking again." | DONE |
| 16 | Token/done/error WebSocket events with `request_id` (+ status/sources, cancel, BUSY) | DONE |
| 17 | Backend tests (chunking, upload, retrieval, policy, ws, provider errors) | DONE — 114 passing |
| 18 | Frontend build + Vitest checks | DONE — 68 passing, build green |
| 19 | README, .env.example, troubleshooting, API/protocol docs | DONE |
| 20 | Transient storage documented (restart clears index, single worker) | DONE |

---

## 2. Locked design decisions (Phase 0)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector store | **FAISS CPU** (flat inner-product, normalized vectors = cosine) | Plan selects FAISS; no ChromaDB. |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2`, 384-dim | Required by SRS, loaded once at startup. |
| PDF parsing | `pypdf` | Plan selection; scanned PDFs rejected with a clear message. |
| LLM | Groq Python SDK, model from `GROQ_MODEL` (default `llama-3.3-70b-versatile`) | Never hard-coded in logic. |
| Storage scope | One shared in-memory collection, single uvicorn worker | Documented single-user/demo limitation. |
| Chunking | 500 chars / 50 overlap, deterministic, non-advancing guard | Faithful to SRS, unit tested. |
| Retrieval | top-k = 3, configurable; context budget enforced in `chat_service` | SRS requirement. |
| Chat guardrail | Central system prompt (prompt-only, best effort) + narrow off-topic keyword short-circuit | Plan prefers prompting over keyword blocking. |
| Transient state | Index + chat live in process/tab memory only | No DB, per SRS. |
| Delete strategy | Rebuild the FAISS index from surviving vectors | Keeps index and metadata in sync without a store. |
| Extension allow-list | `.pdf`, `.txt`, `.md`, `.markdown` | Plan lists PDF/TXT/MD; `.markdown` is a harmless alias. |

---

## 3. Architecture

```
Browser (Vue 3 SPA)
 ├─ DocumentsView / DocumentUploader  --- POST /upload (multipart) ---┐
 ├─ AppSidebar (nav + conversations, in-memory)                       │
 └─ ChatPanel / MessageList / ChatComposer --- WS /ws/chat -----------┤
                                                                     ▼
                                                     FastAPI (uvicorn, 1 worker)
                                                      ├─ api/upload.py  → document_service → chunking_service
                                                      │                                  → embedding_service → vector_store (FAISS)
                                                      └─ api/chat_ws.py → chat_service (policy, retrieval, prompt)
                                                                         → groq_service (streaming adapter)
                                                                         → WS status/sources/token/done/error
```

---

## 4. Phase tracker

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Workspace inspection, requirements lock, status doc | COMPLETE |
| 1 | Project foundation (backend + frontend scaffolding, health, CORS, config) | COMPLETE |
| 2 | Complete frontend UI (three-pane, responsive, dark-first) | COMPLETE |
| 3 | Document ingestion pipeline (validate → extract → chunk → embed → index) | COMPLETE |
| 4 | Retrieval-augmented generation (top-3, context budget, prompt assembly) | COMPLETE |
| 5 | WebSocket chat + streaming (status/sources/token/done/error, cancel, BUSY) | COMPLETE |
| 6 | Frontend/backend integration (CORS verified, real socket smoke test) | COMPLETE |
| 7 | Testing and bug fixing (114 backend + frontend Vitest + integration script) | COMPLETE |
| 8 | Security, performance, quality (XSS-safe markdown, safe errors, no secrets) | COMPLETE |
| 9 | Documentation and final verification (README, backend/frontend docs, status) | COMPLETE |
| A | **Redesign** — audit of the existing UI and change map | COMPLETE |
| B | Redesign — design system (palette tokens, Inter typography, spacing, motion, reduced-motion) | COMPLETE |
| C | Redesign — app shell (top nav + collapsible left nav, four workspaces, responsive drawers) | COMPLETE |
| D | Redesign — welcome homepage (badge, headline, four quick-start cards, KB guidance, recents) | COMPLETE |
| E | Redesign — chat workspace (compact header, borderless answers, editor-style code, composer) | COMPLETE |
| F | Redesign — Documents page (drag-drop, progress, searchable rows, confirmed delete) | COMPLETE |
| G | Redesign — context panel tabs (Sources / Follow-ups / Context) | COMPLETE |
| H | Redesign — motion + polish (fade/stagger, panel + drawer transitions, hover/focus) | COMPLETE |
| I | Redesign — verification (tests, build, integration, docs) | COMPLETE |

---

## 5. Verification evidence

| Check | Command | Result |
|-------|---------|--------|
| Backend tests | `pytest` (from `backend/`) | **114 passed** in 33.9 s |
| Frontend tests | `npm test` (from `frontend/`) | **68 passed** (5 files) |
| Production build | `npm run build` | Passes; JS 413 kB (149 kB gzip), CSS 42 kB (9 kB gzip) |
| Production preview | `vite preview` + `GET /` and assets | 200; `#app` present; JS/CSS referenced and served |
| Real embedding load | backend startup log | `Embedding model ready (dimension=384)` |
| Integration (no key) | `scripts/integration_check.py` vs live `uvicorn` :8000 | **All checks passed** (error path over a real socket) |
| Integration (streaming) | `fake_provider_server.py` :8001 + `integration_check.py` | **All checks passed** — real streaming, cancel, BUSY |
| CORS | `GET /health` with `Origin: http://localhost:5173` | Header echoed; unknown origin gets no ACAO header |
| Dev server | `npm run dev` + `GET /` | 200, `#app` and `/src/main.ts` served |

Integration check coverage (real HTTP + WebSocket, not the in-process test client):
health fields; upload + chunk count; `.exe` rejection; document listing; retrieval
source with real cosine score (0.7296); `status → sources → status → token×n → done`
ordering; incremental streaming; off-topic refusal without a provider call;
mid-stream cancel (29 chars vs 489 full, no `done`); `BUSY` on a second concurrent
request; `INVALID_MESSAGE` on a malformed frame; `DELETE` cleanup.

---

## 6. Environment

- Python 3.11.5 (`backend/.venv`): fastapi 0.143.3, faiss-cpu 1.15.1,
  sentence-transformers 5.7.0, groq 0.37.1, numpy 2.4.6, pypdf 5.9.0, pytest 9.1.1
- Node v24.20.0 / npm 11.19.0; Vite 8, Vue 3.5, TypeScript 6, Tailwind 4.3,
  Vitest 5, markdown-it 15, highlight.js 11, lucide-vue-next 1.0
- OS: Windows (win32), PowerShell
- Groq API key: supplied by the developer in `backend/.env` (never in the repo)

---

## 7. Known blockers / follow-ups

- **Live Groq call not exercised here.** No real `GROQ_API_KEY` exists in the
  workspace. The provider path is covered by mocked adapters
  (`tests/test_provider.py`) and by the fake-provider server
  (`scripts/fake_provider_server.py`), which drives the real streaming path end
  to end. To validate against Groq Cloud, add a key and run the documented
  integration check against `http://127.0.0.1:8000`.
- **`design reference.png` was not inspected.** The active model cannot read
  image input, so the UI was implemented from the written brief, not from the
  reference image. If the image encodes specific layout/colour requirements,
  those should be reviewed against the running UI.
- **No interactive browser inspection was performed.** The redesign is verified
  by the TypeScript build, the Vitest suite (including full-app mount smoke
  tests), the production build/preview serving, and the real backend integration
  script — but a human should still confirm the visuals at 1440 / 1024 / 768 /
  390 px. Exact manual steps are in section 9.

---

## 9. Manual visual verification (redesign)

Backend must be running (`uvicorn app.main:app --reload --port 8000`, single
worker). Then `cd frontend; npm run dev` and open `http://localhost:5173`.

1. **Welcome homepage** — an unindexed, fresh session shows the badge, the
   headline with a gradient phrase, four quick-start cards, the “No documents
   indexed yet” guidance and the onboarding tips. Click a card → the composer is
   filled and focused; send it → the welcome page is replaced by the conversation.
2. **Layouts** — resize to 1440, 1024, 768 and 390 px. Check: left nav collapses
   to a rail (desktop) / becomes a drawer (≤1023 px); the context panel opens
   inline ≥1280 px and as a right drawer below; prompt cards are 2-up ≥640 px and
   1-up on phones; nothing overflows horizontally.
3. **Upload + Documents** — Documents view: drag a PDF/TXT/MD (≤5 MB) onto the
   drop zone; watch the real progress bar, then the indexed row with size/chunk
   count. Search by filename; click the trash icon twice to delete; confirm the
   row disappears and, on the Chat page, the “Knowledge base · N documents”
   indicator updates.
4. **Chat** — ask a question that matches an uploaded doc; confirm sources appear
   as chips (`filename · ch N · score%`). Open the context panel: Sources lists
   real chunk excerpts and similarity, Follow-ups are labelled suggestions, and
   Context shows live runtime facts. Stop a long answer mid-stream → “Generation
   stopped”, no completion.
5. **Motion/a11y** — Tab through the nav, cards and composer (visible focus
   rings, Enter-to-send, Shift+Enter newline). Enable OS “reduce motion” and
   confirm transitions are disabled.

---

## 10. Outcome

All ten implementation phases and the nine redesign phases are complete. The
application builds, all 182 automated tests pass (114 backend + 68 frontend), and
both the error path and the full streaming path were verified against a genuinely
running server over real sockets.
