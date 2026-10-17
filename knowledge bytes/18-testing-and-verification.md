# 18 — Testing and Verification

**Overview:** DevAssist's test strategy is "replace the slow, external, and nondeterministic with fakes — then keep exactly one opt-in path to the real thing." This document inventories both suites as they exist in the repository, explains the faking architecture in `backend/tests/conftest.py`, walks the security-focused test cases, and records the verification results honestly: what was executed for this document, what was not, and known discrepancies between documentation and reality.

**Scope:** Backend pytest suite (9 test files, conftest fakes, PDF factory), frontend Vitest suite (5 spec files), the standalone integration check script, and honest verification status.

**Prerequisites:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md), [04 — Models and viewmodels](04-models-and-viewmodels.md), [15 — Frontend views, JavaScript, CSS](15-frontend-views-javascript-css.md).

**Important source files:**
- `backend/pytest.ini`, `backend/tests/conftest.py`, `backend/tests/pdf_factory.py`
- `backend/tests/test_chat_ws.py`, `test_chunking.py`, `test_document_service.py`, `test_health.py`, `test_policy_and_prompt.py`, `test_provider.py`, `test_real_embeddings.py`, `test_retrieval.py`, `test_upload.py`
- `frontend/tests/chat.spec.ts`, `components.spec.ts`, `format.spec.ts`, `markdown.spec.ts`, `navigation.spec.ts`
- `scripts/integration_check.py`, `scripts/fake_provider_server.py`
- `backend/tests/fixtures/sample_notes.md`

---

### Byte 1: The fake-first architecture — one conftest replaces the whole world

**Builds on:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md), Byte 4

**Source files:** `backend/tests/conftest.py`, `backend/pytest.ini`

**In plain terms:**

Backend tests never touch a network, a GPU, or a real LLM key. Before the app package is even imported, `conftest.py` sets stub environment variables, then a session-scoped fixture monkeypatches the four service modules with deterministic fakes.

**The code:**

```python
# backend/tests/conftest.py — runs before any app import
os.environ.setdefault("EMBEDDING_PRELOAD", "False")
os.environ.setdefault("GROQ_API_KEY", "")

from app.core.config import Settings, reset_settings_cache  # noqa: E402
from app.main import create_app  # noqa: E402
# ... then patch chat_service, embedding_service, groq_service, vector_store

class FakeEmbeddingService:
    """Deterministic bag-of-words embedding: cosine similarity is meaningful."""
    model_name = "fake-deterministic"
    dimension = EMBED_DIM  # 64, not 384 — tests run in milliseconds

    def encode(self, texts: list[str]) -> np.ndarray:
        # each token hashed into a dimension; L2-normalized like the real model
```

**What's happening:**

Three design choices make this conftest worth studying. (1) **Environment before import** — settings are cached at import time, so the env vars must exist before `app.main` loads, and `reset_settings_cache()` lets tests build fresh `Settings` per scenario. (2) **Semantically meaningful fakes** — the fake embedding is a hashed bag-of-words, so "texts sharing words are more similar" holds; retrieval tests assert real ranking behavior, not constant equality. (3) **Isolation fixture** — `_isolate_services` patches all four service modules so no test can accidentally construct the real SentenceTransformer or open a Groq connection. `pytest.ini` sets `asyncio_mode = auto` and `--strict-markers`, so async WebSocket tests need no `@pytest.mark.asyncio` decorators and unknown markers fail loudly.

**Why it matters:**

This is why the backend suite runs in ~33 seconds with no API key, no model download, and no internet — the properties that make RAG hard to test (slow embeddings, paid LLM calls, nondeterministic generation) are all faked, while everything around them (chunking, indexing, streaming protocol, error mapping) is real code under test.

**Trace it further:** Byte 3 for the one escape hatch back to the real model.

---

### Byte 2: The WebSocket suite is a protocol specification in test form

**Builds on:** Byte 1, [02 — Application startup and request flow](02-application-startup-and-request-flow.md) Byte 6

**Source files:** `backend/tests/test_chat_ws.py`

**In plain terms:**

Eleven tests pin down the client-server contract: event ordering, the BUSY rejection, cancellation semantics, and — most importantly — that error events never leak internals.

**The code:**

```python
# backend/tests/test_chat_ws.py — representative assertions
def test_streams_tokens_then_done(ws_client):        # status → tokens… → done
def test_sources_event_precedes_tokens_when_documents_match(ws_client):
def test_second_message_while_generating_is_rejected(monkeypatch):
def test_disconnect_duration_does_not_break_the_server(monkeypatch):  # disconnect during generation
def test_websocket_does_not_leak_configuration(ws_client):           # no key/model host in any event
def test_unexpected_provider_failure_is_scrubbed(monkeypatch):       # generic message, no traceback
```

