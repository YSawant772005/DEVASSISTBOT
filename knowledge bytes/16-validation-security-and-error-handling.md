# 16 — Validation, Security, and Error Handling

**Overview:** This document is the protection inventory: what input validation exists on each boundary, which security controls are **verified implemented** versus **missing/recommended**, how errors are shaped and surfaced, and what logging exists. The honest headline: input validation and secret handling are strong for a demo; there is no authentication, no rate limiting, and no multi-tenant isolation — documented as limitations, not oversights.

**Scope:** Client- and server-side validation, security controls (implemented and absent), error envelopes and codes, exception handling, and logging.

**Prerequisites:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md), [10 — Authentication and authorization](10-authentication-and-authorization.md).

**Important source files:**
- `backend/app/core/errors.py`
- `backend/app/main.py`
- `backend/app/api/upload.py`, `backend/app/api/chat_ws.py`
- `backend/app/core/config.py`
- `frontend/src/services/api.ts`, `frontend/src/utils/markdown.ts`

---

### Byte 1: The validation map

**Builds on:** [09 — Checkout and coupons](09-checkout-and-coupons.md), Byte 2

**Source files:** `backend/app/api/upload.py`, `backend/app/api/chat_ws.py`, `frontend/src/services/api.ts`

**In plain terms:**

Every input crosses a client check (for fast feedback) and a server check (authoritative). The server validates file type, size, emptiness, extractability, message shape, and message length.

**The code:**

```python
# upload boundary (backend/app/api/upload.py)
extension = validate_filename(filename)                 # allow-list: .pdf .txt .md .markdown
data = await _read_limited(file, settings.max_upload_bytes)  # streams 1 MiB blocks
if not data:
    raise EmptyFileError()

# chat boundary (backend/app/api/chat_ws.py)
client_message = ClientChatMessage.model_validate(payload)   # Pydantic: type, request_id 1..128
question = client_message.message.strip()
if not question: raise InvalidMessageError()
if len(question) > settings.max_question_chars: raise MessageTooLongError(…)
```

**What's happening:**

`_read_limited()` is notable: it enforces the 5 MB cap *while reading* the stream, so an oversized upload is rejected mid-transfer rather than after buffering it in memory. `ClientChatMessage.model_validate` runs on every WebSocket frame; `JSONDecodeError` and `ValidationError` are each converted to `INVALID_MESSAGE` events that leave the socket open. Client mirrors: `validateFile()` in `api.ts` (type/size/zero-byte) and the composer's character counter.

**Why it matters:**

Server-side validation is the only kind that counts (client checks are bypassable), and here it is complete for the app's two input channels. The layers are intentionally redundant — same rules twice — so UX stays fast while correctness stays server-owned.

**Trace it further:** Byte 2 covers configuration-time validation.

---

### Byte 2: Configuration-time validation

**Builds on:** Byte 1

**Source files:** `backend/app/core/config.py`

**In plain terms:**

Settings are validated when loaded: chunk overlap must be non-negative and smaller than chunk size, `CHUNK_SIZE` and `TOP_K` must be positive, and log levels are normalized — a bad `.env` fails fast at startup.

**The code:**

```python
# backend/app/core/config.py
@field_validator("chunk_overlap")
@classmethod
def _validate_overlap(cls, value: int, info) -> int:
    size = info.data.get("chunk_size", 500)
    if value < 0:
        raise ValueError("CHUNK_OVERLAP must be >= 0")
    if value >= size:
        raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
    return value

@field_validator("chunk_size", "top_k")
@classmethod
def _positive(cls, value: int) -> int:
    if value <= 0:
        raise ValueError("value must be > 0")
    return value
```

**What's happening:**

Pydantic field validators run during `Settings()` construction — i.e., at import/startup because `get_settings()` is called by `create_app()`. `case_sensitive=False` means `chunk_size` and `CHUNK_SIZE` are equivalent in the environment. `extra="ignore"` means unknown `.env` keys are silently tolerated (a typo like `CHNK_SIZE` does not fail — it quietly uses the default).

**Why it matters:**

Fail-fast on *inconsistent* values (overlap ≥ size) prevents pathological chunking at runtime, while `extra="ignore"` is a small double-edged sword: harmless unknowns pass, but misspelled variables are invisible. Both facts are verified from the config file, not assumed.

**Trace it further:** Byte 3 inventories the security controls that exist.

---

### Byte 3: Verified security controls

**Builds on:** Byte 1, [10 — Authentication and authorization](10-authentication-and-authorization.md), Byte 3

**Source files:** `backend/app/main.py`, `backend/app/prompts/system_prompt.py`, `frontend/src/utils/markdown.ts`, `.gitignore`

**In plain terms:**

Eight protections are implemented and verifiable in code: origin-locked CORS, server-side key custody, extension allow-listing, streaming size limits, untrusted-context separation, HTML-disabled markdown rendering, safe link attributes, and gitignored secrets.

**The code:**

