# 09 — Checkout and Coupons

**Overview:** This repository has **no checkout, no payment, no coupons, and no discounts** — there are no prices, totals, or order-creation transactions anywhere (verified by search). The prescribed topic maps onto the pipeline that plays the same "validate → calculate → commit" structural role: the **question-send pipeline**, where input validation runs, relevance is decided, context is budgeted, and a conversation turn is committed to client state — with failure paths at every stage.

**Scope:** The send pipeline end to end (client validation → protocol validation → policy gate → retrieval budgeting → streaming → commit), error/failure scenarios, and the atomicity that does exist (upload ingestion). Literal checkout/coupon mechanics are explicitly absent.

**Prerequisites:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md), [07 — Search, filtering, sorting, pagination](07-search-filtering-sorting-pagination.md).

**Important source files:**
- `frontend/src/components/ChatComposer.vue`
- `frontend/src/stores/chat.ts`
- `backend/app/api/chat_ws.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/policy_service.py`
- `backend/app/api/upload.py`

---

### Byte 1: No checkout — the "commit" equivalent

**Builds on:** [00 — Project architecture](00-project-architecture.md), Byte 7

**Source files:** `frontend/src/stores/chat.ts`, `backend/app/api/chat_ws.py`

**In plain terms:**

A checkout finalizes a purchase; here the analogous finalization is a completed conversation turn: a user message plus a fully streamed assistant answer, committed to the conversation store when `done` (or `error`) arrives.

**The code:**

```typescript
// frontend/src/stores/chat.ts — the commit step
function handleDone(event: ServerDoneEvent): void {
  const message = findMessage(conversation, event.request_id)
  if (message) {
    message.status = 'complete'
    message.stage = undefined
    conversation!.updatedAt = Date.now()
  }
  state.isGenerating = false
  activeRequestId = null
}
```

**What's happening:**

Commitment is entirely client-side: the backend keeps no record of the exchange (chat history is never persisted server-side — verified: no endpoint accepts or stores message history). `status: 'complete'` marks the turn as final; the partial content accumulated in `message.content` is what remains on any failure.

**Why it matters:**

There is no server-side rollback to perform because there is no server-side write. The nearest true "transaction" in this codebase is upload ingestion (Byte 5) — worth not confusing the two.

**Trace it further:** Byte 2 covers validation before money-equivalent work is done.

---

### Byte 2: Validation gates before anything runs

**Builds on:** Byte 1

**Source files:** `frontend/src/components/ChatComposer.vue`, `frontend/src/stores/chat.ts`, `backend/app/api/chat_ws.py`

**In plain terms:**

A message must pass three gates to reach the model: the composer's non-empty/length check, the store's duplicate-send check, and the server's Pydantic + length validation.

**The code:**

```python
# backend/app/api/chat_ws.py — server-side gates
client_message = ClientChatMessage.model_validate(payload)
question = client_message.message.strip()
if not question:
    raise InvalidMessageError()
if len(question) > settings.max_question_chars:
    raise MessageTooLongError(settings.max_question_chars)
```

```typescript
// frontend/src/stores/chat.ts — client-side mirror
if (!question || state.isGenerating) return
if (question.length > MAX_QUESTION_CHARS) {
  state.lastSendError = `Your message is too long (${question.length.toLocaleString()} characters)…`
  return
}
```

**What's happening:**

The client checks run first for instant feedback (Enter sends only non-empty trimmed text; the counter warns past 3,000 chars — 75% of the 4,000 limit). The server repeats the checks because client checks are advisory: a crafted WebSocket frame still hits `ClientChatMessage.model_validate`, the strip/empty test, and the `MESSAGE_TOO_LONG` gate. Failures return an `error` event **without closing the socket**.

**Why it matters:**

This double-gating is the pattern for anything user-supplied in this app: friendly early rejection on the client, authoritative rejection on the server. Bypassing either side (e.g., trusting the client) would open abuse paths.

**Trace it further:** Byte 3 covers the eligibility gate (policy).

---

### Byte 3: The eligibility gate — programming-only policy

**Builds on:** Byte 2, [07 — Search, filtering, sorting, pagination](07-search-filtering-sorting-pagination.md), Byte 6

**Source files:** `backend/app/services/policy_service.py`, `backend/app/services/chat_service.py`

**In plain terms:**

Before retrieval or any LLM cost, the question passes a keyword heuristic: a clearly off-topic question is declined locally — no provider call, no charge, no latency.

**The code:**

```python
# backend/app/services/policy_service.py
def is_clearly_off_topic(question: str) -> bool:
    text = f" {question.lower()} "
    off_topic = any(_contains(text, signal) for signal in _OFF_TOPIC_SIGNALS)
    return off_topic and not has_technical_signal(question)

# backend/app/services/chat_service.py — prepare()
decision = evaluate_policy(question)
if not decision.allowed:
    return PreparedAnswer(question=question, messages=[], sources=[], refusal=decision.refusal)
```

