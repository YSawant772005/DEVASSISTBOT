# 03 — Data Layer and Database

**Overview:** This project has **no database**. Persistence is an in-memory FAISS vector index plus a parallel list of chunk metadata, both living inside the backend process and lost on restart. This document explains that data layer in full: the index structure, write and delete paths, thread-safety, queries, and the "transactions" that exist (upload atomicity), plus what a real database would replace.

**Scope:** `VectorStore`, `EmbeddingService` storage behavior, chunk metadata, ordering, concurrency, and the absence of migrations/ORM/transactions. Financial-grade or SQL concerns do not apply.

**Prerequisites:** [00 — Project architecture](00-project-architecture.md), [02 — Application startup and request flow](02-application-startup-and-request-flow.md).

**Important source files:**
- `backend/app/services/vector_store.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/chunking_service.py`
- `backend/app/api/upload.py`
- `backend/app/services/chat_service.py`

---

### Byte 1: Why there is no database

**Builds on:** [00 — Project architecture](00-project-architecture.md), Byte 7

**Source files:** `README.md`, `PROJECT_STATUS.md`

**In plain terms:**

The SRS (specification) deliberately chose transient in-memory storage: restarting the backend clears all uploaded documents, and there are no tables, schemas, or migrations anywhere in the repository.

**The code:**

```markdown
- **Transient storage.** The index is in RAM. Restarting the backend clears all
  documents, and chat history clears when the tab reloads.
```

**What's happening:**

Two stateful structures hold everything: the `VectorStore` dataclass in the backend (chunks + vectors + document registry) and Vue reactive state in the browser (conversations). Neither is written to disk.

**Why it matters:**

This is an *implementation fact with consequences*: a backend restart mid-demo loses the knowledge base; running `--workers 2` would give each process its own empty index; and deleting a document only mutates process memory. Treat the data layer as a cache that happens to be the only copy.

**Trace it further:** Byte 2 introduces the actual store.

---

### Byte 2: The VectorStore dataclass

**Builds on:** Byte 1

**Source files:** `backend/app/services/vector_store.py`

**In plain terms:**

`VectorStore` is one dataclass holding four parallel structures — a FAISS index, a list of chunk records, a matrix of vectors, and a dictionary of document records — guarded by a re-entrant lock.

**The code:**

```python
# backend/app/services/vector_store.py
@dataclass
class VectorStore:
    dimension: int = 384
    _index: object | None = field(default=None, init=False, repr=False)
    _records: list[ChunkRecord] = field(default_factory=list, init=False)
    _vectors: np.ndarray | None = field(default=None, init=False, repr=False)
    _docs: dict[str, DocumentRecord] = field(default_factory=dict, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)
```

**What's happening:**

`_records[i]` describes chunk `i` (`doc_id`, `filename`, `chunk_index`, `text`) while `_vectors[i]` is its 384-dimension embedding; FAISS row `i` is the same chunk. `_docs` maps `doc_id → DocumentRecord` (filename, size, chunk count, upload timestamp) for listings. Every public method takes `_lock` before touching any of them.

**Why it matters:**

The parallel-array design means retrieval never needs a database round trip: FAISS returns row indices, and metadata is a direct list lookup. The invariant "row *i* of index/records/vectors is the same chunk" is what deletions must preserve — see Byte 4.

**Trace it further:** Byte 3 covers writes.

---

### Byte 3: The write path — adding a document

**Builds on:** Byte 2, [02 — Application startup and request flow](02-application-startup-and-request-flow.md), Byte 5

**Source files:** `backend/app/api/upload.py`, `backend/app/services/vector_store.py`

**In plain terms:**

An upload only becomes visible if *every* step succeeds: validate → read with a size cap → extract text → chunk → embed → register. The registration itself builds the new state first and swaps it in atomically under the lock.

**The code:**

```python
# backend/app/services/vector_store.py — add_document()
with self._lock:
    # Build the new state first so a failure cannot leave a half-updated index.
    new_vectors = np.vstack([self._vectors, vectors]) if self._vectors is not None and self._vectors.size else vectors
    new_records = [*self._records, *records]
    index = self._new_index()
    if new_vectors.shape[0]:
        index.add(new_vectors)

    self._vectors = new_vectors
    self._records = new_records
    self._index = index
    self._sequence += 1
    self._docs[doc_id] = DocumentRecord(/* … */)
```

**What's happening:**

`add_document()` validates that chunk count matches vector count and that dimensions match the store, then re-builds the whole FAISS index from the combined vector matrix inside one lock. The `_sequence` counter breaks timestamp ties so `documents()` can order uploads deterministically. `doc_id` is a `uuid.uuid4().hex`.

**Why it matters:**

This is the closest thing to a transaction in the system (the alternative — `api/upload.py` raising `IndexingError` before `add_document` is called — means a failed upload registers nothing). If the swap were not atomic, a concurrent search could see records without matching vectors and return wrong chunks.

**Trace it further:** Byte 4 covers the delete path.

---

### Byte 4: Deletion is a rebuild, not a removal

