# 07 — Search, Filtering, Sorting, and Pagination

**Overview:** There is no text search box, no SQL `WHERE`/`ORDER BY`, and no server-side pagination in this project. What exists instead has three parts: **vector similarity search** (top-k retrieval with cosine scores), **server-side fixed ordering** (documents newest-first), and **client-side filtering** (three independent search inputs in the UI that filter already-loaded arrays in JavaScript).

**Scope:** Similarity search and ranking, the top-k + context-budget parameters, defaults and boundary cases, result counts, and each client-side filter. A paginated keyword search does not exist and is documented as absent.

**Prerequisites:** [03 — Data layer and database](03-data-layer-and-database.md), [05 — Product catalog](05-product-catalog.md).

**Important source files:**
- `backend/app/services/vector_store.py`
- `backend/app/services/chat_service.py`
- `backend/app/core/config.py`
- `frontend/src/components/DocumentList.vue`
- `frontend/src/components/AppSidebar.vue`
- `frontend/src/components/PromptGallery.vue`

---

### Byte 1: Similarity search instead of keyword search

**Builds on:** [03 — Data layer and database](03-data-layer-and-database.md), Byte 5

**Source files:** `backend/app/services/vector_store.py`, `backend/app/services/embedding_service.py`

**In plain terms:**

A question is converted to a vector with the same model that embedded the documents, and FAISS returns the chunks whose vectors point in the most similar direction. Words do not need to match — meaning does.

**The code:**

```python
# backend/app/services/chat_service.py — retrieve()
if self.store.is_empty():
    return []
query_vector = self.embedding.encode_one(question)
hits = self.store.search(query_vector, top_k=self.settings.top_k)
```

**What's happening:**

`encode_one()` produces one L2-normalized 384-d vector; `search()` runs `IndexFlatIP.search()` (exact inner product over every stored vector = cosine similarity on normalized data) and returns up to `top_k` hits with scores in `[0, 1]`. There is no BM25, no keyword filter, and no metadata filter stage.

**Why it matters:**

Cosine search explains several user-visible behaviors: paraphrased questions still find the right chunk; a score near 0 means "nothing really matched" (but it is still returned if the index is non-empty — **there is no relevance threshold**); and searching is O(index size) exact, which is fine for MB-scale data but would need an ANN index at scale.

**Trace it further:** Byte 2 covers the ranking parameters.

---

### Byte 2: Top-k, ordering, and result counts

**Builds on:** Byte 1

**Source files:** `backend/app/services/vector_store.py`, `backend/app/core/config.py`

**In plain terms:**

Results are always ordered highest-score-first and capped at `TOP_K` (default 3) — but never more than the number of chunks that exist.

**The code:**

```python
# backend/app/services/vector_store.py — search()
k = max(1, min(top_k, len(self._records)))
scores, indices = self._index.search(query, k)
hits: list[SearchHit] = []
for score, idx in zip(scores[0], indices[0]):
    if idx < 0:              # FAISS returns -1 for missing slots
        continue
    hits.append(SearchHit(record=self._records[int(idx)], score=float(score)))
```

**What's happening:**

`k` is clamped into `[1, len(records)]`: a 1-chunk index returns 1 hit; `top_k=0` (impossible through validated settings) would still search for 1. FAISS's `-1` sentinel is filtered defensively. Scores arrive descending because FAISS sorts them.

**Why it matters:**

The clamp is the boundary case that prevents asking FAISS for more results than rows (which returns `-1` padding — handled anyway). Defaults: `TOP_K=3`, overridable via `backend/.env`. `k` never exceeds available data, so `sources` events shrink naturally as the index does.

**Trace it further:** Byte 3 covers the context budget that further trims results.

---

### Byte 3: The context budget (a second, size-based filter)

**Builds on:** Byte 2

**Source files:** `backend/app/services/chat_service.py`, `backend/app/core/config.py`

**In plain terms:**

After the top-3 are chosen, they are dropped one by one if their combined text would exceed the prompt budget — 4000 tokens ≈ 16,000 characters by default.

**The code:**

```python
# backend/app/services/chat_service.py — retrieve()
char_budget = max(self.settings.max_context_tokens, 256) * 4
kept: list[SearchHit] = []
used = 0
for hit in hits:
    text = hit.record.text
    if kept and used + len(text) > char_budget:
        break
    used += len(text)
    kept.append(hit)
```

**What's happening:**

The `if kept and …` guard means the **first hit is always kept** even if it alone exceeds the budget — better an oversized single excerpt than an empty context. Subsequent hits are added only while they fit; the loop `break`s at the first overflow (scores are descending, so later hits would be worse anyway).

**Why it matters:**

This is the token-cost guardrail: with `MAX_CONTEXT_TOKENS=4000`, prompts stay inside comfortable context windows regardless of `CHUNK_SIZE`. Misconfigure `CHUNK_SIZE` very large and you can still only ever send one chunk. Note the approximation: 4 characters ≈ 1 token is a heuristic, not a real tokenizer.

