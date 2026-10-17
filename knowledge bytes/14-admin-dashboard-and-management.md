# 14 — Admin Dashboard and Management

**Overview:** There is **no admin panel, no admin routes, no roles, and no login** — management endpoints are as open as every other route (see [10 — Authentication and authorization](10-authentication-and-authorization.md)). The prescribed topic maps onto the two real administrative surfaces in this project: the **`GET /health` diagnostics endpoint** (the "dashboard metrics" source) and the **document management UI** (upload, delete, clear) on the Documents view plus the Settings dialog.

**Scope:** Health/diagnostics as dashboard metrics, document management operations and their UI, what would-be admin features (user/order/product management) map to or are absent, and the authorization gap around destructive actions.

**Prerequisites:** [05 — Product catalog](05-product-catalog.md), [10 — Authentication and authorization](10-authentication-and-authorization.md).

**Important source files:**
- `backend/app/main.py` (`/health`)
- `backend/app/api/upload.py`
- `frontend/src/components/DocumentsView.vue`
- `frontend/src/components/DocumentList.vue`
- `frontend/src/components/SettingsDialog.vue`

---

### Byte 1: The dashboard equivalent — `GET /health`

**Builds on:** [02 — Application startup and request flow](02-application-startup-and-request-flow.md), Byte 3

**Source files:** `backend/app/main.py`

**In plain terms:**

One endpoint reports everything an operator would want on a dashboard: readiness, index size, effective limits, and human-readable warnings — computed live, never cached.

**The code:**

```python
# backend/app/main.py
@app.get("/health", tags=["system"])
async def health() -> dict[str, object]:
    current = get_settings()
    embedding = get_embedding_service()
    store = get_vector_store()
    warnings = list(current.health_warnings)
    if not embedding.is_loaded:
        warnings.append("Embedding model is not loaded; uploads and retrieval will fail.")

    status = "ok" if (current.groq_configured and embedding.is_loaded) else "degraded"
    return {
        "status": status,
        "model": current.groq_model,
        "groq_configured": current.groq_configured,
        "embedding_loaded": embedding.is_loaded,
        "documents_indexed": len(store.documents()),
        "chunks_indexed": store.size,
        "limits": { "max_upload_bytes": …, "chunk_size": …, "top_k": … },
        "warnings": warnings,
    }
```

**What's happening:**

`status` is `ok` only when *both* the Groq key is present and the embedding model is loaded; otherwise it is `degraded` and `warnings` says why in plain English. `limits` echoes the *effective* configuration (after `.env` overrides), which makes it the ground truth for "what is this server actually running?"

**Why it matters:**

This is the single source of the UI's status pill, the Settings dialog, and the Documents-page warnings — the app's whole observability story. Crucially, `groq_configured` is a boolean; the endpoint never echoes the key itself.

**Trace it further:** Byte 2 shows the metric surfaces in the UI.

---

### Byte 2: Dashboard surfaces in the UI

**Builds on:** Byte 1

**Source files:** `frontend/src/components/SettingsDialog.vue`, `frontend/src/components/DocumentsView.vue`, `frontend/src/components/TopNav.vue`

**In plain terms:**

Health data is displayed in three places: a status pill in the header, a live diagnostics dialog (Settings), and counts + warnings on the Documents page.

**The code:**

```typescript
// SettingsDialog.vue — the closest thing to an admin console
// (shows on mount and on "Test connection", via documents.checkHealth())
API_BASE_URL · WS_URL · health.model · health.embedding_model
top_k · chunk_size · chunk_overlap · max_upload_bytes/1024/1024 MB
groq_configured status + instructions to add GROQ_API_KEY to backend/.env
health.warnings[]  ·  link to ${API_BASE_URL}/docs  (OpenAPI, new tab)
```

**What's happening:**

`DocumentsView` shows `documentCount`, `totalChunks`, and `limits.top_k` in a definition list and renders `health.warnings` as alerts; `TopNav` maps `documents.state.connection` (`online`/`degraded`/`offline`) to a colored dot. The Settings dialog is the only place that combines *configuration display* with *actionable remediation text*, and it explicitly tells the user the key never reaches the browser.

**Why it matters:**

