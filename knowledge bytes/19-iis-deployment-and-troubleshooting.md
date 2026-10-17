# 19 — IIS Deployment and Troubleshooting

**Overview:** Honest headline first: **IIS is not applicable to this project.** DevAssist has no ASP.NET components, no Windows-specific server code, and no IIS configuration anywhere in the repository — nothing in `web.config` form exists or is required. The application is a Python (FastAPI/uvicorn) backend plus a static-asset frontend (Vite), deployed today via a single uvicorn process and Vite dev/preview servers, optionally exposed through Cloudflare quick tunnels on Windows. This document maps the "deployment and troubleshooting" territory onto what actually exists: the real run commands, the port and proxy topology, the CORS contract, environment-variable handling, and a troubleshooting table drawn from the app's own error behavior.

**Scope:** Actual deployment model (uvicorn + Vite, Windows scripts), port/proxy/CORS topology, environment variables, tunnel-based public exposure, log locations, and troubleshooting; explicit IIS absence statement with guidance for anyone who genuinely needs IIS in front of this stack.

**Prerequisites:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md), [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md), [18 — Testing and verification](18-testing-and-verification.md).

**Important source files:**
- `start-demo.bat`, `start-demo.ps1`
- `backend/app/main.py`, `backend/app/core/config.py`
- `frontend/vite.config.ts`, `frontend/.env.example`
- `README.md` (root), `PROJECT_STATUS.md`

---

### Byte 1: Why IIS does not appear — and what would be involved if it must

**Builds on:** [00 — Project architecture](00-project-architecture.md)

**Source files:** (none — absence statement; verified by full repo search for IIS/web.config/httpPlatform)

**In plain terms:**

A repository-wide search for `IIS`, `web.config`, and `httpPlatformHandler` returns nothing: there is no Windows server configuration to document, because the backend is an ASGI Python application that must be served by uvicorn (or any ASGI server), and the frontend compiles to static files that any web server can host.

**The code:**

```text
# The deployment surface that actually exists:
backend/   → uvicorn app.main:app --host 127.0.0.1 --port 8000   (Python ASGI)
frontend/  → npm run dev (:5173) / npm run preview (:4173)      (Vite)
scripts/, start-demo.bat, start-demo.ps1                        (cloudflared tunnels, Windows)
```

**What's happening:**

If a Windows shop genuinely must publish through IIS, the two standard shapes are: (1) IIS as a static-file + reverse-proxy front — serve the built `frontend/dist` as static content and use URL Rewrite as a reverse proxy to `http://127.0.0.1:8000`, **including WebSocket upgrade rules for `/ws`** (`ws: true` semantics, which `vite.config.ts` already demonstrates); or (2) skip IIS entirely and keep uvicorn directly. Either way the constraints in Byte 3 (CORS origin, WebSocket upgrades) apply unchanged.

**Why it matters:**

Deployment documents that describe infrastructure the project doesn't use are worse than none — they mislead about ports, configs, and failure modes. This project's genuine deployment story is the next five bytes.

**Trace it further:** Byte 3 for the proxy configuration you would replicate in IIS URL Rewrite.

---

### Byte 2: The real run topology — single uvicorn worker, Vite dev/preview, strict ports

**Builds on:** Byte 1, [02 — Application startup and request flow](02-application-startup-and-request-flow.md)

**Source files:** `frontend/vite.config.ts`, root `README.md`

**In plain terms:**

The backend runs as one uvicorn process holding all state in memory. The frontend runs either in Vite dev mode (`:5173`) or preview mode over the production build (`:4173`). Both ports are `strictPort: true`, and both servers proxy API traffic to the backend so the browser usually never talks to `:8000` directly.

**The code:**

```ts
// frontend/vite.config.ts
const backendTarget = process.env.VITE_DEV_BACKEND ?? 'http://127.0.0.1:8000'

server:  { host: '0.0.0.0', port: 5173, strictPort: true, allowedHosts: parseAllowedHosts(), proxy: buildProxy() },
preview: { host: '0.0.0.0', port: 4173, strictPort: true, allowedHosts: parseAllowedHosts(), proxy: buildProxy() },
```

```ts
// the proxied paths — everything the frontend calls
'/health' → backendHttp   '/upload' → backendHttp
'/documents' → backendHttp   '/ws' → backendWs (ws: true)
```

**What's happening:**

Three details matter operationally. **Single worker**: with no database or shared cache, running more than one uvicorn worker would fragment the FAISS index and conversation limits across processes — the README's `--workers 1` story is a correctness constraint, not a resource choice. **strictPort**: if 5173/4173 is occupied, Vite fails loudly instead of silently moving to 5174, which would break the backend's CORS allowlist (Byte 3) and any bookmarked tunnel URL. **Proxy vs. direct**: because `API_BASE_URL` defaults to `''` (same-origin), all requests flow through Vite's proxy in dev/preview, which is why the WebSocket proxy entry exists at all — browsers would otherwise hit a `ws://localhost:8000` cross-origin handshake.

