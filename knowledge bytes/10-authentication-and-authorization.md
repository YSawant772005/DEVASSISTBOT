# 10 — Authentication and Authorization

**Overview:** This application has **no authentication and no authorization** — there is no login, no registration, no passwords, no sessions or tokens, no roles, and no protected routes (verified across the entire backend and frontend). The SRS specifies a local, single-user demo, so identity simply does not exist. This document documents that absence precisely, then explains the real boundary that *does* exist (a locked-down CORS origin) and the secret-handling rules that protect the one credential in the system.

**Scope:** Verified absence of auth mechanisms; the CORS origin boundary; API key custody; and what would be required to add real auth. No secrets or credentials are reproduced anywhere in this document.

**Prerequisites:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md), [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md).

**Important source files:**
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/services/groq_service.py`
- `frontend/src/config.ts`
- `frontend/src/components/SettingsDialog.vue`

---

### Byte 1: Verified absence of auth

**Builds on:** [00 — Project architecture](00-project-architecture.md), Byte 7

**Source files:** `backend/app/`, `frontend/src/`

**In plain terms:**

No endpoint requires credentials of any kind. Every route — upload, list, delete, health, and the WebSocket — is reachable by anyone who can reach the port.

**The code:**

```text
# Verified by searching the backend for auth machinery — all absent:
- No FastAPI dependencies like OAuth2PasswordBearer, HTTPBearer, api_key headers
- No session cookies, JWT, or token validation anywhere in app/
- No user table, user model, roles, or permissions (there is no database at all)
- frontend/src/ contains no login view, no auth store, no Authorization header
```

**What's happening:**

`main.py` registers exactly one middleware (CORS) and no dependency on any router. `delete_all_documents()` — the most destructive endpoint — is protected by nothing beyond knowing the URL.

**Why it matters:**

This is a *documented design choice with a real consequence*: anyone with network access to port 8000 can wipe the index (`DELETE /documents`) or read other indexed content through chat. In the demo setup that is acceptable because access is limited to your machine or a temporary tunnel; deploying it on a shared network without adding auth would be a genuine security gap. Labeled as an **observed limitation, not a bug**.

**Trace it further:** Byte 2 explains the one boundary that does exist.

---

### Byte 2: The CORS origin boundary

**Builds on:** Byte 1

**Source files:** `backend/app/main.py`, `backend/app/core/config.py`

**In plain terms:**

The backend only accepts browser requests originating from one configured URL — the frontend's origin — and never with credentials.

**The code:**

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],   # default http://localhost:5173
    allow_credentials=False,                    # no cookies ever involved
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
```

**What's happening:**

`FRONTEND_ORIGIN` comes from `backend/.env`. `allow_credentials=False` means the browser will never attach cookies to these requests — a deliberate pairing with "there is no session." `allow_headers=["*"]` permits content-type headers for multipart uploads without any auth header.

**Why it matters:**

CORS is *not* authentication — it constrains browsers, not attackers. A `curl` request from any origin bypasses it entirely (CORS is enforced by the browser). Its real function here is preventing arbitrary websites in *your* browser from talking to your local backend. The practical failure it causes is operational: a mismatched origin makes the app appear broken with preflight errors (see [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md)).

**Trace it further:** Byte 3 covers the one real secret.

---

### Byte 3: API key custody — the only credential

**Builds on:** Byte 2

**Source files:** `backend/app/core/config.py`, `backend/app/services/groq_service.py`, `frontend/src/config.ts`

**In plain terms:**

`GROQ_API_KEY` exists only in `backend/.env`, is read only by backend settings, and is used only inside the Groq SDK client. The frontend bundle cannot contain it by construction.

**The code:**

```python
# backend/app/services/groq_service.py — key used at client construction, nowhere else
def _get_client(self):
    if not self.is_configured:
        raise ConfigurationError(
            "The AI provider is not configured. Add GROQ_API_KEY to backend/.env "
            "and restart the server."
        )
    if self._client is None:
        from groq import AsyncGroq
        self._client = AsyncGroq(
            api_key=self.settings.groq_api_key,
            timeout=self.settings.groq_timeout_seconds,
            max_retries=0,
        )
    return self._client
```

