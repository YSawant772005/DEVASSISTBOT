# 05 — Product Catalog

**Overview:** This repository is **not an e-commerce application** — it has no products, categories, prices, or product images. There is nothing named "product" anywhere in the codebase (verified by search). The prescribed catalog topic therefore maps onto this project's closest real equivalent: the **document catalog** — the list of uploaded knowledge-base files, how documents relate to their chunks, how they are retrieved, and how catalog information reaches the UI.

**Scope:** Document upload/registration, document–chunk relationships, catalog queries (`GET /documents`), sorting and counts, and how the list is rendered. Product/category/image concepts are explicitly out of scope because they do not exist.

**Prerequisites:** [03 — Data layer and database](03-data-layer-and-database.md), [04 — Models and ViewModels](04-models-and-viewmodels.md).

**Important source files:**
- `backend/app/api/upload.py`
- `backend/app/services/vector_store.py`
- `backend/app/services/document_service.py`
- `frontend/src/stores/documents.ts`
- `frontend/src/components/DocumentsView.vue`, `frontend/src/components/DocumentList.vue`

---

### Byte 1: "Product catalog" does not exist here

**Builds on:** [00 — Project architecture](00-project-architecture.md), Byte 7

**Source files:** `README.md`, `PROJECT_STATUS.md`

**In plain terms:**

Products, categories, SKUs, prices, and images are absent from this project by design. The catalog-shaped slot in the architecture is filled by uploaded documents: they are the items you list, open, and delete, and each item expands into many chunks.

**The code:**

```markdown
<!-- No product code exists; the catalog equivalent is stated in the root README: -->
To try retrieval immediately, open the **Documents** workspace and upload
`backend\tests\fixtures\sample_notes.md` …
```

**What's happening:**

The Documents workspace is the catalog page, `GET /documents` is the catalog query, and a document's chunks are its "variants" (covered in [06 — Product details and variants](06-product-details-and-variants.md)). This document uses catalog vocabulary only as a bridge to the real implementation.

**Why it matters:**

Stating the absence explicitly prevents two errors: documenting features that are not implemented, and overlooking that the *only* structured collection in the backend is the document registry (`_docs` in `VectorStore`).

**Trace it further:** Byte 2 covers how an item enters the catalog.

---

### Byte 2: Adding an item to the catalog (upload)

**Builds on:** Byte 1, [02 — Application startup and request flow](02-application-startup-and-request-flow.md), Byte 5

**Source files:** `backend/app/api/upload.py`, `backend/app/services/document_service.py`

**In plain terms:**

`POST /upload` accepts one file, rejects anything outside the allow-list, and only registers the document after extraction, chunking, and embedding all succeed.

**The code:**

```python
# backend/app/api/upload.py
@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    settings = get_settings()
    filename = (file.filename or "").strip() or "unnamed"
    extension = validate_filename(filename)          # .pdf/.txt/.md/.markdown only

    data = await _read_limited(file, settings.max_upload_bytes)
    if not data:
        raise EmptyFileError()

    text = extract_text(filename, data)
    chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise NoTextError("The file did not contain enough text to index.")
    # … embed, then store.add_document(...) — returns UploadResponse
```

**What's happening:**

Validation order matters: extension first (cheapest), then a streaming size check, then content extraction. `validate_filename()` uses `Path(filename).suffix.lower()`, so `.PDF` and `.Md` are accepted but `.exe` is rejected with `UNSUPPORTED_FILE_TYPE`. The response echoes real metadata: `doc_id`, size, `chunks_processed`, `characters_extracted`.

**Why it matters:**

Because registration is the *last* step, a file that fails extraction (corrupt PDF) or yields no chunks registers nothing — the catalog never contains half-ingested items. This atomicity is asserted by `test_failed_upload_does_not_register_a_document`.

**Trace it further:** Byte 3 covers the catalog relationship (document → chunks).

---

### Byte 3: The document–chunk relationship

**Builds on:** Byte 2, [03 — Data layer and database](03-data-layer-and-database.md), Byte 2

**Source files:** `backend/app/services/vector_store.py`, `backend/app/services/chunking_service.py`

**In plain terms:**

A document is a parent record; its chunks are children that each carry the parent's `doc_id`. The relationship is maintained in two places — the `_docs` dictionary and the `_records` list — and never stored in a join table.

**The code:**

```python
# each chunk echoes its parent id at creation time
records = [
    ChunkRecord(doc_id=doc_id, filename=filename, chunk_index=i, text=text)
    for i, text in enumerate(chunks)
]
# the parent stores the count, not the chunks themselves
self._docs[doc_id] = DocumentRecord(
    doc_id=doc_id, filename=filename, extension=extension,
    size_bytes=size_bytes, chunk_count=len(chunks),
    uploaded_at=datetime.now(timezone.utc).isoformat(), sequence=self._sequence,
)
```

**What's happening:**