These three surfaces are all read-only consumers of one endpoint — if you add a metric to `/health`, this is everywhere it lands (plus `frontend/src/types/chat.ts`, which must be updated to match or the field is invisible).

**Trace it further:** Byte 3 covers the management actions.

---

### Byte 3: Document management (the CRUD surface)

**Builds on:** Byte 1, [05 — Product catalog](05-product-catalog.md), Byte 5

**Source files:** `backend/app/api/upload.py`, `frontend/src/stores/documents.ts`, `frontend/src/components/DocumentList.vue`

**In plain terms:**

The full management API is five endpoints; the UI wraps the destructive ones in two-click confirmations and reports how many chunks each deletion removed.

**The code:**

```python
# backend/app/api/upload.py
@router.delete("/documents/{doc_id}", response_model=DeleteResponse)
async def delete_document(doc_id: str) -> DeleteResponse:
    removed = get_vector_store().remove_document(doc_id)
    return DeleteResponse(doc_id=doc_id, chunks_removed=removed)

@router.delete("/documents", response_model=DeleteResponse)
async def delete_all_documents() -> DeleteResponse:
    removed = get_vector_store().clear()
    return DeleteResponse(doc_id=None, chunks_removed=removed)
```

```typescript
// DocumentList.vue — two-click destructive pattern
if (pendingRemoval.value !== docId) { pendingRemoval.value = docId; return }
documents.removeDocument(docId)   // second click executes
```

**What's happening:**

Server-side, deletion is `rebuild-on-delete` (see [03 — Data layer and database](03-data-layer-and-database.md), Byte 4) and unknown ids are silent no-ops returning `chunks_removed: 0`. Client-side, `removeDocument()`/`clearAll()` optimistically splice local state after a successful response and update `totalChunks`. "Clear all" uses a separate `confirmingClear` flag with the same two-click pattern.

**Why it matters:**

The two-click pattern is the *only* guard on the destructive surface — there is no undo, because deletion rebuilds the FAISS index and the vectors are gone (re-upload is the only recovery). The honest operational warning: `DELETE /documents` wipes everyone's shared index and is reachable by anyone who can reach the port.

**Trace it further:** Byte 4 maps the admin features that do not exist.

---

### Byte 4: Admin features that do not exist (and their mappings)

**Builds on:** Byte 3, [10 — Authentication and authorization](10-authentication-and-authorization.md)

**Source files:** `backend/app/api/`, `frontend/src/components/`

**In plain terms:**

User management, order management, product/category management, role assignment, and dashboard configuration forms have no equivalent — the mappings below are the closest real features, not implementations of the originals.

**The code:**

```text
Typical admin feature        Status in this repository
───────────────────────────  ─────────────────────────────────────────────
Login / admin role           Absent — every route is open (doc 10)
Metrics dashboard            /health + 3 read-only UI surfaces (Bytes 1–2)
Product management           Absent; document upload/delete is the analogue
                             (doc 05 / Byte 3)
Category management          Absent — documents have no categories; only
                             extension types exist
User management              Absent — no users exist
Order management             Absent — no orders (doc 11)
Config editing forms         Absent — configuration is .env-only; Settings
                             dialog is display + link to /docs
Audit log                    Absent — server logs only (core/__init__.py)
```

**What's happening:**

Configuration is deliberately *not* editable at runtime: `Settings` is frozen after startup (`@lru_cache`), so changing a limit means editing `backend/.env` and restarting — visible afterward through `/health.limits`.

**Why it matters:**

This table is the honest answer to "where is the admin panel": it does not exist, and the pieces that do (health, document CRUD) are unauthenticated endpoints plus read-only UI. Any real admin build starts with auth (Byte 3 of doc 10).

**Trace it further:** [19 — IIS deployment and troubleshooting](19-iis-deployment-and-troubleshooting.md) covers operating these surfaces in a live environment.

---

## Continue learning

- [16 — Validation, security, and error handling](16-validation-security-and-error-handling.md) — what protects these unauthenticated endpoints.
- [18 — Testing and verification](18-testing-and-verification.md) — tests covering health, delete, and clear behavior.
- [06 — Product details and variants](06-product-details-and-variants.md) — the availability metrics in depth.