```typescript
// frontend/src/config.ts — only VITE_* public values are compiled in
const rawApiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim()
```

**What's happening:**

Four properties combine: (1) `config.py` reads `.env` server-side only; (2) `groq_configured` treats empty/placeholder (`replace_with…`) keys as *unconfigured* without ever echoing the value; (3) Vite inlines only `VITE_*` variables into the bundle, and none of them is a secret; (4) error responses carry codes/messages that never include the key — asserted by `test_websocket_does_not_leak_configuration`.

**Why it matters:**

Key custody is the security property this app most depends on, since the key is the only thing worth stealing. The chain breaks if someone copies the key into a `VITE_`-prefixed variable — Vite would ship it to every visitor. The Settings dialog even states the rule in the UI: "The key is never sent to the browser."

**Trace it further:** Byte 4 covers the authorization questions that do apply.

---

### Byte 4: Effective "authorization" — who can do what

**Builds on:** Byte 3, Byte 1

**Source files:** `backend/app/api/upload.py`, `backend/app/api/chat_ws.py`, `frontend/src/components/TopNav.vue`

**In plain terms:**

Every visitor has identical, unrestricted rights: upload, list, delete, clear, and chat. There is no privileged surface, which also means there is no admin privilege to steal.

**The code:**

```text
Effective permission model (verified against the routers):
GET    /health              → anyone
POST   /upload              → anyone (≤ 5 MB, allow-listed extensions)
GET    /documents           → anyone
DELETE /documents/{doc_id}  → anyone
DELETE /documents           → anyone  ← destructive, unauthenticated
WS     /ws/chat             → anyone (one generation per connection)
```

**What's happening:**

The only quasi-throttling is per-connection: one in-flight generation (`BUSY`) and the `MAX_QUESTION_CHARS`/`MAX_UPLOAD_BYTES` caps. Rate limiting toward Groq is handled by surfacing `RATE_LIMITED` to the user rather than by retrying (`max_retries=0`).

**Why it matters:**

If you add multi-user support, this table is your work list: every row needs an identity check, and `DELETE /documents` (which currently affects *everyone's* shared index) is the first to protect. Until then, "all users of one process share one index" is the documented single-worker limitation.

**Trace it further:** Byte 5 sketches what real auth would require here.

---

### Byte 5: What adding authentication would take

**Builds on:** Byte 4

**Source files:** `backend/app/main.py`, `backend/app/services/vector_store.py`, `frontend/src/stores/chat.ts`

**In plain terms:**

Because nothing in the stack assumes identity, adding auth means threading a new concept through every layer — there is no partial hook to reuse.

**The code:**

```text
Hypothetical auth work list (not implemented — guidance only):
1. backend/app/main.py       add a dependency (e.g. HTTPBearer) + per-route guards
2. backend/app/api/*         pass user identity into store calls
3. backend/app/services/vector_store.py   partition _docs/_records per user
4. backend/app/core/config.py secret for signing tokens (new .env var)
5. frontend                  login flow, token storage, Authorization header in api.ts
6. WebSocket                 authenticate during the WS handshake (query/header),
                             since browsers cannot set headers on WebSocket()
```

**What's happening:**

Step 6 is the subtle one: `chatSocket.ts` opens a bare `new WebSocket(url)`, so credentials would need to ride in the URL or a cookie, and the FastAPI handler would validate before `websocket.accept()`. Step 3 is the other structural change — the vector store is currently one shared namespace.

**Why it matters:**

Recording this honestly tells future maintainers that auth is a cross-cutting redesign here, not a middleware drop-in — and that until it exists, network exposure must be treated as full trust (relevant to the tunnel-based demo in [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md)).

**Trace it further:** [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) covers the input-side protections that *are* implemented.

---

## Continue learning

- [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) — implemented protections vs. missing ones.
- [14 — Admin dashboard and management](14-admin-dashboard-and-management.md) — the unauthenticated management surface.
- [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md) — exposing the app safely (or not).