**Trace it further:** Byte 4 covers client-side filtering.

---

### Byte 4: Client-side filtering — three search inputs

**Builds on:** Byte 1, [05 — Product catalog](05-product-catalog.md), Byte 4

**Source files:** `frontend/src/components/DocumentList.vue`, `frontend/src/components/AppSidebar.vue`, `frontend/src/components/PromptGallery.vue`

**In plain terms:**

The UI has three filters — document search, conversation search, and prompt search — and every one of them filters an in-memory array in the browser. None of them calls the backend.

**The code:**

```typescript
// AppSidebar.vue — conversations filtered by title or message content
const filtered = computed(() => {
  const q = ui.state.conversationQuery.trim().toLowerCase()
  if (!q) return chat.state.conversations
  return chat.state.conversations.filter(
    (c) => c.title.toLowerCase().includes(q) ||
      c.messages.some((m) => m.content.toLowerCase().includes(q)),
  )
})
```

**What's happening:**

Each filter has its own query ref (sidebar and document search store theirs in the UI store as `conversationQuery`/`documentQuery`, so they survive view switches; `PromptGallery` keeps a local `query` ref). All use simple `String.includes` (case-insensitive) matching; `DocumentList` additionally shows a dedicated "no matches" empty state distinct from the true empty state.

**Why it matters:**

Client-side filtering is only correct because the datasets are small and already fully loaded — there is no server endpoint to ask. It also means filters cover *only what the client has*: a conversation search cannot find anything from a previous browser session (state is session-only), and document search cannot find documents uploaded after the last `refresh()`.

**Trace it further:** Byte 5 covers sorting and the absence of pagination.

---

### Byte 5: Sorting and pagination — what exists, what does not

**Builds on:** Byte 4

**Source files:** `backend/app/services/vector_store.py`, `frontend/src/components/DocumentList.vue`

**In plain terms:**

The only server-side sort is "documents, newest first." There is no sort selector, no `page`/`limit` parameter, and no offset anywhere in the API.

**The code:**

```python
# backend/app/services/vector_store.py — documents()
return sorted(
    self._docs.values(), key=lambda d: (d.uploaded_at, d.sequence), reverse=True
)
```

**What's happening:**

`GET /documents` returns the entire collection in one response with `total_documents`/`total_chunks` counts; `GET /documents` has no query parameters at all. Within the UI, conversation lists keep insertion order (newest unshifted to front in `ensureConversation()`), and messages are strictly chronological — the app never reorders them.

**Why it matters:**

"Pagination: not implemented" is a fact to state plainly: with a 5 MB-per-file ceiling and a memory-bound index, unpaginated responses are a deliberate trade. If you add pagination you must touch the endpoint, `DocumentListResponse`, `frontend/src/types/chat.ts`, the store's `refresh()`, and the client-side filter that assumes a complete list.

**Trace it further:** [14 — Admin dashboard and management](14-admin-dashboard-and-management.md) shows where listing and counts surface as management tooling.

---

### Byte 6: Defaults and boundary cases

**Builds on:** Byte 2, Byte 3

**Source files:** `backend/app/core/config.py`, `backend/app/services/policy_service.py`, `frontend/src/config.ts`

**In plain terms:**

The knobs and their edge behavior: `TOP_K=3`, `MAX_CONTEXT_TOKENS=4000`, `CHUNK_SIZE=500`, `CHUNK_OVERLAP=50` — validated so bad combinations fail at startup, plus a subtle interaction with the topic policy.

**The code:**

```python
# backend/app/core/config.py — validators
@field_validator("chunk_overlap")
def _validate_overlap(cls, value: int, info) -> int:
    size = info.data.get("chunk_size", 500)
    if value < 0:
        raise ValueError("CHUNK_OVERLAP must be >= 0")
    if value >= size:
        raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
    return value
```

**What's happening:**

Edge cases verified in code/tests: empty index → `search()` returns `[]` immediately (no query embedding is even needed for listing, though `retrieve()` does skip embedding when empty); `overlap >= chunk_size` is rejected at settings load *and* `chunk_text()` clamps `overlap = min(overlap, chunk_size // 2)` and advances by at least one character, so pathological inputs cannot loop forever; and a question with no technical signal never reaches search at all — `evaluate_policy()` short-circuits it first (see [13 — Reviews and moderation](13-reviews-and-moderation.md)).

**Why it matters:**

Knowing which guards are redundant-but-layered (validator + clamp + loop guard) shows the defense-in-depth around the two most common failure modes of chunking code: infinite loops and empty results.

**Trace it further:** [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) consolidates all validation rules.

---

## Continue learning

- [09 — Checkout and coupons](09-checkout-and-coupons.md) — the send pipeline these results feed into.
- [13 — Reviews and moderation](13-reviews-and-moderation.md) — what happens before search runs.
- [18 — Testing and verification](18-testing-and-verification.md) — tests pinning ranking, budgets, and clamps.
