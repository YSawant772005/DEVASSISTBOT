# 01 — Project Structure

**Overview:** The repository is a monorepo with two applications (`backend/`, `frontend/`), a `scripts/` folder for end-to-end checks, and root-level planning/status documents. This document is a guided tour: what each folder and important file is responsible for, and where to find a given feature.

**Scope:** Repository layout, the responsibility of each significant folder/file, and "where do I change X?" pointers. It does not explain the code itself — that is the job of the topic-specific documents.

**Prerequisites:** [00 — Project architecture](00-project-architecture.md).

**Important source files:**
- `backend/app/` (entire application package)
- `frontend/src/` (entire SPA source)
- `scripts/integration_check.py`, `scripts/fake_provider_server.py`
- `README.md`, `PROJECT_STATUS.md`

---

### Byte 1: Top-level layout

**Builds on:** [00 — Project architecture](00-project-architecture.md), Byte 4

**Source files:** `README.md`, `.gitignore`

**In plain terms:**

The repository root holds the two apps, shared scripts, demo launchers, planning documents, and generated logs.

**The code:**

```text
.
├─ backend/          FastAPI app + pytest suite + .venv
├─ frontend/         Vue 3 SPA + Vitest suite + node_modules
├─ scripts/          integration_check.py, fake_provider_server.py
├─ start-demo.bat / start-demo.ps1   cloudflared tunnel launchers
├─ README.md         setup, API contract, troubleshooting
├─ PROJECT_STATUS.md build log & requirement checklist
└─ DevAssist_Chatbot_Implementation_Plan.docx   source-of-truth SRS
```

**What's happening:**

`*.log` files (`backend-live.log`, `frontend-tunnel.log`, …) are run artifacts and are ignored by `.gitignore` (`*.log`). `.gitignore` also blocks `.env` files while whitelisting `.env.example` templates, which is the repository's secret-hygiene rule.

**Why it matters:**

Knowing which files are source (never edit casually), which are generated (safe to delete), and which are documentation keeps changes focused. `DevAssist_Chatbot_Implementation_Plan.docx` is the original specification if you need the "why" behind a requirement.

**Trace it further:** Byte 2 zooms into `backend/`.

---

### Byte 2: The backend package layout

**Builds on:** Byte 1

**Source files:** `backend/app/main.py`, `backend/app/api/__init__.py`, `backend/app/core/__init__.py`

**In plain terms:**

`backend/app/` is a layered Python package: `api/` holds routers, `services/` holds logic, `schemas/` holds Pydantic models, `core/` holds configuration/errors/logging, `prompts/` holds the system prompt, and `main.py` is the application factory.

**The code:**

```text
backend/
├─ app/
│  ├─ api/         upload.py (HTTP), chat_ws.py (WebSocket)
│  ├─ core/        config.py, errors.py, logging helper
│  ├─ prompts/     system_prompt.py — the guardrail text
│  ├─ schemas/     chat.py, upload.py (Pydantic contracts)
│  ├─ services/    chunking, document, embedding, vector_store,
│  │               policy, groq, chat — one responsibility each
│  └─ main.py      create_app(), lifespan, CORS, /health
├─ tests/          pytest suite + fixtures/
├─ requirements.txt
└─ pytest.ini
```

**What's happening:**

Import direction is strictly downward: `main.py` → `api/` → `services/` → `core/`. `services/` never imports `api/`, which is what lets tests construct a `ChatService` with fake collaborators directly (see `backend/tests/conftest.py`).

**Why it matters:**

When you need to change behavior, the folder tells you where: endpoint contract → `api/`; business rule → `services/`; a config knob → `core/config.py`; the refusal wording → `prompts/system_prompt.py`.

**Trace it further:** [03 — Data layer and database](03-data-layer-and-database.md) covers `services/vector_store.py`.

---

### Byte 3: Service-per-responsibility rule

**Builds on:** Byte 2

**Source files:** `backend/app/services/`

**In plain terms:**

Each file in `backend/app/services/` owns exactly one concern, and they compose in a fixed pipeline order for chat.

**The code:**

```text
document_service.py    validate extension, extract text (PDF/TXT/MD)
chunking_service.py    split text into 500-char overlapping chunks
embedding_service.py   turn text into normalized 384-d vectors
vector_store.py        FAISS index + chunk metadata, in memory
policy_service.py      off-topic short-circuit (no provider needed)
groq_service.py        streaming LLM adapter + error normalization
chat_service.py        policy → retrieve → prompt → stream orchestration
```

**What's happening:**

The upload path uses the first four; the chat path uses `policy_service`, `embedding_service`, `vector_store`, `groq_service`, and `chat_service` glues them together. Each service file also exposes `get_x()` / `set_x()` singleton helpers — the `set_*` functions are the injection points used by tests and by `scripts/fake_provider_server.py`.

**Why it matters:**

Because each service is small and injectable, the test suite can swap the embedding model for a deterministic fake and never touch Groq (see [18 — Testing and verification](18-testing-and-verification.md)).

