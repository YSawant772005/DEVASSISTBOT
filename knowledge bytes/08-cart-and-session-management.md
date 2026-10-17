# 08 — Cart and Session Management

**Overview:** There is **no cart** in this repository — no items, quantities, totals, or price calculation exist (verified by search). The prescribed topic maps onto this project's real state-management story: the **browser-session state** that plays the cart's structural role. Conversations and messages live in a reactive store for the life of the tab; the document index lives in backend process memory; the only persisted preference is the theme.

**Scope:** How conversation state is created, mutated, and abandoned; how quantity/totals analogues (counts) are computed; what "session" means on each side of the wire; and exactly what survives a reload or restart.

**Prerequisites:** [00 — Project architecture](00-project-architecture.md), [11 — Orders and order history](11-orders-and-order-history.md) (the message-level view).

**Important source files:**
- `frontend/src/stores/chat.ts`
- `frontend/src/stores/ui.ts`
- `frontend/src/stores/documents.ts`
- `frontend/src/services/chatSocket.ts`
- `backend/app/services/vector_store.py`

---

### Byte 1: No cart — what plays its role

**Builds on:** [00 — Project architecture](00-project-architecture.md), Byte 7

**Source files:** `frontend/src/stores/chat.ts`, `backend/app/services/vector_store.py`

**In plain terms:**

The stateful "basket" of this application is the pair of in-memory stores: conversations in the browser and the indexed document set in the backend. Neither has add-to-cart semantics; both are session-scoped collections the user curates.

**The code:**

```typescript
// frontend/src/stores/chat.ts — the entire state shape
interface ChatState {
  conversations: Conversation[]
  activeId: string | null
  isGenerating: boolean
  socketStatus: SocketStatus
  lastSendError: string | null
  inspectedMessageId: string | null
}
```

**What's happening:**

This `reactive` object (plus the parallel `DocumentsState`) is the application's client-side session. `ensureConversation()` lazily creates a conversation when the user acts; `activeId` selects which one is on screen. There are no line items, quantities, or totals — the closest arithmetic analogues are `totalChunks` and the health `documents_indexed`/`chunks_indexed` counts, both computed server-side.

**Why it matters:**

Stating this mapping once, up front, lets the rest of the document describe real mechanisms (store lifecycle, socket lifecycle, persistence rules) instead of inventing cart mechanics.

**Trace it further:** Byte 2 covers the two lifetimes that matter — tab and process.

---

### Byte 2: Two session lifetimes — tab and process

**Builds on:** Byte 1

**Source files:** `frontend/src/stores/chat.ts`, `frontend/src/App.vue`, `backend/app/main.py`

**In plain terms:**

Client state dies with the tab; server state dies with the process. The UI warns about both in plain language.

**The code:**

```typescript
// frontend/src/App.vue — teardown on component unmount
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  chat.reset()          // clears conversations and closes the socket
})

// frontend/src/stores/chat.ts
function reset(): void {
  state.conversations = []
  activeRequestId = null
  socket?.close()
  socket = null
}
```

```python
# backend/app/main.py — the index is created fresh at every startup
set_vector_store(VectorStore(dimension=embedding.dimension))
```

**What's happening:**

`reset()` is the "end of session" — it drops all conversations and tears down the WebSocket. (In practice `App.vue`'s `onBeforeUnmount` fires on full page teardown/navigation, so a normal F5 reload keeps the store object only until the page's JS context is destroyed — everything is lost either way; there is no `sessionStorage`/`localStorage` serialization of chats.) Server-side, each boot constructs a brand-new empty `VectorStore`.

**Why it matters:**

This is the single most common demo surprise: reload the tab → chat history gone; restart uvicorn → knowledge base gone. The UI copy in `AppSidebar` and `ContextPanel` exists precisely to set that expectation, and it must stay truthful if persistence is ever added.

**Trace it further:** Byte 3 covers the mutation rules inside a session.

---

### Byte 3: Adding, updating, and removing conversation state

**Builds on:** Byte 1

**Source files:** `frontend/src/stores/chat.ts`

**In plain terms:**

Messages are appended in fixed pairs (user + empty assistant placeholder), the first message names the conversation, and removal has three distinct operations: clear, delete, and switch.

**The code:**