**What's happening:**

Two lists interact: `_OFF_TOPIC_SIGNALS` (weather, recipes, sports, …) and a much larger `_TECH_SIGNALS` list (languages, tools, concepts). A question is refused **only** if an off-topic signal matches *and* no technical signal does — so "why is the temperature in my CPU too high?" is allowed ("temperature" + "cpu"-adjacent technical terms). The refusal arrives as ordinary `token` events followed by `done`, indistinguishable in shape from a real answer.

**Why it matters:**

This gate is deliberately conservative because it can only *decline*, never *verify* — the real guardrail is the system prompt (see [13 — Reviews and moderation](13-reviews-and-moderation.md)). Refusing a valid question would be worse than answering an odd one, hence the "any technical keyword wins" rule.

**Trace it further:** Byte 4 covers the "price calculation" analogue — budgeting context.

---

### Byte 4: "Price calculation" — the context budget

**Builds on:** Byte 3, [07 — Search, filtering, sorting, pagination](07-search-filtering-sorting-pagination.md), Byte 3

**Source files:** `backend/app/services/chat_service.py`, `backend/app/prompts/system_prompt.py`

**In plain terms:**

Just as checkout totals line items against a limit, retrieval totals excerpt characters against a token budget, and prompt assembly decides exactly which "line items" (message turns) are sent to the provider.

**The code:**

```python
# backend/app/prompts/system_prompt.py — what actually gets billed
messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
if excerpts:
    context_body = DOCUMENT_CONTEXT_HEADER + "\n\n" + format_context(excerpts)
    messages.append({"role": "user", "content": f"{context_body}\n\nUse the excerpts above only if they are relevant to my question." })
else:
    messages.append({"role": "user", "content": NO_DOCUMENTS_NOTE})
messages.append({"role": "user", "content": question})
```

**What's happening:**

The "total" is bounded twice: `retrieve()` enforces the 16,000-character budget over kept hits, and `groq_service.stream()` caps output with `max_tokens=GROQ_MAX_OUTPUT_TOKENS` (1024). Context is delivered as a **separate user turn**, never merged into the system message — a security-relevant structural choice (untrusted document text cannot dilute trusted instructions).

**Why it matters:**

This is where cost and safety intersect: budgets keep requests predictable, and turn separation keeps the guardrail authoritative. Note there is *no conversation history* in these messages — only system + context + current question — so each turn is stateless server-side.

**Trace it further:** Byte 5 covers failure scenarios (the "failed payment" paths).

---

### Byte 5: Failure scenarios and atomicity

**Builds on:** Byte 4

**Source files:** `backend/app/api/chat_ws.py`, `backend/app/services/groq_service.py`, `backend/app/api/upload.py`

**In plain terms:**

Every stage can fail with a distinct, stable error code, and the one true all-or-nothing operation (document ingestion) registers nothing unless every step succeeded.

**The code:**

```python
# backend/app/api/upload.py — nothing is committed until the end
vectors = embedding.encode(chunks)          # raises → nothing registered
doc_id = store.add_document(                # raises → nothing registered
    filename=filename, extension=extension, size_bytes=len(data),
    chunks=chunks, vectors=vectors,
)
```

```text
Failure codes across the send pipeline:
INVALID_MESSAGE · MESSAGE_TOO_LONG · BUSY · CONFIG_ERROR ·
PROVIDER_AUTH_ERROR · PROVIDER_TIMEOUT · PROVIDER_UNAVAILABLE ·
PROVIDER_ERROR · RATE_LIMITED
```

**What's happening:**

Chat failures are *terminal single events* — one `error` frame, stream over, socket stays open, partial content already delivered stays on screen (the store marks `status: 'error'` and keeps `message.content`). `cancel` is the non-error exit: the stream stops and **no `done` is sent**. `BUSY` rejects a second concurrent message while the first keeps streaming. `groq_service._normalize_error()` maps SDK exceptions onto the codes above so raw provider internals never cross the wire.

**Why it matters:**

Partial-stream-then-error is the trickiest UX case: the user sees a half-answer plus an error box with a Retry button (`retryLast()` removes the failed assistant turn and re-sends the same question). Knowing `cancel` suppresses `done` prevents misreading a stopped stream as a hang.

**Trace it further:** [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) inventories every code; [11 — Orders and order history](11-orders-and-order-history.md) covers how failed vs. complete turns appear afterward.

---

## Continue learning

- [10 — Authentication and authorization](10-authentication-and-authorization.md) — what replaces "who is checking out".
- [13 — Reviews and moderation](13-reviews-and-moderation.md) — the policy gate in depth.
- [18 — Testing and verification](18-testing-and-verification.md) — the tests covering busy/cancel/error paths.