```text
VERIFIED CONTROLS (each traceable to source):
1. CORS single-origin, credentials off        main.py:74-80
2. GROQ key server-side only; boolean health  config.py groq_configured; /health
3. Extension allow-list + case-folded         document_service.py ALLOWED_EXTENSIONS
4. 5 MB cap enforced during stream read       upload.py _read_limited()
5. Document excerpts in a separate user turn  system_prompt.py build_messages()
6. markdown-it html:false (XSS)               markdown.ts md renderer config
7. rel="noopener noreferrer" + no javascript: links   markdown.ts link_open rule
8. .env gitignored, templates whitelisted     .gitignore
```

**What's happening:**

Controls 5 and 6 are the deep ones: structural containment of untrusted text server-side, and structural XSS-safety client-side — both backed by tests (`test_prompt_with_documents_marks_context_as_untrusted_and_separate`; all of `markdown.spec.ts`, including the `javascript:`-link case). Control 4 prevents memory exhaustion from huge uploads.

**Why it matters:**

When reviewing a change, these eight lines are what must not regress. Each maps to at least one test, so `pytest` + `npm test` effectively pin the control set.

**Trace it further:** Byte 4 lists what is *not* protected.

---

### Byte 4: Missing and recommended protections

**Builds on:** Byte 3

**Source files:** `backend/app/api/upload.py`, `backend/app/api/chat_ws.py`, `backend/app/main.py`

**In plain terms:**

Clearly absent: authentication on destructive endpoints, request rate limiting, filename sanitization beyond extension checks, output content filtering, and TLS at the app layer. Each is labeled *missing* rather than *bug*, with its trigger condition.

**The code:**

```text
MISSING / RECOMMENDED (observed, not implemented):
- No auth: DELETE /documents (wipe) is open to any reachable client   → add before any
  shared deployment (see doc 10, Byte 5)
- No rate limit: anyone can open many WebSockets and drive Groq cost  → per-IP limit before
  public hosting; today only per-connection BUSY exists
- Filename kept as-is after extension check (stored as metadata text, never as a path —
  no path traversal sink exists, but display should stay escaped)   → sanitize on display
- No output moderation: model text is rendered (safely) but not content-checked → optional
- No TLS: uvicorn serves plain HTTP; use a reverse proxy/tunnel for transport security
- CORS origins: exact single-origin match; no wildcard observed (good), but FRONTEND_ORIGIN
  must be edited per environment
```

**What's happening:**

Some "missing" items are mitigated by design: the filename never becomes a filesystem path (uploads are never written to disk), which removes the traversal risk class entirely; content is rendered as escaped text, which neutralizes stored-XSS-style payloads even without output filtering.

**Why it matters:**

Distinguishing "missing but structurally harmless in this design" (filename sanitization) from "missing and dangerous if deployed naively" (auth, rate limiting) is the point of this byte — it is the risk register for taking this demo beyond localhost.

**Trace it further:** Byte 5 covers error handling and logging.

---

### Byte 5: Error handling and logging

**Builds on:** Byte 3, [04 — Models and ViewModels](04-models-and-viewmodels.md), Byte 5

**Source files:** `backend/app/core/errors.py`, `backend/app/main.py`, `backend/app/api/chat_ws.py`, `backend/app/core/__init__.py`

**In plain terms:**

All user-facing failures are typed `AppError`s with stable codes and safe messages; unexpected exceptions are logged server-side and replaced with a generic message so internals never cross the wire.

**The code:**

```python
# backend/app/core/errors.py — the pattern
@dataclass
class AppError(Exception):
    code: str          # stable machine code, e.g. "FILE_TOO_LARGE"
    message: str       # safe for end users
    status_code: int = 400

# backend/app/api/chat_ws.py — unexpected failure is scrubbed
except Exception as exc:
    logger.exception("Chat request %s failed unexpectedly: %s", request_id, type(exc).__name__)
    await _send_error(websocket, request_id, ProviderError())   # generic, no details
```

**What's happening:**

HTTP errors funnel through the `AppError` handler in `main.py` (plus `INVALID_REQUEST` for Pydantic 422s with field-level `details`); WebSocket errors funnel through `_send_error()` as one terminal event. Logging (`configure_logging` in `core/__init__.py`) is a compact stdout format (`HH:MM:SS LEVEL name | message`) with noisy third-party loggers quieted, and the format deliberately excludes secrets.

**Why it matters:**

The scrubbing rule — *server logs get the exception, clients get a code* — is what keeps tracebacks, headers, and keys off the wire. It is asserted end-to-end by `test_websocket_does_not_leak_configuration`, `test_unexpected_provider_failure_is_scrubbed`, and the integration check's "error message leaks no internals" assertion.

**Trace it further:** [18 — Testing and verification](18-testing-and-verification.md) shows those tests; [13 — Reviews and moderation](13-reviews-and-moderation.md) covers content-level safety.

---

## Continue learning

- [13 — Reviews and moderation](13-reviews-and-moderation.md) — content moderation in depth.
- [18 — Testing and verification](18-testing-and-verification.md) — tests pinning these controls.
- [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md) — operating the secure configuration in practice.