**What's happening:**

The scrubbing tests are the security heart of the suite. `test_websocket_does_not_leak_configuration` walks every event received over a full conversation and asserts that the Groq API key, the provider host, and internal settings never appear in any serialized payload. `test_unexpected_provider_failure_is_scrubbed` raises an arbitrary exception inside the provider and asserts the client sees only the generic error envelope — not the exception message. `test_malformed_messages_return_an_error_event_without_crashing` (parametrized over garbage payloads) proves the socket survives bad JSON and schema violations. The disconnect test exercises the hard case: cancellation mid-generation must not leave the chat service stuck in its busy state.

**Why it matters:**

A streaming protocol's tests are its specification. If you change the event envelope or the token grouping, these tests are the contract you must consciously revise — and the leak-scrubbing tests protect a property (no internal details on the wire) that is invisible in normal operation until it fails.

**Trace it further:** [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) for the error codes these tests assert against.

---

### Byte 3: The `real_model` marker — one honest bridge to production reality

**Builds on:** Byte 1

**Source files:** `backend/tests/test_real_embeddings.py`, `backend/pytest.ini`, `backend/tests/conftest.py`

**In plain terms:**

Fakes can drift from reality. The suite has exactly one guarded path back to the real SentenceTransformer model: three tests marked `real_model`, excluded from the default run.

**The code:**

```ini
# backend/pytest.ini
markers =
    real_model: exercises the real Sentence Transformers model (slow, needs the model cached)
```

```python
# backend/tests/test_real_embeddings.py
def test_model_produces_normalized_384_dim_vectors(real_embedding):
def test_real_retrieval_finds_the_matching_chunk(real_embedding, monkeypatch):
def test_upload_and_search_end_to_end_with_real_embeddings(real_embedding, monkeypatch):
```

**What's happening:**

The three tests validate the assumptions the fakes take on faith: that the real model emits 384-dimensional L2-normalized vectors (dimension mismatch would break `IndexFlatIP` cosine ranking), that a genuinely relevant chunk ranks first, and that the full upload→chunk→embed→index→search pipeline works with real embeddings. They are opt-in (`pytest -m real_model`) because they require the model to be downloaded or cached — hence `EMBEDDING_PRELOAD=False` in conftest for the default fast run. **Note for honesty:** these three tests were *not* executed when this document was written (they need the model cache); the default 114-test run includes everything else.

**Why it matters:**

The fake says "cosine similarity is meaningful"; only the real test proves the *actual* model behaves that way in this pipeline. Marking them instead of deleting them keeps the fast suite fast without letting the fakes become the only truth.

**Trace it further:** [03 — Data layer and database](03-data-layer-and-database.md) for how real embeddings flow into FAISS.

---

### Byte 4: Security and policy are tested behavior, not claims

**Builds on:** [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md), [13 — Reviews and moderation](13-reviews-and-moderation.md)

**Source files:** `backend/tests/test_policy_and_prompt.py`, `backend/tests/test_provider.py`, `backend/tests/test_upload.py`

**In plain terms:**

Three suites turn the security document's claims into executable assertions: prompt injection defenses, provider error scrubbing, and upload boundary enforcement.

**The code:**

```python
# test_policy_and_prompt.py — the untrusted-context contract
def test_prompt_without_documents_has_no_excerpts():
def test_prompt_with_documents_marks_context_as_untrusted_and_separate():
def test_policy_refusal_short_circuits_before_the_provider(chat_service):  # no LLM call spent

# test_provider.py — every mapped error uses the required safe message
def test_rate_limit_uses_the_required_message():
def test_placeholder_key_is_not_treated_as_configured():   # "your-key" ≠ configured

# test_upload.py — the 5 MB boundary, both sides
def test_upload_rejects_file_over_5mb(client):
def test_upload_accepts_file_exactly_at_limit(client):      # boundary is inclusive
def test_failed_upload_does_not_register_a_document(client):  # atomicity
```

**What's happening:**

Several tests encode subtle invariants. `test_upload_accepts_file_exactly_at_limit` plus its over-limit twin pin the inclusive boundary. `test_failed_upload_does_not_register_a_document` proves an upload that fails during extraction leaves no ghost document in the list — an atomicity property that is easy to break when adding features. `test_placeholder_key_is_not_treated_as_configured` guards against the classic demo failure of shipping with a literal placeholder that looks configured. The chunking suite (`test_chunking.py`) contributes its own edge cases: exact-size inputs, overlap larger than chunk size still terminating, and code indentation surviving chunking.

**Why it matters:**

Every "Why it matters" claim in [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) ultimately rests on these tests. When you extend the app, these are the files to run and to extend — a new boundary without a both-sides-of-the-limit test pair is an unverified boundary.

**Trace it further:** [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) for the full control inventory.