**Trace it further:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md) shows these services being wired at boot.

---

### Byte 4: The frontend source layout

**Builds on:** Byte 1

**Source files:** `frontend/src/`, `frontend/index.html`

**In plain terms:**

`frontend/src/` separates concerns into `components/` (rendering), `stores/` (state), `services/` (network), `types/` (shared interfaces), `utils/`, `composables/`, `data/`, plus `style.css` and `config.ts`.

**The code:**

```text
frontend/src/
├─ components/      TopNav, AppSidebar, ChatPanel, MessageList, MessageBubble,
│                   ChatComposer, DocumentsView, DocumentUploader, DocumentList,
│                   PromptGallery, ContextPanel, SourcePanel, FollowUpPanel,
│                   SettingsDialog, WelcomeState, MarkdownMessage, ui/ProgressBar
├─ stores/          chat.ts, documents.ts, ui.ts (plain Vue reactivity)
├─ services/        api.ts (HTTP), chatSocket.ts (WebSocket client)
├─ types/chat.ts    interfaces mirroring the backend contract
├─ utils/           markdown.ts, format.ts
├─ composables/     useMediaQuery.ts (breakpoints + auto-scroll)
├─ data/            promptCards.ts (static starter prompts)
├─ config.ts        public runtime configuration
├─ style.css        Tailwind v4 design tokens + component classes
├─ App.vue          application shell / view switching
└─ main.ts          entry point
```

**What's happening:**

There is no `router/` folder because the app has no client-side router: `App.vue` renders `ChatPanel`, `DocumentsView`, or `PromptGallery` based on `ui.state.view`. `types/chat.ts` mirrors the backend's Pydantic contracts (`HealthResponse`, `UploadResponse`, `ServerEvent`, …) so TypeScript catches drift.

**Why it matters:**

A change to the chat message shape must be made twice — in `backend/app/schemas/chat.py` and `frontend/src/types/chat.ts`. Keeping the mirrors aligned is a recurring maintenance task; the type-check step in `npm run build` validates the frontend half.

**Trace it further:** [15 — Frontend views, JavaScript, and CSS](15-frontend-views-javascript-css.md) explains how these files collaborate at runtime.

---

### Byte 5: Tests and scripts folders

**Builds on:** Byte 2, Byte 4

**Source files:** `backend/tests/`, `frontend/tests/`, `scripts/integration_check.py`, `scripts/fake_provider_server.py`

**In plain terms:**

There are three verification layers: backend unit/integration tests (pytest), frontend unit tests (Vitest), and a standalone end-to-end script that drives a *running* backend over real sockets.

**The code:**

```text
backend/tests/    test_chunking, test_document_service, test_upload,
                  test_retrieval, test_policy_and_prompt, test_chat_ws,
                  test_provider, test_health, test_real_embeddings,
                  conftest.py (fakes + fixtures), fixtures/sample_notes.md
frontend/tests/   chat.spec.ts, components.spec.ts, format.spec.ts,
                  markdown.spec.ts, navigation.spec.ts
scripts/          integration_check.py, fake_provider_server.py
```

**What's happening:**

`conftest.py` installs a deterministic bag-of-words fake embedding so unit tests are fast and offline; exactly one backend test (marked `real_model`) exercises the real Sentence Transformers model. `scripts/fake_provider_server.py` runs the real app with a canned streaming provider so the full WebSocket path can be tested without a Groq key.

**Why it matters:**

Understanding this split tells you which check to run: change a pure function → pytest; change a component → Vitest; change the wire protocol → `integration_check.py` against a live server.

**Trace it further:** [18 — Testing and verification](18-testing-and-verification.md) documents each suite and its verified results.

---

### Byte 6: Configuration and generated files

**Builds on:** Byte 1

**Source files:** `frontend/.env.example`, `.gitignore`, `start-demo.ps1`

**In plain terms:**

Configuration lives in two `.env` files (backend and frontend), both excluded from git; everything else at the root — logs, `dist/`, `__pycache__/`, `.venv/` — is generated.

**The code:**

```gitignore
# .gitignore
.env
.env.*
!.env.example
```

**What's happening:**

The frontend ships a `.env.example` template; the root README instructs creating `backend/.env` from an `backend/.env.example` template — **note:** no `backend/.env.example` file currently exists in the repository (verified by file search), so that copy step fails as written. The backend still runs without a `.env` (it starts in `degraded` mode without `GROQ_API_KEY`).

**Why it matters:**

Two practical consequences: you must create `backend/.env` by hand (a single line: `GROQ_API_KEY=...`), and you should never commit it — `.gitignore` is the only thing preventing a key leak. This is an *observed documentation gap*, not a runtime bug.

**Trace it further:** [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md) covers configuration and environment handling in detail.

---

## Continue learning

- [02 — Application startup and request flow](02-application-startup-and-request-flow.md) — the same structure, seen in motion.
- [14 — Admin dashboard and management](14-admin-dashboard-and-management.md) — the closest thing to an admin surface: health diagnostics and document management.
- [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) — where validation lives in this layout.
