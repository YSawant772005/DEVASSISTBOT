# 06 — Product Details and Variants

**Overview:** This project has **no products and no product variants** — there are no sizes, colors, SKUs, per-variant prices, or stock levels anywhere in the codebase (verified by search). The closest implemented equivalent of a "detail page with selectable variants" is the **source inspection flow**: opening a retrieved chunk (the "detail") with its filename, chunk number, similarity score, and text preview (the "attributes" that vary per hit).

**Scope:** How individual chunks are identified and surfaced, what data accompanies each retrieved source, how the "detail view" is opened in the UI, and what inventory/availability analogues exist (index size, embedding readiness). Prices and variant selection are explicitly out of scope.

**Prerequisites:** [05 — Product catalog](05-product-catalog.md), [04 — Models and ViewModels](04-models-and-viewmodels.md).

**Important source files:**
- `backend/app/services/chat_service.py`
- `backend/app/schemas/chat.py`
- `frontend/src/components/SourcePanel.vue`
- `frontend/src/components/MessageBubble.vue`
- `frontend/src/components/ContextPanel.vue`

---

### Byte 1: The "variant" equivalent: one chunk, many attributes

**Builds on:** [05 — Product catalog](05-product-catalog.md), Byte 1

**Source files:** `backend/app/schemas/chat.py`, `backend/app/services/chat_service.py`

**In plain terms:**

When retrieval finds relevant chunks, each one is identified by a compound key — `doc_id` + `chunk_index` — and presented with the attributes that differ per chunk: filename, score, and preview text.

**The code:**

```python
# backend/app/schemas/chat.py
class SourceReference(BaseModel):
    """A retrieved chunk that informed the answer."""
    doc_id: str
    filename: str
    chunk_index: int
    score: float = Field(description="Cosine similarity in [0, 1] from the FAISS index")
    preview: str = Field(description="Truncated chunk text for display")
```

**What's happening:**

`ChatService.to_sources()` builds these from `SearchHit`s: `score` is clamped to `[0, 1]` and rounded to 4 decimals, `preview` is the first 240 characters of the chunk (`PREVIEW_CHARS = 240`). The pair `(doc_id, chunk_index)` uniquely identifies a chunk across the whole index and doubles as the Vue `:key` in the sources list.

**Why it matters:**

Unlike a product variant, a chunk's identity never changes and it has no mutable state to select — the only per-instance variation is the score, which changes with each query. Everything else (stock, price) has no counterpart; the app never exposes chunk text beyond the preview over this channel.

**Trace it further:** Byte 2 covers the detail view itself.

---

### Byte 2: The "detail page" — SourcePanel

**Builds on:** Byte 1

**Source files:** `frontend/src/components/SourcePanel.vue`, `frontend/src/stores/chat.ts`

**In plain terms:**

Clicking a source chip on an assistant message opens the right-hand context panel on the Sources tab, where every retrieved chunk is listed with its score bar and an expandable preview.

**The code:**

```typescript
// frontend/src/components/ChatPanel.vue — opening the detail view
function onInspect(messageId: string): void {
  chat.inspectMessage(messageId)
  ui.toggleContext(true, 'sources')
}
```

```typescript
// frontend/src/stores/chat.ts — which message's sources are shown
const inspected = state.inspectedMessageId
  ? messages.find((message) => message.id === state.inspectedMessageId)
  : null
const target =
  inspected ??
  [...messages].reverse().find((message) => message.role === 'assistant' && message.sources) ??
  null
```

**What's happening:**

`inspectMessage()` pins a specific assistant turn; `currentSources` falls back to the *latest* assistant message that has sources when nothing is pinned. `SourcePanel` renders each source with filename, "Chunk N · X% similar", a similarity-colored bar, and a preview collapsed to two lines that expands into a scrollable `<pre>` (expansion state keyed by `doc_id:chunk_index`).

**Why it matters:**

This is the app's transparency mechanism: it is how a user verifies *why* an answer was given. The fallback logic also means the panel is never blank during a stream — sources appear as soon as the `sources` event arrives, before the first token.

**Trace it further:** Byte 3 covers availability/stock analogues.

---

### Byte 3: "Inventory" analogues — is content available?

**Builds on:** Byte 2, [05 — Product catalog](05-product-catalog.md), Byte 4

**Source files:** `backend/app/main.py`, `frontend/src/stores/documents.ts`, `frontend/src/components/DocumentsView.vue`

**In plain terms:**

There is no stock count. The availability questions this app answers are: how many documents/chunks are indexed, is the embedding model loaded, and is the provider configured — all reported by `GET /health`.

**The code:**

```python
# backend/app/main.py — /health
status = "ok" if (current.groq_configured and embedding.is_loaded) else "degraded"
return {
    "status": status,
    "documents_indexed": len(store.documents()),
    "chunks_indexed": store.size,
    "limits": { "max_upload_bytes": …, "chunk_size": …, "top_k": … },
    "warnings": warnings,
}
```

**What's happening:**

`documents_indexed` and `chunks_indexed` are live counts from the store; `warnings` explains any `degraded` state (missing key, unloaded model). The UI maps `status` to a connection pill (`online`/`degraded`/`offline`) and surfaces `warnings` as alerts on the Documents page.

**Why it matters:**

These numbers are the app's notion of "in stock": retrieval can only return chunks that exist in the index, and a `degraded` health status predicts exactly which features will fail (chat → `CONFIG_ERROR`; uploads → `EMBEDDING_UNAVAILABLE`). See [14 — Admin dashboard and management](14-admin-dashboard-and-management.md) for the full diagnostics view.

**Trace it further:** Byte 4 explains why there is no price, image, or variant-selection interaction.

---

### Byte 4: What is deliberately missing (price, images, selection)

**Builds on:** Byte 3

**Source files:** `frontend/src/components/MessageBubble.vue`, `frontend/src/components/ContextPanel.vue`

**In plain terms:**

The interactions a product page would have — picking options, seeing a price change, adding to a basket — have no counterpart. The nearest analogues are score display and tab switching, both read-only.

**The code:**

```typescript
// MessageBubble.vue — score is displayed, never selected
function scorePercent(score: number): number {
  return Math.round(Math.max(0, Math.min(1, score)) * 100)
}
```

```typescript
// ContextPanel.vue — the only "selection" is which detail tab is open
export type ContextTab = 'sources' | 'followups' | 'context'
```

**What's happening:**

Source chips show `filename · ch N · NN%`; clicking them opens the panel rather than choosing anything. The context panel's three tabs (sources, follow-ups, runtime info) are pure navigation. There is no state anywhere that resembles an option selection with downstream price or availability effects.

**Why it matters:**

Documenting this explicitly stops readers from hunting for nonexistent selection logic and clarifies where *real* selection-like state does live: the active conversation and active view in the UI store (see [08 — Cart and session management](08-cart-and-session-management.md)).

**Trace it further:** [07 — Search, filtering, sorting, pagination](07-search-filtering-sorting-pagination.md) explains how chunks are ranked and chosen.

---

## Continue learning

- [07 — Search, filtering, sorting, pagination](07-search-filtering-sorting-pagination.md) — how the top-3 chunks are picked.
- [13 — Reviews and moderation](13-reviews-and-moderation.md) — the content-control equivalent: the topic guardrail.
- [15 — Frontend views, JavaScript, and CSS](15-frontend-views-javascript-css.md) — how the panels render and respond.
