# 11 — Orders and Order History

**Overview:** There are **no orders** in this repository — no order entities, statuses, payments, or server-side order history (verified by search). The prescribed topic maps onto the project's real "history" feature: the **conversation store**, which groups messages into conversations, tracks per-message lifecycle states (the closest analogue to order statuses), and presents them in a browsable recent-conversations list — all session-only.

**Scope:** Message creation, message status transitions, the conversation–message relationship, retrieval/browsing of history, and what is (not) persisted server-side. Order/payment concepts are explicitly out of scope.

**Prerequisites:** [08 — Cart and session management](08-cart-and-session-management.md), [04 — Models and ViewModels](04-models-and-viewmodels.md).

**Important source files:**
- `frontend/src/stores/chat.ts`
- `frontend/src/types/chat.ts`
- `frontend/src/components/AppSidebar.vue`
- `frontend/src/components/MessageList.vue`
- `backend/app/api/chat_ws.py`

---

### Byte 1: The conversation is the "order"

**Builds on:** [08 — Cart and session management](08-cart-and-session-management.md), Byte 1

**Source files:** `frontend/src/types/chat.ts`

**In plain terms:**

A conversation is a titled, timestamped list of messages; it is created implicitly on the first send and identified by a generated id. This is the aggregate that "order history" would browse.

**The code:**

```typescript
// frontend/src/types/chat.ts
export interface Conversation {
  id: string
  title: string        // derived from the first question (42 chars max)
  createdAt: number
  updatedAt: number    // bumped on every token and completion
  messages: ChatMessage[]
}
```

**What's happening:**

`ensureConversation()` creates a conversation only when one is needed (first send or explicit "New chat"), `unshift`s it to the front of `state.conversations` (so the list is implicitly newest-first), and sets `activeId`. `updatedAt` maintenance is what keeps the sidebar ordering meaningful over a long session.

**Why it matters:**

The conversation is the unit everything else hangs off: clear/delete/switch operate on it, the sidebar lists it, and message lookup (`findMessage`) walks the active one. Because it exists only in a `reactive` array, its lifecycle is exactly the tab lifetime described in [08 — Cart and session management](08-cart-and-session-management.md).

**Trace it further:** Byte 2 covers message states — the status-transition analogue.

---

### Byte 2: Message lifecycle states

**Builds on:** Byte 1, [09 — Checkout and coupons](09-checkout-and-coupons.md), Byte 1

**Source files:** `frontend/src/types/chat.ts`, `frontend/src/stores/chat.ts`

**In plain terms:**

Each assistant message moves through four possible states — `streaming → complete | stopped | error` — driven directly by server events. User messages are born `complete`.

**The code:**

```typescript
// frontend/src/types/chat.ts
export type MessageStatus = 'streaming' | 'complete' | 'error' | 'stopped'

// frontend/src/stores/chat.ts — transitions
handleDone:    message.status = 'complete'
handleError:   message.status = 'error';  message.error = { code, message }
stopGeneration: message.status = 'stopped'  (content kept; placeholder if empty)
```

**What's happening:**

`streaming` is set when the message placeholder is pushed. `done` → `complete` clears `stage`. `error` → `error` stores the coded failure but **keeps any partial content**. User-initiated cancel → `stopped`, where `stopGeneration()` writes `'_Generation stopped._'` if nothing streamed yet. There is no state that reverts: once terminal, a message only leaves history by clearing/deleting the conversation or by `retryLast()` popping it.

**Why it matters:**

These transitions are the visible, testable contract of the WebSocket protocol — every state maps to a specific event, and `chat.spec.ts` pins each one. Understanding them prevents the classic bug of showing a spinner forever: no `done`/`error` arrives after a cancel *by design*.

**Trace it further:** Byte 3 covers creation of history "records" (the send path).

---

### Byte 3: Creating history — the message pair

**Builds on:** Byte 2, [09 — Checkout and coupons](09-checkout-and-coupons.md), Byte 2

**Source files:** `frontend/src/stores/chat.ts`

**In plain terms:**

Every send commits two records at once — the user's question and an empty assistant slot whose id is the future `request_id` — before any network I/O.

**The code:**