**Why it matters:**

Port conflicts and "works on dev, fails in preview" bugs almost always trace to one of these three settings. When something can't connect, verify in this order: is the backend actually up on `127.0.0.1:8000`, did Vite stay on its strict port, and is the client going through the proxy or directly?

**Trace it further:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md) for the backend's own startup sequence; [18 — Testing and verification](18-testing-and-verification.md) for verifying both halves before deploying.

---

### Byte 3: The CORS contract — one origin, server-configured

**Builds on:** Byte 2, [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md)

**Source files:** `backend/app/main.py`, `backend/app/core/config.py`

**In plain terms:**

The backend allows exactly one browser origin, taken from `FRONTEND_ORIGIN` with a default matching Vite's dev port. If the frontend is served from anywhere else without setting this variable, browsers will block the responses.

**The code:**

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],   # default: http://localhost:5173
)
```

**What's happening:**

This is a single-element allowlist by design — one frontend, one origin. The tunnel scripts in Byte 4 work without touching CORS because the browser loads the page *from the tunnel origin* but the frontend assets carry the same-origin `API_BASE_URL` default, so calls go back through the proxied origin rather than cross-origin to `:8000`. Trouble appears when someone sets `VITE_API_BASE_URL=http://localhost:8000` (as `frontend/.env.example` shows for direct-backend setups) while serving the UI from another host: now every fetch is cross-origin and `FRONTEND_ORIGIN` must be updated to match, restart required.

**Why it matters:**

"CORS error in console" is the single most likely deployment failure for this app, and the fix is configuration, not code: either keep same-origin proxying (recommended, zero CORS involvement) or align `FRONTEND_ORIGIN` with the actual page origin.

**Trace it further:** [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) Byte on CORS.

---

### Byte 4: Public demos on Windows — cloudflared quick tunnels

**Builds on:** Byte 2

**Source files:** `start-demo.bat`, `start-demo.ps1`

**In plain terms:**

Two launcher scripts expose the local backend and frontend to the internet using Cloudflare quick tunnels. They do **not** start the app processes themselves — backend and frontend must already be running — and the generated URLs change on every restart.

**The code:**

```powershell
# start-demo.ps1 (abridged, verified)
$cloudflared = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
Start-Process -FilePath $cloudflared -ArgumentList @('tunnel','--url','http://127.0.0.1:8000') `
  -RedirectStandardOutput $backendLog -RedirectStandardError $backendLog
Start-Process -FilePath $cloudflared -ArgumentList @('tunnel','--url','http://127.0.0.1:4173') `
  -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendLog
# Public URLs appear in backend-tunnel.log / frontend-tunnel.log
```

```bat
REM start-demo.bat additionally checks for an existing cloudflared.exe (warns, doesn't spawn twice)
tasklist /FI "IMAGENAME eq cloudflared.exe" | find /I "cloudflared.exe" >NUL
```

**What's happening:**

Two tunnels are created because the frontend and backend live on different ports. The `allowedHosts` list in `vite.config.ts` already includes `.trycloudflare.com`, so Vite's host check accepts tunnel visitors — that constant is the fingerprint of this deployment approach. Each tunnel's URL is written to a log at the repo root (`backend-tunnel.log`, `frontend-tunnel.log`); users read the URL out of `frontend-tunnel.log` and share *that* one. The `.bat` variant warns (rather than fails) if cloudflared is already running, since duplicate spawns would produce confusing extra URLs.

**Why it matters:**

Quick tunnels are ideal for evaluator demos: no DNS, no certificates, no cloud account. Their two gotchas are documented in the scripts themselves — URLs are ephemeral, and the tunnels survive closing the launcher window but die with their host processes. Note that tunnel traffic arrives at the frontend's `:4173` preview server, so the production build (not the dev server) is what evaluators see.

**Trace it further:** Byte 6 for tunnel-related troubleshooting.

---

### Byte 5: Environment variables and secrets — what exists, what's missing

**Builds on:** Byte 2, [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md)

**Source files:** `backend/app/core/config.py`, `frontend/.env.example`

**In plain terms:**

Backend configuration is pydantic-settings over `.env` (chunk sizes, limits, log level, `GROQ_API_KEY`, `FRONTEND_ORIGIN`, `EMBEDDING_PRELOAD`). Frontend configuration is two optional Vite variables. One documentation gap is worth flagging: the root README references `backend/.env.example`, **which does not exist in the repository** — only `frontend/.env.example` is present.

**The code:**

```bash
# frontend/.env.example — the only env template in the repo (verified)
VITE_API_BASE_URL=http://localhost:8000   # Base URL of the FastAPI backend (no trailing slash)
VITE_WS_URL=                               # optional; derived as ws(s)://<host>/ws/chat when empty
```