**Builds on:** Byte 3

**Source files:** `backend/app/services/vector_store.py`

**In plain terms:**

FAISS flat indexes do not support removing individual vectors efficiently here, so deleting a document filters the surviving records/vectors and rebuilds the index from scratch — cheap at this scale and impossible to desynchronize.

**The code:**

```python
# backend/app/services/vector_store.py — remove_document()
def remove_document(self, doc_id: str) -> int:
    with self._lock:
        doc = self._docs.pop(doc_id, None)
        if doc is None:
            return 0
        keep = [i for i, record in enumerate(self._records) if record.doc_id != doc_id]
        self._records = [self._records[i] for i in keep]
        if self._vectors is not None and self._vectors.shape[0]:
            self._vectors = self._vectors[keep] if keep else np.zeros((0, self.dimension), dtype="float32")
        self._rebuild()
        return doc.chunk_count
```

**What's happening:**

`keep` is the list of retained row indices; both `_records` and `_vectors` are filtered with the same mask, then `_rebuild()` creates a fresh `IndexFlatIP` and re-adds all surviving vectors. `clear()` does the same wholesale. Unknown `doc_id` is a silent no-op returning 0.

**Why it matters:**

Rebuild-on-delete guarantees index rows and metadata rows can never drift apart — the classic bug of vector stores with separate metadata. The cost is O(N) per deletion, acceptable for a single-user 5 MB-per-file demo, but it is the first thing to redesign if you add bulk deletes or millions of chunks.

**Trace it further:** Byte 5 covers the read/query path.

---

### Byte 5: The query path — similarity search

**Builds on:** Byte 2, [00 — Project architecture](00-project-architecture.md), Byte 3

**Source files:** `backend/app/services/vector_store.py`, `backend/app/services/chat_service.py`

**In plain terms:**

To answer a question, the backend embeds it with the same model used for chunks and asks FAISS for the top-3 most similar rows; the results are then trimmed to fit a character budget.

**The code:**

```python
# backend/app/services/vector_store.py — search()
k = max(1, min(top_k, len(self._records)))
scores, indices = self._index.search(query, k)
for score, idx in zip(scores[0], indices[0]):
    if idx < 0:
        continue
    hits.append(SearchHit(record=self._records[int(idx)], score=float(score)))

# backend/app/services/chat_service.py — retrieve() budget
char_budget = max(self.settings.max_context_tokens, 256) * 4   # 4 chars ≈ 1 token
for hit in hits:
    if kept and used + len(text) > char_budget:
        break
    used += len(text)
    kept.append(hit)
```

**What's happening:**

Vectors are L2-normalized at embedding time and the index uses *inner product*, so the returned score equals cosine similarity in `[0, 1]`. `k` is clamped so a 2-chunk index never asks for 3 results. The budget loop keeps at least one hit unconditionally and drops later hits once the assembled context would exceed `MAX_CONTEXT_TOKENS × 4` characters (16,000 by default).

**Why it matters:**

Retrieval quality and prompt size are both controlled here: `TOP_K` and `MAX_CONTEXT_TOKENS` in `backend/.env` are the tuning knobs, and scores are what the UI displays as "81% similar". An empty index short-circuits to `[]`, so chat still works — it just answers from general knowledge with an explicit "no documents indexed" note.

**Trace it further:** [07 — Search, filtering, sorting, pagination](07-search-filtering-sorting-pagination.md) covers ranking, ordering, and client-side filtering.

---

### Byte 6: What a real database would replace

**Builds on:** Byte 1, Byte 4

**Source files:** `backend/app/services/vector_store.py`, `backend/app/main.py`

**In plain terms:**

If you needed durability, the change would be localized: `VectorStore`'s public API (`add_document`, `remove_document`, `clear`, `documents`, `search`, `size`) is the entire persistence interface of the application.

**The code:**

```python
# The full persistence surface consumed by the API layer:
store = get_vector_store()
store.add_document(...)          # POST /upload
store.documents()                # GET /documents
store.remove_document(doc_id)    # DELETE /documents/{doc_id}
store.clear()                    # DELETE /documents
store.search(query_vector, top_k) # chat retrieval
```

**What's happening:**

No other module touches FAISS or numpy directly; routers and `ChatService` only call these six members. A durable implementation (SQLite + a saved FAISS index file, or a vector DB) could replace the dataclass body without changing callers.

**Why it matters:**

This seam is why the tests can substitute `VectorStore(dimension=64)` with a fake embedding and still exercise real API endpoints. Recognizing it tells you exactly how far a persistence migration would reach — and that no migration files or ORM exist today.

**Trace it further:** [04 — Models and ViewModels](04-models-and-viewmodels.md) documents the record types flowing through this interface.

---

## Continue learning

- [04 — Models and ViewModels](04-models-and-viewmodels.md) — the dataclasses, Pydantic models, and TypeScript interfaces that mirror this layer.
- [07 — Search, filtering, sorting, pagination](07-search-filtering-sorting-pagination.md) — ranking behavior and client-side filters.
- [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) — the guards around every write.