```typescript
// frontend/src/stores/chat.ts — sendMessage() (core of it)
const requestId = uid('msg')
const userMessage: ChatMessage = { id: uid('user'), role: 'user', content: question,
  createdAt: Date.now(), status: 'complete' }
const assistantMessage: ChatMessage = { id: requestId, role: 'assistant', content: '',
  createdAt: Date.now(), status: 'streaming' }

if (conversation.messages.length === 0) conversation.title = titleFromMessage(question)
conversation.messages.push(userMessage, assistantMessage)
state.isGenerating = true
activeRequestId = requestId
lastFailedQuestion = question
try {
  await getSocket().send({ type: 'message', request_id: requestId, message: question })
} catch {
  assistantMessage.status = 'error'   // …CONNECTION_FAILED with retry
}
```

**What's happening:**

History is written optimistically: the pair appears instantly, and only the assistant slot is later mutated by events. `retryLast()` reverses the commit — it pops the failed assistant turn and, if it matches, the re-sent user turn, then calls `sendMessage()` again so duplicates never accumulate.

**Why it matters:**

Because history is client-written, the store is the single place where corruption can happen; the backend's only guarantee is event ordering (`request_id` echo). This design also means history and transport failures are decoupled — a dropped socket mid-answer leaves a coherent partial record rather than a lost message.

**Trace it further:** Byte 4 covers how history is retrieved and displayed.

---

### Byte 4: Browsing order history — the sidebar

**Builds on:** Byte 3

**Source files:** `frontend/src/components/AppSidebar.vue`, `frontend/src/components/MessageList.vue`

**In plain terms:**

History browsing has three surfaces: a searchable conversation list in the sidebar, the message thread itself with auto-scroll, and a welcome page showing the most recent conversations.

**The code:**

```typescript
// AppSidebar.vue — searchable "Recent" list (session-only, with copy saying so)
const filtered = computed(() => { /* title or message-content match on ui.state.conversationQuery */ })

// WelcomeState.vue — up to 4 most recent, sorted by updatedAt
[...conversations].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 4)
```

**What's happening:**

The sidebar lists conversations with `relativeTime(updatedAt)`, offers a two-click delete confirm, and displays an explicit warning that chats "live in this browser tab only." `MessageList` renders the active conversation's messages via `MessageBubble` and auto-scrolls only when the user is near the bottom (threshold 140 px), showing a "Jump to latest" button otherwise.

**Why it matters:**

This is the complete retrieval story for history: filter in memory, sort by timestamp, no server query. Its limits are the honest ones — no cross-session history, no export, no pagination — all consequences of the storage decision in [03 — Data layer and database](03-data-layer-and-database.md).

**Trace it further:** Byte 5 covers what the server remembers (nothing).

---

### Byte 5: Server-side history — deliberately none

**Builds on:** Byte 4, [08 — Cart and session management](08-cart-and-session-management.md), Byte 2

**Source files:** `backend/app/api/chat_ws.py`, `backend/app/services/chat_service.py`, `README.md`

**In plain terms:**

The backend never stores a conversation: prompts are built per request from system + context + current question only, and no endpoint accepts or returns message history.

**The code:**

```python
# backend/app/prompts/system_prompt.py — no prior turns are included
messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
if excerpts:
    messages.append({"role": "user", "content": f"{context_body}\n\n…"})   # context turn
else:
    messages.append({"role": "user", "content": NO_DOCUMENTS_NOTE})
messages.append({"role": "user", "content": question})                    # current question only
```

**What's happening:**

Each question is answered statelessly — the model has no memory of earlier turns, and follow-up questions only work because the *user* re-states context or retrieval happens to find it. The root README documents this as a design decision: "Session-only history. Conversations live in browser memory and are labelled as such."

**Why it matters:**

Two practical consequences: (1) "follow up" questions like "what about the second one?" usually fail unless the referent is in an uploaded document, because neither history nor coreference is available server-side; (2) there is no server-side history to leak — a privacy upside of the storage choice. Both are **implementation facts**, not oversights to "fix" casually; adding history would change prompt cost and privacy posture simultaneously.

**Trace it further:** [12 — Wishlist](12-wishlist.md) covers the other user-facing "collection" features (and their absence).

---

## Continue learning

- [08 — Cart and session management](08-cart-and-session-management.md) — the lifecycle around these records.
- [15 — Frontend views, JavaScript, and CSS](15-frontend-views-javascript-css.md) — how history is rendered and navigated.
- [18 — Testing and verification](18-testing-and-verification.md) — the store tests pinning every state transition.