```text
# vite.config.ts process variables (build/dev-time, not browser)
VITE_DEV_BACKEND       # proxy target, default http://127.0.0.1:8000
VITE_ALLOWED_HOSTS     # comma-separated extra hosts for Vite's allowedHosts
```

**What's happening:**

The settings validators make a missing or invalid `.env` fail fast at startup (see [18 — Testing and verification](18-testing-and-verification.md) Byte 4) rather than failing mid-request — `GROQ_API_KEY` absent yields a **degraded** `/health` and chat answers grounded only in general knowledge (the UI states this). The key is read server-side only and, per the WebSocket leak tests, can never appear in any client-visible payload. Tunnel logs, `npm` output, and any committed `.env` are the places secrets typically leak; here the only secret is `GROQ_API_KEY`, and it belongs in an uncommitted `backend/.env` with restrictive permissions.

**Why it matters:**

When setting up this project fresh, expect to create `backend/.env` yourself (with `GROQ_API_KEY=` and optionally `FRONTEND_ORIGIN=`) because no backend template ships with the repo. Treat that missing template as a checklist item, not an error — [18 — Testing and verification](18-testing-and-verification.md) shows the whole test suite runs without any key at all.

**Trace it further:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md) for where settings load; [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) for secret-handling claims and their tests.

---

### Byte 6: Troubleshooting playbook — symptoms to verified causes

**Builds on:** Bytes 2–5

**Source files:** `frontend/vite.config.ts`, `backend/app/main.py`, `backend/app/core/errors.py`, `start-demo.ps1`

**In plain terms:**

Each row below is grounded in code verified in this repository:

| Symptom | Verified cause | Fix |
|---|---|---|
| Vite exits immediately on start | `strictPort: true` and 5173/4173 is taken | `netstat -ano | findstr :5173` and stop the holder; ports never silently shift |
| Browser console shows CORS errors | UI served from an origin other than `FRONTEND_ORIGIN` (default `http://localhost:5173`) | Prefer same-origin proxying; else set `FRONTEND_ORIGIN` and restart uvicorn |
| WebSocket connects then closes | Not a socket issue — the protocol rejects a second message while generating (`BUSY`) and suppresses `done` after cancel | Wait for terminal event; see [02 — Application startup and request flow](02-application-startup-and-request-flow.md) |
| Chat answers ignore documents | `/health` reports `degraded` — `GROQ_API_KEY` missing/placeholder, or nothing indexed | Set the real key in `backend/.env`; check the Settings dialog's diagnostics |
| Tunnel page won't load API calls | Backend tunnel not running, or uvicorn not on `127.0.0.1:8000` | Read `backend-tunnel.log`; confirm `curl http://127.0.0.1:8000/health` works locally |
| Fresh evaluator sees new empty URLs | Quick-tunnel URLs are ephemeral by design | Re-read `frontend-tunnel.log` after every restart; share the frontend URL |
| Upload fails at 5 MB | `_read_limited` rejects mid-stream by design (limit is inclusive) | `MAX_UPLOAD_BYTES` is a settings value; the boundary is tested both sides |
| Startup crashes on bad config | Settings validators fail fast (e.g. overlap ≥ chunk size) | Fix `backend/.env`; the error message names the offending variable |

**What's happening:**

The diagnostic surface for a running deployment is the Settings dialog (Byte 5 of [17 — Contact, newsletter, and static pages](17-contact-newsletter-and-static-pages.md)): it renders `/health` data — backend URL, WebSocket URL, model name, index size, provider status — which distinguishes "frontend can't reach backend" from "backend degraded" in one glance. Backend logs go to the uvicorn console; tunnel logs are the two `*-tunnel.log` files at the repo root.

**Why it matters:**

Every failure mode in the table is observable before a user reports it: `/health` for the backend, the Settings dialog for the full stack, the tunnel logs for exposure. Nothing in the deployment path is invisible — which is the practical definition of a well-diagnosable demo.

**Trace it further:** [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) for the error envelope shapes surfacing in these logs; [18 — Testing and verification](18-testing-and-verification.md) for pre-deployment verification.

---

## Continue learning

- For a production posture beyond quick tunnels: put a real reverse proxy (or IIS URL Rewrite, per Byte 1) in front of uvicorn, serve `frontend/dist` statically with the same `/health`, `/upload`, `/documents`, `/ws` proxy rules from `vite.config.ts`, and pin `FRONTEND_ORIGIN` to the real page origin.
- Before any deployment, run the verification trio from [18 — Testing and verification](18-testing-and-verification.md): `pytest`, `npm test`, `npm run typecheck`.
- To understand what the single uvicorn worker is protecting, read [03 — Data layer and database](03-data-layer-and-database.md) — the in-memory FAISS index is why multi-worker would break correctness.