`doc_id = uuid4().hex` is generated in `add_document()` and stamped on every chunk. `chunk_index` is the chunk's position in the file (0-based), which is why the UI displays "ch 1" for `chunk_index: 0`. Deleting the parent removes all children by filtering `record.doc_id != doc_id`.

**Why it matters:**

The denormalized `filename` on every chunk is what lets a `SourceReference` show a filename without a lookup — the retrieval path touches no document registry at all. Changing the relationship (e.g., storing only ids) would force a join into every search result.

**Trace it further:** Byte 4 covers the catalog query itself.

---

### Byte 4: The catalog query and ordering

**Builds on:** Byte 3

**Source files:** `backend/app/api/upload.py`, `backend/app/services/vector_store.py`

**In plain terms:**

`GET /documents` returns every document, newest first, with totals — no pagination, no filters, no field selection.

**The code:**

```python
# backend/app/services/vector_store.py — documents()
return sorted(
    self._docs.values(), key=lambda d: (d.uploaded_at, d.sequence), reverse=True
)

# backend/app/api/upload.py — list_documents()
return DocumentListResponse(
    documents=documents,
    total_documents=len(documents),
    total_chunks=sum(doc.chunks for doc in documents),
)
```

**What's happening:**

Sorting is by ISO timestamp descending with the monotonic `sequence` counter as tiebreaker (two uploads in the same microsecond still order deterministically). `total_chunks` is recomputed on every request by summing parent counts.

**Why it matters:**

This is the complete "catalog query" surface: one endpoint, fixed order, whole result set. For a 5 MB-per-file single-user index that is fine; any real pagination would have to be added here and mirrored in `frontend/src/types/chat.ts` (see [07 — Search, filtering, sorting, pagination](07-search-filtering-sorting-pagination.md) for the client-side filtering that exists today).

**Trace it further:** Byte 5 follows the data to the screen.

---

### Byte 5: How catalog information reaches the UI

**Builds on:** Byte 4

**Source files:** `frontend/src/stores/documents.ts`, `frontend/src/components/DocumentsView.vue`, `frontend/src/components/DocumentList.vue`, `frontend/src/components/ChatPanel.vue`

**In plain terms:**

The documents store fetches the list once at app start and again after every mutation; components read counts and rows from that store rather than calling the API themselves.

**The code:**

```typescript
// frontend/src/stores/documents.ts
async function refresh(): Promise<void> {
  state.loading = true
  try {
    const response = await api.fetchDocuments()
    state.documents = response.documents
    state.totalChunks = response.total_chunks
    state.error = null
  } catch (error) {
    state.error = error instanceof api.ApiError ? error.message : 'Could not load documents.'
  } finally {
    state.loading = false
  }
}
```

**What's happening:**

`App.vue` calls `refresh()` + `checkHealth()` on mount; `uploadFiles()` calls `refresh()` after each successful upload; `removeDocument()` and `clearAll()` update local state optimistically after the server confirms. Consumers: `DocumentsView` (counts, warnings), `DocumentList` (rows, search, delete), `ChatPanel` header ("Knowledge base · N documents"), and `ChatComposer` (grounding disclaimer).

**Why it matters:**

Because the store is the single source of truth, a stale catalog is impossible *within a session* — but a backend restart behind a live UI shows old rows until the next refresh, since the frontend never learns the server restarted except through failed requests or `checkHealth()`.

**Trace it further:** [14 — Admin dashboard and management](14-admin-dashboard-and-management.md) covers the management actions (delete, clear) in depth.

---

### Byte 6: Document images and metadata rendering

**Builds on:** Byte 5

**Source files:** `frontend/src/components/DocumentList.vue`, `frontend/src/components/DocumentUploader.vue`

**In plain terms:**

Documents have no cover images; the list renders an extension-derived icon, human-readable size, chunk count, and an "Indexed" status pill instead.

**The code:**

```typescript
// DocumentList.vue — icon chosen by extension, not by content
function iconFor(extension: string) {
  return extension === '.pdf' ? FileText : FileCode2
}
```

**What's happening:**

`.pdf` files get a document icon; `.txt`/`.md`/`.markdown` get a code icon. Sizes go through `formatBytes()` (B/KB/MB), timestamps are shown by `relativeTime()` in the sidebar's conversation list, and the status pill pairs icon *and* text (not color alone — an accessibility choice).

**Why it matters:**

With no thumbnails or previews, the UI's only visual catalog cues are these icons — and because `extract_text()` never persists the file itself (only its text and vectors), there is no way to re-download or preview the original document after upload. That is a real, verified limitation worth knowing: **the original file is not stored anywhere.**

**Trace it further:** [15 — Frontend views, JavaScript, and CSS](15-frontend-views-javascript-css.md) details the components involved.

---

## Continue learning

- [06 — Product details and variants](06-product-details-and-variants.md) — chunk-level "detail pages": source previews and scores.
- [07 — Search, filtering, sorting, pagination](07-search-filtering-sorting-pagination.md) — similarity search and client-side filtering.
- [14 — Admin dashboard and management](14-admin-dashboard-and-management.md) — managing the catalog (delete/clear).