```typescript
// frontend/src/stores/chat.ts — sendMessage()
const conversation = ensureConversation()
const requestId = uid('msg')
const userMessage: ChatMessage = { id: uid('user'), role: 'user', content: question, /* … */ }
const assistantMessage: ChatMessage = { id: requestId, role: 'assistant', content: '', status: 'streaming' }

if (conversation.messages.length === 0) {
  conversation.title = titleFromMessage(question)   // first message becomes the title
}
conversation.messages.push(userMessage, assistantMessage)
```

**What's happening:**

The assistant placeholder is pushed *before* the round trip so tokens have a destination — its `id` is the `request_id` echoed by every server event. `titleFromMessage()` truncates the question to 42 characters. Three mutations follow: `clearActiveConversation()` empties messages but keeps the conversation; `removeConversation(id)` splices it out and reselects the first remaining one; `selectConversation(id)` just repoints `activeId` and resets `inspectedMessageId`/`lastSendError`.

**Why it matters:**

The push-before-send design is why the UI can show a streaming bubble immediately, and why a `CONNECTION_FAILED` send leaves a visible error message instead of nothing. Deleting the active conversation while streaming is avoided because `stopGeneration()` runs through store state, not per-conversation tasks.

**Trace it further:** Byte 4 covers the socket that supplies this state over time.

---

### Byte 4: The socket session (lazy, persistent, self-healing)

**Builds on:** Byte 3

**Source files:** `frontend/src/services/chatSocket.ts`, `frontend/src/stores/chat.ts`

**In plain terms:**

One WebSocket is shared by the whole app session: it connects on the first message, stays open, queues sends while connecting, and reconnects transparently on the next send after a drop.

**The code:**

```typescript
// frontend/src/services/chatSocket.ts
async send(event: ClientEvent): Promise<void> {
  await this.connect()
  const payload = JSON.stringify(event)
  if (this.socket && this.socket.readyState === WebSocket.OPEN) {
    this.socket.send(payload)
  } else {
    // Rare race: the socket closed while we awaited connect().
    this.queue.push(payload)
    await this.connect()
  }
}
```

**What's happening:**

`connect()` resolves immediately for an open socket, chains onto the pending open for a connecting one, or creates a fresh `WebSocket`. The `queue` buffer plus `flushQueue()` covers the close-during-connect race. `onclose` nulls the socket and reports `closed`, so the *next* `send()` reconnects — there is no automatic background retry. Backend-side, each connection independently enforces "one in-flight generation" (`BUSY`) and cancels its task on disconnect.

**Why it matters:**

Session state and transport state are deliberately coupled: `socketStatus` (`idle/connecting/open/closed/error`) drives the header pill, and a backend restart mid-session manifests as a `closed` status plus a `CONNECTION_FAILED` message — recoverable by simply sending again.

**Trace it further:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md), Byte 5 traces one full round trip.

---

### Byte 5: What persists — the full inventory

**Builds on:** Byte 2

**Source files:** `frontend/src/stores/ui.ts`, `frontend/src/stores/chat.ts`, `frontend/src/stores/documents.ts`

**In plain terms:**

Exactly one thing survives a reload: the color theme. Everything else is volatile, and every store exposes an explicit `reset()` for tests.

**The code:**

```typescript
// frontend/src/stores/ui.ts — the only persistence in the client
const THEME_KEY = 'devassist-theme'

function initTheme(): void {
  let stored: string | null = null
  try { stored = localStorage.getItem(THEME_KEY) } catch { stored = null }
  state.theme = stored === 'light' || stored === 'dark' ? stored : 'dark'
  applyTheme()
}
```

**What's happening:**

`localStorage` is read inside try/catch (private-browsing modes can throw). Searches (`conversationQuery`, `documentQuery`), the active view, drafts in the composer, and all conversations reset on reload. On the server, persistence = RAM only; `uploaded_at` timestamps are ISO strings in memory, not rows.

**Why it matters:**

The persistence audit is a prerequisite for any "save my chats" feature: you would add serialization to `chat.ts` (or a backend endpoint — which would be the first server-side persistence in the project) and update the UI copy that currently promises loss-on-reload. Until then, the honest documentation is: one key, one value, everything else volatile.

**Trace it further:** [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md) covers restart semantics operationally.

---

## Continue learning

- [11 — Orders and order history](11-orders-and-order-history.md) — the messages/conversations themselves.
- [14 — Admin dashboard and management](14-admin-dashboard-and-management.md) — managing the server-side half of session state.
- [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) — why volatile state is also a security property here.