---

### Byte 5: Frontend suite — stores, components, and escaping tested in isolation

**Builds on:** [15 — Frontend views, JavaScript, CSS](15-frontend-views-javascript-css.md), Byte 2

**Source files:** `frontend/tests/chat.spec.ts`, `components.spec.ts`, `format.spec.ts`, `markdown.spec.ts`, `navigation.spec.ts`

**In plain terms:**

68 Vitest tests in jsdom cover the frontend in five layers: chat store streaming logic (14), component behavior (15), formatting/validation utilities (9), markdown escaping (12), and navigation/sidebar workflows (17).

**The code:**

```ts
// markdown.spec.ts — the XSS contract, mirroring the backend scrubbing tests
it('escapes raw HTML instead of executing it', () => { … })
it('does not allow javascript: links', () => { … })

// chat.spec.ts — streaming protocol from the client's side
it('appends streamed tokens to one assistant message', async () => { … })
it('stops generation locally and cancels server-side', async () => { … })
it('marks the message as failed when the socket send rejects', async () => { … })
```

**What's happening:**

The suites deliberately overlap the backend's contract from the other direction: `chat.spec.ts` feeds the store the same event sequences `test_chat_ws.py` emits (status → sources → tokens → done/error), so a protocol change breaks both sides in one run. Component tests use real interactions — Enter sends, Shift+Enter inserts a newline, the composer's send button becomes a stop button while generating. `navigation.spec.ts` covers destructive-action safety ("requires a second click before deleting, then calls the backend"). The frontend tests use a mocked socket rather than a live connection, matching the backend's fake-provider philosophy.

**Why it matters:**

These 68 tests are the safety net behind [15 — Frontend views, JavaScript, CSS](15-frontend-views-javascript-css.md)'s claim that the client is "typecheck-clean with passing tests." Note one documentation discrepancy, verified during this writing: the root README mentions "48 frontend tests," while the actual count is 68 across 5 spec files — consistent with `PROJECT_STATUS.md`, not with the README.

**Trace it further:** [15 — Frontend views, JavaScript, CSS](15-frontend-views-javascript-css.md) for the code under test; [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md) for running these commands in CI.

---

### Byte 6: The integration check — real sockets, and what was actually verified

**Builds on:** Bytes 1–5

**Source files:** `scripts/integration_check.py`, `scripts/fake_provider_server.py`, `backend/tests/fixtures/sample_notes.md`

**In plain terms:**

Beyond the in-process suites, a standalone script exercises a *running* backend over real network sockets: health → upload `sample_notes.md` → list documents → stream a chat over a real WebSocket → verify a policy refusal → clear the index. `fake_provider_server.py` exists so this can run without a Groq key.

**The code:**

```python
# scripts/integration_check.py — docstring, its own spec
#   1. GET /health reports the loaded embedding model and index size
#   2. POST /upload indexes a document and returns real metadata
#   3. GET /documents lists it again
#   4. WS /ws/chat delivers the streaming protocol in order
#   5. the programming-only policy refuses an off-topic question
#   6. DELETE /documents clears the index
# Usage: python scripts/integration_check.py [base_url]
```

**What's happening — honest verification status:**

Executed while writing this document (Windows, repo working tree):
- `backend`: `pytest` → **114 passed in 32.75s** (default marker set; the three `real_model` tests were deselected, so they are *not* claimed as passing).
- `frontend`: `npm test` (Vitest) → **68 passed, 5 files**.
- `frontend`: `npm run typecheck` (`vue-tsc -b`) → **clean, no errors**.

**Not executed:** `scripts/integration_check.py` (requires a running backend instance and would index documents into a live server), and the `real_model` tests (require the cached SentenceTransformer model). No claim is made about their pass status.

**Why it matters:**

Verification reports are only useful if they distinguish "ran and passed" from "exists and looks correct." The three-tier structure — fast fakes, opt-in real model, live-network integration — mirrors how production risk actually scales, and this document's own reporting follows the same honesty rule the codebase's error handling does: never claim more than is verified.

**Trace it further:** [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md) for how these scripts fit into a demo or deployment pipeline; [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) for the error envelopes the integration script asserts over the wire.

---

## Continue learning

- To run everything yourself: `cd backend && pytest` then `cd frontend && npm test && npm run typecheck`. For the real-model tier, pre-cache `all-MiniLM-L6-v2` and run `pytest -m real_model`.
- To extend the integration check with new endpoints, follow its `check()` helper pattern in `scripts/integration_check.py` — each step is a labeled PASS/FAIL line with collected failures at exit.
- To understand what the fakes abstract away, read [03 — Data layer and database](03-data-layer-and-database.md) (real FAISS behavior) and [02 — Application startup and request flow](02-application-startup-and-request-flow.md) (real provider flow).
